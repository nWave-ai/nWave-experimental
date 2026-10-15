"""Current acceptance measures original-source RED without undoing a committed fix.

@contract-shape: real-io
The existing orchestrator journey is extended through its real in-process CLI.
Git, disposable checkouts and native pytest execution are real, not mocked.
"""

from __future__ import annotations

import hashlib
import json
import os
import site
import subprocess
import sys
import sysconfig
import venv
from enum import Enum
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import design_manifest, referencing_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    git,
    observation,
)


ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
AUTHORITY = "docs/product/architecture/brief.md"
PYTHON = sys.executable
NATIVE = [PYTHON, "-m", "pytest", "-p", "no:cacheprovider", ORACLE]
REQUEST = "Measure current acceptance against original source without undoing the fix."


class ReceiptFault(Enum):
    REFUSED = "refused-child"
    FOREIGN_NONCE = "foreign-nonce-child"


def _require(condition: bool, what: str, why: str, how: str) -> None:
    assert condition, f"WHAT: {what}\nWHY: {why}\nHOW: {how}"


def _oracle_body(captures: Path, *, offset: int = 0) -> str:
    """The fixture's public value and current support determine the assertion."""
    return (
        "import json\nimport pathlib\nimport runpy\n\n"
        "def test_committed_value_meets_current_expectation():\n"
        "    root = pathlib.Path(__file__).resolve().parents[2]\n"
        "    actual = runpy.run_path(str(root / 'product_value.py'))['VALUE']\n"
        "    expected = runpy.run_path(str(root / "
        "'tests/acceptance/support.py'))['EXPECTED']\n"
        f"    with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "        output.write(json.dumps({'cwd': str(root), 'actual': actual, "
        f"'expected': expected, 'offset': {offset}}}) + '\\n')\n"
        f"    assert actual + {offset} == expected, (\n"
        "        f'WHAT: product value {actual} does not meet current expectation "
        "{expected}. WHY: the committed value must satisfy current acceptance. "
        "HOW: implement the promised value in production, not in the oracle.')\n"
    )


def _write_acceptance(root: Path, captures: Path, *, offset: int = 0) -> None:
    (root / ORACLE).parent.mkdir(parents=True, exist_ok=True)
    (root / ORACLE).write_text(_oracle_body(captures, offset=offset))
    (root / SUPPORT).write_text(f"EXPECTED = {1 + offset}\n")


def _facts(*, revised: bool = False) -> dict:
    absent = {
        "applicability": "not_applicable",
        "reason": "This fixture introduces no additional boundary or shared contract.",
    }
    return {
        "targets": [{"path": TARGET, "decision": "EXTEND"}],
        "paradigm": "object_oriented",
        "decisions": [
            "The committed value must meet current acceptance.",
            *(
                ["Corrected acceptance observes value plus one through its support."]
                if revised
                else []
            ),
        ],
        "oracle": ORACLE,
        "acceptance_supports": [SUPPORT],
        "verification": [NATIVE],
        "oracle_verification_index": 0,
        "architectural_tests": absent,
        "contract_tests": absent,
        "prefactoring": absent,
        "agreement_analysis": absent,
    }


def _manifest(*, revised: bool = False) -> dict:
    return design_manifest(_facts(revised=revised), observation("committed value"), 1)


def _bind(root: Path, step) -> None:
    result = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("committed value")],
        stdin=REQUEST,
    )
    _require(
        result[0] == 0,
        f"Product construction failed: {result}",
        "An invalid fixture cannot demonstrate baseline measurement.",
        "Construct the fixture's single value through the existing public PO port.",
    )
    result = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=json.dumps(_manifest()),
    )
    _require(
        result[0] == 0,
        f"DESIGN construction failed: {result}",
        "Oracle execution needs a real bound target, support and native recipe.",
        "Bind the complete fixture manifest through des design --input -.",
    )


def _workspace(root: Path) -> dict:
    """The whole non-DES file population, index, status, HEAD and worktree registry."""
    paths = {
        name
        for name in git(
            root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        ).split("\0")
        if name and not name.startswith(".nwave/des/")
    }
    files = {}
    for name in sorted(paths):
        path = root / name
        if path.is_symlink():
            files[name] = {"symlink": str(path.readlink())}
        elif path.is_file():
            files[name] = {
                "bytes": path.read_bytes().hex(),
                "mode": path.stat().st_mode,
            }
        else:
            files[name] = None
    return {
        "head": git(root, "rev-parse", "HEAD"),
        "index": git(root, "ls-files", "--stage", "-z"),
        "status": git(
            root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude).nwave/des",
        ),
        "files": files,
        "worktrees": git(root, "worktree", "list", "--porcelain"),
    }


def _invoke(
    root: Path,
    step,
    output: Path,
    action: str,
    *extra: str,
    position: int = 1,
) -> tuple:
    before = _workspace(root)
    payload = {
        "outcome": "accepted",
        "diagnostic": "Host supplied current acceptance and implementation bytes.",
    }
    if action == "craft":
        payload["blocked_by"] = None
    result = step(
        action,
        "--repo-root",
        str(root),
        "--value",
        str(position),
        *extra,
        "--input",
        "-",
        stdin=json.dumps({"structured_output": payload}),
    )
    after = _workspace(root)
    with output.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "stimulus": [action, "--value", str(position), *extra],
                    "exit": result[0],
                    "stdout": result[1],
                    "stderr": result[2],
                    "before": before,
                    "after": after,
                }
            )
            + "\n"
        )
    _require(
        after == before,
        f"{action} changed workspace state; snapshots: {output}",
        "Measuring original source must not undo dirty bytes, the index or fixed HEAD.",
        "Execute in the existing disposable checkout and preserve the host workspace.",
    )
    return result


def _success(result: tuple, action: str) -> dict:
    _require(
        result[0] == 0,
        f"{action} did not succeed: {result}",
        "Current acceptance must measure the explicit original source and admit fixed GREEN.",
        "Expose --baseline on des oracle, measure its resolved commit in isolation, "
        "and let craft consume the current DESIGN-bound witness.",
    )
    return block(result[1], result[2])


def _history(root: Path) -> list[dict]:
    refs = [
        ref
        for ref in git(
            root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
        ).splitlines()
        if ref.endswith("/oracle-witness")
    ]
    _require(
        len(refs) == 1,
        f"Expected one value's witness in enumerated refs: {refs}",
        "Successful measurement must persist original-source provenance.",
        "Record the selected value's measured oracle witness.",
    )
    return json.loads(
        git(root, "show", "-s", "--format=%B", refs[0]).partition("\n\n")[2]
    )


def _assert_witness(root: Path, baseline: str, verdict: str, source: str) -> dict:
    entry = _history(root)[-1]
    expected_base = {
        "sha": baseline,
        "tree": git(root, "rev-parse", f"{baseline}^{{tree}}"),
        "source": source,
    }
    _require(
        entry.get("baseline") == expected_base,
        f"Witness baseline differs from caller provenance: {entry}",
        "Every measurement must identify its immutable source commit and tree.",
        "Persist the resolved source actually selected by explicit or witness precedence.",
    )
    oracles = entry["oracles"]
    _require(
        {item["oracle"] for item in oracles} == {ORACLE}
        and all(item["verdict"] == verdict for item in oracles),
        f"Measured oracle population or verdict is wrong: {oracles}",
        "The selected current oracle must fail behaviorally at original source.",
        "Run the declared current acceptance against the selected execution tree.",
    )
    tree = entry["acceptance_tree"]
    _require(
        set(git(root, "ls-tree", "-r", "--name-only", tree).splitlines())
        == {ORACLE, SUPPORT},
        f"Witness acceptance population is not oracle plus declared support: {tree}",
        "An omitted support could silently measure historical expectations.",
        "Record the complete current declared acceptance tree.",
    )
    for name in (ORACLE, SUPPORT):
        _require(
            git(root, "show", f"{tree}:{name}") == (root / name).read_text().strip(),
            f"Witness contains stale acceptance bytes for {name}",
            "Craft and reviewers must consume the same bytes measured by oracle.",
            "Overlay and record the current oracle and support, not baseline versions.",
        )
    return entry


def _assert_red(result: tuple, root: Path, baseline: str, source: str) -> dict:
    lines = _success(result, "oracle")
    _require(
        lines.get("ORACLE-BASELINE") == f"{baseline} source={source}"
        and "verdict=red" in lines.get("ORACLE-RED", ""),
        f"Original-source RED provenance is absent or incorrect: {lines}",
        "The workspace is already fixed, so its GREEN cannot stand for original RED.",
        "Measure current acceptance against the explicit or recorded original commit.",
    )
    entry = _assert_witness(root, baseline, "red", source)
    _require(
        all(
            item["exit"] == 1 and item["completed"] is True for item in entry["oracles"]
        ),
        f"RED did not complete as a native assertion failure: {entry['oracles']}",
        "Import, collection and environment failures are BROKEN, not intended RED.",
        "Run the native pytest recipe until the product-value assertion is reached.",
    )
    return entry


def _native_observation(
    root: Path,
    output: Path,
    *,
    expected_exit: int = 0,
    argv: list[str] | None = None,
    environment: dict[str, str] | None = None,
) -> None:
    command = NATIVE if argv is None else argv
    environment = {
        key: value
        for key, value in (os.environ if environment is None else environment).items()
        if key != "PYTEST_ADDOPTS"
    }
    result = subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    with output.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "stimulus": command,
                    "cwd": str(root),
                    "exit": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            + "\n"
        )
    _require(
        result.returncode == expected_exit
        and (expected_exit == 0 or "1 failed" in result.stdout),
        f"Native control expected exit {expected_exit}: {result.stdout}{result.stderr}",
        "The baseline contrast must concern production behavior, not broken test setup.",
        "Run the declared .venv vector without ambient DES observer addopts.",
    )


def _refuses_without_recording(  # noqa: PLR0913 - one public refusal's stimulus and observation context
    root: Path,
    step,
    output: Path,
    baseline: str | None,
    what: str,
    *named: str,
    captures: Path | None = None,
    position: int = 1,
    disposition: str | None = None,
) -> tuple:
    refs = git(
        root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/nwave/turns"
    )
    native_before = captures.read_bytes() if captures is not None else None
    extra = () if baseline is None else ("--baseline", baseline)
    result = _invoke(root, step, output, "oracle", *extra, position=position)
    lines = block(result[1], result[2])
    expected_outcome = disposition or (
        "Refusal"
        if baseline is not None or what == "OracleBaselineMissing"
        else "Indeterminate"
    )
    _require(
        result[0] != 0
        and lines.get("WHAT") == what
        and lines.get("DELIVERY-OUTCOME") == expected_outcome
        and bool(lines.get("WHY"))
        and bool(lines.get("HOW"))
        and all(value in result[1] + result[2] for value in named)
        and "ORACLE-RED" not in lines,
        f"Baseline refusal is not loud and unambiguous: {result}",
        "Missing or unreadable source must never become valid RED or a fallback.",
        "Name WHAT/WHY/HOW and the supplied/recorded commits without measuring.",
    )
    _require(
        git(
            root,
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/nwave/turns",
        )
        == refs
        and (captures is None or captures.read_bytes() == native_before),
        f"Refusal switched witness, baseline or turn records: {result}",
        "An unsuccessful comparison cannot replace admitted evidence.",
        "Resolve the baseline before appending witness or oracle-turn records.",
    )
    return result


def _recorded_source_failures(  # noqa: PLR0913, PLR0917 - reversible fault stimuli share the public fixture context
    root: Path,
    step,
    output: Path,
    captures: Path,
    original: str,
    tmp_path: Path,
) -> None:
    """Reversibly lose a real commit, then replace a real witness with unreadable history."""
    object_path = root / git(root, "rev-parse", "--git-path", "objects")
    original_tree = git(root, "rev-parse", f"{original}^{{tree}}")
    original_object = object_path / original[:2] / original[2:]
    _require(
        original_object.is_file(),
        f"Fixture original commit is not a loose object: {original_object}",
        "The missing-recorded-source stimulus must remove the actual recorded commit.",
        "Keep this throwaway repository's fixture commits loose until the observation.",
    )
    displaced = tmp_path / "temporarily-unavailable-original-commit"
    original_object.rename(displaced)
    try:
        _refuses_without_recording(
            root,
            step,
            output,
            None,
            "OracleBaselineUnavailable",
            "witness",
            original,
            original_tree,
            captures=captures,
        )
    finally:
        displaced.rename(original_object)

    witness_refs = [
        ref
        for ref in git(
            root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
        ).splitlines()
        if ref.endswith("/oracle-witness")
    ]
    _require(
        len(witness_refs) == 1,
        f"Fixture witness population changed: {witness_refs}",
        "History corruption must target the selected value's actual recorded witness.",
        "Retain the one-value fixture and corrupt only its temporary witness ref.",
    )
    ref = witness_refs[0]
    recorded = git(root, "rev-parse", ref)
    malformed = git(
        root,
        "commit-tree",
        f"{recorded}^{{tree}}",
        "-p",
        recorded,
        "-m",
        "unreadable fixture witness history",
    )
    git(root, "update-ref", ref, malformed, recorded)
    try:
        _refuses_without_recording(
            root,
            step,
            output,
            None,
            "OracleBaselineUnobservable",
            captures=captures,
        )
    finally:
        git(root, "update-ref", ref, recorded)

    # Well-formed but mismatching immutable tree and malformed baseline shape
    # are distinct persisted-input failures; both must remain non-measurements.
    wrong_tree = git(root, "rev-parse", "HEAD^{tree}")
    subject = git(root, "show", "-s", "--format=%s", recorded)
    for field, invalid, what in (
        ("tree", wrong_tree, "OracleBaselineUnavailable"),
        ("sha", "not-an-immutable-commit", "OracleBaselineUnobservable"),
    ):
        history = _history(root)
        history[-1]["baseline"][field] = invalid
        corrupted = git(
            root,
            "commit-tree",
            f"{recorded}^{{tree}}",
            "-p",
            recorded,
            "-m",
            subject,
            "-m",
            json.dumps(history),
        )
        git(root, "update-ref", ref, corrupted, recorded)
        try:
            _refuses_without_recording(
                root,
                step,
                output,
                None,
                what,
                captures=captures,
            )
        finally:
            git(root, "update-ref", ref, recorded)


def _probe_storage_failure(
    root: Path,
    step,
    output: Path,
    captures: Path,
    original: str,
) -> None:
    """A fresh overlay cannot be stored in the real read-only object database."""
    _require(
        os.geteuid() != 0,
        "Root privileges would bypass the fixture's object-storage write denial.",
        "This real-boundary failure requires the declared non-root host environment.",
        "Run the acceptance oracle as the normal repository owner, not root.",
    )
    oracle = root / ORACLE
    current_bytes = oracle.read_bytes()
    # These bytes have never been added to Git, so even an otherwise reusable
    # tree needs a new blob before it can construct the baseline probe.
    oracle.write_bytes(current_bytes + b"\n# Fresh unstorable baseline overlay.\n")
    objects = root / git(root, "rev-parse", "--git-path", "objects")
    directories = [objects, *(path for path in objects.rglob("*") if path.is_dir())]
    modes = [(path, path.stat().st_mode) for path in directories]
    try:
        for path, mode in modes:
            path.chmod(mode & ~0o222)
        _refuses_without_recording(
            root,
            step,
            output,
            None,
            "OracleProbeUnavailable",
            captures=captures,
        )
    finally:
        for path, mode in modes:
            path.chmod(mode)
        oracle.write_bytes(current_bytes)


def _assert_measured_semantics(lines: dict, root: Path, entry: dict) -> None:
    """Stable public facts and measured semantics, excluding variable evidence locators."""
    expected = {
        "DELIVERY-OUTCOME": "Success",
        "VALUE-1": json.dumps(observation("committed value")),
        "ORACLE": ORACLE,
        "DIAGNOSTIC": json.dumps(
            "Host supplied current acceptance and implementation bytes."
        ),
    }
    _require(
        all(lines.get(key) == value for key, value in expected.items())
        and "ORACLE-BASELINE" in lines
        and "WHAT" not in lines,
        f"Measured terminal facts changed: expected {expected}, actual {lines}",
        "Immutable-source measurement must preserve the existing measured-result facts.",
        "Keep success/value/oracle/host-diagnostic facts while reporting baseline provenance.",
    )
    expected_measurement = {
        "oracle": ORACLE,
        "verdict": "red",
        "exit": 1,
        "counts": [1, 0, 1],
        "argv": NATIVE,
        "completed": True,
    }
    _require(
        len(_history(root)) == 1
        and isinstance(entry.get("revision"), str)
        and bool(entry["revision"])
        and isinstance(entry.get("design_sections"), str)
        and bool(entry["design_sections"])
        and len(entry["oracles"]) == 1
        and all(
            entry["oracles"][0].get(key) == value
            for key, value in expected_measurement.items()
        ),
        f"Witness lost bound identity or native assertion semantics: {entry}",
        "The one declared test must complete with one assertion failure and zero setup errors.",
        "Preserve the selected revision, DESIGN identity and real native measured witness.",
    )


def _fixed_head_journey(root: Path, step, tmp_path: Path) -> None:
    captures = tmp_path / "native-baseline-observations.jsonl"
    output = tmp_path / "public-baseline-observations.jsonl"
    _write_acceptance(root, captures)
    # Historical acceptance was GREEN for the original value; CURRENT acceptance
    # must replace both that oracle and its support when measuring the baseline.
    (root / SUPPORT).write_text("EXPECTED = 0\n")
    (root / ORACLE).write_text(
        _oracle_body(captures) + "\n# Historical original-source acceptance.\n"
    )
    (root / TARGET).write_text("VALUE = 0\n")
    (root / "notes.txt").write_text("committed notes\n")
    git(root, "add", ORACLE, SUPPORT, TARGET, "notes.txt")
    git(root, "commit", "-qm", "original value and historical acceptance")
    original = git(root, "rev-parse", "HEAD")
    (root / TARGET).write_text("VALUE = 1\n")
    git(root, "add", TARGET)
    git(root, "commit", "-qm", "fixed value already committed")
    fixed = git(root, "rev-parse", "HEAD")
    _bind(root, step)
    git(root, "add", AUTHORITY)
    git(root, "commit", "-qm", "bound current DESIGN")
    _write_acceptance(root, captures)
    (root / "notes.txt").write_text("staged host notes\n")
    git(root, "add", "notes.txt")
    (root / "notes.txt").write_text("unstaged host notes\n")
    (root / "scratch.txt").write_bytes(b"untracked host bytes\x00\n")
    _native_observation(root, output)
    _refuses_without_recording(
        root,
        step,
        output,
        None,
        "OracleBaselineMissing",
        "--baseline",
        captures=captures,
    )
    _refuses_without_recording(
        root,
        step,
        output,
        "0" * 39 + "1",
        "OracleBaselineUnavailable",
        "0" * 39 + "1",
        captures=captures,
    )
    result = _invoke(root, step, output, "oracle", "--baseline", original[:12])
    first = _assert_red(result, root, original, "explicit")
    _success(_invoke(root, step, output, "craft"), "craft")

    # Correct BOTH oracle and support, then bind the current DESIGN without
    # inventing a new baseline or silently continuing with an earlier witness.
    _write_acceptance(root, captures, offset=1)
    result = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--replace-current",
        "--input",
        "-",
        stdin=json.dumps(_manifest(revised=True)),
    )
    _require(
        result[0] == 0,
        f"Current DESIGN correction failed: {result}",
        "The corrected oracle must be measured under its current bound authority.",
        "Use the existing des design --replace-current constructor.",
    )
    _native_observation(root, output)
    corrected = _assert_red(
        _invoke(root, step, output, "oracle"), root, original, "witness"
    )
    _require(
        corrected["acceptance_tree"] != first["acceptance_tree"]
        and corrected["design_sections"] != first["design_sections"],
        f"Corrected acceptance or DESIGN reused stale witness coordinates: {corrected}",
        "Correction must bind current bytes and authority while retaining the original source.",
        "Append a newly measured witness over the current DESIGN and acceptance tree.",
    )
    _success(_invoke(root, step, output, "craft"), "craft")
    overridden = _success(
        _invoke(root, step, output, "oracle", "--baseline", fixed),
        "explicit override",
    )
    _require(
        overridden.get("ORACLE-BASELINE") == f"{fixed} source=explicit"
        and "verdict=green" in overridden.get("ORACLE-RED", ""),
        f"Explicit source did not override earlier original-source witness: {overridden}",
        "The caller's explicit baseline has precedence even when it differs.",
        "Resolve and measure the explicit commit; do not restore the retired conflict gate.",
    )
    _assert_witness(root, fixed, "green", "explicit")
    reused = _success(_invoke(root, step, output, "oracle"), "new witness reuse")
    _require(
        reused.get("ORACLE-BASELINE") == f"{fixed} source=witness"
        and "verdict=green" in reused.get("ORACLE-RED", ""),
        f"Flagless reuse selected an earlier rather than newest baseline: {reused}",
        "The last measured explicit baseline must become the recorded source.",
        "Read the newest usable baseline from the real witness history.",
    )
    _assert_witness(root, fixed, "green", "witness")
    _assert_red(
        _invoke(root, step, output, "oracle", "--baseline", original),
        root,
        original,
        "explicit",
    )
    _assert_red(_invoke(root, step, output, "oracle"), root, original, "witness")
    _recorded_source_failures(root, step, output, captures, original, tmp_path)
    _probe_storage_failure(root, step, output, captures, original)
    observations = [json.loads(line) for line in captures.read_text().splitlines()]
    _require(
        any(
            row["actual"] == 0
            and row["expected"] == 1
            and row["offset"] == 0
            and Path(row["cwd"]) != root
            for row in observations
        )
        and any(
            row["actual"] == 0
            and row["expected"] == 2
            and row["offset"] == 1
            and Path(row["cwd"]) != root
            for row in observations
        )
        and any(
            row["actual"] == 1 and row["expected"] == 2 and Path(row["cwd"]) == root
            for row in observations
        ),
        f"Native captures do not distinguish original/current/corrected execution: {captures}",
        "A RED label alone cannot prove current supports ran over original production.",
        "Run current acceptance in the disposable original checkout and fixed workspace.",
    )


def _base_equal_journey(root: Path, step, tmp_path: Path) -> None:
    captures = tmp_path / "native-base-equal-observations.jsonl"
    output = tmp_path / "public-base-equal-observations.jsonl"
    (root / TARGET).write_text("VALUE = 0\n")
    git(root, "add", TARGET)
    git(root, "commit", "-qm", "clean original source")
    original = git(root, "rev-parse", "HEAD")
    _bind(root, step)
    _write_acceptance(root, captures)
    _native_observation(root, output, expected_exit=1)
    explicit_result = _invoke(root, step, output, "oracle", "--baseline", original)
    entry = _assert_red(explicit_result, root, original, "explicit")
    _assert_measured_semantics(
        block(explicit_result[1], explicit_result[2]), root, entry
    )
    recorded = _assert_red(
        _invoke(root, step, output, "oracle"), root, original, "witness"
    )
    _require(
        recorded["acceptance_tree"] == entry["acceptance_tree"]
        and recorded["revision"] == entry["revision"]
        and recorded["design_sections"] == entry["design_sections"]
        and all(item["verdict"] == "red" for item in recorded["oracles"]),
        "Base-equal measurement changed the acceptance tree.",
        "The same current acceptance over equal production must retain its verdict.",
        "Use the same oracle executor and acceptance identity for explicit and witness sources.",
    )


def test_current_acceptance_measures_original_red_and_admits_fixed_green(
    root: Path,
    step,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    _fixed_head_journey(root, step, tmp_path)


def test_baseline_equal_to_original_source_preserves_native_red_observation(
    root: Path,
    step,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    _base_equal_journey(root, step, tmp_path)


def _native_completion_body(captures: Path, assertion: str) -> str:
    """Report one actual assertion invocation, never a preselected native outcome."""
    return (
        "\nif __name__ == '__main__':\n"
        "    observation = {'version': 1, 'observed': 0, "
        "'assertions_failed': 0, 'setup_failed': 0}\n"
        "    try:\n"
        f"        {assertion}()\n"
        "    except AssertionError:\n"
        "        observation['observed'] = 1\n"
        "        observation['assertions_failed'] = 1\n"
        "        traceback.print_exc()\n"
        "    except Exception:\n"
        "        observation['setup_failed'] = 1\n"
        "        traceback.print_exc()\n"
        "    else:\n"
        "        observation['observed'] = 1\n"
        "    exit_code = int(bool(observation['assertions_failed'] "
        "or observation['setup_failed']))\n"
        f"    with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "        output.write(json.dumps({'cwd': str(pathlib.Path(__file__).resolve()"
        ".parents[2]), 'completed_observation': observation, 'exit': exit_code}) + '\\n')\n"
        "    print('DES-ORACLE-OBSERVATION: ' + json.dumps(observation))\n"
        "    raise SystemExit(exit_code)\n"
    )


def _import_oracle_body(captures: Path, workspace: Path) -> str:
    """Import is inside the test, so absent baseline production is behavioral RED."""
    return (
        "import json\nimport pathlib\nimport runpy\nimport sys\nimport traceback\n\n"
        "def test_original_source_provides_imported_feature():\n"
        "    root = pathlib.Path(__file__).resolve().parents[2]\n"
        "    expected = runpy.run_path(str(root / "
        "'tests/acceptance/support.py'))['EXPECTED']\n"
        # Deliberately reintroduce the foreign source AFTER interpreter startup:
        # isolation must apply at lookup, not only to the initial sys.path.
        f"    sys.path.insert(0, {str(workspace / 'src')!r})\n"
        "    try:\n"
        "        import product_feature\n"
        "    except ModuleNotFoundError as failure:\n"
        f"        with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "            output.write(json.dumps({'cwd': str(root), "
        "'available': False, 'missing': failure.name}) + '\\n')\n"
        "        assert False, (\n"
        "            'WHAT: original source has no imported product_feature. "
        "WHY: baseline acceptance must measure only the original first-party source. "
        "HOW: implement product_feature in the measured source; never borrow the "
        "fixed module from another workspace.')\n"
        f"    with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "        output.write(json.dumps({'cwd': str(root), 'available': True, "
        "'origin': product_feature.__file__, 'actual': product_feature.FEATURE, "
        "'expected': expected}) + '\\n')\n"
        "    assert product_feature.FEATURE == expected, (\n"
        "        'WHAT: imported feature does not satisfy current acceptance. "
        "WHY: workspace craft must retain its normal import environment. "
        "HOW: provide the promised feature through the declared source import.')\n"
    ) + _native_completion_body(
        captures, "test_original_source_provides_imported_feature"
    )


def _bind_imported_value(root: Path, step, native: list[str]) -> None:
    result = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("committed value", "imported feature")],
        stdin=REQUEST,
    )
    _success(result, "imported-feature product construction")
    prior = _facts()
    prior["oracle"] = "tests/acceptance/test_prior_value.py"
    prior["verification"] = [[PYTHON, "-m", "pytest", prior["oracle"]]]
    imported = _facts()
    imported["purpose"] = observation("imported feature")
    imported["targets"] = [
        {
            "path": "src/product_feature.py",
            "decision": "CREATE_NEW",
            "reason": "The original commit does not contain the imported first-party module.",
        }
    ]
    imported["decisions"] = [
        "Import resolution must observe only the original first-party source.",
    ]
    imported["reuse_analysis"] = {
        "candidates": [
            {
                "symbol": "product_feature",
                "locator": "src/product_feature.py:1",
                "decision": "CREATE_NEW",
                "reason": "The original source has no owner for this imported feature.",
            }
        ],
    }
    imported["verification"] = [native]
    imported["public_oracle"] = {
        "observation": "Current acceptance imports the feature only from the measured source.",
        "stimulus": "Import product_feature through the declared native interpreter.",
        "expected": "Original source is RED while implemented workspace and craft are GREEN.",
        "falsifier": "Baseline imports the implemented module through foreign workspace roots.",
    }
    # Both values repeat the fixture's absent-section reasons: the shared DESIGN
    # defines that meaning once and each value references it.
    shared = design_manifest(prior, observation("committed value"), 0)
    _success(
        step(
            "design",
            "--repo-root",
            str(root),
            "--shared",
            "--input",
            "-",
            stdin=json.dumps(shared),
        ),
        "imported-feature shared DESIGN construction",
    )
    manifests = (
        referencing_manifest(prior, observation("committed value"), 1, shared),
        referencing_manifest(imported, observation("imported feature"), 2, shared),
    )
    for position, manifest in enumerate(manifests, start=1):
        result = step(
            "design",
            "--repo-root",
            str(root),
            "--value",
            str(position),
            "--input",
            "-",
            stdin=json.dumps(manifest),
        )
        _success(result, f"imported-feature DESIGN construction for value {position}")


def _import_runtime(
    root: Path,
    editable_site: bool,
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Keep installed pytest external; inject source roots through the selected real route."""
    tooling = sysconfig.get_path("purelib")
    _require(
        (Path(tooling) / "pytest").is_dir(),
        f"The declared host runtime has no installed pytest at {tooling}",
        "The import isolation oracle must establish tooling before behavioral RED.",
        "Run this oracle with the DESIGN-selected .venv interpreter and installed dependencies.",
    )
    environment = {
        key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    native = list(NATIVE)
    path_hashes = {}
    if editable_site:
        virtualenv = root / ".venv"
        venv.EnvBuilder(system_site_packages=True, with_pip=False).create(virtualenv)
        sites = [
            Path(path)
            for path in site.getsitepackages([str(virtualenv)])
            if Path(path).is_dir()
        ]
        _require(
            bool(sites) and (virtualenv / "bin" / "python").is_file(),
            f"The fixture has no real declared virtualenv/site-packages: {virtualenv}",
            "Candidate execution needs a linkable subject environment, not a missing argv.",
            "Create the declared --system-site-packages --without-pip environment.",
        )
        pth = sites[0] / "_editable_impl_fixture.pth"
        pth.write_text(f"{root}\n{root / 'src'}\n{tooling}\n")
        for path in (pth, virtualenv / "pyvenv.cfg"):
            path_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        native[0] = ".venv/bin/python"
        environment["PYTHONPATH"] = tooling
    else:
        environment["PYTHONPATH"] = os.pathsep.join(
            (str(root / "src"), str(root), tooling)
        )
    return native, environment, path_hashes


def _imported_source_journey(  # noqa: PLR0913 - one public source contrast shares its runtime and fixture context
    root: Path,
    step,
    tmp_path: Path,
    *,
    editable_site: bool,
    isolated_startup: bool = False,
    script_observation: bool = False,
    receipt_fault: ReceiptFault | None = None,
) -> None:
    captures = tmp_path / "native-import-observations.jsonl"
    output = tmp_path / "public-import-observations.jsonl"
    (root / ".gitignore").write_text(".venv/\n")
    (root / TARGET).write_text("VALUE = 1\n")
    (root / "notes.txt").write_text("original import notes\n")
    git(root, "add", ".gitignore", TARGET, "notes.txt")
    git(root, "commit", "-qm", "original source lacks imported feature")
    original = git(root, "rev-parse", "HEAD")
    feature = root / "src" / "product_feature.py"
    feature.parent.mkdir()
    feature.write_text("FEATURE = 1\n")
    git(root, "add", "src/product_feature.py")
    git(root, "commit", "-qm", "imported feature already committed")
    fixed = git(root, "rev-parse", "HEAD")
    _write_acceptance(root, captures)
    (root / ORACLE).write_text(_import_oracle_body(captures, root))
    (root / "tests/acceptance/test_prior_value.py").write_text(_oracle_body(captures))
    native, environment, path_hashes = _import_runtime(root, editable_site)
    if receipt_fault is not None:
        for name in (
            "NWAVE_ORACLE_GUARD_DIR",
            "NWAVE_ORACLE_GUARD_RECEIPTS",
            "NWAVE_ORACLE_GUARD_NONCE",
        ):
            environment.pop(name, None)
        child_python = root / ".venv/bin/python"
        if receipt_fault is ReceiptFault.REFUSED:
            child_python, child_hashes = _refusing_child_runtime(root)
            path_hashes.update(child_hashes)
        (root / ORACLE).write_text(
            _receipt_oracle_body(captures, receipt_fault, child_python)
        )
        native = [native[0], ORACLE]
    if isolated_startup:
        native.insert(1, "-I")
        if script_observation:
            native = [native[0], "-I", ORACLE]
    _bind_imported_value(root, step, native)
    (root / "notes.txt").write_text("dirty import notes\n")
    (root / "scratch.txt").write_text("untracked import notes\n")
    _native_observation(root, output, argv=native, environment=environment)
    host_pythonpath_before = os.environ.get("PYTHONPATH")

    def public_step(*argv: str, stdin: str = ""):
        # This is only the existing protocol driver, with explicit ambient
        # input. The shared stepper intentionally replaces ambient PYTHONPATH.
        return run_cli_in_process(
            list(argv),
            cwd=root,
            env=environment,
            stdin_text=stdin,
            catch_all=True,
        )

    if receipt_fault is not None:
        rejected = _refuses_without_recording(
            root,
            public_step,
            output,
            original,
            "OracleProbeUnavailable",
            position=2,
            disposition="Indeterminate",
        )
        why = block(rejected[1], rejected[2])["WHY"].lower()
        defect = "refused" if receipt_fault is ReceiptFault.REFUSED else "nonce"
        _require(
            defect in why,
            f"Isolation refusal did not name the actual {receipt_fault.value} defect: {why}",
            "An unrelated missing-startup or report error cannot satisfy this receipt alternative.",
            "Explain the authentic refused or foreign-nonce receipt that invalidated admission.",
        )
    elif isolated_startup:
        _refuses_without_recording(
            root,
            public_step,
            output,
            original,
            "OracleProbeUnavailable",
            ".venv/bin/python",
            "-I",
            position=2,
            disposition="Indeterminate",
        )
    else:
        entry = _assert_red(
            _invoke(
                root,
                public_step,
                output,
                "oracle",
                "--baseline",
                original,
                position=2,
            ),
            root,
            original,
            "explicit",
        )
        _require(
            entry["oracles"][0]["counts"] == [1, 0, 1],
            f"Missing imported production did not reach the one behavioral assertion: {entry}",
            "A tooling, collection or setup error cannot establish original-source RED.",
            "Import inside the test body and fail the absent first-party capability explicitly.",
        )
        _success(
            _invoke(root, public_step, output, "craft", position=2),
            "imported-feature craft",
        )
        equal_base = _success(
            _invoke(
                root, public_step, output, "oracle", "--baseline", fixed, position=2
            ),
            "fixed-source import measurement",
        )
        _require(
            equal_base.get("ORACLE-BASELINE") == f"{fixed} source=explicit"
            and "verdict=green" in equal_base.get("ORACLE-RED", ""),
            f"Late workspace import roots could not resolve existing measured production: {equal_base}",
            "Isolation must remap existing first-party source, not refuse every late import.",
            "Resolve the feature from the fixed measuring checkout while excluding foreign origins.",
        )
        _assert_witness(root, fixed, "green", "explicit")
    after_hashes = {
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in path_hashes
    }
    with output.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "import_route": "editable-site" if editable_site else "ambient",
                    "isolated_startup": isolated_startup,
                    "script_observation": script_observation,
                    "receipt_fault": receipt_fault.value
                    if receipt_fault is not None
                    else None,
                    "declared_pythonpath": environment["PYTHONPATH"],
                    "host_pythonpath_before": host_pythonpath_before,
                    "host_pythonpath_after": os.environ.get("PYTHONPATH"),
                    "environment_hashes_before": path_hashes,
                    "environment_hashes_after": after_hashes,
                }
            )
            + "\n"
        )
    _require(
        os.environ.get("PYTHONPATH") == host_pythonpath_before
        and after_hashes == path_hashes,
        f"Baseline measurement changed the subject's import inputs; captures: {output}",
        "Isolation is invocation-local; craft must retain shared tooling and .pth bytes.",
        "Filter foreign source access in the measuring process, never rewrite the subject venv.",
    )
    observations = [json.loads(line) for line in captures.read_text().splitlines()]
    _require(
        (
            isolated_startup
            or receipt_fault is not None
            or any(
                row.get("available") is False
                and row.get("missing") == "product_feature"
                and Path(row["cwd"]) != root
                for row in observations
            )
        )
        and any(
            row.get("available") is True
            and row.get("actual") == 1
            and Path(row["cwd"]) == root
            and Path(row["origin"]) == feature
            for row in observations
        ),
        f"Native observations do not distinguish absent baseline from workspace import: {captures}",
        "An absolute runpy fixture cannot expose first-party import fallthrough.",
        "Measure the missing module through actual Python import resolution, then workspace craft.",
    )
    if not isolated_startup and receipt_fault is None:
        _require(
            any(
                row.get("available") is True
                and row.get("actual") == 1
                and Path(row["cwd"]) != root
                and Path(row["origin"]).resolve()
                == (Path(row["cwd"]) / "src/product_feature.py").resolve()
                for row in observations
            ),
            f"Fixed-source GREEN borrowed the subject module rather than remapping: {captures}",
            "Late workspace paths must resolve existing first-party code from the measuring checkout.",
            "Rebase import origins onto the selected tree, including runtime sys.path insertions.",
        )
    if script_observation:
        passed = {
            "version": 1,
            "observed": 1,
            "assertions_failed": 0,
            "setup_failed": 0,
        }
        _require(
            any(
                row.get("completed_observation") == passed
                and row.get("exit") == 0
                and Path(row["cwd"]) == root
                for row in observations
            )
            and any(
                row.get("available") is True
                and row.get("actual") == 1
                and Path(row["cwd"]) == root
                and Path(row["origin"]) == feature
                for row in observations
            ),
            f"Independent workspace control did not complete native GREEN: {captures}",
            "Missing pytest instrumentation must not be the reason the receipt refusal is satisfied.",
            "Run the real workspace assertion directly; permit DES to refuse before candidate execution.",
        )
    if receipt_fault is not None:
        _assert_authentic_receipt_pair(observations, receipt_fault, root)


@pytest.mark.parametrize(
    "editable_site",
    [False, True],
    ids=["ambient-workspace-roots", "editable-workspace-roots"],
)
def test_original_source_cannot_import_new_workspace_feature(
    root: Path,
    step,
    tmp_path: Path,
    editable_site: bool,
) -> None:
    _imported_source_journey(root, step, tmp_path, editable_site=editable_site)


def test_baseline_without_guard_startup_refuses_instead_of_recording_a_verdict(
    root: Path,
    step,
    tmp_path: Path,
) -> None:
    _imported_source_journey(
        root,
        step,
        tmp_path,
        editable_site=True,
        isolated_startup=True,
    )


def test_completed_native_green_without_guard_receipt_is_not_admitted(
    root: Path,
    step,
    tmp_path: Path,
) -> None:
    _imported_source_journey(
        root,
        step,
        tmp_path,
        editable_site=True,
        isolated_startup=True,
        script_observation=True,
    )


def _refusing_child_runtime(root: Path) -> tuple[Path, dict[str, str]]:
    """A separate ordinary child venv preloads foreign production before the copied guard."""
    child = root / ".venv/refusing-child"
    venv.EnvBuilder(system_site_packages=True, with_pip=False).create(child)
    sites = [
        Path(path) for path in site.getsitepackages([str(child)]) if Path(path).is_dir()
    ]
    _require(
        bool(sites) and (child / "bin/python").is_file(),
        f"The refusing child has no real interpreter/site-packages: {child}",
        "The fault must come from an ordinary guarded interpreter, not missing runtime setup.",
        "Create the separate declared child environment before the native workspace control.",
    )
    source_paths = sites[0] / "_fixture_sources.pth"
    source_paths.write_text(
        f"{root}\n{root / 'src'}\n{sysconfig.get_path('purelib')}\n"
    )
    preload = sites[0] / "_fixture_preload.pth"
    preload.write_text(
        f"import sys; sys.path.insert(0, {str(root / 'src')!r}); import product_feature\n"
    )
    hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (source_paths, preload, child / "pyvenv.cfg")
    }
    return child / "bin/python", hashes


def _receipt_oracle_body(
    captures: Path, fault: ReceiptFault, child_python: Path
) -> str:
    """The native assertion reads receipts written by the real copied guard, never writes them."""
    child_program = (
        "import json, os\n"
        "if os.environ.get('NWAVE_ORACLE_GUARD_RECEIPTS'):\n"
        "    print(json.dumps({'started': True}))\n"
        "else:\n"
        "    import product_feature\n"
        "    print(json.dumps({'available': True, 'actual': product_feature.FEATURE, "
        "'origin': product_feature.__file__}))\n"
    )
    return (
        "import json\nimport os\nimport pathlib\nimport subprocess\nimport traceback\n\n"
        "def test_ordinary_child_produces_authentic_startup_evidence():\n"
        "    root = pathlib.Path(__file__).resolve().parents[2]\n"
        "    expected_nonce = os.environ.get('NWAVE_ORACLE_GUARD_NONCE')\n"
        "    receipt_dir = os.environ.get('NWAVE_ORACLE_GUARD_RECEIPTS')\n"
        "    environment = dict(os.environ)\n"
        f"    fault = {fault.value!r}\n"
        "    if receipt_dir and fault == 'foreign-nonce-child':\n"
        "        environment['NWAVE_ORACLE_GUARD_NONCE'] = "
        "('0' if expected_nonce[0] != '0' else '1') + expected_nonce[1:]\n"
        f"    child = subprocess.Popen([{str(child_python)!r}, '-c', {child_program!r}],\n"
        "        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)\n"
        "    stdout, stderr = child.communicate()\n"
        "    if receipt_dir:\n"
        "        receipts = pathlib.Path(receipt_dir)\n"
        "        parent_receipt = json.loads((receipts / f'{os.getpid()}.json').read_text())\n"
        "        child_receipt = json.loads((receipts / f'{child.pid}.json').read_text())\n"
        "        evidence = {'cwd': str(root), 'receipt_fault': fault,\n"
        "            'parent_pid': os.getpid(), 'child_pid': child.pid,\n"
        "            'expected_nonce': expected_nonce, 'parent_receipt': parent_receipt,\n"
        "            'child_receipt': child_receipt, 'child_exit': child.returncode,\n"
        "            'child_stdout': stdout, 'child_stderr': stderr}\n"
        f"        with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "            output.write(json.dumps(evidence) + '\\n')\n"
        "        assert parent_receipt['status'] == 'armed' and "
        "parent_receipt['nonce'] == expected_nonce, (\n"
        "            'WHAT: the ordinary parent is not authentically armed. "
        "WHY: a missing-parent gate cannot distinguish mixed receipt admission. "
        "HOW: run the ordinary parent under the copied startup guard.')\n"
        "        if fault == 'refused-child':\n"
        "            assert child.returncode == 3 and child_receipt['status'] == 'refused' "
        "and child_receipt['nonce'] == expected_nonce, (\n"
        "                'WHAT: the preloaded foreign child did not produce a real refused receipt. "
        "WHY: admission must reject refusal even beside valid armed evidence. "
        "HOW: preserve the real guard refusal for the foreign preloaded module.')\n"
        "        else:\n"
        "            assert child.returncode == 0 and child_receipt['status'] == 'armed' "
        "and child_receipt['nonce'] != expected_nonce, (\n"
        "                'WHAT: the ordinary child did not arm under its different invocation nonce. "
        "WHY: a valid parent must not mask mismatched child provenance. "
        "HOW: retain both authentic startup receipts and check every invocation identity.')\n"
        "    else:\n"
        "        assert child.returncode == 0, (\n"
        "            'WHAT: healthy workspace child failed. WHY: tooling failure is not receipt evidence. "
        "HOW: provide the ordinary child interpreter and its real fixture source paths.')\n"
        "        imported = json.loads(stdout.strip())\n"
        "        assert imported['actual'] == 1, (\n"
        "            'WHAT: workspace feature is not implemented. WHY: the control must be native GREEN. "
        "HOW: retain the committed FEATURE=1 control source.')\n"
        f"        with pathlib.Path({str(captures)!r}).open('a') as output:\n"
        "            output.write(json.dumps({'cwd': str(root), **imported}) + '\\n')\n"
    ) + _native_completion_body(
        captures, "test_ordinary_child_produces_authentic_startup_evidence"
    )


def _assert_authentic_receipt_pair(
    observations: list[dict],
    fault: ReceiptFault,
    workspace: Path,
) -> None:
    pairs = [row for row in observations if row.get("receipt_fault") == fault.value]
    _require(
        bool(pairs),
        f"No authentic {fault.value} receipt pair was observed.",
        "Missing guard startup alone cannot falsify accepting any available armed receipt.",
        "Run the ordinary armed parent and its real guarded child before receipt admission.",
    )
    passed = {"version": 1, "observed": 1, "assertions_failed": 0, "setup_failed": 0}
    for pair in pairs:
        parent = pair["parent_receipt"]
        child = pair["child_receipt"]
        expected_nonce = pair["expected_nonce"]
        child_bad = (
            child.get("status") == "refused" and child.get("nonce") == expected_nonce
            if fault is ReceiptFault.REFUSED
            else child.get("status") == "armed" and child.get("nonce") != expected_nonce
        )
        _require(
            parent.get("status") == "armed"
            and parent.get("nonce") == expected_nonce
            and pair["parent_pid"] != pair["child_pid"]
            and child_bad
            and Path(pair["cwd"]) != workspace
            and any(
                row.get("completed_observation") == passed
                and row.get("exit") == 0
                and row["cwd"] == pair["cwd"]
                for row in observations
            ),
            f"The observed startup population did not contain the required valid/bad pair: {pair}",
            "Receipt refusal must win even when an ordinary parent completed valid native assertions.",
            "Inspect both real guard-produced receipts, then reject any refused or mismatched nonce.",
        )


@pytest.mark.parametrize(
    "fault",
    [ReceiptFault.REFUSED, ReceiptFault.FOREIGN_NONCE],
    ids=["refused-child-with-armed-parent", "foreign-nonce-child-with-armed-parent"],
)
def test_invalid_child_receipt_cannot_be_admitted_beside_valid_parent_receipt(
    root: Path,
    step,
    tmp_path: Path,
    fault: ReceiptFault,
) -> None:
    _imported_source_journey(
        root,
        step,
        tmp_path,
        editable_site=True,
        receipt_fault=fault,
    )
