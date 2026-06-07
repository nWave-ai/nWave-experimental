"""Unit tests for LogIntegrityValidator (UT-1 through UT-10).

Tests the three integrity checks:
- Phase name validation
- Foreign step_id detection
- Timestamp plausibility
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.domain.log_integrity_validator import LogIntegrityValidator
from des.domain.phase_event import PhaseEvent
from des.domain.tdd_schema import TDDSchema
from des.ports.driven_ports.time_provider_port import TimeProvider


# Valid phases matching the schema fixture
VALID_PHASES = {
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "REVIEW",
    "REFACTOR_CONTINUOUS",
    "COMMIT",
}

# Fixed "now" for deterministic timestamp checks
FIXED_NOW = "2026-02-10T15:00:00+00:00"
TASK_START = "2026-02-10T12:00:00+00:00"
TS_01 = "2026-02-10T12:01:00+00:00"
TS_02 = "2026-02-10T12:02:00+00:00"
TS_03 = "2026-02-10T12:03:00+00:00"
TS_BEFORE = "2026-02-10T11:00:00+00:00"


class StubTimeProvider(TimeProvider):
    """Returns a fixed time for deterministic testing."""

    def now_utc(self) -> datetime:
        return datetime(2026, 2, 10, 15, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def schema() -> TDDSchema:
    """Minimal TDD schema for testing."""
    return TDDSchema(
        tdd_phases=(
            "PREPARE",
            "RED_ACCEPTANCE",
            "RED_UNIT",
            "GREEN",
            "REVIEW",
            "REFACTOR_CONTINUOUS",
            "COMMIT",
        ),
    )


@pytest.fixture
def validator(schema: TDDSchema) -> LogIntegrityValidator:
    return LogIntegrityValidator(schema=schema, time_provider=StubTimeProvider())


def _make_event(
    step_id: str = "01-01",
    phase_name: str = "PREPARE",
    timestamp: str = TS_01,
) -> PhaseEvent:
    return PhaseEvent(
        step_id=step_id,
        phase_name=phase_name,
        status="EXECUTED",
        outcome="PASS",
        timestamp=timestamp,
    )


class TestHappyPath:
    """UT-1: Valid events produce no warnings."""

    def test_valid_events_no_warnings(self, validator: LogIntegrityValidator) -> None:
        events = [
            _make_event(phase_name="PREPARE", timestamp=TS_01),
            _make_event(phase_name="RED_ACCEPTANCE", timestamp=TS_02),
            _make_event(phase_name="COMMIT", timestamp=TS_03),
        ]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert result.warnings == []


class TestPhaseNameCheck:
    """UT-2: Unrecognized phase names produce warnings with suggestions."""

    def test_wrong_phase_name_produces_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [_make_event(phase_name="REFACTOR")]
        result = validator.validate(step_id="01-01", all_events=events)
        assert len(result.warnings) == 1
        assert "Unrecognized phase name 'REFACTOR'" in result.warnings[0]
        assert "REFACTOR_CONTINUOUS" in result.warnings[0]

    def test_completely_unknown_phase_no_suggestion(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [_make_event(phase_name="XYZZY")]
        result = validator.validate(step_id="01-01", all_events=events)
        assert len(result.warnings) == 1
        assert "Unrecognized phase name 'XYZZY'" in result.warnings[0]
        assert "did you mean" not in result.warnings[0]


class TestFutureTimestampProperty:
    """PBT: Any event with timestamp > now produces a 'Future timestamp' warning."""

    @given(
        future_dt=st.datetimes(
            min_value=datetime(2027, 1, 1),
            max_value=datetime(2099, 12, 31),
        )
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_any_future_timestamp_produces_warning(
        self, validator: LogIntegrityValidator, future_dt: datetime
    ) -> None:
        ts = future_dt.replace(tzinfo=timezone.utc).isoformat()
        events = [_make_event(timestamp=ts)]
        result = validator.validate(step_id="01-01", all_events=events)
        assert any("Future timestamp" in w for w in result.warnings)


class TestUnrecognizedPhaseProperty:
    """PBT: Any phase_name NOT in schema.tdd_phases produces an 'Unrecognized phase name' warning."""

    @given(
        phase_name=st.text(min_size=1, max_size=30).filter(
            lambda s: s not in VALID_PHASES
        )
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_any_non_schema_phase_produces_warning(
        self, validator: LogIntegrityValidator, phase_name: str
    ) -> None:
        events = [_make_event(phase_name=phase_name)]
        result = validator.validate(step_id="01-01", all_events=events)
        assert any("Unrecognized phase name" in w for w in result.warnings)


class TestForeignStepIdCheck:
    """UT-3/UT-4: Foreign step_id detection within task window."""

    def test_foreign_step_id_in_window_produces_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [
            _make_event(step_id="01-03", phase_name="PREPARE", timestamp=TS_01),
            _make_event(step_id="01-04", phase_name="PREPARE", timestamp=TS_02),
        ]
        result = validator.validate(
            step_id="01-03",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.warnings) == 1
        assert "Foreign step_id '01-04'" in result.warnings[0]

    def test_foreign_step_id_outside_window_no_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [
            _make_event(step_id="01-03", phase_name="PREPARE", timestamp=TS_01),
            _make_event(step_id="01-04", phase_name="PREPARE", timestamp=TS_BEFORE),
        ]
        result = validator.validate(
            step_id="01-03",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert result.warnings == []


class TestTimestampCheck:
    """UT-5/UT-6/UT-7: Timestamp plausibility checks."""

    def test_future_timestamp_produces_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [_make_event(timestamp="2099-01-01T00:00:00+00:00")]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.warnings) == 1
        assert "Future timestamp" in result.warnings[0]

    def test_pre_task_timestamp_produces_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [_make_event(timestamp=TS_BEFORE)]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.warnings) == 1
        assert "Pre-task timestamp" in result.warnings[0]

    def test_no_task_start_time_still_detects_future_timestamps(
        self, validator: LogIntegrityValidator
    ) -> None:
        """Future check runs without task_start_time (Causa B fix)."""
        events = [
            _make_event(timestamp="2099-01-01T00:00:00+00:00"),
        ]
        result = validator.validate(step_id="01-01", all_events=events)
        assert len(result.warnings) == 1
        assert "Future timestamp" in result.warnings[0]

    def test_no_task_start_time_skips_pre_task_and_foreign_checks(
        self, validator: LogIntegrityValidator
    ) -> None:
        """Pre-task and foreign checks still require task_start_time."""
        events = [
            _make_event(timestamp=TS_BEFORE),  # would be pre-task if start known
            _make_event(step_id="01-04", timestamp=TS_01),  # foreign
        ]
        result = validator.validate(step_id="01-01", all_events=events)
        assert all("Pre-task" not in w for w in result.warnings)
        assert all("Foreign" not in w for w in result.warnings)


class TestFilterCorrectness:
    """UT-8: Phase name check only applies to events matching step_id."""

    def test_wrong_phase_on_different_step_no_warning(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [
            _make_event(step_id="01-01", phase_name="PREPARE"),
            _make_event(step_id="01-02", phase_name="REFACTOR"),
        ]
        result = validator.validate(step_id="01-01", all_events=events)
        assert result.warnings == []


class TestAccumulation:
    """UT-9: Multiple warnings are all collected."""

    def test_multiple_warnings_accumulated(
        self, validator: LogIntegrityValidator
    ) -> None:
        events = [
            _make_event(phase_name="REFACTOR", timestamp=TS_01),
            _make_event(phase_name="BOGUS", timestamp=TS_02),
            _make_event(timestamp="2099-01-01T00:00:00+00:00", phase_name="PREPARE"),
        ]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.warnings) == 3


class TestEmptyEvents:
    """UT-10: Empty events list produces no warnings."""

    @pytest.mark.parametrize(
        "task_start_time",
        [None, "2026-02-10T14:00:00+00:00"],
        ids=["no-task-start", "with-task-start"],
    )
    def test_empty_events_no_warnings(
        self, validator: LogIntegrityValidator, task_start_time: str | None
    ) -> None:
        result = validator.validate(
            step_id="01-01",
            all_events=[],
            task_start_time=task_start_time,
        )
        assert result.warnings == []


class TestCorrectableEntries:
    """Correction detection tests for timestamp enforcement."""

    @pytest.mark.parametrize(
        ("timestamp", "expected_reason", "phase_name"),
        [
            ("2026-02-10T10:00:00+00:00", "pre_task", "PREPARE"),
            ("2099-01-01T00:00:00+00:00", "future", "GREEN"),
        ],
        ids=["pre-task-timestamp", "future-timestamp"],
    )
    def test_timestamp_anomalies_produce_correctable_entries(
        self,
        validator: LogIntegrityValidator,
        timestamp: str,
        expected_reason: str,
        phase_name: str,
    ) -> None:
        """Timestamps >60s before task start or in the future are correctable."""
        events = [_make_event(phase_name=phase_name, timestamp=timestamp)]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.correctable_entries) == 1
        assert result.correctable_entries[0].reason == expected_reason
        assert result.correctable_entries[0].phase_name == phase_name

    def test_within_tolerance_not_correctable(
        self, validator: LogIntegrityValidator
    ) -> None:
        """Timestamps within 60s before task start are warned but NOT correctable."""
        # TASK_START is 12:00:00, so 11:59:30 is within 60s tolerance
        events = [_make_event(timestamp="2026-02-10T11:59:30+00:00")]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        # Still produces a warning
        assert len(result.warnings) >= 1
        assert any("Pre-task" in w for w in result.warnings)
        # But NOT correctable
        assert len(result.correctable_entries) == 0

    def test_phase_name_typo_stays_warning_only(
        self, validator: LogIntegrityValidator
    ) -> None:
        """Phase name errors are warnings, never correctable entries."""
        events = [_make_event(phase_name="REFACTOR", timestamp=TS_01)]
        result = validator.validate(
            step_id="01-01",
            all_events=events,
            task_start_time=TASK_START,
        )
        assert len(result.warnings) == 1
        assert "Unrecognized" in result.warnings[0]
        assert len(result.correctable_entries) == 0
