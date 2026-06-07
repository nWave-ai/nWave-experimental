"""Step definitions -- slice-01: feature-scoped contract gate + non-vacuity floor.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE slice-01. Layer 3 (subprocess / FS
acceptance): the run_contract_gate CLI with --feature-id is the driving port;
the real filesystem is the only driven port. Example-based sad paths
(Mandate 11) -- the M-1/M-8 non-vacuity floor is an enumerated Scenario Outline,
not a Hypothesis @given (Mandate 9, layer 3).

The walking-skeleton happy path authors a GENUINELY collectable pytest-bdd
slice (a .feature file + bound test module + step module) so that "the gate
passes when the feature genuinely collects >= 1 node-id for the entering slice"
is a true, witnessed claim -- not a tag-presence proxy (the W2/W4/W6 non-vacuity
contract). A multi-file row exercises the gate's slice-tag UNION across all of
a feature's .feature files (C3).

Shares ``CarpaccioSpineComposition`` (Pillar 3, shared vocabulary). Step bodies
delegate; no inline logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CarpaccioSpineComposition
from .domain_types import (
    CONTRACT_GATE_OUTCOME_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    FEATURE_FILE_COUNT_BY_WORD,
    FeatureId,
    GateVerdict,
)


scenarios("../slice-01-feature-scoped-contract-gate.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioSpineComposition:
    return CarpaccioSpineComposition(project_root=tmp_path / "project")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature project with a multi-slice plan")
def given_feature_project(composition: CarpaccioSpineComposition) -> None:
    composition.create_feature_project(FeatureId("acceptance-fixture-feature"))


@given(
    parsers.parse(
        "the feature has {files} .feature file(s) carrying a runnable scenario "
        "tagged for the entering slice"
    )
)
def given_collected_with_tag(
    composition: CarpaccioSpineComposition, files: str
) -> None:
    composition.author_collected_feature_tests(FEATURE_FILE_COUNT_BY_WORD[files])


@given(parsers.parse("a feature-scoped invocation where {vacuity}"))
def given_vacuous_collection(
    composition: CarpaccioSpineComposition, vacuity: str
) -> None:
    composition.arrange_vacuous_invocation(CONTRACT_GATE_OUTCOME_BY_PHRASE[vacuity])


# --- When --------------------------------------------------------------------


@when("the orchestrator runs the feature-scoped contract gate")
def when_run_contract_gate(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result_box["result"] = composition.run_arranged_contract_gate()


# --- Then --------------------------------------------------------------------


@then("the feature-scoped contract gate passes")
def then_gate_passes(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[GateVerdict.CLEARED], (
        f"expected exit 0 (cleared); got {result.exit_code}: {result.stderr}"
    )


@then("the gate reports it collected at least one node-id for the entering slice")
def then_gate_reports_collected_node_ids(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    # Non-vacuity witness: a genuine pass emits the COUNT of node-ids the
    # feature-scoped collection resolved. A tag-presence proxy emits no such
    # count -- so this step stays RED until _mode_feature_scoped routes through
    # real node-id collection (the W2/W4/W6 contract).
    result = result_box["result"]
    verdict = composition.parsed_verdict(result)
    collected = verdict.get("collected_node_ids")
    assert isinstance(collected, int) and collected >= 1, (
        f"expected the gate to report >= 1 genuinely-collected node-id "
        f"(non-vacuity floor); got verdict={verdict!r}"
    )


@then("the feature-scoped contract gate is refused as malformed")
def then_gate_malformed(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"the contract gate crashed rather than refusing "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )
    # RED-honesty guard: a genuine non-vacuity-floor refusal emits a structured
    # JSON verdict naming the cause "malformed". A bare argparse usage error
    # emits no such verdict -- so this step cannot pass on an exit-code
    # collision; it is genuinely RED until the CLI's M-1/M-8 floor does REAL
    # collection (a malformed slice tag must yield empty-intersection, not a
    # tag-text match).
    verdict = composition.parsed_verdict(result)
    assert verdict.get("cause") == "malformed", (
        f"expected a structured malformed verdict (non-vacuity floor); "
        f"got verdict={verdict!r}, exit {result.exit_code}: {result.stderr}"
    )
    assert result.exit_code == EXIT_CODE_BY_VERDICT[GateVerdict.MALFORMED], (
        f"expected exit 2 (malformed -- non-vacuity floor); "
        f"got {result.exit_code}: {result.stderr}"
    )
