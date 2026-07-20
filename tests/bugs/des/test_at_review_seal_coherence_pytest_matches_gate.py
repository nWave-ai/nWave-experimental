"""Regression (bugfix at-review-seal-coherence): the AT seal PRODUCER (``des
record-at-review-verdict``, ``at_review_verdict.py::_slice_at_derivation``)
and the AT seal CONSUMER (``carpaccio_slice_gate.py``'s assertion 5,
``_check_verdict_record``) must derive the IDENTICAL ``(at_ids,
at_content_hash)`` pair for the SAME slice, for BOTH ``at_kind`` values --
otherwise a genuinely APPROVED review permanently reads as seal-stale.

RCA (grounded [read-in-code], both defects live in ``_slice_at_derivation``,
``src/des/cli/at_review_verdict.py``):

Defect A -- ``at_kind="gherkin"`` (default), zero scenarios tagged
``@{slice_id}`` (the slice's ATs are pytest ``test_*.py``, no ``.feature``
file at all): ``_slice_at_derivation`` silently computes
``_at_content_hash([])`` = ``sha256("")`` = the well-known
``e3b0c44298fc1c...`` digest, and WRITES an APPROVED ``ATReviewVerdict``
record carrying that empty-string hash -- a GDP-6 silent-wrong: an
unparseable/empty AT set looks like a validly-sealed empty one instead of
refusing loud. The gate's OWN assertion-1 (`check_carpaccio`) already refuses
this exact condition loud via ``_no_scenarios_rejection`` -- the producer
never consulted it.

Defect B -- ``at_kind="pytest-regression"`` with a regression file SHARED
across >1 slice (a predecessor slice already attested some of its
``test_*`` functions via the ledger): the producer's ``at_count`` came from
``carpaccio_format.count_pytest_regression_ats`` (the file's WHOLE-FILE AST
count), while the gate's ``_check_verdict_record`` (assertion 5) and
``check_carpaccio`` (assertion 1) both call
``carpaccio_format.count_net_new_pytest_regression_ats`` (the count minus
whatever total is already attested to OTHER slices in the AT-completion
ledger) for the SAME regression file. A shared file's second-or-later slice
therefore seals an ``at_ids`` set (``AT-1..AT-{whole_file}``) the gate can
NEVER match (``AT-1..AT-{net_new}``) -- permanent ``stale-at-set``,
regardless of how many times the reviewer re-approves.

THE FIX (this commit): ``_slice_at_derivation`` now (1) calls
``count_net_new_pytest_regression_ats`` -- the SAME function the gate calls
-- for the pytest-regression AT count, and (2) raises the gate's own
``_no_scenarios_rejection`` GateError when the gherkin scenario set for the
slice is empty, instead of sealing ``sha256("")``.

Driving surface (Mandate 13 driving-port-only): the REAL
``des.cli.at_review_verdict.main`` CLI EDGE followed by the REAL
``des.cli.carpaccio_slice_gate.main`` CLI EDGE, both driven in-process via
``tests.common.in_process_cli.run_cli_in_process`` against an isolated
``tmp_path`` repo -- proving record-then-gate coherence end-to-end, never a
re-derivation of the two hashes in the test itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli.at_review_verdict import main as record_verdict_main
from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "at-review-seal-coherence-fixture"


def _feature_delta(rows: list[tuple[str, str]]) -> str:
    header = (
        "# Feature Delta: AT-review seal coherence fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
    )
    body = "".join(
        f"| {slice_id} | {value} | pending | | |\n" for slice_id, value in rows
    )
    return header + body


def _make_repo(tmp_path: Path, plan_rows: list[tuple[str, str]]) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        _feature_delta(plan_rows), encoding="utf-8"
    )
    return repo


def _record_verdict(repo: Path, argv: list[str]) -> tuple[int, str, str]:
    return run_cli_in_process(argv, cwd=repo, main=record_verdict_main)


def _run_gate(repo: Path, argv: list[str]) -> tuple[int, dict[str, object]]:
    exit_code, stdout, _stderr = run_cli_in_process(
        argv, cwd=repo, main=carpaccio_gate_main
    )
    payload: dict[str, object] = next(
        (
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ),
        {},
    )
    return exit_code, payload


# ---------------------------------------------------------------------------
# 1. pytest-regression, a SHARED regression file across slices (Defect B):
#    record-at-review-verdict's net-new at_ids must match what the gate
#    expects, so the entering slice's genuinely-APPROVED verdict clears.
# ---------------------------------------------------------------------------

_PREDECESSOR_2_ATS = "".join(
    f"def test_predecessor_slice_01_at_{n:02d}():\n    assert True\n\n\n"
    for n in range(1, 3)
)
_SLICE_02_ONE_NEW_AT = "def test_slice_02_rejects_invalid_input():\n    assert True\n"


def test_pytest_regression_shared_file_record_matches_gate_expectation(
    tmp_path: Path,
) -> None:
    """POSITIVE AT: slice-02 adds exactly ONE new ``test_*`` to a regression
    file that already carries 2 ATs attested to predecessor slice-01. Once
    ``des record-at-review-verdict --at-kind pytest-regression`` APPROVES
    slice-02, the SAME slice must clear ``carpaccio-slice-gate``'s assertion
    5 (exit 0, ``SliceCleared``) -- proving the producer's net-new
    ``at_ids``/``at_content_hash`` are exactly what the gate expects.

    Before the fix: the producer sealed ``at_ids=[AT-1, AT-2, AT-3]`` (the
    file's whole-file total) while the gate expects ``at_ids=[AT-1]``
    (net-new) -- a permanent ``stale-at-set`` rejection (exit 45) no
    re-approval could ever clear.
    """
    regression_rel = "tests/regression/test_shared_slice_ats.py"
    repo = _make_repo(
        tmp_path,
        plan_rows=[
            ("slice-01", "Predecessor slice already attested"),
            ("slice-02", "Entering slice adds exactly one new AT"),
        ],
    )
    regression_file = repo / regression_rel
    regression_file.parent.mkdir(parents=True, exist_ok=True)
    regression_file.write_text(_PREDECESSOR_2_ATS, encoding="utf-8")

    exit_code, _stdout, stderr = _record_verdict(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            "slice-01",
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_rel,
        ],
    )
    assert exit_code == 0, f"predecessor slice-01 verdict recording failed: {stderr!r}"

    regression_file.write_text(
        _PREDECESSOR_2_ATS + _SLICE_02_ONE_NEW_AT, encoding="utf-8"
    )

    exit_code, _stdout, stderr = _record_verdict(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            "slice-02",
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_rel,
        ],
    )
    assert exit_code == 0, f"entering slice-02 verdict recording failed: {stderr!r}"

    gate_exit_code, gate_payload = _run_gate(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            "slice-02",
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_rel,
        ],
    )

    assert gate_exit_code == 0 and gate_payload.get("event") == "SliceCleared", (
        "slice-02's genuinely-APPROVED verdict (1 net-new AT on a shared "
        f"file) was rejected by the gate: exit_code={gate_exit_code} "
        f"payload={gate_payload}. The producer's net-new at_ids/content-hash "
        "must equal the gate's own net-new derivation -- see this module's "
        "docstring (Defect B) for the whole-file-vs-net-new root cause."
    )


# ---------------------------------------------------------------------------
# 2. gherkin, no-overcorrection guard: a real scenario set still records and
#    clears (parity pin -- the gherkin path was already coherent).
# ---------------------------------------------------------------------------


def _write_gherkin_scenario(feature_file_path: Path, feature_id: str) -> None:
    feature_file_path.parent.mkdir(parents=True, exist_ok=True)
    feature_file_path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: Customer checkout\n\n"
        "  @slice-01 @walking_skeleton @driving_port\n"
        "  Scenario: Customer completes checkout and sees confirmation\n"
        "    Given customer has a valid payment method on file\n"
        "    When customer completes checkout\n"
        "    Then customer sees order confirmation\n",
        encoding="utf-8",
    )


def test_gherkin_record_matches_gate_expectation(tmp_path: Path) -> None:
    """POSITIVE AT (parity/no-regression pin): a real ``.feature`` scenario
    still records and clears the gate end-to-end -- the fix must not disturb
    the already-coherent gherkin round trip when scenarios ARE present.
    """
    repo = _make_repo(tmp_path, plan_rows=[("slice-01", "checkout confirmation")])
    _write_gherkin_scenario(
        repo / "tests" / "acceptance" / _FEATURE_ID / "slice-01.feature", _FEATURE_ID
    )

    exit_code, _stdout, stderr = _record_verdict(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            "slice-01",
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--repo-root",
            str(repo),
        ],
    )
    assert exit_code == 0, f"gherkin verdict recording failed: {stderr!r}"

    gate_exit_code, gate_payload = _run_gate(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            "slice-01",
            "--repo-root",
            str(repo),
        ],
    )

    assert gate_exit_code == 0 and gate_payload.get("event") == "SliceCleared", (
        "a real gherkin scenario's APPROVED verdict must clear the gate -- "
        f"exit_code={gate_exit_code} payload={gate_payload}"
    )


# ---------------------------------------------------------------------------
# 3. GDP-6: an empty gherkin scenario set must refuse loud, never seal a
#    silent sha256("") as an APPROVED review (Defect A).
# ---------------------------------------------------------------------------


def test_gherkin_empty_scenario_set_refuses_loud_not_silent_empty_hash(
    tmp_path: Path,
) -> None:
    """POSITIVE AT: a slice whose ATs are pytest ``test_*.py`` (no
    ``.feature`` file at all) recorded WITHOUT ``--at-kind pytest-
    regression`` must be REFUSED (non-zero exit, no ledger write) -- never
    silently sealed with ``at_content_hash=sha256("")`` as if an empty AT
    set were a legitimately-reviewed one.
    """
    repo = _make_repo(tmp_path, plan_rows=[("slice-01", "pytest-only slice")])
    # Deliberately no `.feature` file anywhere for this feature.

    exit_code, stdout, stderr = _record_verdict(
        repo,
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            "slice-01",
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--repo-root",
            str(repo),
        ],
    )

    assert exit_code != 0, (
        "recording an APPROVED verdict for a slice with ZERO gherkin "
        "scenarios (and no --at-kind pytest-regression) must be REFUSED -- "
        f"got exit_code=0, stdout={stdout!r}, stderr={stderr!r}. Before the "
        "fix this silently wrote an APPROVED record with "
        "at_content_hash=sha256('')."
    )
    combined = stdout + stderr
    assert "no-scenarios-for-slice" in combined, (
        "the refusal must name the SAME 'no-scenarios-for-slice' reason the "
        f"gate's own assertion-1 uses -- got: {combined!r}"
    )

    ledger_path = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    if ledger_path.exists():
        lines = [
            line
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert not any(
            json.loads(line).get("event") == "ATReviewVerdict"
            and json.loads(line).get("at_content_hash")
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            for line in lines
        ), "no ATReviewVerdict record may carry the silent sha256('') seal"
