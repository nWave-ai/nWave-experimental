"""des-verify-slice-commit-completeness -- slice-commit verify-then-record gate.

slice-14 of the atdd-pure-roadmap-free-rollout (E1, the completeness check) +
slice-02 of simplify-atdd-pure-carpaccio-spine (DDD-3, the atomic
verify-then-record exit gate).

Given a commit carrying a `Slice-Id:` trailer, this CLI runs two checks in
order -- E1 completeness then E2 the feature-scoped contract gate -- and
appends a `SliceCommitVerified` ledger record IF AND ONLY IF both exit 0, in
the same process. On any non-zero half the CLI exits non-zero and appends
nothing: an unverified slice never leaves a record behind (the M-3
non-vacuity contract, wall W3).

E1 completeness: assert every scenario tagged `@slice-NN` for the slice lives
in a git-tracked `.feature` file that is EITHER present in this commit OR
already tracked and unmodified by this slice. Under `--feature-id` the
`.feature` search is scoped to that feature via the `@feature-{id}` tag
(wall W5 -- a global `rglob` collides `@slice-NN` tags across features).

E2 contract gate: compose `run_contract_gate --feature-id` as a subprocess --
the feature-scoped contract suite with the M-1/M-8 non-vacuity floor.

Bounded-change: the ONLY filesystem mutation is one `SliceCommitVerified`
record appended per listed slice to the feature's M7 AT-completion ledger
(`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`, via
`AtCompletionLedger.append_gate_event`), performed IFF E1 exit 0 AND E2 exit 0.
Reads otherwise (`git show`, `.feature` files).

MUST be stdlib-only (no `import yaml`) per the DES-bundle contract -- the very
contract the slice-01 regression violated. Every import below is stdlib or an
intra-package `des` module that is itself stdlib-only:
`carpaccio_slice_gate._feature_tag_files` (the `@feature-{id}` resolver, the
same import `run_contract_gate` uses for its `--feature-id` scope) and
`AtCompletionLedger` (the M7 ledger writer -- `fcntl` / `hashlib` / `json`,
all stdlib).

A commit MAY carry MULTIPLE `Slice-Id:` trailer lines -- the whole-tree-stashing
pre-commit hook forces interleaved multi-slice work to batch into ONE commit,
which then lists every slice it covers as a separate `Slice-Id:` trailer (see
friction F-07, docs/analysis/atdd-pure-dogfooding-friction-2026-05-20.md). The
gate verifies slice-commit completeness for EVERY listed slice and certifies
the commit only when every listed slice is complete; a single-`Slice-Id:`
commit is the one-element case of the same logic.

Exit codes:
    0 = verified -- E1 and E2 both cleared; exactly one `SliceCommitVerified`
        record was appended for the slice(s).
    1 = refused -- E1 (completeness) or E2 (contract gate) failed; the JSON
        payload names the failed half. Nothing was appended.
    2 = malformed input -- no `Slice-Id:` trailer, or repo / commit unreadable.

Reference: docs/feature/atdd-pure-roadmap-free-rollout/feature-delta.md
           # slice-14 design note (E1);
           docs/feature/simplify-atdd-pure-carpaccio-spine/feature-delta.md
           # slice-02 (DDD-3).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.runner.runner_json import read_runner_json
from des.adapters.driven.runner.runner_registry import seed_runner_registry
from des.application.slice_at_completeness import (
    _regression_file_glob_candidates,
    canonical_regression_test_path,
    feature_files_for_slice,
    files_in_commit,
    missing_at_files,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.carpaccio_format import (
    _feature_tag_files,
    _lane_profile_for_slice,
    parse_slice_plan,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.run_contract_gate import _GATE_INDETERMINATE_EXIT_CODE
from des.cli.verify_deliver_integrity import _slice_commit_verified_slices
from des.domain.lane_profile import AtRequirement
from des.domain.repo_path_resolver import feature_delta_path
from des.domain.slice_id_trailer import (
    _SLICE_ID_TRAILER_RE,
    extract_slice_id,
    extract_slice_ids,
)
from des.ports.test_runner_port import (
    RunnerAdapter,
    RunnerAdapterUnavailable,
    RunnerResolutionContext,
)
from des.ports.test_runner_port import resolve as resolve_runner
from des.runtime.interpreter import Capability, InterpreterUnavailable, des_spawn


# The contract gate's dedicated INDETERMINATE exit code (DDD-2): the E2 gate
# could not resolve a usable interpreter on this machine and degraded LOUD
# INDETERMINATE-and-proceed rather than hard-refusing -- distinct from 0
# (cleared), 1 (refused), 2 (hard-refuse / malformed). On this outcome the
# exit gate mints an honest ``SliceCommitIndeterminate``, never a fabricated
# ``SliceCommitVerified`` and never a bare refusal.
#
# Imported from ``run_contract_gate`` (the SSOT -- slice-05 refactor,
# certification-legs-observe-real-execution) rather than re-declared: this
# module already composes ``run_contract_gate`` as its E2 leg (both as a
# subprocess via ``des.cli.run_contract_gate`` and, for pytest-regression,
# through the SAME degrade-LOUD sentinel), so a second independent
# ``= 3`` definition was a duplicated exit-code literal, not an
# intentional second contract. Re-exported here (module-level name
# unchanged) so every existing import site
# (``from des.cli.verify_slice_commit_completeness import
# _GATE_INDETERMINATE_EXIT_CODE``) keeps resolving to the identical value.


# The regression-collection leg's runner-aware whole-tree run convention, keyed
# by the resolved runner name (verify-slice-commit-runner-aware-collection,
# slice-01, sister of Bug B pt.2). A committed feature-dir ``runner.json``
# ``test_command`` OVERRIDES this (the SAME override
# ``run_contract_gate._cargo_scope_command`` consults for the Gherkin/
# feature-scoped path); with none, a KNOWN runner falls back to its whole-tree
# convention -- ``cargo nextest run`` auto-discovers every ``tests/*.rs``
# integration target, so the declared ``--regression-test-file`` is exercised
# without needing a feature-scoped selector. A runner absent from this table
# has no established regression-run convention in this feature -- the caller
# degrades LOUD INDETERMINATE rather than guessing a command shape.
_REGRESSION_RUNNER_WHOLE_TREE_COMMAND: dict[str, tuple[str, ...]] = {
    "cargo-test": ("cargo", "nextest", "run"),
}


def _routes_through_runner_port(
    repo: Path, feature_id: str, regression_test_file: str
) -> bool:
    """Whether the E2 regression collection leg routes through the runner-port.

    PINNED CONTRACT: the declared ``--regression-test-file`` is NON-Python
    (extension not ``.py``), OR the feature-dir declares a committed
    ``runner.json`` ``test_command`` override -- either signal alone is
    sufficient. A ``.py`` file with no override keeps the EXISTING
    pytest-native collection path byte-identical (the regression guard).
    """
    if Path(regression_test_file).suffix != ".py":
        return True
    override = read_runner_json(feature_id, repo)
    return override is not None and bool(override.get("test_command"))


def _regression_runner_command(
    repo: Path, feature_id: str, runner_name: str
) -> tuple[str, ...] | None:
    """The runner command to RUN the declared regression-test-file, or ``None``.

    A committed ``runner.json`` ``test_command`` OVERRIDES; with none, a KNOWN
    runner (``_REGRESSION_RUNNER_WHOLE_TREE_COMMAND``) falls back to its
    whole-tree convention. ``None`` means this runner has no established
    regression-run convention in this feature -- the caller degrades LOUD
    INDETERMINATE.
    """
    override = read_runner_json(feature_id, repo)
    if override is not None and override.get("test_command"):
        return tuple(str(override["test_command"]).split())
    return _REGRESSION_RUNNER_WHOLE_TREE_COMMAND.get(runner_name)


def _run_regression_gate_via_runner(
    repo: Path, feature_id: str
) -> tuple[int, str | None, str | None]:
    """Run E2 for a regression-test-file through the runner-port (non-Python).

    Mirrors ``run_contract_gate._maybe_route_through_cargo`` (the PROVEN
    Gherkin/feature-scoped precedent composing the SAME seam): seed the
    runner registry, RESOLVE the target's runner, derive/read its run
    command, and map the verdict. Returns ``(exit_code, reason, diagnostic)``
    -- ``reason``/``diagnostic`` are non-``None`` ONLY on an INDETERMINATE
    exit, naming the RUNNER as the cause (never the pytest-native
    uncollectible literal -- that diagnostic means the pytest collector ran,
    which never happens on this leg).
    """
    seed_runner_registry()
    resolution = resolve_runner(
        repo, RunnerResolutionContext(feature_id=feature_id, repo=repo)
    )
    if not isinstance(resolution, RunnerAdapter):
        reason = getattr(resolution, "reason", "no recognized test-runner resolved")
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "regression_runner_unresolvable",
            "no test-runner resolved for the declared --regression-test-file's "
            f"target -- {reason} -- recorded an honest SliceCommitIndeterminate "
            "(unverified here), never coerced through the pytest-native "
            "collector on a non-Python target",
        )
    command = _regression_runner_command(repo, feature_id, resolution.name)
    if command is None:
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "regression_runner_unresolvable",
            f"the resolved runner {resolution.name!r} has no known regression-run "
            "convention in this feature -- recorded an honest "
            "SliceCommitIndeterminate (unverified here), never a fabricated pass",
        )
    try:
        verdict = resolution.run(repo, command)
    except RunnerAdapterUnavailable as exc:
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "regression_runner_unavailable",
            f"the {resolution.name!r} runner could not produce a trustworthy "
            f"verdict for the declared --regression-test-file: {exc} -- recorded "
            "an honest SliceCommitIndeterminate (unverified here), never a "
            "fabricated pass",
        )
    return (0 if verdict.passed else 1, None, None)


# DDD-3 identity guarantee: re-export the pure-function SSOT symbols so the
# 18 pre-existing callers (reverify_slice_commit + the multi-slice-trailer /
# atdd-pure-exit-gate ATs) keep importing from this module unchanged. The
# completeness symbols' canonical home is ``des.application.slice_at_completeness``;
# the pure trailer-parsers (``extract_slice_id`` / ``extract_slice_ids`` and the
# ``_SLICE_ID_TRAILER_RE`` they share) are domain logic homed in
# ``des.domain.slice_id_trailer`` (AD-05 layering fix -- adapters imported them
# downward from this CLI module). This module is the CLI driving port that wraps
# them with argparse + verdict emission. ``__all__`` marks the re-exported names
# as intentional so autoflake keeps the otherwise-internally-unused regex.
__all__ = [
    "_GATE_INDETERMINATE_EXIT_CODE",
    "_SLICE_ID_TRAILER_RE",
    "canonical_regression_test_path",
    "extract_slice_id",
    "extract_slice_ids",
    "feature_files_for_slice",
    "files_in_commit",
    "main",
    "missing_at_files",
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-slice-commit",
        description="Verify a slice commit carries the slice's .feature AT files.",
    )
    add_repo_root_argument(
        parser, "--repo", required=True, help="Path to the git repository to inspect."
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="The commit-ish to inspect (e.g. HEAD).",
    )
    parser.add_argument(
        "--feature-id",
        help=(
            "The feature the slice commit belongs to. When given, the CLI runs "
            "the atomic verify-then-record exit gate: E1 completeness scoped to "
            "this feature, then E2 the feature-scoped contract gate, then one "
            "SliceCommitVerified ledger record IFF both clear. When omitted the "
            "CLI runs the legacy E1-only completeness check (classic-mode "
            "callers -- reverify_slice_commit, the U2 hook)."
        ),
    )
    parser.add_argument(
        "--expected-head",
        help=(
            "The pinned HEAD SHA the gate was launched against (M9). When "
            "present, the CLI re-reads HEAD and fails closed with "
            "CommitHeadRaced if HEAD has moved off this SHA. When absent, no "
            "race check runs -- behaviour is byte-for-byte unchanged."
        ),
    )
    parser.add_argument(
        "--scope-feature-id",
        help=(
            "Scope the legacy E1-only completeness check to this feature's "
            "`@feature-{id}`-tagged `.feature` files (slice-03). Unlike "
            "`--feature-id` (which flips the CLI into the verify-then-record "
            "exit gate -- E1 + E2 + a SliceCommitVerified ledger record), "
            "`--scope-feature-id` keeps the legacy E1-only verdict shape and "
            "writes NO ledger record: it only narrows E1's `.feature` candidate "
            "scan so a co-resident feature sharing the slice number on the tree "
            "is not cross-bound into this commit's completeness check. The U2 "
            "hook supplies it so E1 runs scoped while the hook stays the sole "
            "author of the verified record (E1 runs once, one record)."
        ),
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        default="gherkin",
        choices=(
            "gherkin",
            "pytest-regression",
            "native-regression",
            "rust-regression",
        ),
        help=(
            "The acceptance-test kind the slice's E2 leg attests (default: "
            "gherkin, byte-identical for every existing caller). "
            "'pytest-regression' (#13) replaces the feature-scoped contract "
            "gate -- which cannot resolve a pytest-regression bugfix's "
            "structure -- with a BEHAVIORAL attestation: it actually runs "
            "--regression-test-file on the committed tree and uses its exit "
            "code as the E2 verdict. 'native-regression' "
            "(fix-rust-regression-at-kind-wiring) is the SAME behavioral "
            "attestation for a non-Python regression file (e.g. `.rs`) -- "
            "it routes through the SAME runner-port seam "
            "`_routes_through_runner_port` already resolves for a "
            "pytest-regression file whose suffix is not `.py`. "
            "'rust-regression' (rust-regression-at-kind-semi-wired) is an "
            "accepted ALIAS of 'native-regression', normalized right after "
            "parsing -- never a second code path."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        dest="regression_test_file",
        default=None,
        help=(
            "Repo-relative path to the pytest regression file E2 runs "
            "behaviorally (paired with --at-kind pytest-regression)."
        ),
    )
    parser.add_argument(
        "--slice-id",
        dest="slice_id",
        default=None,
        help=(
            "Override slice id for a bare legacy commit carrying NO "
            "Slice-Id: trailer (#51). When the commit has no resolvable "
            "trailer, this supplies the slice id instead of failing -- "
            "attesting on the BEHAVIORAL proof (the E2 pytest-regression "
            "leg passing on the committed tree) rather than the trailer. "
            "REQUIRES --at-kind pytest-regression + --regression-test-file "
            "(behavioral proof is mandatory without a trailer). REFUSES if "
            "it conflicts with a real Slice-Id: trailer already on the "
            "commit. The written SliceCommitVerified record carries a "
            "transparent attested_via: 'slice-id-override' field."
        ),
    )
    return parser


def _commit_head_raced(
    repo: Path, expected_head: str | None
) -> dict[str, object] | None:
    """Detect a HEAD that has raced off the pinned ``expected_head`` SHA (M9 / F3).

    Returns a `CommitHeadRaced` payload when HEAD has moved off the pinned SHA;
    None when HEAD still matches (or no `--expected-head` was given, so no race
    check runs). Under a concurrent amend/rebase the HEAD the gate was launched
    against can move before the gate inspects it -- a stale verdict. Re-reading
    HEAD makes the race detectable and fail-closed.
    """
    if expected_head is None:
        return None
    try:
        current = _git(repo, "rev-parse", "HEAD").strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {
            "event": "CommitHeadRaced",
            "pinned_sha": expected_head,
            "current_sha": "",
            "error": f"cannot re-read HEAD to verify the pinned SHA: {exc}",
        }
    if current == expected_head:
        return None
    return {
        "event": "CommitHeadRaced",
        "pinned_sha": expected_head,
        "current_sha": current,
        "error": (
            "HEAD moved during the G_COMMIT exit gate "
            f"(pinned {expected_head}, now {current}); re-run the gate"
        ),
    }


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object on BOTH stdout and stderr.

    The pre-existing machine-readable contract (DISCUSS row 4: no breaking
    change for existing pre-commit / CI / hook consumers) keeps the event on
    stdout; the slice-02 human-readable surface co-emits it on stderr so a
    single channel carries both the structured event and the new colored
    verdict line.
    """
    line = json.dumps(payload)
    print(line)
    print(line, file=sys.stderr)


def _human_summary_for(payload: dict[str, object]) -> tuple[Verdict, str]:
    """Return the (verdict, summary) pair the named ``event`` maps to.

    Per slice-02 verdict mapping: SliceCommitComplete / SliceCommitVerified
    → ✅ PASS, every refusal / malformed input → ❌ FAIL. The summary names
    the listed slice(s) when available so the operator immediately sees what
    cleared / refused.
    """
    event = payload.get("event")
    slice_ids = payload.get("slice_ids")
    slice_label = (
        ", ".join(slice_ids) if isinstance(slice_ids, list) and slice_ids else ""
    )
    if event in ("SliceCommitComplete", "SliceCommitVerified"):
        verdict = Verdict.PASS
        summary = (
            f"slice commit verified ({slice_label})"
            if slice_label
            else "slice commit verified"
        )
        return verdict, summary
    verdict = Verdict.FAIL
    error = payload.get("error")
    summary = (
        f"slice commit refused: {error}"
        if isinstance(error, str) and error
        else "slice commit refused"
    )
    return verdict, summary


def _emit_with_human_surface(payload: dict[str, object]) -> None:
    """Emit the JSON event on both channels plus the human-readable verdict line.

    Composes ``_emit`` (dual-channel JSON) with ``print_human_summary``: every
    operator-facing verdict point in this CLI carries BOTH surfaces, so the
    operator sees a colored ✅/❌ line and the structured event lands on
    stderr for the slice-02 AT assertions.
    """
    _emit(payload)
    verdict, summary = _human_summary_for(payload)
    print_human_summary(verdict, summary)


def _is_at_exempt_lane(repo: Path, feature_id: str, slice_id: str) -> bool:
    """Resolve whether ``slice_id`` is AT-EXEMPT, mirroring the entry gate.

    Reads the SAME `[REF] Slice Plan` datum the carpaccio ENTRY gate consults
    (`_lane_profile_for_slice`, `carpaccio_format.py:640-655`) via the SAME
    `feature_delta_path` + `parse_slice_plan` resolution
    (`carpaccio_slice_gate.py:880-892`) -- the single shared consulting
    mechanism (D11/D12), so the exit gate's lane awareness never diverges
    from the entry gate's. Returns ``False`` (never exempt) when the
    feature-delta is absent or the slice carries no `@prefactoring`
    annotation -- the fail-closed default that leaves the non-exempt path
    byte-identical.
    """
    delta_path = feature_delta_path(repo, feature_id)
    if not delta_path.is_file():
        return False
    plan = parse_slice_plan(delta_path.read_text(encoding="utf-8"))
    profile = _lane_profile_for_slice(plan, slice_id)
    return profile is not None and profile.at_requirement is AtRequirement.EXEMPT


def _examine_verdict_clears_slice(repo: Path, feature_id: str, slice_id: str) -> bool:
    """Resolve whether an armed examine-verdict PASS clears ``slice_id`` at E1.

    RCA fix-carpaccio-e1-vacuous-taxonomy-gap: E1's zero-recognized-AT-
    candidates refusal previously only exempted `@prefactoring` lanes
    (`_is_at_exempt_lane` above), leaving no carve-out for a slice that
    genuinely owns zero executable AT candidates by nature (a prose/
    documentation slice) but WAS examined and cleared by a human observer.
    Mirrors E2's OWN examine-verdict carve-out (ADR-DES-001 addendum Rule 1,
    below) at the earlier E1 gate: an ARMED gate (a charter exists for this
    feature) with `check_examine_verdict` returning ``None`` (fresh,
    matching-seal PASS) is the same legitimate "examined and passed" signal
    E2 already trusts -- E1 must not refuse a slice E2 would go on to clear
    anyway. `_examine_gate_armed` and `check_examine_verdict` are imported
    LOCALLY (not at module scope) to avoid a circular import with
    `des.cli.commit_slice`, exactly as E2's own rescue does.
    """
    from des.cli.commit_slice import _examine_gate_armed, check_examine_verdict

    return _examine_gate_armed(repo, feature_id) and (
        check_examine_verdict(repo, feature_id, slice_id) is None
    )


def _parse_single_line_json_payload(stdout: str) -> dict[str, object] | None:
    """Parse a child gate's own single-line JSON verdict off its captured stdout.

    Mirrors this AT file's own ``_run_verify_slice_commit`` helper convention:
    the LAST line starting with ``{`` is the verdict payload (a preceding
    human-readable line, if any, is not JSON and is skipped). Returns ``None``
    when no JSON line is present or it fails to parse/is not an object --
    never raises, so a malformed/absent child payload degrades to "nothing to
    thread through" rather than crashing the parent gate.
    """
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    if not json_lines:
        return None
    try:
        payload = json.loads(json_lines[-1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_contract_gate(
    repo: Path, feature_id: str, slice_id: str
) -> tuple[int, dict[str, object] | None]:
    """Run E2 -- the feature-scoped contract gate -- for one slice.

    Composes `run_contract_gate --feature-id` as a subprocess (DDD-12: the
    test-runner seam stays inside `run_contract_gate`; this CLI adds no pytest
    call site of its own). Returns ``(exit_code, child_payload)`` -- exit_code
    is 0 when the feature-scoped suite cleared, non-zero on a refusal or a
    malformed scope; ``child_payload`` is the child gate's OWN single-line
    JSON verdict (e.g. a ``FeatureScopeMalformed`` naming its ``reason``/
    ``error``), or ``None`` when it could not be captured/parsed.

    The child ALREADY emits a self-explaining verdict -- it is the authority
    on WHY it refused. This function's job is to CARRY that verdict, not
    re-derive or summarize it: the caller threads ``child_payload``'s own
    ``error``/``next`` straight into the parent's refusal instead of
    replacing it with a generic, reason-less template (the trap that void'd
    two independent examinations: a refusal naming an unrelated cause is
    worse than one that says nothing).

    DDD-1/DDD-2 degrade-LOUD: when ``des_spawn`` itself cannot resolve a usable
    interpreter on this machine it raises ``InterpreterUnavailable`` (the spawn
    boundary, not the child). That is the same non-Python-target interpreter
    absence the gate's own collection path degrades on -- map it to the
    dedicated ``_GATE_INDETERMINATE_EXIT_CODE`` so the caller records an honest
    ``SliceCommitIndeterminate`` instead of crashing. INDETERMINATE is never
    coerced to 0 (a pass) -- a runnable-but-failing gate returns its own
    non-zero code unchanged.

    verify-slice-commit-e2-wrapper-divergence: this composed E2 subprocess
    used ``des_spawn(..., capture_output=True, text=True)`` -- an IN-MEMORY
    pipe pair -- and was observed to return a DIFFERENT exit code than an
    identical hand-run of the same child under a large feature-scoped suite
    (suspected in-memory-pipe hazard). The child's stdout/stderr now stream to
    real on-disk tempfiles instead (``_spawn_streamed_to_tempfiles``): nothing
    to fill/deadlock on, and the full text is read back only after the child
    has genuinely exited, never partially.
    """
    try:
        completed = _spawn_streamed_to_tempfiles(
            None,
            "des.cli.run_contract_gate",
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--entering-slice",
            slice_id,
        )
    except InterpreterUnavailable:
        return _GATE_INDETERMINATE_EXIT_CODE, None
    return completed.returncode, _parse_single_line_json_payload(completed.stdout)


def _spawn_streamed_to_tempfiles(
    capability: Capability | None,
    *module_args: str,
    script: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a ``des_spawn`` module subprocess with stdout/stderr streamed to disk.

    verify-slice-commit-e2-wrapper-divergence: ``subprocess.run(capture_
    output=True)`` (via ``Popen.communicate()``) drains the child through an
    IN-MEMORY pipe pair -- under a genuinely large child (a full feature-
    scoped suite's combined stdout/stderr) this is the suspected proximate
    cause of the wrapper's composed subprocess call returning a DIFFERENT
    exit code than an identical hand-run of the SAME child. Streaming both
    streams to real, separate on-disk tempfiles removes the in-memory pipe
    entirely -- the child writes directly to a file descriptor with no
    capacity ceiling to fill, and this function only reads the files back
    once ``des_spawn`` has returned (the child has genuinely exited).

    Mirrors ``des_spawn``'s own ``capture_output=True`` contract from the
    caller's side: returns a ``CompletedProcess`` whose ``.stdout``/``.stderr``
    are the full text the child wrote, and whose ``.returncode`` is the
    child's own exit code, untouched.

    ``script`` (keyword-only, forwarded to ``des_spawn``'s own ``-c
    <inline-script>`` form) is unused by the production call site
    (``_run_contract_gate`` always passes ``module_args``) -- it exists so a
    regression test can drive this helper with a synthetic large-output
    child without needing a real ``des.cli`` module on disk.
    """
    with (
        tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", prefix="des-e2-stdout-", delete=False
        ) as stdout_fh,
        tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", prefix="des-e2-stderr-", delete=False
        ) as stderr_fh,
    ):
        stdout_path = Path(stdout_fh.name)
        stderr_path = Path(stderr_fh.name)
    try:
        with (
            stdout_path.open("w", encoding="utf-8") as stdout_w,
            stderr_path.open("w", encoding="utf-8") as stderr_w,
        ):
            completed = des_spawn(
                capability,
                *module_args,
                script=script,
                stdout=stdout_w,
                stderr=stderr_w,
            )
        stdout_text = stdout_path.read_text(encoding="utf-8")
        stderr_text = stderr_path.read_text(encoding="utf-8")
    finally:
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
    return subprocess.CompletedProcess(
        completed.args, completed.returncode, stdout_text, stderr_text
    )


def _run_regression_gate(
    repo: Path, feature_id: str, regression_test_file: str
) -> tuple[int, str | None, str | None]:
    """Run E2 BEHAVIORALLY for a pytest-regression slice (#13, Ale-ratified).

    RUNNER-AWARE (verify-slice-commit-runner-aware-collection, slice-01): a
    NON-Python ``regression_test_file`` (extension not ``.py``), OR one whose
    feature-dir declares a committed ``runner.json`` ``test_command``, routes
    through the runner-port (``_run_regression_gate_via_runner``) instead of
    the pytest-native spawn below -- pytest cannot collect a non-Python file.
    The ``.py``-with-no-override path stays BYTE-IDENTICAL to the original
    pytest-native attestation.

    The pytest-native path: the feature-scoped contract gate cannot resolve a
    pytest-regression bugfix's structure, so this replaces it with an
    execution-observing attestation: it actually RUNS the declared
    ``regression_test_file`` on the committed tree (``-m pytest <file> -q``
    via ``des_spawn`` -- the SAME interpreter-resolution boundary
    ``_run_contract_gate`` uses, mirroring ``verify_red_green.py``'s
    subprocess pattern) and uses ITS exit code as the E2 verdict. Only an
    OBSERVED pass (exit 0) ever earns E2-clear.

    Every interpreter spawn in ``src/des`` MUST route through
    ``des.runtime.interpreter.python_for`` (the build-tier arch-test
    ``test_no_inline_interpreter_spawn.py`` bans a raw ``sys.executable``) --
    ``des_spawn("pytest", ...)`` composes that resolution BY CONSTRUCTION, so
    this never trusts the running interpreter's name.

    Returns ``(exit_code, reason, diagnostic)``. A declared file that is
    missing, or whose interpreter ``des_spawn`` itself cannot resolve
    (``InterpreterUnavailable``), is NEVER trusted by presence alone -- it
    returns the SAME ``_GATE_INDETERMINATE_EXIT_CODE`` sentinel
    ``_run_contract_gate`` uses for its own degrade-LOUD path, now with a
    NAMED ``reason``/``diagnostic`` distinguishing WHICH of the two causes
    fired (fix-runner-resolves-per-scope-language slice-01, Fix B --
    previously both causes collapsed into the SAME reason-less ``(exit,
    None, None)``, forcing the caller's generic ``pytest_regression_file_
    unrunnable`` fallback to speak for both): a genuinely MISSING file
    returns ``regression_test_file_missing_on_committed_tree``; an
    unresolvable interpreter returns
    ``regression_test_file_interpreter_unavailable`` (naming the probed
    candidates). So the caller routes it through the existing
    ``SliceCommitIndeterminate`` machinery (never a fabricated
    ``SliceCommitVerified``, never a silent pass). The runner-routed path
    names the RUNNER as the cause instead (never these literals -- see
    ``_run_regression_gate_via_runner``).
    """
    test_path = repo / regression_test_file
    if not test_path.is_file():
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "regression_test_file_missing_on_committed_tree",
            (
                f"the declared --regression-test-file {regression_test_file!r} "
                "does not exist on the committed tree -- recorded an honest "
                "SliceCommitIndeterminate (unverified here), never a "
                "fabricated pass"
            ),
        )
    if _routes_through_runner_port(repo, feature_id, regression_test_file):
        return _run_regression_gate_via_runner(repo, feature_id)
    try:
        completed = des_spawn(
            "pytest",
            "pytest",
            str(test_path),
            "-q",
            cwd=repo,
            capture_output=True,
            text=True,
        )
    except InterpreterUnavailable as exc:
        probed = ", ".join(exc.probed) if exc.probed else "(none)"
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "regression_test_file_interpreter_unavailable",
            (
                "no usable pytest interpreter could be resolved on this "
                f"machine to run the declared --regression-test-file "
                f"{regression_test_file!r} -- probed: {probed} -- recorded "
                "an honest SliceCommitIndeterminate (unverified here), never "
                "a fabricated pass"
            ),
        )
    return completed.returncode, None, None


def _declared_regression_test_file(
    repo: Path, feature_id: str, slice_id: str
) -> str | None:
    """The repo-relative pytest-regression file ``slice_id`` itself declared
    via ``--regression-test-file`` at its OWN ``SliceCommitVerified`` time
    (#59, fix-commit-slice-reverify-uses-stored-file).

    Raw-JSONL scan of the legacy per-feature ledger
    (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``) -- mirrors
    ``_slice_commit_verified_slices``'s (``verify_deliver_integrity.py``)
    tolerant-scan shape (skip unparseable lines, absent ledger -> None)
    rather than ``AtCompletionLedger.read_records``'s fail-closed integrity
    sweep: this is a best-effort STORED-value lookup feeding a
    conservative-keep fallback (the naming-convention glob), never the sole
    source of truth, so a corrupt/unreadable ledger degrades to "no stored
    value" (glob fallback fires) instead of crashing the commit-slice gate.

    Returns the LAST matching record's ``regression_test_file`` (idempotent
    re-verification of an already-verified slice may append further records,
    C4a) -- the most recent declaration wins. ``None`` when no
    ``SliceCommitVerified`` record for ``slice_id`` carries the field (e.g. a
    historical record predating this feature, or a non-pytest-regression
    slice).
    """
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    if not ledger.is_file():
        return None
    declared: str | None = None
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if '"SliceCommitVerified"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if (
                rec.get("event") == "SliceCommitVerified"
                and rec.get("slice_id") == slice_id
                and isinstance(rec.get("regression_test_file"), str)
            ):
                declared = rec["regression_test_file"]
    except OSError:
        return None
    return declared


def _shipped_and_entering_regression_files(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    entering_regression_test_file: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Resolve the {shipped} UNION {entering} regression-file set (RC2 Fix A).

    The entering slice always uses its explicitly declared
    ``entering_regression_test_file`` (never re-resolved by convention -- the
    caller's own declaration always wins). Every SHIPPED slice (per the
    ledger resolver ``_slice_commit_verified_slices``, REUSE -- the
    un-gameable "which slices are delivered" resolver, already imported one
    hop away in ``commit_slice.py``) other than the entering slice itself is
    resolved:

    1. FIRST, its own STORED declaration (#59, fix-commit-slice-reverify-
       uses-stored-file): ``_declared_regression_test_file`` reads the file
       the shipped slice itself declared via ``--regression-test-file`` at
       its OWN commit time. If present AND still a real file on this tree,
       it wins -- no naming-convention guessing needed.
    2. Else, the naming-convention glob (``_regression_file_glob_candidates``,
       UNCHANGED) -- the pre-#59 behaviour, still the only signal available
       for a historical record that predates this field.

    Only when BOTH miss is the slice ``unresolved`` (GDP-6: never a silent
    guess -- a genuinely missing file, whether the stored path was deleted or
    no convention match exists, degrades LOUD).

    Returns ``(resolved, unresolved_slice_ids)``: ``resolved`` is an ordered
    list of ``(slice_id, repo_relative_path)`` pairs -- shipped slices first,
    then the entering slice; ``unresolved_slice_ids`` names every SHIPPED
    slice whose file could not be resolved (no stored value, and zero or
    ambiguous convention matches) -- a conservative-keep signal (never a
    silent skip) the caller degrades LOUD INDETERMINATE on, mirroring
    ``_narrow_to_shipped_entering``'s "never silently narrow" discipline.
    """
    shipped = sorted(
        slice_id
        for slice_id in _slice_commit_verified_slices(repo, feature_id)
        if slice_id != entering_slice
    )
    resolved: list[tuple[str, str]] = []
    unresolved: list[str] = []
    for slice_id in shipped:
        declared = _declared_regression_test_file(repo, feature_id, slice_id)
        if declared is not None and (repo / declared).is_file():
            resolved.append((slice_id, declared))
            continue
        candidates = _regression_file_glob_candidates(repo, feature_id, slice_id)
        if len(candidates) != 1:
            unresolved.append(slice_id)
            continue
        resolved.append((slice_id, str(candidates[0].relative_to(repo))))
    resolved.append((entering_slice, entering_regression_test_file))
    return resolved, unresolved


def _run_regression_gate_shipped_and_entering(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    entering_regression_test_file: str,
) -> tuple[int, str | None, str | None, str, str, list[str]]:
    """Run E2 behaviorally over {shipped} UNION {entering} (RC2 Fix A).

    Composes ``_shipped_and_entering_regression_files`` (the ledger-backed
    shipped-set resolver) with ``_run_regression_gate`` (REUSE, unchanged) in
    an AND-closed loop -- ALL resolved files must pass, mirroring
    ``build_tier_exit_verdict``'s "the whole shipped set is retained"
    preservation clause.

    Returns ``(exit_code, reason, diagnostic, failed_slice_id,
    failed_regression_test_file, executed_regression_test_files)``.
    ``failed_slice_id`` / ``failed_regression_test_file`` name the file that
    actually produced the non-zero/INDETERMINATE outcome -- which may be a
    SHIPPED slice, not the entering one (the honest attribution RC2's fix
    introduces: today's E2 leg never re-checks a shipped slice at all, so it
    FALSE-GREENs). On a fully clean run, or when the shipped set itself is
    unresolvable, the entering slice's own values are returned.

    ``executed_regression_test_files`` is the ordered list of repo-relative
    regression-file paths this call ACTUALLY ran (the examiner's finding --
    "I cannot tell whether the gate really ran my slice's tests" -- a
    successful verdict must exhibit its own executed scope, not merely name
    slice ids). It is truncated at the first failing/INDETERMINATE file (the
    files after it were never reached) and empty when the shipped set itself
    was unresolvable (nothing was run).

    A SHIPPED slice with NO resolvable regression file degrades LOUD
    INDETERMINATE (``reason="shipped_regression_file_unresolvable"``) --
    conservative-keep, never a silent skip of a shipped slice's regression
    protection.
    """
    resolved, unresolved = _shipped_and_entering_regression_files(
        repo, feature_id, entering_slice, entering_regression_test_file
    )
    if unresolved:
        return (
            _GATE_INDETERMINATE_EXIT_CODE,
            "shipped_regression_file_unresolvable",
            (
                "the SHIPPED slice(s) "
                + ", ".join(unresolved)
                + " have no resolvable regression file on this tree (zero or "
                "ambiguous convention matches) -- recorded an honest "
                "SliceCommitIndeterminate (unverified here), never a silent "
                "skip of a shipped slice's regression protection"
            ),
            entering_slice,
            entering_regression_test_file,
            [],
        )
    executed: list[str] = []
    for checked_slice_id, checked_file in resolved:
        executed.append(checked_file)
        contract_code, indeterminate_reason, indeterminate_diagnostic = (
            _run_regression_gate(repo, feature_id, checked_file)
        )
        if contract_code != 0:
            return (
                contract_code,
                indeterminate_reason,
                indeterminate_diagnostic,
                checked_slice_id,
                checked_file,
                executed,
            )
    return 0, None, None, entering_slice, entering_regression_test_file, executed


def _infer_pytest_regression_at_kind(
    repo: Path, feature_id: str, slice_ids: list[str]
) -> tuple[str | None, dict[str, object] | None]:
    """Infer ``at_kind = pytest-regression`` from feature-layout (RC1 Fix B).

    Fires ONLY when the caller supplied neither ``--at-kind`` nor
    ``--regression-test-file`` (checked by the caller BEFORE invoking this).
    Reuses ``_feature_tag_files`` (REUSE, already imported for E1) as the
    ``.feature``-file resolver: when the feature owns at least one
    ``.feature`` file, gherkin stays the explicit default, byte-identical for
    every existing caller -- this function only ever routes TOWARD
    pytest-regression, never away from a genuine gherkin feature.

    Returns ``(regression_test_file, refusal_payload)``:

    - ``(None, None)`` -- ``.feature`` files exist (or ``slice_ids`` is
      empty); stay on the gherkin default unchanged.
    - ``(<repo-relative-path>, None)`` -- zero ``.feature`` files AND exactly
      one convention-matching regression file resolved for the entering
      (last-listed) slice; the caller flips to ``at_kind =
      pytest-regression`` with this file.
    - ``(None, <payload>)`` -- zero ``.feature`` files AND the entering
      slice's regression file could not be resolved unambiguously (GDP-6,
      never silently guessed): ``payload`` carries an ``exit_code`` key (pop
      it before emitting) plus a self-explaining ``error``/``how`` naming the
      mismatch -- never a bare, reason-less refusal.
    """
    if not slice_ids:
        return None, None
    if _feature_tag_files(repo, feature_id):
        return None, None
    entering_slice = slice_ids[-1]
    candidates = _regression_file_glob_candidates(repo, feature_id, entering_slice)
    if len(candidates) == 1:
        return str(candidates[0].relative_to(repo)), None
    if len(candidates) > 1:
        matches = ", ".join(str(c.relative_to(repo)) for c in candidates)
        return None, {
            "exit_code": 1,
            "event": "SliceCommitRefused",
            "refused_half": "E2",
            "slice_ids": slice_ids,
            "error": (
                "no --at-kind was given and this feature owns zero .feature "
                f"files -- multiple regression files match the "
                f"{entering_slice} pytest-regression naming convention, an "
                f"ambiguous inference is never silently resolved: {matches}"
            ),
            "how": (
                "pass --at-kind pytest-regression --regression-test-file "
                "<repo-relative-path> explicitly to disambiguate"
            ),
        }
    # Zero candidates: no POSITIVE signal this is a pytest-regression feature
    # at all (it may simply be a feature that doesn't exist on this tree, or
    # predates the naming convention) -- conservative-keep means staying on
    # the gherkin default rather than force-routing away from it, so the
    # existing gherkin path still reaches ITS OWN real verdict (pinned by
    # ``test_verify_slice_commit_requires_feature_id.py::
    # test_present_feature_id_is_never_downgraded_to_indeterminate``: a
    # nonexistent feature must resolve via E2's contract gate to
    # ``SliceCommitRefused``, never be diverted into an inference-only
    # INDETERMINATE). This only ever routes TOWARD pytest-regression on
    # POSITIVE evidence (>=1 convention match); zero evidence changes
    # nothing.
    return None, None


def _append_slice_commit_verified(
    repo: Path,
    feature_id: str,
    slice_ids: list[str],
    *,
    attested_via: str | None = None,
    entering_slice_id: str | None = None,
    entering_regression_test_file: str | None = None,
    commit_sha: str | None = None,
) -> None:
    """Record one `SliceCommitVerified` event per verified slice (DDD-3).

    The single filesystem mutation of this CLI -- performed only after E1 and
    E2 have both cleared. Each record is written through
    ``AtCompletionLedger.append_gate_event`` (REUSE-unchanged, DDD-3 Reuse
    Analysis), so it lands on the carpaccio chain's read substrate
    (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``) carrying the M7
    integrity fields (gap-free ``seq`` + ``record_hash``) the slice-03
    predecessor check and the M-2 backstop fail-closed on.

    Idempotency (C4a): ``AtCompletionLedger.verified_slices()`` is set-valued,
    so a re-run on an already-verified commit appends a further record yet the
    carpaccio chain still sees the slice exactly once -- the predecessor
    ordering it depends on is uncorrupted.

    ``attested_via`` (#51): when supplied (the ``--slice-id`` override path),
    threaded through to the ledger record as a transparent field so the audit
    shows the trailer was bypassed. Absent/None on the normal trailer path --
    that record stays byte-unchanged.

    ``entering_slice_id`` / ``entering_regression_test_file`` (#59,
    fix-commit-slice-reverify-uses-stored-file): when the entering commit
    declared a pytest-regression file, ``entering_regression_test_file`` is
    threaded into the ``SliceCommitVerified`` record for ``entering_slice_id``
    ONLY -- every other slice_id in ``slice_ids`` (a batched multi-Slice-Id
    commit) is written exactly as before, with no ``regression_test_file``
    field. This is the STORED value a later slice's commit re-check reads
    (``_declared_regression_test_file``) instead of re-guessing a naming-
    convention glob against a possibly non-convention-named file.

    ``commit_sha`` (fix-slice-seal-carries-commit-sha): the real git sha of
    the sealed commit this batch of ``SliceCommitVerified`` records attests,
    threaded through to every ``slice_id`` in ``slice_ids`` -- so a later
    check can join a seal to the commit it attests. Absent/None leaves the
    record byte-unchanged (additive/optional field).
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for slice_id in slice_ids:
        regression_test_file = (
            entering_regression_test_file if slice_id == entering_slice_id else None
        )
        ledger.append_gate_event(
            "SliceCommitVerified",
            slice_id,
            attested_via=attested_via,
            regression_test_file=regression_test_file,
            commit_sha=commit_sha,
        )


def _append_examine_deferred_to_feature_end(
    repo: Path, feature_id: str, slice_ids: frozenset[str]
) -> None:
    """Record one `ExamineDeferredToFeatureEnd` event per `@coupled` slice
    whose examine was DEFERRED (RCA fix-coupled-slice-examine-deferred-to-
    feature-end, constraints c + e).

    Written at the SAME single chokepoint as `_append_slice_commit_verified`
    (`_run_verify_then_record`, the ONE place this function is called) --
    never inside `check_examine_verdict` itself and never at any of that
    function's 2-3 call sites per commit invocation, so the attestation is
    never duplicated. Deliberately visible, never a silent bypass: an auditor
    scanning `.nwave/**/*.jsonl` can tell "deferred on purpose" apart from
    "nobody checked".
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for slice_id in slice_ids:
        ledger.append_gate_event("ExamineDeferredToFeatureEnd", slice_id)


def _append_slice_commit_indeterminate(
    repo: Path,
    feature_id: str,
    slice_ids: list[str],
    reason: str = "contract_gate_interpreter_unavailable",
) -> None:
    """Record one honest `SliceCommitIndeterminate` event per slice (DDD-2 / DDD-6).

    The non-Python-target degrade record: the E2 contract gate could not resolve
    a usable interpreter on this machine and degraded LOUD INDETERMINATE, so the
    ledger states "unverified on this machine" truthfully -- NEVER a fabricated
    `SliceCommitVerified` (no-silent-pass) and never a bare refusal that wedges
    the slice chain. Written through the SSOT mint
    ``AtCompletionLedger.append_slice_commit_indeterminate`` (DDD-6 reuse -- the
    SAME writer ``des commit-slice``'s committed-scope-digest degrade routes
    through), so the record carries the free-text ``reason`` plus the honesty
    fields (`gate_scope == "INDETERMINATE"`, `at_verified == False`) and lands on
    the carpaccio chain's read substrate. The in-order guard's
    predecessor-satisfied predicate (which accepts an INDETERMINATE predecessor)
    then lets the successor slice dispatch.
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for slice_id in slice_ids:
        ledger.append_slice_commit_indeterminate(slice_id, reason)


def _find_loose_slice_trailer_value(commit_message: str) -> str | None:
    """Return the value of a loose `Slice-Id:`/`Step-Id:` trailer line, if any.

    Unlike ``extract_slice_ids`` (which requires the value to already be in
    strict `slice-NN` form), this finds ANY line that starts with the
    trailer key -- git's own trailer parser is exactly this lenient. Used to
    distinguish "a trailer line IS present but its value is malformed" from
    "no trailer line at all", so the two meanings never collapse into the
    same misleading error (GDP-3, RCA in
    ``tests/bugs/des/test_verify_slice_commit_trailer_value_message.py``).
    """
    for line in commit_message.splitlines():
        stripped = line.strip()
        for key in ("Slice-Id:", "Step-Id:"):
            if stripped.startswith(key):
                return stripped[len(key) :].strip()
    return None


def _resolve_slice_ids(
    repo: Path, commit: str, slice_id_override: str | None = None
) -> tuple[list[str], str, int | None, bool]:
    """Read a commit's `Slice-Id:` trailer(s) + its SHA.

    Returns ``(slice_ids, commit_sha, error_code, used_override)``.
    ``error_code`` is None on success, or the exit code (2) when the commit is
    unreadable / has no trailer and no override / the override conflicts with
    a real trailer -- in which case the malformed/refusal verdict has already
    been emitted. ``used_override`` is True iff the commit carried NO
    resolvable trailer AND ``slice_id_override`` supplied the slice id instead
    (#51, the ``--slice-id`` legacy-commit-attestation path) -- False on every
    other outcome, including a matching (idempotent) override.
    """
    try:
        commit_message = _git(repo, "log", "-1", "--format=%B", commit)
        commit_sha = _git(repo, "rev-parse", commit).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": f"cannot read commit {commit!r}: {exc}",
            }
        )
        return [], "", 2, False

    slice_ids = extract_slice_ids(commit_message)
    if not slice_ids:
        if slice_id_override is not None:
            return [slice_id_override], commit_sha, None, True
        loose_value = _find_loose_slice_trailer_value(commit_message)
        if loose_value is not None:
            _emit_with_human_surface(
                {
                    "event": "MalformedInput",
                    "error": (
                        "commit carries a Slice-Id:/Step-Id: trailer, but "
                        f"its value {loose_value!r} is not a slice-NN "
                        "identity (expected e.g. slice-01)"
                    ),
                }
            )
            return [], "", 2, False
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": "commit carries no Slice-Id:/Step-Id: trailer",
            }
        )
        return [], "", 2, False

    if slice_id_override is not None and slice_id_override not in slice_ids:
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "commit": commit,
                "error": (
                    f"--slice-id {slice_id_override!r} conflicts with the "
                    f"commit's real Slice-Id: trailer(s) {slice_ids!r} -- an "
                    "override must never silently contradict a real trailer"
                ),
                "how": (
                    "drop --slice-id (the commit already carries a real "
                    "Slice-Id: trailer) or correct the mismatched slice id"
                ),
            }
        )
        return [], "", 2, False

    return slice_ids, commit_sha, None, False


def _missing_by_slice(
    repo: Path,
    commit: str,
    slice_ids: list[str],
    feature_id: str | None,
    *,
    at_kind: str | None = None,
    regression_test_file: str | None = None,
) -> tuple[dict[str, list[str]], dict[str, bool], int | None]:
    """Run E1 completeness for every listed slice.

    Returns ``(deficient, verifiable, error_code)``: ``deficient`` maps each
    slice with missing `.feature` files to that list; ``verifiable`` maps
    each slice to whether >=1 AT candidate was found for it at all (Bug #126
    / F-CARPACCIO-E1-VACUOUS-BLOCKS-PREDECESSOR-DISCRIMINATION -- "verified
    everything" and "verified nothing" must not collapse into the same
    empty ``deficient`` dict); ``error_code`` is 2 (and the malformed
    verdict already emitted) when the repository is unreadable.

    ``at_kind``/``regression_test_file`` (fix-e1-explicit-regression-test-file)
    are forwarded to ``missing_at_files`` as the FOURTH evidence source ONLY
    when exactly one slice is listed -- an unambiguous "this declaration is
    for THIS slice" reading. A multi-slice commit does not get the override
    (conservative-keep, same ambiguity discipline as the path-naming-
    convention fix): granting it to every listed slice from one declared
    file would be a false pass, not a fix.
    """
    single_slice = len(slice_ids) == 1
    try:
        outcomes = {
            slice_id: missing_at_files(
                repo,
                commit,
                slice_id,
                feature_id,
                at_kind=at_kind if single_slice else None,
                regression_test_file=(regression_test_file if single_slice else None),
            )
            for slice_id in slice_ids
        }
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": f"cannot inspect repository: {exc}",
            }
        )
        return {}, {}, 2
    deficient = {sid: o.missing for sid, o in outcomes.items() if o.missing}
    verifiable = {sid: o.verifiable for sid, o in outcomes.items()}
    return deficient, verifiable, None


def _effective_scope(
    repo: Path, slice_ids: list[str], scope_feature_id: str | None
) -> str | None:
    """Resolve the feature scope E1 narrows its `.feature` scan to (Seam A).

    Returns ``scope_feature_id`` when that feature actually owns at least one
    `@feature-{id}`-tagged `.feature` file for one of the listed slices, so the
    scoped scan ignores a co-resident feature sharing the slice number (the
    slice-03 cross-feature isolation property). Returns ``None`` -- the legacy
    whole-tree scan -- when ``scope_feature_id`` is absent OR resolves to ZERO
    candidate files: a feature that tags no `.feature` under its id must NOT
    have its completeness check silently degrade to a vacuous always-pass.
    Falling back to the whole-tree scan keeps the genuine-incompleteness guard
    intact for callers whose `.feature` files predate the `@feature-{id}`
    convention (anti-vacuity: scoping narrows, it never blinds the check).
    """
    if scope_feature_id is None:
        return None
    has_scoped_candidate = any(
        feature_files_for_slice(repo, slice_id, scope_feature_id)
        for slice_id in slice_ids
    )
    return scope_feature_id if has_scoped_candidate else None


def _run_legacy_completeness(repo: Path, args: argparse.Namespace) -> int:
    """The legacy E1-only completeness check (no `--feature-id`).

    Classic-mode callers -- `reverify_slice_commit`, the U2 hook -- invoke the
    CLI without `--feature-id` and expect the original `SliceCommitComplete` /
    `SliceCommitIncomplete` verdict shape and the pure-read git contract.

    slice-03 (Seam A): when `--scope-feature-id` is supplied the E1 `.feature`
    candidate scan is scoped to that feature's `@feature-{id}`-tagged files, so
    a co-resident feature sharing the slice number on the tree is not
    cross-bound into this commit's completeness check. The verdict shape stays
    the legacy E1-only `SliceCommitComplete` / `SliceCommitIncomplete` and NO
    ledger record is written -- the verify-then-record seam (`--feature-id`) is
    not entered.

    Bug #126 (false-green, verify-slice-commit-requires-feature-id):
    ``missing_at_files`` vacuously reports "nothing missing" when it found
    ZERO `.feature` AT candidates for the listed slice(s) anywhere on the
    scanned tree -- "I verified everything" and "I had nothing to verify"
    must not collapse into the same `SliceCommitComplete` PASS. When no
    candidate exists, this emits an honest `SliceCommitIndeterminate` (exit
    `_GATE_INDETERMINATE_EXIT_CODE`) instead -- unverified, not verified.
    """
    slice_ids, _commit_sha, error_code, _used_override = _resolve_slice_ids(
        repo, args.commit
    )
    if error_code is not None:
        return error_code

    scope = _effective_scope(repo, slice_ids, args.scope_feature_id)
    deficient, verifiable, error_code = _missing_by_slice(
        repo, args.commit, slice_ids, scope
    )
    if error_code is not None:
        return error_code

    if deficient:
        _emit_with_human_surface(
            {
                "event": "SliceCommitIncomplete",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "missing_feature_files_by_slice": deficient,
                "error": "; ".join(
                    f"slice {slice_id} commit is missing "
                    f"{len(missing)} .feature AT file(s): " + ", ".join(missing)
                    for slice_id, missing in deficient.items()
                ),
            }
        )
        return 1

    if not any(verifiable.values()):
        _emit_with_human_surface(
            {
                "event": "SliceCommitIndeterminate",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "error": (
                    "no --feature-id was given and no .feature AT file "
                    "candidate matched any listed slice anywhere on the "
                    "scanned tree -- nothing was verified, so this is not "
                    "a pass"
                ),
                "how": (
                    "pass --feature-id <feature-id> (or --scope-feature-id "
                    "<feature-id> naming a feature that owns @slice-NN "
                    ".feature files) to scope the completeness check to a "
                    "resolvable feature"
                ),
            }
        )
        return _GATE_INDETERMINATE_EXIT_CODE

    _emit_with_human_surface(
        {
            "event": "SliceCommitComplete",
            "slice_ids": slice_ids,
            "commit": args.commit,
        }
    )
    return 0


@dataclass(frozen=True)
class _VerifiedSliceContext:
    """The data the CLI-facing atomic needs to record + emit a verified outcome.

    Returned by `_run_verify_checks` ONLY when E1+E2(+E3) have fully cleared
    for every listed slice -- the exact moment the pre-Prefactoring
    `_run_verify_then_record` used to append the ledger record and emit
    `SliceCommitVerified` inline. Extracting this as a small explicit value
    (Prefactoring, fix-commit-slice-verify-before-commit slice-00) is what
    lets a future pre-flight caller invoke `_run_verify_checks` against a
    shadow commit WITHOUT ALSO triggering the `SliceCommitVerified` ledger
    write -- that write stays exclusively in `_run_verify_then_record`, the
    unchanged post-commit CLI path.
    """

    feature_id: str
    slice_ids: list[str]
    commit_sha: str
    attested_via: str | None
    regression_test_files_executed: list[str]
    deferred_examine_slices: frozenset[str] = frozenset()
    entering_slice_id: str | None = None
    entering_regression_test_file: str | None = None


def _run_verify_checks(
    repo: Path, args: argparse.Namespace
) -> tuple[int, _VerifiedSliceContext | None]:
    """The pure verify half (Prefactoring): E1 + E2 + E3, no ledger write.

    Same E1 completeness + E2 contract-gate/regression logic + E3
    examine-verdict logic `_run_verify_then_record` ran before this split --
    byte-identical refusal/indeterminate payload shapes, byte-identical exit
    codes, byte-identical `SliceCommitIndeterminate` ledger-write timing
    (unchanged: that write happens on THIS half, exactly as before -- it is
    not the conflated write this split targets). The ONE thing this function
    never does is append a `SliceCommitVerified` record or emit its payload:
    on a full clear it returns ``(0, _VerifiedSliceContext(...))`` instead,
    handing the caller everything it needs to do that write itself. Every
    other exit point returns ``(exit_code, None)`` after already emitting its
    own verdict (unchanged behaviour) -- ``None`` signals "already handled,
    nothing left to record".

    Reusable pre-flight seam: a future caller (`des commit-slice`'s
    shadow-commit pre-flight, ADR-DES-001, slice-01) can call this function
    directly against an unreachable `git commit-tree` object without risking
    a duplicate `SliceCommitVerified` write -- the write only ever happens in
    `_run_verify_then_record`, which this function does not call.
    """
    feature_id = args.feature_id
    slice_id_override = getattr(args, "slice_id", None)

    # Honesty guard #1 (#51, GDP-6, fail-closed): --slice-id overrides a
    # trailer only on the strength of a behavioral proof -- a bare structural
    # attestation cannot be trusted without a trailer. Checked BEFORE any
    # repo access so the refusal is deterministic and self-explaining.
    if slice_id_override is not None and (
        args.at_kind != "pytest-regression" or not args.regression_test_file
    ):
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "commit": args.commit,
                "error": (
                    "--slice-id requires --at-kind pytest-regression and "
                    "--regression-test-file -- behavioral proof is "
                    "mandatory when overriding a missing Slice-Id: trailer"
                ),
                "how": (
                    "pass --at-kind pytest-regression --regression-test-file "
                    "<repo-relative-path> alongside --slice-id"
                ),
            }
        )
        return 2, None

    slice_ids, commit_sha, error_code, used_override = _resolve_slice_ids(
        repo, args.commit, slice_id_override
    )
    if error_code is not None:
        return error_code, None

    # E1 -- completeness. A deficient slice refuses before E2 is reached.
    deficient, verifiable, error_code = _missing_by_slice(
        repo,
        args.commit,
        slice_ids,
        feature_id,
        at_kind=args.at_kind,
        regression_test_file=args.regression_test_file,
    )
    if error_code is not None:
        return error_code, None
    if deficient:
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "refused_half": "E1",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "missing_feature_files_by_slice": deficient,
                "error": "; ".join(
                    f"slice {slice_id} commit is missing "
                    f"{len(missing)} .feature AT file(s): " + ", ".join(missing)
                    for slice_id, missing in deficient.items()
                ),
                "how": (
                    "stage and land the missing .feature AT file(s) into the "
                    "slice commit via `des commit-slice`"
                ),
            }
        )
        return 1, None

    # RCA fix-carpaccio-e1-vacuous-taxonomy-gap: a slice with ZERO recognized
    # AT candidates anywhere (not "verified complete", "nothing to verify")
    # must never fall through to E2 as if genuinely cleared -- UNLESS it is
    # explicitly declared @prefactoring-exempt in the Slice Plan (the
    # legitimate zero-AT lane, RCA "Legitimate-Zero-AT Non-Regression Note").
    # This carve-out is MANDATORY: omitting it regresses that lane into a
    # false refusal.
    non_verifiable = [
        sid
        for sid in slice_ids
        if not verifiable.get(sid, False)
        and not _is_at_exempt_lane(repo, feature_id, sid)
        and not _examine_verdict_clears_slice(repo, feature_id, sid)
    ]
    if non_verifiable:
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "refused_half": "E1",
                "slice_ids": non_verifiable,
                "commit": args.commit,
                "error": (
                    f"feature {feature_id!r} owns no recognized AT "
                    f"candidates for slice(s) {non_verifiable!r} -- "
                    "nothing was verified, this is not a pass"
                ),
                "how": (
                    "author a recognized AT for the listed slice(s), or if "
                    "genuinely zero-AT by design mark the slice "
                    "@prefactoring in the feature-delta Slice Plan "
                    "(AtRequirement.EXEMPT) or route it through `des "
                    "record-prose-delivered`, or clear it via an armed "
                    "examine-verdict PASS (`des record-examine-verdict`)"
                ),
            }
        )
        return 1, None

    # E2 -- one run per listed slice. Default (`gherkin`): the feature-scoped
    # contract gate, unchanged. `--at-kind pytest-regression` (#13): a
    # BEHAVIORAL attestation -- actually runs the {shipped} UNION {entering}
    # regression-file set on the committed tree in place of the contract
    # gate, which cannot resolve a pytest-regression bugfix's structure.
    #
    # RC1 Fix B: when the caller supplied NEITHER --at-kind NOR
    # --regression-test-file, infer pytest-regression from feature-layout
    # introspection (zero .feature files) instead of unconditionally routing
    # into the gherkin scope resolver, which would refuse `zero-collected`
    # for a reason unrelated to the operator's code.
    # native-regression (fix-rust-regression-at-kind-wiring): the SAME
    # behavioral-attestation dispatch as pytest-regression, for a non-Python
    # regression file. Never inferred (unlike pytest-regression's RC1 Fix B
    # below) -- native-regression is always an explicit operator declaration,
    # so an operator who declares it without --regression-test-file gets the
    # clean "requires --regression-test-file" refusal further down, never a
    # guessed Python file.
    is_pytest_regression = args.at_kind == "pytest-regression"
    is_native_regression = args.at_kind == "native-regression"
    is_regression_attestation = is_pytest_regression or is_native_regression
    regression_test_file = args.regression_test_file
    if not is_regression_attestation and regression_test_file is None:
        inferred_file, refusal_payload = _infer_pytest_regression_at_kind(
            repo, feature_id, slice_ids
        )
        if refusal_payload is not None:
            inferred_exit_code = refusal_payload.pop("exit_code")
            refusal_payload["commit"] = args.commit
            _emit_with_human_surface(refusal_payload)
            assert isinstance(inferred_exit_code, int)
            return inferred_exit_code, None
        if inferred_file is not None:
            is_pytest_regression = True
            is_regression_attestation = True
            regression_test_file = inferred_file

    pytest_regression_checked = False
    regression_test_files_executed: list[str] = []
    entering_regression_slice_id: str | None = None
    examine_cleared_slices: set[str] = set()
    for slice_id in slice_ids:
        if _is_at_exempt_lane(repo, feature_id, slice_id):
            # Mirrors the entry gate's `LaneAtExemptionAccepted` early-return
            # (carpaccio_format.py:627-633): a 0-AT `@prefactoring` slice has
            # no `@slice-NN` scenarios to intersect, so `run_contract_gate`'s
            # M-8 non-vacuity floor would refuse it `empty-intersection`. The
            # SAME lane exemption the entry gate honors is honored here --
            # short-circuit E2 to an honest clear instead of spawning the
            # vacuous feature-scoped contract-gate subprocess.
            continue
        if is_regression_attestation:
            if not regression_test_file:
                _emit_with_human_surface(
                    {
                        "event": "SliceCommitRefused",
                        "refused_half": "E2",
                        "slice_ids": slice_ids,
                        "commit": args.commit,
                        "failed_slice": slice_id,
                        "error": (
                            f"--at-kind {args.at_kind} requires --regression-test-file"
                        ),
                        "how": (
                            "pass --regression-test-file <repo-relative-path> "
                            f"alongside --at-kind {args.at_kind}"
                        ),
                    }
                )
                return 1, None
            if pytest_regression_checked:
                # RC2 Fix A already ran the {shipped} UNION {entering} set
                # once for this commit -- a second listed slice (a batched
                # multi-Slice-Id commit) shares the SAME feature-wide
                # attestation, never re-run per listed slice.
                continue
            pytest_regression_checked = True
            entering_regression_slice_id = slice_id
            (
                contract_code,
                indeterminate_reason,
                indeterminate_diagnostic,
                regression_failed_slice,
                regression_failed_file,
                regression_test_files_executed,
            ) = _run_regression_gate_shipped_and_entering(
                repo, feature_id, slice_id, regression_test_file
            )
        else:
            contract_result = _run_contract_gate(repo, feature_id, slice_id)
            # Compatibility normalization: several pre-existing regression
            # ATs monkeypatch `_run_contract_gate` with a bare-int stub
            # (`lambda *a, **k: 0`) to skip the real subprocess spawn. The
            # genuine implementation returns `(exit_code, child_payload)`;
            # normalizing here keeps both call shapes working without
            # touching those tests (single-locus constraint).
            if isinstance(contract_result, tuple):
                contract_code, contract_child_payload = contract_result
            else:
                contract_code, contract_child_payload = contract_result, None
            indeterminate_reason = None
            indeterminate_diagnostic = None
            regression_failed_slice = slice_id
            regression_failed_file = regression_test_file
        # DDD-2 degrade-LOUD: an INDETERMINATE gate (no usable interpreter on
        # this machine, or -- pytest-regression -- a regression-test-file that
        # could not be run) is NOT a refusal -- record the honest
        # SliceCommitIndeterminate (never a fabricated SliceCommitVerified) and
        # let the slice chain progress, distinct from both the verified mint and
        # a genuine refusal. A runnable-but-failing gate returns its own
        # non-zero code and refuses.
        if contract_code == _GATE_INDETERMINATE_EXIT_CODE:
            if is_regression_attestation:
                return (
                    _record_indeterminate_outcome(
                        repo,
                        args,
                        feature_id,
                        slice_ids,
                        reason=(
                            indeterminate_reason or "pytest_regression_file_unrunnable"
                        ),
                        diagnostic=indeterminate_diagnostic
                        or (
                            f"the declared --regression-test-file "
                            f"{regression_failed_file!r} could not be run on "
                            "the committed tree (missing or uncollectible) -- "
                            "recorded an honest SliceCommitIndeterminate "
                            "(unverified here), never a fabricated pass"
                        ),
                    ),
                    None,
                )
            return (
                _record_indeterminate_outcome(repo, args, feature_id, slice_ids),
                None,
            )
        if contract_code != 0:
            if is_regression_attestation:
                _emit_with_human_surface(
                    {
                        "event": "SliceCommitRefused",
                        "refused_half": "E2",
                        "slice_ids": slice_ids,
                        "commit": args.commit,
                        "failed_slice": regression_failed_slice,
                        "regression_test_file": regression_failed_file,
                        "contract_gate_exit_code": contract_code,
                        "error": (
                            f"slice {regression_failed_slice} failed the E2 "
                            f"behavioral attestation -- {regression_failed_file} "
                            f"did not pass on the committed tree (exit "
                            f"{contract_code})"
                        ),
                        "how": (
                            f"run `pytest {regression_failed_file} -q` "
                            "locally, fix the regression, then re-commit via "
                            "`des commit-slice`"
                        ),
                    }
                )
                return 1, None
            # ADR-DES-001 addendum Rule 1 -- E2-vacuous evidence-aggregation
            # carve-out. A genuinely empty feature scope ("zero-collected" /
            # "empty-intersection" -- nothing to run, NEVER a real failure
            # like "collection-failed"/"arch-invariant-failed"/
            # "arch-scope-zero-collected", which are never carved out) is the
            # correct, expected state for a prose/documentation slice that
            # owns no executable AT by nature. Consult the EXISTING
            # check_examine_verdict reader for THIS slice before refusing: an
            # ARMED gate (a charter exists for this feature) with a fresh,
            # matching-seal PASS clears E2 via the examine evidence instead.
            # Any other outcome -- unarmed (no charter at all, the
            # "zero-evidence lie" case), no verdict recorded, a stale seal,
            # FAIL, INDETERMINATE -- leaves the refusal below UNCHANGED.
            reason = (
                contract_child_payload.get("reason") if contract_child_payload else None
            )
            if reason in ("zero-collected", "empty-intersection"):
                from des.cli.commit_slice import (
                    _examine_gate_armed,
                    check_examine_verdict,
                )

                if (
                    _examine_gate_armed(repo, feature_id)
                    and check_examine_verdict(repo, feature_id, slice_id) is None
                ):
                    examine_cleared_slices.add(slice_id)
                    continue
            # The child gate already emitted a self-explaining verdict (e.g.
            # a `FeatureScopeMalformed` naming its own `reason`/`error`/
            # `next`) -- thread THAT through rather than overwriting it with
            # a generic, reason-less summary. A refusal that names an
            # unrelated cause (or none at all) sends the operator hunting a
            # phantom in innocent code; the child is the authority on why it
            # refused, this CLI only carries the verdict.
            child_error = (
                contract_child_payload.get("error") if contract_child_payload else None
            )
            child_how = (
                contract_child_payload.get("next") if contract_child_payload else None
            )
            # DDD-CERT-6 (C9): thread the child's `kind` build-vs-test-failure
            # discriminator through unchanged -- a crafter reading the E2
            # SliceCommitRefused verdict alone must see the SAME distinction
            # C8 names at the raw run_contract_gate level. Additive: a child
            # payload carrying no `kind` (e.g. the zero-collected/
            # empty-intersection carve-out reasons) leaves the key absent from
            # this payload too, never a fabricated `None`.
            child_kind = (
                contract_child_payload.get("kind") if contract_child_payload else None
            )
            refused_payload: dict[str, object] = {
                "event": "SliceCommitRefused",
                "refused_half": "E2",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "failed_slice": slice_id,
                "contract_gate_exit_code": contract_code,
                "error": (
                    child_error
                    if isinstance(child_error, str) and child_error
                    else (
                        f"slice {slice_id} failed the feature-scoped "
                        f"contract gate (exit {contract_code})"
                    )
                ),
                "how": (
                    child_how
                    if isinstance(child_how, str) and child_how
                    else (
                        f"inspect the failure with `run_contract_gate "
                        f"--repo .` (feature {feature_id}, slice "
                        f"{slice_id}), green the failing feature-scoped "
                        "acceptance test(s), then re-commit via "
                        "`des commit-slice`"
                    )
                ),
            }
            if isinstance(child_kind, str) and child_kind:
                refused_payload["kind"] = child_kind
            _emit_with_human_surface(refused_payload)
            return 1, None

    # E3 -- the examine-verdict DoD gate (evolution-plan P1.2, hard-wired into
    # the verify-then-record path too, not only `des commit-slice`). EXAMINE is
    # the true Definition of DONE: green tests verify the CODE, EXAMINE (Vera)
    # verifies the running SYSTEM through the real surface and attaches the
    # observed artifact -- the two diverge (isolated-green != assembled-green).
    # `check_examine_verdict` is a NO-OP unless ARMED (a charter dir exists under
    # `docs/product/expectations/{feature_id}/`, or the opt-in env); when armed,
    # EVERY entering slice must carry a fresh PASS ExamineVerdict whose
    # charter_seal still matches the charter's CURRENT bytes, else the slice is
    # refused fail-closed and NO SliceCommitVerified is recorded. A
    # behavior-preserving prefactoring/refactoring slice carries no charter ->
    # unarmed -> green-to-green suffices (it goes through a separate path anyway).
    # This closes the bypass where a slice committed via `git commit` + `des
    # verify-slice-commit` skipped the examine gate that only `des commit-slice`
    # enforced (Ale 2026-07-05: "without evidence the slice is not implemented").
    from des.cli.commit_slice import check_examine_verdict

    deferred_examine_slices: set[str] = set()
    for slice_id in slice_ids:
        examine_rejection = check_examine_verdict(repo, feature_id, slice_id)
        if examine_rejection is None:
            continue
        if "exit_code" not in examine_rejection:
            # DEFER outcome (RCA fix-coupled-slice-examine-deferred-to-
            # feature-end): a `@coupled` slice with no per-slice record --
            # not a refusal. Collect it so `_run_verify_then_record`'s SOLE
            # write chokepoint (constraint e) can attest the deferral exactly
            # once; this pure half writes nothing itself.
            deferred_examine_slices.add(slice_id)
            continue
        exit_code = examine_rejection.pop("exit_code")
        examine_rejection["refused_half"] = "E3"
        examine_rejection.setdefault(
            "error",
            f"{examine_rejection.get('what', '')} -- "
            f"FIX: {examine_rejection.get('how', '')}",
        )
        _emit_with_human_surface(examine_rejection)
        assert isinstance(exit_code, int)
        return exit_code, None

    # E1, E2 and E3 all cleared. The CLI-facing atomic (`_run_verify_then_record`)
    # is the ONLY place that appends the SliceCommitVerified ledger record and
    # emits its payload -- this pure half hands back the data that record
    # needs instead (Prefactoring, fix-commit-slice-verify-before-commit
    # slice-00). (#51) the --slice-id override path carries the transparent
    # attested_via marker so the audit shows the trailer was bypassed; the
    # normal trailer path carries no such field (byte-unchanged). ADR-DES-001
    # addendum Rule 2: a slice cleared via Rule 1's examine-verdict carve-out
    # carries "examine-verdict" instead -- honest attribution, never a blanket
    # restatement of "nothing failed". Never applied to a normally-cleared
    # slice (Rule 2's negative half).
    if used_override:
        attested_via: str | None = "slice-id-override"
    elif examine_cleared_slices:
        attested_via = "examine-verdict"
    elif deferred_examine_slices:
        attested_via = "examine-deferred"
    else:
        attested_via = None
    return 0, _VerifiedSliceContext(
        feature_id=feature_id,
        slice_ids=slice_ids,
        commit_sha=commit_sha,
        attested_via=attested_via,
        regression_test_files_executed=regression_test_files_executed,
        deferred_examine_slices=frozenset(deferred_examine_slices),
        entering_slice_id=entering_regression_slice_id,
        entering_regression_test_file=(
            regression_test_file if entering_regression_slice_id is not None else None
        ),
    )


def _run_verify_then_record(repo: Path, args: argparse.Namespace) -> int:
    """The atomic verify-then-record exit gate (`--feature-id` given, DDD-3).

    Composes the pure verify half (`_run_verify_checks`, Prefactoring
    slice-00) with the ONE `SliceCommitVerified` ledger write: E1 then E2
    then E3 (unmodified logic, now living in `_run_verify_checks`), then
    appends exactly one `SliceCommitVerified` record IFF all three clear. On
    any non-zero half `_run_verify_checks` has ALREADY emitted the
    refusal/indeterminate verdict -- this function only returns that exit
    code unchanged and writes nothing further. Behaviour for this function's
    own caller (`main`) is byte-identical to before the split: same exit
    codes, same JSON payload shapes, same single ledger-write timing.
    """
    exit_code, verified_context = _run_verify_checks(repo, args)
    if verified_context is None:
        return exit_code

    _append_slice_commit_verified(
        repo,
        verified_context.feature_id,
        verified_context.slice_ids,
        attested_via=verified_context.attested_via,
        entering_slice_id=verified_context.entering_slice_id,
        entering_regression_test_file=verified_context.entering_regression_test_file,
        commit_sha=verified_context.commit_sha,
    )
    if verified_context.deferred_examine_slices:
        _append_examine_deferred_to_feature_end(
            repo,
            verified_context.feature_id,
            verified_context.deferred_examine_slices,
        )
    verified_payload: dict[str, object] = {
        "event": "SliceCommitVerified",
        "slice_ids": verified_context.slice_ids,
        "commit": args.commit,
        "commit_sha": verified_context.commit_sha,
    }
    if verified_context.attested_via is not None:
        verified_payload["attested_via"] = verified_context.attested_via
    if verified_context.regression_test_files_executed:
        # The examiner's finding (certification-legs-observe-real-execution):
        # a verdict that does not exhibit what it observed is indistinguishable
        # from a verdict issued over nothing observed. Exhibit the {shipped}
        # UNION {entering} regression file(s) this call actually ran, so the
        # consent testifies at least as much as the refusal already does.
        verified_payload["regression_test_files_executed"] = (
            verified_context.regression_test_files_executed
        )
    _emit_with_human_surface(verified_payload)
    return 0


_INDETERMINATE_NO_EXAMINE_RESCUE_HOW = (
    "this degrade has no examine-verdict escape -- the examine-verdict "
    "carve-out only fires on a genuinely empty AT scope "
    "(zero-collected/empty-intersection), not on an unavailable interpreter "
    "or runner. Fix the interpreter/runner resolution on this machine and "
    "re-run `des commit-slice`, OR, if this slice's AT scope is genuinely "
    "empty by design (a prose/@prefactoring slice), record a PASS "
    "examine-verdict first (`des record-examine-verdict`), then re-run "
    "`des commit-slice` -- it will re-run E2 and, on a genuinely empty "
    "scope, seal via attested_via: examine-verdict."
)


def _record_indeterminate_outcome(
    repo: Path,
    args: argparse.Namespace,
    feature_id: str,
    slice_ids: list[str],
    *,
    reason: str = "contract_gate_interpreter_unavailable",
    diagnostic: str = (
        "the feature-scoped contract gate could not resolve a usable "
        "interpreter on this machine -- recorded an honest "
        "SliceCommitIndeterminate (unverified here), never a fabricated pass"
    ),
    how: str = _INDETERMINATE_NO_EXAMINE_RESCUE_HOW,
) -> int:
    """Mint the honest INDETERMINATE outcome for the listed slices (DDD-2).

    The E2 gate degraded LOUD INDETERMINATE -- either the feature-scoped
    contract gate found no usable interpreter (the default `reason` /
    `diagnostic`), or (#13) a `--at-kind pytest-regression` slice declared a
    `--regression-test-file` that could not be run on the committed tree
    (missing / uncollectible -- the caller passes an accurate `reason` /
    `diagnostic` for that case). Either way the exit gate records one
    `SliceCommitIndeterminate` per slice -- never a fabricated
    `SliceCommitVerified` (no-silent-pass) and never a bare refusal that
    wedges the chain -- and emits the honest event so the operator sees the
    gate could not verify here. Returns the dedicated INDETERMINATE exit code
    (distinct from 0 verified, 1 refused, 2 malformed).

    `how` is TRUE per cause (RCA Q3): both callers of this function reach it
    only via the interpreter/runner-unavailable branch of `_run_verify_checks`
    (`contract_code == _GATE_INDETERMINATE_EXIT_CODE`, line 1354) -- a branch
    that RETURNS before the examine-verdict carve-out (a genuinely-empty AT
    scope, a different branch at line 1405-1432) is ever consulted. The
    default `how` therefore states honestly that THIS degrade has no direct
    examine-verdict rescue, while still naming the conditional rescue for a
    genuinely-empty AT scope -- never an unconditional (false) promise.
    """
    _append_slice_commit_indeterminate(repo, feature_id, slice_ids, reason)
    _emit_with_human_surface(
        {
            "event": "SliceCommitIndeterminate",
            "slice_ids": slice_ids,
            "commit": args.commit,
            "error": diagnostic,
            "how": how,
        }
    )
    return _GATE_INDETERMINATE_EXIT_CODE


def main(argv: list[str] | None = None) -> int:
    """Verify a slice commit -- and, under `--feature-id`, record it.

    With `--feature-id`: the atomic verify-then-record exit gate (DDD-3) --
    E1 then E2 then one ledger record IFF both clear. Without `--feature-id`:
    the legacy E1-only completeness check (classic-mode callers).
    """
    args = _build_parser().parse_args(argv)
    # rust-regression-at-kind-semi-wired: 'rust-regression' is a CLI-facing
    # ALIAS of 'native-regression', normalized here (before any downstream
    # `args.at_kind` read) so this entry point -- and `commit_slice.py`'s
    # preflight fold-in, which reuses this SAME `_build_parser` -- reuse the
    # SAME unified 'native-regression' AT-discovery path, never a second one.
    if args.at_kind == "rust-regression":
        args.at_kind = "native-regression"
    repo = Path(args.repo)

    # M9 / F3: a HEAD raced off the pinned SHA fails closed before any verdict.
    raced = _commit_head_raced(repo, args.expected_head)
    if raced is not None:
        _emit_with_human_surface(raced)
        return 1

    if args.feature_id:
        return _run_verify_then_record(repo, args)
    return _run_legacy_completeness(repo, args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
