"""Step definitions -- slice-01: derive_coverage_map walking skeleton.

F-DISTILL-HUMAN-SIGNOFF slice-01. Layer 3 (subprocess / FS acceptance): the
derive_coverage_map CLI is the driving port; the real filesystem (tmp_path)
is the only driven port. Example-based sad paths (Mandate 11).

Step bodies delegate to ``HumanSignoffComposition`` -- a typed lookup plus a
composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the manifest file is unchanged by rendering (rendering reads the
manifest, writes the coverage-map) via ``assert_state_delta`` over a
port-exposed universe (Mandate 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import HumanSignoffComposition
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    PARSER_EDGE_BY_PHRASE,
    CoverageDimension,
    CoverageMapVerdict,
    FeatureId,
    ParserEdgeShape,
)


scenarios("../slice-01-coverage-map-skeleton.feature")


# Section labels every coverage-map must carry, in this fixed order (§5.1).
_MANDATORY_SECTIONS_IN_ORDER: tuple[str, ...] = (
    "## Feature surface declared",
    "## NOT covered -- and why",
    "## Known residues carried forward",
    "## Negative-space completeness statement",
    "## Signoff",
)


@pytest.fixture
def composition(tmp_path: Path) -> HumanSignoffComposition:
    """Production-wired composition root over a tmp_path feature project."""
    return HumanSignoffComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + scenario-derived state across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has produced a component manifest")
def given_design_wave_produced_manifest(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))
    result_box["domain_ids"] = (
        composition.write_manifest_with_one_domain_per_dimension()
    )


# --- Given ------------------------------------------------------------------


@given("every manifest domain is covered by an acceptance scenario tag")
def given_every_domain_covered(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.write_scenario_covering_all_domains(result_box["domain_ids"])


@given("a manifest domain is left uncovered by every acceptance scenario tag")
def given_one_domain_uncovered(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    # Deliberately leave the BEHAVIOURAL dimension's domain uncovered.
    result_box["uncovered_dimension"] = CoverageDimension.BEHAVIOURAL
    composition.write_scenario_covering_subset(
        result_box["domain_ids"], leave_uncovered=CoverageDimension.BEHAVIOURAL
    )


@given(parsers.parse("an acceptance scenario authored where {parser_edge}"))
def given_parser_edge(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    parser_edge: str,
) -> None:
    edge: ParserEdgeShape = PARSER_EDGE_BY_PHRASE[parser_edge]
    result_box["parser_edge"] = edge
    composition.write_parser_edge_fixture(edge, result_box["domain_ids"])


# --- When -------------------------------------------------------------------


@when("the acceptance designer renders the coverage map")
def when_render(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_derive_coverage_map()
    after = composition.capture_universe()
    # Manifest stays unchanged (renderer is a read of the manifest, write of
    # the coverage-map); feature-delta stays unchanged.
    # coverage_map.present transitions false -> true ONLY on success (exit 0);
    # on a malformed-id fail (exit 2) the renderer MUST NOT write the map.
    cli_result = result_box["result"]
    if cli_result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED]:
        coverage_expected = set_to(True)
    else:
        coverage_expected = unchanged()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "manifest.present",
            "coverage_map.present",
            "feature_delta.present",
        },
        expected={
            "manifest.present": unchanged(),
            "coverage_map.present": coverage_expected,
            "feature_delta.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then("a coverage map is written to the feature distill directory")
def then_coverage_map_written(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
        f"expected exit 0 (rendered); got {result.exit_code}: {result.stderr}"
    )
    assert composition.coverage_map_path().is_file(), (
        "the renderer reported success but no coverage-map.md was written"
    )


@then("the coverage map carries the four mandatory dimension rows each marked none")
def then_four_none_rows(composition: HumanSignoffComposition) -> None:
    body = composition.read_coverage_map()
    for dimension in CoverageDimension:
        # Every dimension row is always present; with full coverage each is "none".
        expected_row_prefix = f"| {dimension.value}"
        assert expected_row_prefix in body, (
            f"dimension row missing: {dimension.value!r}\n--\n{body}"
        )
        # Find that dimension's row and assert its "What is NOT covered" cell is "none".
        for line in body.splitlines():
            if line.startswith(expected_row_prefix):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                assert len(cells) >= 2 and cells[1] == "none", (
                    f"dimension {dimension.value!r} expected 'none' as What is NOT covered; "
                    f"saw {cells[1]!r}\nrow: {line!r}"
                )
                break


@then("the coverage map carries the feature surface declared section in order")
def then_sections_in_order(composition: HumanSignoffComposition) -> None:
    body = composition.read_coverage_map()
    last_index = -1
    for heading in _MANDATORY_SECTIONS_IN_ORDER:
        idx = body.find(heading)
        assert idx >= 0, f"mandatory section heading missing: {heading!r}\n--\n{body}"
        assert idx > last_index, (
            f"mandatory section out of order: {heading!r} appears before earlier sections\n"
            f"--\n{body}"
        )
        last_index = idx


@then("the uncovered manifest domain appears on the not covered table")
def then_uncovered_on_not_covered_table(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
        f"expected exit 0 (rendered); got {result.exit_code}: {result.stderr}"
    )
    uncovered_dim: CoverageDimension = result_box["uncovered_dimension"]
    uncovered_id = result_box["domain_ids"][uncovered_dim]
    body = composition.read_coverage_map()
    # Find the ## NOT covered section
    not_covered_idx = body.find("## NOT covered -- and why")
    assert not_covered_idx >= 0, "## NOT covered -- and why section missing"
    not_covered_section = body[not_covered_idx:]
    assert str(uncovered_id) in not_covered_section, (
        f"uncovered domain {uncovered_id!r} not listed in '## NOT covered' section\n"
        f"--\n{not_covered_section[:500]}"
    )


@then(
    "the not covered table places the domain on the dimension row matching its category"
)
def then_uncovered_on_correct_dimension(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    uncovered_dim: CoverageDimension = result_box["uncovered_dimension"]
    uncovered_id = result_box["domain_ids"][uncovered_dim]
    body = composition.read_coverage_map()
    # The uncovered domain id must appear on a row whose first cell is the
    # uncovered dimension label.
    for line in body.splitlines():
        if str(uncovered_id) in line and line.startswith(f"| {uncovered_dim.value}"):
            return
    raise AssertionError(
        f"uncovered domain {uncovered_id!r} not on the row for dimension "
        f"{uncovered_dim.value!r}\n--\n{body}"
    )


@then(
    parsers.parse(
        "the rendered coverage matches the parser edge expectation for {parser_edge}"
    )
)
def then_parser_edge_expectation(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    parser_edge: str,
) -> None:
    edge: ParserEdgeShape = PARSER_EDGE_BY_PHRASE[parser_edge]
    result = result_box["result"]
    # Malformed id is the sole sad-path in this outline: exit 2 fail-closed,
    # no coverage-map emitted. A scaffold AssertionError exits 1, so the exit
    # code alone is Fixture-Theater-prone; require no Python traceback on stderr.
    if edge is ParserEdgeShape.MALFORMED_DOMAIN_ID:
        assert "Traceback (most recent call last)" not in result.stderr, (
            "the renderer crashed rather than refusing the malformed id "
            f"(exit {result.exit_code}); stderr:\n{result.stderr}"
        )
        assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.MALFORMED], (
            f"expected exit 2 (malformed); got {result.exit_code}: {result.stderr}"
        )
        return
    # The four happy-path edges share a contract: rendering succeeds (exit 0)
    # and the coverage-map exists; the per-edge expectation is rendered into
    # the not-covered table the renderer produced.
    assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
        f"edge {edge.value!r}: expected exit 0 (rendered); got {result.exit_code}: "
        f"{result.stderr}"
    )
    body = composition.read_coverage_map()
    env_id = str(result_box["domain_ids"][CoverageDimension.ENVIRONMENTAL])
    behav_id = str(result_box["domain_ids"][CoverageDimension.BEHAVIOURAL])
    not_covered_idx = body.find("## NOT covered -- and why")
    assert not_covered_idx >= 0, "## NOT covered -- and why section missing"
    not_covered_section = body[not_covered_idx:]

    if edge is ParserEdgeShape.MULTI_TAG_ONE_LINE:
        # Two domains on one tag line => both counted as covered =>
        # both ABSENT from `## NOT covered`.
        assert env_id not in not_covered_section, (
            f"multi-tag: env domain {env_id!r} should be covered, not listed in NOT covered"
        )
        assert behav_id not in not_covered_section, (
            f"multi-tag: behav domain {behav_id!r} should be covered, not listed in NOT covered"
        )
    elif edge is ParserEdgeShape.OUTLINE_COVERS_ONCE:
        # Outline-with-3-Examples covers env once => env ABSENT from NOT covered.
        # behav has no covering tag => behav PRESENT in NOT covered.
        assert env_id not in not_covered_section, (
            f"outline: env domain {env_id!r} should be covered once, not listed in NOT covered"
        )
        assert behav_id in not_covered_section, (
            f"outline: behav domain {behav_id!r} should be uncovered, listed in NOT covered"
        )
    elif edge is ParserEdgeShape.FEATURE_LINE_IGNORED:
        # Feature-line covers tag is IGNORED => env uncovered too.
        # Both env and behav PRESENT in NOT covered.
        assert env_id in not_covered_section, (
            f"feature-line: env domain {env_id!r} tag is on Feature line and must be ignored "
            f"(domain should be listed in NOT covered)"
        )
        assert behav_id in not_covered_section, (
            f"feature-line: behav domain {behav_id!r} should be uncovered, listed in NOT covered"
        )
    elif edge is ParserEdgeShape.NO_TAG_EMPTY:
        # No covers tag anywhere => every manifest domain uncovered.
        for dim, did in result_box["domain_ids"].items():
            assert str(did) in not_covered_section, (
                f"no-tag: every manifest domain must be listed in NOT covered; "
                f"missing {did!r} (dimension {dim.value!r})"
            )
    else:  # pragma: no cover -- exhaustive over ParserEdgeShape
        raise AssertionError(f"unhandled parser edge: {edge!r}")
