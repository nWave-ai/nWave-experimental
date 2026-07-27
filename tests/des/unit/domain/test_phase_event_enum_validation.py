"""Unit tests: PhaseEventParser validates phase_name/status against the domain enums.

ADR-PLAT-006 Fix 3 declares that ``PhaseEventParser`` "validates and converts at
the parsing boundary" so invalid phase statuses/names are caught at parse time,
not at use time. Prior to this fix, ``parse()``/``parse_structured()`` assigned
the raw string straight into ``PhaseEvent`` with no check against ``PhaseName``/
``PhaseStatus`` (src/des/domain/value_objects.py) -- an arbitrary string in a
malformed execution-log.json line entered the domain unchecked.

Test Budget: 2 behaviors (pipe-format validation, structured-dict validation)
x 2 = 4 max. Using 4.
"""

from __future__ import annotations

from des.domain.phase_event import PhaseEventParser


class TestPipeFormatEnumValidation:
    """parse() rejects unknown phase_name/status instead of admitting them."""

    def test_parse_rejects_unknown_phase_name(self) -> None:
        event = PhaseEventParser().parse(
            "01-01|NOT_A_REAL_PHASE|EXECUTED|PASS|2026-02-02T10:00:00Z"
        )
        assert event is None

    def test_parse_rejects_unknown_status(self) -> None:
        event = PhaseEventParser().parse(
            "01-01|PREPARE|NOT_A_REAL_STATUS|PASS|2026-02-02T10:00:00Z"
        )
        assert event is None

    def test_parse_still_accepts_known_legacy_phase_and_status(self) -> None:
        """Regression: every legacy PhaseName/PhaseStatus member must keep parsing."""
        event = PhaseEventParser().parse(
            "01-01|RED_ACCEPTANCE|SKIPPED|NOT_APPLICABLE|2026-02-02T10:00:00Z"
        )
        assert event is not None
        assert event.phase_name == "RED_ACCEPTANCE"
        assert event.status == "SKIPPED"


class TestStructuredFormatEnumValidation:
    """parse_structured() applies the same enum validation as parse()."""

    def test_parse_structured_rejects_unknown_phase_or_status(self) -> None:
        event = PhaseEventParser().parse_structured(
            {
                "sid": "08-01",
                "p": "NOT_A_REAL_PHASE",
                "s": "EXECUTED",
                "d": "PASS",
                "t": "2026-02-11T10:00:00Z",
            }
        )
        assert event is None
