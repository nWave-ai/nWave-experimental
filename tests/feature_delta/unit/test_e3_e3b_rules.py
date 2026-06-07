"""Unit tests for E3 (non-empty rows) and E3b (cherry-pick check) rules.

Test Budget: 4 distinct behaviors * 2 = 8 max unit tests.
Using 4 tests — one per behavior.

Port-to-port: pure domain functions check() ARE their driving ports.
"""

from __future__ import annotations

from nwave_ai.feature_delta.domain.model import (
    CommitmentRow,
    DDDEntry,
    FeatureDeltaModel,
    WaveSection,
)
from nwave_ai.feature_delta.domain.rules import e3_non_empty_rows, e3b_cherry_pick


def _row(
    commitment: str, ddd: str = "n/a", impact: str = "some impact"
) -> CommitmentRow:
    return CommitmentRow(origin="n/a", commitment=commitment, ddd=ddd, impact=impact)


def _model(*sections: WaveSection) -> FeatureDeltaModel:
    return FeatureDeltaModel(feature_id="test", sections=tuple(sections))


# ---------------------------------------------------------------------------
# E3: Non-empty rows
# ---------------------------------------------------------------------------


def test_e3_flags_empty_commitment_cell():
    """E3 returns a violation when a commitment cell is empty."""
    section = WaveSection(
        name="DESIGN",
        rows=(
            _row("real commitment"),
            _row(""),  # empty Commitment cell
        ),
        ddd_entries=(),
    )
    model = _model(section)

    violations = e3_non_empty_rows.check(model)

    assert len(violations) == 1
    assert violations[0].rule == "E3"
    assert "Commitment" in violations[0].offender or "E3" in violations[0].rule


def test_e3_passes_when_all_cells_filled():
    """E3 returns empty tuple when all commitment cells are non-empty."""
    section = WaveSection(
        name="DESIGN",
        rows=(_row("real commitment"),),
        ddd_entries=(),
    )
    model = _model(section)

    violations = e3_non_empty_rows.check(model)

    assert violations == ()


# ---------------------------------------------------------------------------
# E3b: Cherry-pick check
# ---------------------------------------------------------------------------


def test_e3b_flags_cherry_pick_without_ddd():
    """E3b returns violation when downstream drops a row with no DDD ratification."""
    discuss = WaveSection(
        name="DISCUSS",
        rows=(
            _row("commitment-1"),
            _row("commitment-2"),
            _row("commitment-3"),
        ),
        ddd_entries=(),
    )
    design = WaveSection(
        name="DESIGN",
        rows=(
            _row("commitment-1"),
            _row("commitment-2"),
            # commitment-3 silently dropped
        ),
        ddd_entries=(),  # no DDD authorization
    )
    model = _model(discuss, design)

    violations = e3b_cherry_pick.check(model)

    assert len(violations) >= 1
    assert any(v.rule == "E3b" for v in violations)
    # Error must name the dropped commitment text
    offenders = " ".join(v.offender for v in violations)
    assert "commitment-3" in offenders


def test_e3b_passes_authorized_removal_with_ddd():
    """E3b returns empty tuple when a dropped row is ratified by a DDD entry."""
    discuss = WaveSection(
        name="DISCUSS",
        rows=(
            _row("commitment-1"),
            _row("commitment-2"),
            _row("commitment-3"),
        ),
        ddd_entries=(),
    )
    design = WaveSection(
        name="DESIGN",
        rows=(
            _row("commitment-1"),
            _row("commitment-2"),
            # commitment-3 dropped but DDD-1 authorizes it
        ),
        ddd_entries=(
            DDDEntry(number=1, text="drop CLI commitment because feature is API-only"),
        ),
    )
    model = _model(discuss, design)

    violations = e3b_cherry_pick.check(model)

    assert violations == ()
