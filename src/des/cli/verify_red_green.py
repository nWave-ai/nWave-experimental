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


_SEAL_DIR = Path(".nwave") / "telemetry" / "red-green"
_DEFAULT_RUN_CMD = (
    sys.executable,
    "-m",
    "pytest",
    "{test_file}",
    "--junitxml={junit_out}",
    "-q",
    "--tb=no",
)
_RUN_TIMEOUT_SECONDS = 600

_EXIT_OK = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2


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


def _default_run_cmd(repo: Path) -> tuple[str, ...]:
    """Derive the DEFAULT runner command from the TARGET ``repo``'s Python
    packaging manifest (filesystem-only, no shelling out -- GDP-7).

    ``sys.executable`` binds to the interpreter that LAUNCHED verify-red-green,
    not the target repo's environment -- on a uv/poetry/pipenv target repo
    that runs pytest in the WRONG env. Derive from the manifest instead so the
    default always runs in the target's own environment; fall back to the
    unchanged ``_DEFAULT_RUN_CMD`` (current sys.executable -m pytest form)
    when no recognized manifest is present. An explicit ``--run-cmd`` always
    wins over this derivation (see ``main``).
    """
    tail = ("{test_file}", "--junitxml={junit_out}", "-q", "--tb=no")
    if (repo / "uv.lock").is_file() or _has_tool_uv_table(repo / "pyproject.toml"):
        return ("uv", "run", "pytest", *tail)
    if (repo / "poetry.lock").is_file():
        return ("poetry", "run", "pytest", *tail)
    if (repo / "Pipfile.lock").is_file() or (repo / "Pipfile").is_file():
        return ("pipenv", "run", "pytest", *tail)
    return _DEFAULT_RUN_CMD


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload))


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit({"event": "RedGreenIndeterminate", "what": what, "why": why, "how": how})
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


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
            )
        except subprocess.TimeoutExpired:
            return _indeterminate(
                what=f"test run timed out after {_RUN_TIMEOUT_SECONDS}s",
                why="the declared run command did not finish.",
                how="run it manually; fix or re-budget the suite.",
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
            )
        outcomes: dict[str, str] = {}
        raw_ids: list[str] = []
        for case in tree.iter("testcase"):
            classname = case.get("classname", "") or ""
            test_id = f"{classname}::{case.get('name', '')}"
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
            )
        if len(raw_ids) != len(outcomes):
            duplicate_ids = sorted({tid for tid in raw_ids if raw_ids.count(tid) > 1})
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


def _record_red(repo: Path, test_file: Path, run_cmd: tuple[str, ...]) -> int:
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
        }
    )
    print(f"✓ RED observed — {len(failing)} failing (witness candidates) recorded")
    return _EXIT_OK


def _verify_green(repo: Path, test_file: Path, run_cmd: tuple[str, ...]) -> int:
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
                "what": "test file CHANGED between RED and GREEN",
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
        print("✗ REFUSED — test content changed since RED; evidence void")
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
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-red-green",
        description=(
            "Seal the RED->GREEN transition of an AT file as mechanical "
            "non-vacuity evidence (evolution P0.2)."
        ),
    )
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument(
        "--test-file", required=True, help="The AT file (repo-relative or absolute)."
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
    test_file = (repo / args.test_file).resolve()
    if not test_file.is_file():
        return _indeterminate(
            what=f"test file not found: {args.test_file}",
            why="nothing to observe.",
            how="check the path.",
        )
    run_cmd = (
        tuple(shlex.split(args.run_cmd)) if args.run_cmd else _default_run_cmd(repo)
    )
    if args.record_red:
        return _record_red(repo, test_file, run_cmd)
    return _verify_green(repo, test_file, run_cmd)


if __name__ == "__main__":
    sys.exit(main())
