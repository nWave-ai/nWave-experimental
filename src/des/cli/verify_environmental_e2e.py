"""des.cli.verify_environmental_e2e -- the shared cross-tree environmental-e2e gate.

Feature `fix-oss-environmental-e2e-gate`, gate class 1 of the gate-family epic
(the Class-A environment-divergence gate). The single CLI both trees (OSS and
SF) wrap with identical semantics.

CONTRACT SOURCE: NORMATIVE-FROZEN L1.4
(``docs/architecture/methodology/gate-family-implementation-2026-05-21.md``
section L1.4, v5) -- the SINGLE SSOT for this contract.

    --mode {verify-authored,verify-present,run,verify-merge-ready,audit}
      --feature-id <kebab>            # all modes except audit
      --feature-delta <path>          # all modes except audit
      --tests-root <dir>              # verify-authored/present/merge-ready/audit
      --clean-prefix <dir|auto>       # run
      --results-json <path>           # run (write), verify-merge-ready (read)
      --source-tree <path>            # verify-merge-ready
      --reruns <N>                    # run -- default 3
      --build-command "<cmd>"         # run, verify-merge-ready
      --fixture-junit-xml <path>      # test seam -- NEVER passed by the CI job
      --max-age-days <N>              # audit -- default 30

    Exit codes (uniform across modes):
      0  PASS         1  check failed
      2  parse/IO     3  misscoped (no `## Environmental E2E` block)

Stdlib-only at import time (the `des.cli` bundle-scan contract, per F-11's
fix); build / install / pytest are invoked as subprocesses, never imported.

slice-01 scope: only `--mode run` is implemented. Other advertised modes
refuse honestly with verdict=misscoped / exit 3 via `_emit_unbuilt_mode`
(slice-03 wires verify-authored + audit; slice-02 done-gate is separate code).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from des.adapters.driven.e2e.pytest_e2e_runner import run_pytest_against_installed
from des.adapters.driven.runner.reentrancy_guard import (
    is_routing_active_for,
    routing_active_for,
)
from des.adapters.driven.runner.runner_registry import (
    GLOBAL_REGISTRY,
    seed_runner_registry,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.environmental_e2e import (
    GateExit,
    GateVerdict,
    ResultsRecord,
    StdoutToken,
    VerdictInputBreakdown,
    compute_verdict_input_digest,
    format_stdout_token,
    has_environmental_e2e_block,
    serialize_results_record,
    write_deferral_marker,
)
from des.ports.test_runner_port import RunnerAdapter
from des.ports.test_runner_port import resolve as resolve_runner
from des.runtime.interpreter import des_spawn


_CLI_VERSION = "1.0.0"

_E2E_BLOCK_HEADER_RE = re.compile(r"^##\s+Environmental\s+E2E\s*$", re.MULTILINE)
_E2E_TEST_LINE_RE = re.compile(r"^\s*-\s*test:\s*(?P<path>\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class _FacetMissingForResolvedRunner:
    """DDD-CERT-7 disambiguation marker -- NOT a legitimate fall-through.

    Distinguishes cause (b) (a REAL, KNOWN non-pytest ``RunnerAdapter``
    resolved, but no ``environmental_e2e`` facet is registered for it) from
    cause (a) (``resolve_runner`` did not resolve a known ``RunnerAdapter`` at
    all -- the legitimate implicit-Python-tree fallthrough, UNCHANGED,
    returns plain ``None``). The caller (``_run_mode``) reads ``runner_name``
    to emit an honest ``GateVerdict.MISSCOPED`` naming the gap, instead of
    silently falling through to ``_build_wheel`` against the wrong toolchain.
    """

    runner_name: str


def _maybe_route_through_registered_e2e_adapter(
    repo: Path, e2e_abs: Path
) -> int | None | _FacetMissingForResolvedRunner:
    """Route through a REGISTERED ``environmental_e2e`` facet; else ``None``.

    unified-language-adapter-registry slice-01 (ADR-ULAR-001 prefactoring, C6):
    sprout-and-fall-through seam mirroring ``run_contract_gate.py``'s
    ``_maybe_route_through_cargo`` shape -- seed the registry, RESOLVE the
    target's runner, and look up an ``EnvironmentalE2EPort`` facet under the
    resolved TOOL-NAME (never ``target_language``, DDD-U5). Returns ``None``
    when ``resolve_runner`` did not resolve a known ``RunnerAdapter`` at all
    (the legitimate implicit-Python-tree fallthrough -- UNCHANGED), so the
    caller falls through to the EXISTING build/install/run path. Returns a
    ``_FacetMissingForResolvedRunner`` (DDD-CERT-7) when a REAL, KNOWN
    non-pytest runner resolved but no facet is registered for it -- an
    illegitimate cause the caller must confess as ``MISSCOPED``, never fall
    through to a Python wheel build against the wrong toolchain. This file
    imported no runner-resolution mechanism before this seam (Tsunami
    re-verified, 0 prior call sites) -- this is 1 NEW call site of the
    EXISTING ``resolve()`` function, not a new resolution component.
    """
    seed_runner_registry()
    resolution = resolve_runner(repo, None)
    if not isinstance(resolution, RunnerAdapter):
        return None
    facet = GLOBAL_REGISTRY.lookup_environmental_e2e(resolution.name)
    if facet is None:
        return _FacetMissingForResolvedRunner(runner_name=resolution.name)
    if is_routing_active_for(repo):
        print(
            "health.gate.lang-adapter.reentrancy-skipped: routing already "
            f"active for {repo} -- skipping to avoid self-recursion",
            file=sys.stderr,
        )
        return None
    try:
        with routing_active_for(repo):
            with tempfile.TemporaryDirectory(
                prefix="env-e2e-registered-"
            ) as work_dir_str:
                work_dir = Path(work_dir_str)
                artifact = facet.build(repo)
                prefix = _resolve_clean_prefix(None)
                facet.install(artifact, prefix)
                junit_path = work_dir / "junit.xml"
                facet.run_against_installed(e2e_abs, prefix, junit_path, work_dir)
                verdict, _collected = _verdict_from_junit(junit_path, [])
    except NotImplementedError:
        return None
    return 0 if verdict is GateVerdict.PASS else 1


def _build_parser() -> argparse.ArgumentParser:
    """Build the L1.4 argument parser; modes share one parser."""
    parser = argparse.ArgumentParser(
        prog="des verify-environmental-e2e",
        description="L1.4 environmental-e2e gate CLI (cross-tree SSOT).",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "verify-authored",
            "verify-present",
            "run",
            "verify-merge-ready",
            "audit",
        ),
    )
    parser.add_argument("--feature-id", required=False)
    parser.add_argument("--feature-delta", required=False)
    parser.add_argument("--tests-root", required=False)
    parser.add_argument("--clean-prefix", required=False)
    parser.add_argument("--results-json", required=False)
    parser.add_argument("--source-tree", required=False)
    parser.add_argument("--reruns", type=int, default=3)
    parser.add_argument(
        "--build-command", default="python -m build --wheel --outdir {outdir} {srcdir}"
    )
    parser.add_argument("--fixture-junit-xml", required=False)
    parser.add_argument("--max-age-days", type=int, default=30)
    # Fail-mode-D: when --mode run cannot provision a hermetic prefix, write a
    # deferral marker at this path. Marker-write failure itself fails closed
    # (exit 2). Out-of-band relative to L1.4 args; the wrapper specifies it.
    parser.add_argument("--deferral-marker", required=False)
    return parser


def _sha256_file(path: Path) -> str:
    """Hash a single file's bytes with SHA-256."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_concat(paths: list[Path]) -> str:
    """Hash the ordered concatenation of file hashes — deterministic over a file set."""
    hasher = hashlib.sha256()
    for path in sorted(paths):
        hasher.update(_sha256_file(path).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _ci_closure_hash(feature_id: str) -> str:
    """Compute the CI-job-closure hash — slice-01 substrate: deterministic per feature.

    slice-01 floor: no real CI parsing yet. Hash the feature id so the digest
    is stable across runs of the same feature but distinct per feature. Real
    CI closure parsing arrives with slice-03 / verify-merge-ready.
    """
    return hashlib.sha256(f"ci-closure-substrate:{feature_id}".encode()).hexdigest()


def _parse_feature_delta_e2e_block(feature_delta: Path) -> str | None:
    """Return the e2e test path from the feature-delta's `## Environmental E2E` block.

    `None` when the block is absent (mis-scoped feature). When the block is
    present but malformed, raise `ValueError` (mapped to exit 2 by the caller).
    """
    text = feature_delta.read_text(encoding="utf-8")
    header = _E2E_BLOCK_HEADER_RE.search(text)
    if header is None:
        return None
    block = text[header.end() :]
    next_header = re.search(r"^##\s+\S", block, re.MULTILINE)
    if next_header is not None:
        block = block[: next_header.start()]
    test_line = _E2E_TEST_LINE_RE.search(block)
    if test_line is None:
        raise ValueError(
            "## Environmental E2E block present but no `- test: <path>` line found"
        )
    return test_line.group("path")


def _resolve_source_tree(args: argparse.Namespace) -> Path:
    """Resolve the project source root for `--mode run`.

    Slice-01 convention: `--source-tree` overrides; otherwise the parent of
    `--feature-delta` is the source root. The L1.4 contract permits
    `--source-tree` on every mode; slice-01 defaults it on `run`.
    """
    if args.source_tree is not None:
        return Path(args.source_tree).resolve()
    return Path(args.feature_delta).resolve().parent


def _resolve_clean_prefix(arg_value: str | None) -> Path:
    """Resolve the clean-prefix directory; 'auto' or None mints a fresh tmp dir."""
    if arg_value is None or arg_value == "auto":
        return Path(tempfile.mkdtemp(prefix="env-e2e-prefix-"))
    prefix = Path(arg_value)
    prefix.mkdir(parents=True, exist_ok=True)
    return prefix


def _build_wheel(source_tree: Path, build_command: str, build_outdir: Path) -> Path:
    """Build the feature's wheel into `build_outdir`; return the wheel path.

    Raises `RuntimeError` (mapped to exit 2) on build failure or no wheel.
    """
    build_outdir.mkdir(parents=True, exist_ok=True)
    rendered = build_command.format(outdir=str(build_outdir), srcdir=str(source_tree))
    result = subprocess.run(
        shlex.split(rendered),
        capture_output=True,
        text=True,
        cwd=str(source_tree),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"build failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    wheels = sorted(build_outdir.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"build produced no wheel under {build_outdir}")
    return wheels[-1]


def _install_into_prefix(wheel: Path, prefix: Path) -> None:
    """`pip install --target` the wheel into a hermetic clean prefix.

    Raises `RuntimeError` (mapped to exit 2) on install failure.
    """
    result = des_spawn(
        None,
        "pip",
        "install",
        "--no-deps",
        "--no-index",
        "--target",
        str(prefix),
        str(wheel),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pip install --target failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def _run_e2e_against_installed(
    e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
) -> None:
    """Run pytest on the e2e test with PYTHONPATH=prefix, write JUnit XML.

    Delegates to the shared `pytest_e2e_runner.run_pytest_against_installed`
    (DDD-02) -- the same implementation
    `PythonEnvironmentalE2EAdapter.run_against_installed` uses via the
    registered-facet routing path (D4: one implementation, no duplication).
    """
    run_pytest_against_installed(e2e_path, prefix, junit_path, work_dir)


def _verdict_from_junit(
    junit_path: Path, rerun_results: list[str]
) -> tuple[GateVerdict, int]:
    """Read a pytest JUnit XML and append to `rerun_results`; return (verdict, collected)."""
    tree = ElementTree.parse(junit_path)
    testsuite = tree.getroot().find("testsuite")
    if testsuite is None:
        testsuite = tree.getroot()
    tests = int(testsuite.attrib.get("tests", "0"))
    failures = int(testsuite.attrib.get("failures", "0"))
    errors = int(testsuite.attrib.get("errors", "0"))
    if tests == 0:
        rerun_results.append("broken")
        return GateVerdict.BROKEN, 0
    if failures + errors > 0:
        rerun_results.append("fail")
        return GateVerdict.FAIL, tests
    rerun_results.append("pass")
    return GateVerdict.PASS, tests


def _consume_fixture_junit(
    fixture_junit_spec: str, reruns: int
) -> tuple[GateVerdict, int, list[str]]:
    """L1.4 test seam: read pre-baked JUnit XML once per rerun.

    The seam exists because L1.4 documents `--fixture-junit-xml` as the way to
    inject the JUnit shape `--mode run` would consume from a real pytest --
    'NEVER passed by the CI job'. `fixture_junit_spec` is either a single path
    (reused for every rerun -- deterministic across reruns) OR a comma-separated
    list of paths, one consumed per rerun in order; a list shorter than
    `reruns` cycles from the start. The list form lets the seam stage genuine
    rerun-to-rerun variance for the FLAKY verdict path; the single-path form
    keeps the slice-01 PASS/FAIL determinism.
    """
    paths = [
        Path(part.strip()) for part in fixture_junit_spec.split(",") if part.strip()
    ]
    if not paths:
        raise RuntimeError("--fixture-junit-xml resolved to no paths")
    rerun_results: list[str] = []
    verdict: GateVerdict | None = None
    collected = 0
    for index in range(reruns):
        junit_path = paths[index % len(paths)]
        verdict, collected = _verdict_from_junit(junit_path, rerun_results)
    assert verdict is not None  # `reruns` >= 1 by L1.4 contract (default 3).
    return verdict, collected, rerun_results


def _emit_token(token: StdoutToken) -> None:
    """Print the L1.4 stdout token to stdout."""
    print(format_stdout_token(token))


def _emit_parse_error(mode: str, feature_id: str, message: str) -> None:
    """Print an L1.4 BROKEN token for a parse/IO failure; verdict=broken / exit 2.

    Slice-03 surface (F-D1-HUMAN-READABLE-GATE-SURFACES): in addition to the
    pre-existing L1.4 stdout token (unchanged byte-content on stdout) and the
    free-text diagnostic line (unchanged on stderr), emit a colored human-
    readable ❌ FAIL line on stderr so the operator sees the verdict alongside
    the diagnostic. ANSI escapes only under a TTY; plain text under a pipe.
    """
    token = StdoutToken(
        mode=mode,
        feature=feature_id,
        authored=False,
        genuine=False,
        collected=0,
        verdict=GateVerdict.BROKEN,
        verdict_input_digest=None,
        fresh=None,
        xfail_present=None,
    )
    _emit_token(token)
    print(f"diagnostic: {message}", file=sys.stderr)
    print_human_summary(
        Verdict.FAIL,
        f"environmental e2e {mode} parse/IO failure for {feature_id}: {message}",
    )


def _emit_misscoped(mode: str, feature_id: str) -> None:
    """Print the L1.4 misscoped token; verdict=misscoped / exit 3.

    Slice-03 surface (F-D1-HUMAN-READABLE-GATE-SURFACES): in addition to the
    pre-existing L1.4 stdout token (unchanged byte-content on stdout) and the
    free-text diagnostic line (unchanged on stderr), emit a colored human-
    readable ⚠️ DEGRADED line on stderr -- misscoped is the operator's
    legitimate "this feature does not need env-e2e" outcome.
    """
    token = StdoutToken(
        mode=mode,
        feature=feature_id,
        authored=False,
        genuine=False,
        collected=0,
        verdict=GateVerdict.MISSCOPED,
        verdict_input_digest=None,
        fresh=None,
        xfail_present=None,
    )
    _emit_token(token)
    print(
        "diagnostic: feature delta carries no `## Environmental E2E` block — "
        "the work is mis-scoped as a feature",
        file=sys.stderr,
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"environmental e2e {mode} misscoped for {feature_id} "
        "(feature has no `## Environmental E2E` block -- gate not applicable)",
    )


def _emit_misscoped_facet(mode: str, feature_id: str, runner_name: str) -> None:
    """Print the L1.4 misscoped token for a resolved-but-unfaceted runner.

    DDD-CERT-7: distinct cause from ``_emit_misscoped`` (an absent
    ``## Environmental E2E`` block). Here the block IS present and a REAL,
    KNOWN non-pytest runner resolved (``cargo-test``/``go-test``/``vitest``),
    but no ``environmental_e2e`` facet is registered for it -- confesses the
    coverage gap honestly (naming the missing runner, GDP-3 what/why/how)
    rather than silently falling through to a Python wheel build against the
    wrong toolchain. Reuses the EXISTING frozen ``GateVerdict.MISSCOPED``
    (exit 3) -- no 5th L1.4 exit value.
    """
    token = StdoutToken(
        mode=mode,
        feature=feature_id,
        authored=False,
        genuine=False,
        collected=0,
        verdict=GateVerdict.MISSCOPED,
        verdict_input_digest=None,
        fresh=None,
        xfail_present=None,
    )
    _emit_token(token)
    print(
        f"diagnostic: no environmental-e2e facet is registered for runner "
        f"{runner_name!r}; build a "
        f"{runner_name!r}-targeted EnvironmentalE2EAdapter per the "
        "unified-language-adapter-registry pattern, or declare "
        "`walking_skeleton_applicable: false` for this feature",
        file=sys.stderr,
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"environmental e2e {mode} misscoped for {feature_id} "
        f"(no environmental-e2e facet registered for runner {runner_name!r} "
        "-- gate not applicable to this language yet)",
    )


def _emit_real_fail_diagnostic(
    feature_id: str,
    feature_delta: Path,
    verdict: GateVerdict,
    collected: int,
    rerun_results: list[str],
) -> None:
    """Print a human WHAT/WHY/HOW diagnostic for the genuine test-FAIL branch.

    Slice-01 surface (fix-env-e2e-real-fail-emits-diagnostic, GDP-3): the
    CHECK_FAILED branch of `--mode run` previously returned bare -- only the
    L1.4 machine `StdoutToken` on stdout, no human-readable explanation. This
    mirrors `_emit_parse_error` / `_emit_misscoped`: a `diagnostic: ...` line
    on stderr plus a colored `print_human_summary` line. The check itself
    (exit stays CHECK_FAILED, verdict logic unchanged) is untouched -- this
    only adds the explanation before the pre-existing return.
    """
    non_passing = sum(1 for outcome in rerun_results if outcome != "pass")
    total_reruns = len(rerun_results)
    print(
        f"diagnostic: environmental e2e for {feature_id} did not pass "
        f"(verdict={verdict.value}, {collected} case(s) collected, "
        f"{non_passing}/{total_reruns} rerun(s) non-passing)",
        file=sys.stderr,
    )
    print_human_summary(
        Verdict.FAIL,
        f"environmental e2e run failed for {feature_id} "
        f"(verdict={verdict.value}) -- reproduce with "
        "'des verify-environmental-e2e --mode run --feature-delta "
        f"{feature_delta}'; per-test outcomes are in the JUnit XML produced "
        "by that run",
    )


def _try_write_deferral_marker(marker_arg: str | None, reason: str) -> None:
    """Write the L1.7 deferral marker for fail-mode D when requested; fail-closed.

    When ``marker_arg`` is unset, this is a no-op (the wrapper that knows where
    the marker lives is free to omit it). When set, the marker is written
    atomically; any I/O failure propagates so the caller can map it to exit 2
    (parse/IO) per fail-closed semantics: the marker is the only on-disk
    evidence of a deferred run, so we never silently proceed past a write
    failure.
    """
    if marker_arg is None:
        return
    write_deferral_marker(Path(marker_arg), reason)


def _emit_unbuilt_mode(mode: str, feature_id: str) -> None:
    """Print an honest refusal for an advertised `--mode` with no shipped
    behavior yet; verdict=misscoped / exit 3 (GateExit.MISSCOPED) -- reuses
    the frozen L1.4 capability-gap exit value, never a raw traceback.

    Bugfix `fix-verify-authored-mode-not-implemented`: distinct cause from
    `_emit_misscoped` (an absent `## Environmental E2E` block) and
    `_emit_misscoped_facet` (an unregistered runner facet) -- here the MODE
    itself has no shipped implementation yet. Names the mode (WHAT), states
    plainly it is not implemented (WHY), and points at `--mode run` -- the
    one mode this CLI ships today (HOW) -- so the refusal removes the wall
    instead of just moving it (GDP-3).
    """
    token = StdoutToken(
        mode=mode,
        feature=feature_id,
        authored=False,
        genuine=False,
        collected=0,
        verdict=GateVerdict.MISSCOPED,
        verdict_input_digest=None,
        fresh=None,
        xfail_present=None,
    )
    _emit_token(token)
    print(
        f"diagnostic: --mode {mode} is not implemented yet -- use "
        "--mode run instead, the only mode this CLI ships today",
        file=sys.stderr,
    )
    print_human_summary(
        Verdict.DEGRADED,
        f"environmental e2e --mode {mode} not yet implemented for "
        f"{feature_id} -- use --mode run instead",
    )


def _verify_authored_mode(args: argparse.Namespace) -> int:
    """Execute `--mode verify-authored` (slice-03 scope: misscoped detector).

    L1.4 question: 'Has the feature's environmental e2e been authored, is it
    RED-for-the-right-reason, is it genuine?'. The misscoped branch is the
    structural pre-condition: if the feature-delta carries no `## Environmental
    E2E` block, the work itself is mis-scoped as a feature -- verdict=misscoped
    / exit 3 / diagnostic names the absent block. The full authored/genuine
    checks ship in later slices; the misscoped detection is mandatory here
    because every downstream verdict assumes the block exists.
    """
    if args.feature_id is None or args.feature_delta is None:
        _emit_parse_error(
            "verify-authored",
            args.feature_id or "?",
            "--feature-id and --feature-delta required",
        )
        return int(GateExit.PARSE_IO)
    feature_delta = Path(args.feature_delta).resolve()
    if not feature_delta.is_file():
        _emit_parse_error(
            "verify-authored",
            args.feature_id,
            f"feature delta not found: {feature_delta}",
        )
        return int(GateExit.PARSE_IO)
    text = feature_delta.read_text(encoding="utf-8")
    if not has_environmental_e2e_block(text):
        _emit_misscoped("verify-authored", args.feature_id)
        return int(GateExit.MISSCOPED)
    # Block present -- the verify-authored happy path (authored+genuine
    # verification) is out of slice-03 scope; the slice-03 contract here is
    # the misscoped branch only. Refuse honestly rather than crash (bugfix
    # fix-verify-authored-mode-not-implemented).
    _emit_unbuilt_mode("verify-authored", args.feature_id)
    return int(GateExit.MISSCOPED)


def _run_mode(args: argparse.Namespace) -> int:
    """Execute `--mode run` per L1.4: build -> install -> run -> verdict + digest."""
    if args.feature_id is None or args.feature_delta is None:
        _emit_parse_error(
            "run", args.feature_id or "?", "--feature-id and --feature-delta required"
        )
        return int(GateExit.PARSE_IO)
    feature_delta = Path(args.feature_delta).resolve()
    if not feature_delta.is_file():
        _emit_parse_error(
            "run", args.feature_id, f"feature delta not found: {feature_delta}"
        )
        return int(GateExit.PARSE_IO)

    try:
        e2e_rel = _parse_feature_delta_e2e_block(feature_delta)
    except ValueError as exc:
        _emit_parse_error("run", args.feature_id, str(exc))
        return int(GateExit.PARSE_IO)
    if e2e_rel is None:
        _emit_misscoped("run", args.feature_id)
        return int(GateExit.MISSCOPED)

    source_tree = _resolve_source_tree(args)
    e2e_abs = (source_tree / e2e_rel).resolve()

    routed_registered = _maybe_route_through_registered_e2e_adapter(
        source_tree, e2e_abs
    )
    if isinstance(routed_registered, _FacetMissingForResolvedRunner):
        _emit_misscoped_facet("run", args.feature_id, routed_registered.runner_name)
        return int(GateExit.MISSCOPED)
    if routed_registered is not None:
        return routed_registered

    with tempfile.TemporaryDirectory(prefix="env-e2e-build-") as build_outdir_str:
        build_outdir = Path(build_outdir_str)
        try:
            wheel = _build_wheel(source_tree, args.build_command, build_outdir)
        except (RuntimeError, FileNotFoundError) as exc:
            # Fail-mode D: no provisionable artifact -> write the deferral
            # marker. Marker-write failure raises -> caught below -> exit 2.
            _try_write_deferral_marker(args.deferral_marker, f"build: {exc}")
            _emit_parse_error("run", args.feature_id, str(exc))
            return int(GateExit.PARSE_IO)

        wheel_hash = _sha256_file(wheel)
        prefix = _resolve_clean_prefix(args.clean_prefix)
        try:
            _install_into_prefix(wheel, prefix)
        except RuntimeError as exc:
            # Fail-mode D: no provisionable hermetic install target.
            _try_write_deferral_marker(args.deferral_marker, f"install: {exc}")
            _emit_parse_error("run", args.feature_id, str(exc))
            return int(GateExit.PARSE_IO)

        if not e2e_abs.is_file():
            _emit_parse_error(
                "run", args.feature_id, f"environmental e2e not found: {e2e_abs}"
            )
            return int(GateExit.PARSE_IO)
        e2e_files_hash = _sha256_concat([e2e_abs])
        ci_closure_hash = _ci_closure_hash(args.feature_id)
        breakdown = VerdictInputBreakdown(
            wheel=wheel_hash,
            e2e_files=e2e_files_hash,
            ci_job_closure=ci_closure_hash,
        )
        digest = compute_verdict_input_digest(breakdown)

        if args.fixture_junit_xml is not None:
            # Test seam: a pre-baked JUnit XML (or comma-separated list, one
            # per rerun) stands in for real pytest runs.
            verdict, collected, rerun_results = _consume_fixture_junit(
                args.fixture_junit_xml, args.reruns
            )
        else:
            rerun_results = []
            with tempfile.TemporaryDirectory(prefix="env-e2e-run-") as run_dir_str:
                run_dir = Path(run_dir_str)
                junit_path = run_dir / "junit.xml"
                for _ in range(args.reruns):
                    _run_e2e_against_installed(e2e_abs, prefix, junit_path, run_dir)
                    verdict, collected = _verdict_from_junit(junit_path, rerun_results)
        # Stability across reruns -> flaky downgrades a mixed-bag PASS/FAIL.
        if len(set(rerun_results)) > 1:
            verdict = GateVerdict.FLAKY

    record = ResultsRecord(
        feature_id=args.feature_id,
        verdict_input_digest=digest,
        verdict_input_breakdown=breakdown,
        verdict=verdict,
        collected=collected,
        reruns=args.reruns,
        rerun_results=tuple(rerun_results),
        xfail_marker_present=False,
        e2e_path=str(e2e_rel),
        built_at=datetime.now(timezone.utc).isoformat(),
        cli_version=_CLI_VERSION,
    )

    if args.results_json is not None:
        results_path = Path(args.results_json)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(serialize_results_record(record), encoding="utf-8")

    token = StdoutToken(
        mode="run",
        feature=args.feature_id,
        authored=True,
        genuine=True,
        collected=collected,
        verdict=verdict,
        verdict_input_digest=digest,
        fresh=True,
        xfail_present=False,
    )
    _emit_token(token)

    if verdict is GateVerdict.PASS:
        return int(GateExit.PASS)
    _emit_real_fail_diagnostic(
        args.feature_id, feature_delta, verdict, collected, rerun_results
    )
    return int(GateExit.CHECK_FAILED)


def main(argv: list[str] | None = None) -> int:
    """L1.4 entry point — dispatch on `--mode`."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.mode == "run":
        return _run_mode(args)
    if args.mode == "verify-authored":
        return _verify_authored_mode(args)
    # verify-present / verify-merge-ready / audit: no shipped behavior yet.
    # Refuse honestly rather than crash (bugfix
    # fix-verify-authored-mode-not-implemented) -- before any argument
    # validation runs, per the frozen L1.4 exit-code grid.
    _emit_unbuilt_mode(args.mode, args.feature_id or "?")
    return int(GateExit.MISSCOPED)


if __name__ == "__main__":  # pragma: no cover -- subprocess entry
    sys.exit(main(sys.argv[1:]))
