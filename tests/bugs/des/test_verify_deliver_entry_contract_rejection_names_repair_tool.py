"""Regression: DELIVER-entry contract-freeze rejections must name a HOW, not
just a WHAT + WHY.

DEFECT (GDP-3/GDP-4, the standing what/why/how rule): the two rejection
branches in ``src/des/cli/verify_deliver_entry_contract.py`` name WHAT failed
and cite the ADR/DDD WHY, but carry NO actionable HOW -- no command the
operator can run to close the gap:

  * ``_evaluate_structural`` (missing-section branch, ~line 193-200) --
    "is MISSING locked section(s) [...] every named [REF] section [...] must
    be present for the contract to freeze." Never routes to the one-pass gap
    tool that already exists for exactly this: ``des feature-delta-doctor
    <feature-delta-path>`` (``src/des/cli/feature_delta_doctor.py``).
  * ``_fold_code_design_manifest`` (invalid-manifest branch, ~line 291-298) --
    names the manifest path + the validator's raw exit-code detail, but the
    detail comes from a subprocess whose own diagnostic may not spell out the
    concrete repair (update the manifest's ``sut:`` symbol / re-run the
    manifest validator).

This AT pins the missing-section branch (the FIRST, most common rejection
class): the diagnostic must contain the routing string ``des
feature-delta-doctor`` so the operator can go run the producing tool instead
of re-deriving the gap by hand.

Driving surface (Mandate 16 -- driving-port-only): the REAL ``des
verify-deliver-entry-contract`` gate, driven in-process via the shared
``tests/common/in_process_cli.run_cli_in_process`` -- the in-process analogue
of ``python -m des.cli.__main__ verify-deliver-entry-contract ...`` (reuses
the exact driving surface + fixture conventions already established in
``tests/des/acceptance/f_deliver_entry_contract_freeze/steps/composition.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


_FEATURE_ID = "f-deliver-entry-doctor-routing-fixture"
_ROUTING_TOOL = "des feature-delta-doctor"

# The four DDD-1 locked [REF] sections, rendered verbatim (same shape as the
# established `ContractFreezeComposition._render_feature_delta` fixture).
_SLICE_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | A thin DELIVER-IN vertical. | pending | "
    "@walking-skeleton @driving_port | ~4 ATs. |\n"
)
_ARCH_TESTS = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\n"
    "| ID | Contract | SUT | Verdict | Consumed-by |\n"
    "|----|----------|-----|---------|-------------|\n"
    "| CT-1 | a contract is frozen | x::main | FAIL | DISTILL |\n"
)
_ADR_REFS = "## Wave: DESIGN / [REF] ADR Refs\n\n- slice-01: ADR-FLOW-004\n"
_REUSE_ANALYSIS = (
    "## Reuse Analysis\n\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|--------------------|------|---------|----------|---------------|\n"
    "| gate | x.py | none | CREATE_NEW | new gate. |\n"
)


def _write_feature_delta(repo_root: Path, *, drop_reuse_analysis: bool) -> None:
    """A feature-delta with all 4 locked sections, optionally dropping one."""
    feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    sections = [_ARCH_TESTS, _ADR_REFS, _SLICE_PLAN]
    if not drop_reuse_analysis:
        sections.append(_REUSE_ANALYSIS)
    header = f"# Feature Delta: {_FEATURE_ID}\n\n"
    (feature_dir / "feature-delta.md").write_text(
        header + "\n".join(sections) + "\n", encoding="utf-8"
    )


def _write_slice_01_at_module(repo_root: Path) -> None:
    """A `.feature` binding slice-01 to an AT (the `feature_tag_files` resolution)."""
    at_dir = repo_root / "tests" / "acceptance" / _FEATURE_ID.replace("-", "_")
    at_dir.mkdir(parents=True, exist_ok=True)
    (at_dir / "slice-01.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: the slice-01 walking skeleton\n\n"
        "  @slice-01 @walking_skeleton @driving_port\n"
        "  Scenario: the thin vertical is exercised\n"
        "    Given a structurally-complete contract\n"
        "    When the freeze gate runs\n"
        "    Then the contract is frozen\n",
        encoding="utf-8",
    )


def _run_freeze_gate(repo_root: Path) -> dict[str, object]:
    """Drive the REAL `des verify-deliver-entry-contract` gate in-process."""
    _exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-deliver-entry-contract",
            "--feature-id",
            _FEATURE_ID,
            "--repo-root",
            str(repo_root),
            "--format=json",
        ],
        cwd=repo_root,
    )
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        return json.loads(line)
    raise AssertionError(
        f"no JSON verdict envelope on stdout -- stdout={stdout!r} stderr={stderr!r}"
    )


def test_missing_locked_section_rejection_names_feature_delta_doctor(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a feature-delta MISSING a locked [REF]
    section is REJECTED, and the rejection diagnostic must ROUTE the operator
    to the producing gap-report tool (`des feature-delta-doctor`).

    ACTIVE-RED today: the diagnostic names the missing section ('Reuse
    Analysis') and cites the locked-section contract, but never mentions
    `des feature-delta-doctor` -- there is no HOW an operator can act on
    without re-deriving the gap by hand.
    """
    _write_feature_delta(tmp_path, drop_reuse_analysis=True)
    seed_dev_checkout_marker(tmp_path)

    envelope = _run_freeze_gate(tmp_path)

    assert envelope["verdict"] == "fail", (
        f"a feature-delta missing a locked [REF] section must FAIL -- got "
        f"verdict={envelope['verdict']!r}, diagnostic={envelope['diagnostic']!r}"
    )
    diagnostic = str(envelope["diagnostic"])
    assert _ROUTING_TOOL in diagnostic, (
        f"the missing-section rejection names WHAT failed and WHY "
        f"({diagnostic!r}) but carries no actionable HOW -- it must route the "
        f"operator to the producing tool ({_ROUTING_TOOL!r}, the one-pass "
        f"gap-report CLI already shipped at "
        f"src/des/cli/feature_delta_doctor.py) so the gap can be closed "
        f"without re-deriving it by hand."
    )


@pytest.mark.negative_at
def test_structurally_complete_feature_delta_is_not_rejected_and_never_names_doctor(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): a
    structurally-COMPLETE feature-delta (all 4 locked sections + a valid
    Slice Plan + an authored AT module for the one planned slice) is NOT
    rejected, and its diagnostic never spuriously mentions the doctor routing
    string on a well-formed input -- proving the routing-string fix is scoped
    to the FAIL branch only, never leaking onto a PASS.
    """
    _write_feature_delta(tmp_path, drop_reuse_analysis=False)
    _write_slice_01_at_module(tmp_path)
    seed_dev_checkout_marker(tmp_path)

    envelope = _run_freeze_gate(tmp_path)

    assert envelope["verdict"] == "pass", (
        f"a structurally-complete feature-delta must PASS -- got "
        f"verdict={envelope['verdict']!r}, diagnostic={envelope['diagnostic']!r}"
    )
    assert str(envelope["diagnostic"]) == "", (
        f"a PASS carries an empty diagnostic -- got "
        f"diagnostic={envelope['diagnostic']!r}"
    )
    assert _ROUTING_TOOL not in str(envelope["diagnostic"]), (
        "a PASSing contract must never spuriously mention the doctor routing "
        "tool -- the routing string belongs to the FAIL diagnostic only."
    )
