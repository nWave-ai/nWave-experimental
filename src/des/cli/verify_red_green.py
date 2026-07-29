"""``des verify-red-green`` -- the P0.2 RED->GREEN non-vacuity seal.

Expectation (evolution-plan P0.2): an AT that passes WITHOUT the
implementation cannot count as coverage. The transition RED (observed,
fail-for-right-reason) -> GREEN (observed, same unchanged test content) is
mechanical proof the test actually witnesses the implementation. Kills the
always-pass/never-red class outright; weak-but-once-red assertions are the
negative-AT mandate's job (P0.3), stated honestly in the manifesto.

Two phases, one seal record per test file
(``.nwave/telemetry/red-green/<relpath-slug>.json``):

  --record-red   run the tests NOW (pre-implementation); REFUSE (exit 1) if
                 nothing fails -- an all-passing pre-implementation AT set
                 witnesses nothing. Store per-test outcomes + the test file's
                 content sha256.
  --verify-green run the tests NOW (post-implementation); REFUSE unless
                 (a) a red record exists, (b) the test content hash is
                 UNCHANGED (a test edited after RED voids its own evidence --
                 the crafter-touched-the-test class), (c) every red test now
                 passes. Report the SEALED set (red->green: real coverage)
                 and the PINS set (green->green: regression pins, legitimate
                 but not counted as new-behavior coverage).

Outcome contract: JUnit XML (``--junitxml`` / equivalent) -- deliberately
runner-agnostic: pytest, cargo-nextest and vitest all emit it. The run
command is declared (``--run-cmd``, ``{test_file}`` and ``{junit_out}``
placeholders); default is the pytest form. Degrade-LOUD: no runner / no
record / malformed XML -> exit 2 INDETERMINATE with what/why/how, never a
silent pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile

# The XML parsed here is produced locally by the test runner we just invoked,
# in a temp file we own -- not untrusted input.
from pathlib import Path
from xml.etree import ElementTree

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument
from des.ports import test_runner_port


_SEAL_DIR = Path(".nwave") / "telemetry" / "red-green"
# Fix B (enabling change, docs/feature/fix-seal-keys-on-nodeid-not-docstring):
# ``-p no:pspec`` isolates the seal run from pytest-pspec, whose UNGUARDED
# ``pytest_collection_modifyitems`` rewrites ``item._nodeid`` to embed the
# test function's docstring on every run, not only ``--pspec`` runs. This is
# a denylist mitigation, not the fix -- it makes the shape guard below
# (Fix A) usable on THIS repo's pytest path; it does not, by itself, protect
# against the NEXT nodeid-mutating plugin.
_PYTEST_PLUGIN_ISOLATION = ("-p", "no:pspec")
_DEFAULT_RUN_CMD = (
    sys.executable,
    "-m",
    "pytest",
    *_PYTEST_PLUGIN_ISOLATION,
    "{test_file}",
    "--junitxml={junit_out}",
    "-q",
    "--tb=no",
)
_RUN_TIMEOUT_SECONDS = 600

_EXIT_OK = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2

# Fix A v2 (root-cause fix, replaces the SHAPE proxy this once was): the
# proxy (embedded newline OR length > 200 chars) is DELETED -- it is BLIND
# to a short, single-line docstring shared across parametrize cases, the
# overwhelmingly common real corruption vector
# (docs/feature/fix-seal-keys-on-nodeid-not-docstring). The settled
# invariant is COUNT, not SHAPE: it never inspects a `name`'s content, only
# whether the number of raw <testcase> elements equals the number of
# distinct classname::name identities derived from them. See the collapse-
# refusal block in ``_run_and_collect`` below.


def _has_tool_uv_table(pyproject: Path) -> bool:
    """Filesystem-only, no shelling out (GDP-7): scan pyproject.toml text for
    a ``[tool.uv]`` table header."""
    if not pyproject.is_file():
        return False
    try:
        text = pyproject.read_text()
    except OSError:
        return False
    return any(line.strip() == "[tool.uv]" for line in text.splitlines())


class _UnsupportedRunnerLayout(Exception):
    """Raised by ``_default_run_cmd`` when ``test_runner_port.resolve`` matches
    a REGISTERED, RECOGNIZED runner (e.g. ``cargo-test``, ``vitest``,
    ``go-test``) that verify-red-green has no pytest-style run-cmd template
    for. Distinct from an UNRECOGNIZED layout (zero matched lockfiles at
    all), which keeps the legacy Python-assumed pytest fallback -- see
    ``_default_run_cmd``. Caught in ``main`` and turned into a loud REFUSAL
    (exit 1), never a silent fall-through to pytest.
    """

    def __init__(self, runner: str) -> None:
        self.runner = runner
        super().__init__(
            f"resolved runner {runner!r} has no verify-red-green run-cmd template"
        )


def _default_run_cmd(repo: Path) -> tuple[str, ...]:
    """Derive the DEFAULT runner command from the TARGET ``repo``'s test-runner
    layout (filesystem-only, no shelling out -- GDP-7).

    Delegates layout RESOLUTION to the existing closed-union registry
    ``des.ports.test_runner_port.resolve`` (never a private, hand-rolled,
    open-ended if/elif chain) -- the SAME registry the contract gate already
    consumes:

    * resolves to the ``pytest`` runner (``pyproject.toml`` / ``pytest.ini``)
      -> layer the Python-env run-prefix (uv/poetry/pipenv) on top, exactly as
      before -- orthogonal to *which* runner, not a competing resolver.
      ``sys.executable`` binds to the interpreter that LAUNCHED
      verify-red-green, not the target repo's environment -- on a
      uv/poetry/pipenv target repo that runs pytest in the WRONG env, so the
      manifest-derived prefix always runs in the target's own environment.
    * resolves to a DIFFERENT recognized runner (``cargo-test``, ``vitest``,
      ``go-test``, ...) -> verify-red-green has no run-cmd template for it;
      raises ``_UnsupportedRunnerLayout`` so ``main`` can REFUSE loud instead
      of silently reaching pytest against a non-Python target.
    * resolves to NOTHING (``Indeterminate`` / ``UnrecognizedRunner`` -- zero
      matched lockfiles) -> preserves the legacy behavior: assume a
      lockfile-less Python repo and fall back to the unchanged
      ``_DEFAULT_RUN_CMD`` (current sys.executable -m pytest form).

    An explicit ``--run-cmd`` always wins over this derivation (see ``main``).
    """
    resolution = test_runner_port.resolve(repo)
    if (
        isinstance(resolution, test_runner_port.RunnerAdapter)
        and resolution.name != "pytest"
    ):
        raise _UnsupportedRunnerLayout(resolution.name)
    # Either resolved to "pytest", or Indeterminate/UnrecognizedRunner (no
    # matched lockfile at all) -- both keep the legacy Python-assumed pytest
    # fallback (unchanged behavior for the plain-repo case).
    return _pytest_default_run_cmd(repo)


def _pytest_default_run_cmd(repo: Path) -> tuple[str, ...]:
    """Layer the Python-env run-prefix (uv/poetry/pipenv) on the pytest tail."""
    tail = ("{test_file}", "--junitxml={junit_out}", "-q", "--tb=no")
    if (repo / "uv.lock").is_file() or _has_tool_uv_table(repo / "pyproject.toml"):
        return ("uv", "run", "pytest", *_PYTEST_PLUGIN_ISOLATION, *tail)
    if (repo / "poetry.lock").is_file():
        return ("poetry", "run", "pytest", *_PYTEST_PLUGIN_ISOLATION, *tail)
    if (repo / "Pipfile.lock").is_file() or (repo / "Pipfile").is_file():
        return ("pipenv", "run", "pytest", *_PYTEST_PLUGIN_ISOLATION, *tail)
    return _DEFAULT_RUN_CMD


def _indeterminate(what: str, why: str, how: str, cmd: object = None) -> int:
    payload: dict[str, object] = {
        "event": "RedGreenIndeterminate",
        "what": what,
        "why": why,
        "how": how,
    }
    if cmd is not None:
        payload["cmd"] = list(cmd) if isinstance(cmd, (list, tuple)) else cmd
    _emit(payload)
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _unsupported_layout_refusal(exc: _UnsupportedRunnerLayout) -> int:
    """REFUSE loud (exit 1) for a resolved runner verify-red-green has no
    run-cmd template for -- names the incapacity, the resolved layout, and
    the ``--run-cmd`` escape hatch (GDP-3/GDP-4), never a silent pytest
    fall-through against a non-Python target."""
    what = (
        f"no verify-red-green run-cmd template for the resolved runner {exc.runner!r}"
    )
    why = (
        "des.ports.test_runner_port.resolve() recognized this target's "
        f"layout (runner={exc.runner!r}) but verify-red-green only carries "
        "a pytest-style run-cmd template -- running pytest against this "
        "target would silently mis-execute (empty/false results), not "
        "witness the developer's tests."
    )
    how = (
        "pass --run-cmd '<runner invocation> {test_file} {junit_out}' "
        "explicitly (verify-red-green is runner-agnostic via JUnit XML -- "
        "pytest, cargo-nextest, and vitest all emit it)."
    )
    cmd = [f"<no run-cmd template for runner={exc.runner!r}>"]
    _emit(
        {
            "event": "RedGreenRefused",
            "phase": "layout",
            "what": what,
            "why": why,
            "how": how,
            "cmd": cmd,
        }
    )
    print(f"✗ REFUSED — {what}. {why} Fix: {how}")
    return _EXIT_REFUSED


def _seal_path(repo: Path, test_file: Path) -> Path:
    rel = test_file.relative_to(repo)
    slug = str(rel).replace("/", "__")
    return repo / _SEAL_DIR / f"{slug}.json"


def _content_sha(test_file: Path) -> str:
    return hashlib.sha256(test_file.read_bytes()).hexdigest()


def _run_and_collect(
    repo: Path, test_file: Path, run_cmd: tuple[str, ...]
) -> dict[str, str] | int:
    """Run the declared command; parse JUnit XML -> {test_id: pass|fail}."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        junit_out = Path(tmp.name)
    try:
        cmd = [
            part.replace("{test_file}", str(test_file)).replace(
                "{junit_out}", str(junit_out)
            )
            for part in run_cmd
        ]
        try:
            subprocess.run(
                cmd,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=_RUN_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return _indeterminate(
                what=f"runner not found: {cmd[0]}",
                why="the declared run command's tool is not on PATH.",
                how="install it or declare another via --run-cmd.",
                cmd=cmd,
            )
        except subprocess.TimeoutExpired:
            return _indeterminate(
                what=f"test run timed out after {_RUN_TIMEOUT_SECONDS}s",
                why="the declared run command did not finish.",
                how="run it manually; fix or re-budget the suite.",
                cmd=cmd,
            )
        try:
            tree = ElementTree.parse(junit_out)
        except (ElementTree.ParseError, FileNotFoundError) as exc:
            return _indeterminate(
                what="no parseable JUnit XML produced",
                why=f"{exc} — without per-test outcomes there is nothing to seal.",
                how=(
                    f"ensure the run command emits JUnit XML at {junit_out} "
                    "(pytest --junitxml / cargo-nextest / vitest all can) "
                    "-- OR, if this is a pre-implementation RED on a "
                    "compiled language (the acceptance test is a compile "
                    "error because the production code does not exist "
                    "yet), it produces no per-test XML: seal it via "
                    "`des record-at-review-verdict` (two-part attestation) "
                    "instead."
                ),
                cmd=cmd,
            )
        outcomes: dict[str, str] = {}
        raw_ids: list[str] = []
        verdicts_by_id: dict[str, list[str]] = {}
        for case in tree.iter("testcase"):
            classname = case.get("classname", "") or ""
            name = case.get("name", "") or ""
            test_id = f"{classname}::{name}"
            failed = any(child.tag in ("failure", "error") for child in case)
            skipped = any(child.tag == "skipped" for child in case)
            # A collection-error testcase (pytest shape: empty classname,
            # <error> child) means the file did not even collect -- that is
            # BROKEN, not RED (ADR-025: red must be a SEMANTIC failure). A
            # broken file yields no per-test outcomes and can seal nothing.
            if failed and not classname:
                _emit(
                    {
                        "event": "RedGreenRefused",
                        "phase": "collect",
                        "what": "the test file is BROKEN, not RED "
                        "(collection/import error)",
                        "why": (
                            "a file that fails to collect exercises nothing; "
                            "its redness is a syntax/import accident, not a "
                            "witnessed missing behavior."
                        ),
                        "how": (
                            "reference the not-yet-implemented names INSIDE "
                            "test bodies (RED-not-BROKEN discipline) so the "
                            "file collects and fails semantically."
                        ),
                    }
                )
                print("✗ REFUSED — BROKEN (collection error), not RED")
                return _EXIT_REFUSED
            if skipped:
                continue
            raw_ids.append(test_id)
            verdicts_by_id.setdefault(test_id, []).append("fail" if failed else "pass")
            # Fail-dominant fold: a duplicate classname::name (e.g. a
            # pytest-bdd Scenario Outline with N Examples rows emitting
            # byte-identical <testcase> ids) must never let a later PASS
            # silently overwrite an earlier FAIL (GDP-6, backlog #105).
            outcomes[test_id] = (
                "fail" if (failed or outcomes.get(test_id) == "fail") else "pass"
            )
        if not outcomes:
            return _indeterminate(
                what="zero test cases collected",
                why="an empty run seals nothing (and must never pass).",
                how="check the test file path and the runner invocation.",
                cmd=cmd,
            )
        if len(raw_ids) != len(outcomes):
            duplicate_ids = sorted({tid for tid in raw_ids if raw_ids.count(tid) > 1})
            # Settled invariant (COUNT, not SHAPE --
            # docs/feature/fix-seal-keys-on-nodeid-not-docstring): raw
            # <testcase> count must equal distinct classname::name identity
            # count. A collapse is untrustworthy -- REFUSE fail-closed --
            # when either (a) it swallows the WHOLE run into one identity
            # (no distinct id survives to anchor trust), or (b) any one
            # duplicate group disagrees within itself (a fold would
            # silently pick an arbitrary verdict). A collapse that is a
            # genuine subset -- other distinct ids remain, and the
            # duplicated group agrees with itself -- loses no information
            # and is only declared, not refused. This never inspects a
            # `name`'s content: a nodeid-mutating plugin is caught at ANY
            # docstring length the same way, and honest distinct prose
            # titles (the vitest `describe > it` shape) are left alone.
            whole_run_collapse = len(outcomes) == 1
            disagreeing_ids = sorted(
                tid for tid in duplicate_ids if len(set(verdicts_by_id[tid])) > 1
            )
            if whole_run_collapse or disagreeing_ids:
                return _indeterminate(
                    what=(
                        f"{len(raw_ids)} <testcase> element(s) collapsed "
                        f"into {len(outcomes)} identit"
                        f"{'y' if whole_run_collapse else 'ies'}: "
                        f"{', '.join(duplicate_ids)}"
                    ),
                    why=(
                        "the runner must produce one distinct classname::"
                        "name identity per real test case; a nodeid-"
                        "mutating plugin (e.g. pytest-pspec's unguarded "
                        "pytest_collection_modifyitems rewriting `name` to "
                        "shared docstring/prose content, at any length) can "
                        "collapse distinct cases into one id, and no single "
                        "verdict can be trusted for the folded id(s)."
                    ),
                    how=(
                        "isolate the nodeid-mutating plugin from the run "
                        "command (e.g. -p no:<plugin>), or ensure the "
                        "runner emits one distinct classname::name per "
                        "real test case."
                    ),
                )
            _emit(
                {
                    "event": "RedGreenDuplicateIdCollapse",
                    "what": f"{len(raw_ids)} <testcase> element(s) folded "
                    f"into {len(outcomes)} test id(s)",
                    "why": (
                        "duplicate classname::name pairs in the JUnit XML "
                        "(e.g. a pytest-bdd Scenario Outline with multiple "
                        "Examples rows) collapse to one outcome key; the "
                        "fold is fail-dominant so any failing occurrence "
                        "keeps the id failed."
                    ),
                    "how": (
                        "disambiguate the ids at the source (unique "
                        "scenario/example titles) if independent verdicts "
                        "are required."
                    ),
                    "duplicate_ids": duplicate_ids,
                }
            )
            print(
                f"⚠ COLLAPSED — {len(raw_ids)} testcase(s) folded into "
                f"{len(outcomes)} id(s); duplicate: {', '.join(duplicate_ids)}"
            )
        return outcomes
    finally:
        junit_out.unlink(missing_ok=True)


def _record_red(
    repo: Path,
    test_file: Path,
    run_cmd: tuple[str, ...],
    *,
    feature_id: str | None = None,
    slice_id: str | None = None,
) -> int:
    outcomes = _run_and_collect(repo, test_file, run_cmd)
    if isinstance(outcomes, int):
        return outcomes
    failing = sorted(t for t, o in outcomes.items() if o == "fail")
    if not failing:
        _emit(
            {
                "event": "RedGreenRefused",
                "phase": "red",
                "what": (
                    "every test PASSES pre-implementation — this AT set "
                    "witnesses nothing"
                ),
                "why": (
                    "a test that is green before the behavior exists cannot "
                    "evidence that behavior (the always-pass/vacuous class)."
                ),
                "how": (
                    "make the ATs assert the promised behavior so they FAIL "
                    "for the right reason now, then re-record RED."
                ),
                "tests": sorted(outcomes),
            }
        )
        print("✗ REFUSED — RED phase: nothing fails; the AT set witnesses nothing")
        return _EXIT_REFUSED
    seal = _seal_path(repo, test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": str(test_file.relative_to(repo)),
                "content_sha256": _content_sha(test_file),
                "outcomes": outcomes,
            },
            indent=2,
        )
    )
    _emit(
        {
            "event": "RedObserved",
            "test_file": str(test_file.relative_to(repo)),
            "failing": failing,
            "passing_pins": sorted(t for t, o in outcomes.items() if o == "pass"),
            "cmd": list(run_cmd),
        }
    )
    print(f"✓ RED observed — {len(failing)} failing (witness candidates) recorded")
    if feature_id is not None and slice_id is not None:
        AtCompletionLedger(feature_id, repo).append_gate_event(
            "RedObserved", slice_id, feature_id=feature_id, gate="verify-red-green"
        )
    return _EXIT_OK


def _verify_green(
    repo: Path,
    test_file: Path,
    run_cmd: tuple[str, ...],
    *,
    feature_id: str | None = None,
    slice_id: str | None = None,
) -> int:
    seal = _seal_path(repo, test_file)
    if not seal.is_file():
        return _indeterminate(
            what=f"no RED record for {test_file.name}",
            why="GREEN without an observed RED is unsealable (never-red class).",
            how="run --record-red BEFORE implementing, then re-verify.",
        )
    record = json.loads(seal.read_text())
    if record["content_sha256"] != _content_sha(test_file):
        _emit(
            {
                "event": "RedGreenRefused",
                "phase": "green",
                "test_file": test_file.name,
                "recorded_content_sha256": record["content_sha256"],
                "current_content_sha256": _content_sha(test_file),
                "what": f"test file CHANGED between RED and GREEN: {test_file.name}",
                "why": (
                    "edited tests void their own RED evidence — the "
                    "crafter-touched-the-test class."
                ),
                "how": (
                    "re-record RED for the current test content (it must fail "
                    "pre-implementation again), or revert the test edit."
                ),
            }
        )
        print(f"✗ REFUSED — {test_file.name} changed since RED; evidence void")
        return _EXIT_REFUSED
    outcomes = _run_and_collect(repo, test_file, run_cmd)
    if isinstance(outcomes, int):
        return outcomes
    red_outcomes: dict[str, str] = record["outcomes"]
    was_red = {t for t, o in red_outcomes.items() if o == "fail"}
    still_failing = sorted(t for t in was_red if outcomes.get(t, "fail") == "fail")
    if still_failing:
        _emit(
            {
                "event": "RedGreenRefused",
                "phase": "green",
                "what": f"{len(still_failing)} red test(s) still failing",
                "why": "the implementation does not satisfy the witnessed ATs.",
                "how": "fix the implementation; the tests are the contract.",
                "still_failing": still_failing,
            }
        )
        print(f"✗ REFUSED — {len(still_failing)} red test(s) still failing")
        return _EXIT_REFUSED
    sealed = sorted(was_red)
    pins = sorted(t for t, o in red_outcomes.items() if o == "pass")
    _emit(
        {
            "event": "RedGreenSealed",
            "test_file": str(test_file.relative_to(repo)),
            "sealed": sealed,
            "pins": pins,
        }
    )
    print(
        f"✓ SEALED — {len(sealed)} test(s) witnessed red→green; "
        f"{len(pins)} regression pin(s) (not new-behavior coverage)"
    )
    if feature_id is not None and slice_id is not None:
        AtCompletionLedger(feature_id, repo).append_gate_event(
            "RedGreenSealed", slice_id, feature_id=feature_id, gate="verify-red-green"
        )
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-red-green",
        description=(
            "Seal the RED->GREEN transition of an AT file as mechanical "
            "non-vacuity evidence (evolution P0.2)."
        ),
    )
    add_repo_root_argument(parser, "--repo", default=".", help="Repository root.")
    parser.add_argument(
        "--test-file", required=True, help="The AT file (repo-relative or absolute)."
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help=(
            "Feature id to key an AT-completion ledger RedObserved/"
            "RedGreenSealed gate event (optional; requires --slice-id)."
        ),
    )
    parser.add_argument(
        "--slice-id",
        default=None,
        help=(
            "Slice id to key an AT-completion ledger RedObserved/"
            "RedGreenSealed gate event (optional; requires --feature-id)."
        ),
    )
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--record-red", action="store_true")
    phase.add_argument("--verify-green", action="store_true")
    parser.add_argument(
        "--run-cmd",
        default=None,
        help=(
            "Declared runner command with {test_file} and {junit_out} "
            "placeholders (default: pytest --junitxml form)."
        ),
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        return _indeterminate(
            what=f"--repo {repo} is not an existing directory",
            why=(
                "the tool cannot resolve the test file or write the "
                "red/green seal without a real repo root."
            ),
            how="pass --repo pointing at an existing repository directory.",
        )
    test_file = (repo / args.test_file).resolve()
    if not test_file.is_file():
        return _indeterminate(
            what=f"test file not found: {args.test_file}",
            why="nothing to observe.",
            how="check the path.",
        )
    try:
        test_file.relative_to(repo)
    except ValueError:
        return _indeterminate(
            what=f"--test-file {test_file} is outside --repo {repo}",
            why=(
                "the red/green seal is keyed to the test file's repo-relative "
                "path, so a file outside the repo cannot be sealed."
            ),
            how=(
                "pass a --test-file that lives inside --repo (repo-relative, "
                "or an absolute path under the repo root)."
            ),
        )
    if args.run_cmd:
        run_cmd = tuple(shlex.split(args.run_cmd))
    else:
        try:
            run_cmd = _default_run_cmd(repo)
        except _UnsupportedRunnerLayout as exc:
            return _unsupported_layout_refusal(exc)
    if args.record_red:
        return _record_red(
            repo,
            test_file,
            run_cmd,
            feature_id=args.feature_id,
            slice_id=args.slice_id,
        )
    return _verify_green(
        repo, test_file, run_cmd, feature_id=args.feature_id, slice_id=args.slice_id
    )


if __name__ == "__main__":
    sys.exit(main())
