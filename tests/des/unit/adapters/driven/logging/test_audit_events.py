"""
Acceptance tests for AuditEvent dataclass refactoring.

Tests verify that AuditEvent correctly uses feature_name and step_id
instead of the deprecated step_path field.

Also carries slice-03 ATs for feature `gate-outcome-record-seam`
(docs/feature/gate-outcome-record-seam/feature-delta.md, DDD-6/DDD-7):
retirement of AuditEvent's producerless `duration_minutes`/`outcome` fields
and deletion of the 8 EventType members measured ZERO-ANYWHERE on both axes
(enum-construction reference and literal-string reference) across
src/, scripts/, tests/, nWave/.
"""

import pytest

from des.adapters.driven.logging.audit_events import AuditEvent, EventType


# DDD-7: measured ZERO-ANYWHERE on both axes, re-verified in this worktree
# 2026-07-30 including tests/ per DDD-7's own stated precondition. DELETE.
_RETIRED_EVENT_TYPE_MEMBERS = (
    "COMMIT_FAILURE",
    "COMMIT_SUCCESS",
    "PHASE_EXECUTED",
    "PHASE_FAILED",
    "PHASE_SKIPPED",
    "SUBAGENT_STOP_FAILURE",
    "TASK_INVOCATION_REJECTED",
    "VALIDATION_REJECTED",
)

# DDD-7: test-referenced only -- DORMANT-WITH-A-REASON, not deleted this slice.
_DORMANT_WITH_A_REASON_MEMBERS = (
    "PHASE_STARTED",
    "SUBAGENT_STOP_VALIDATION",
)

# Sibling live members the 8-member deletion must not regress.
_SURVIVING_LIVE_MEMBERS = (
    "HOOK_PRE_TASK_PASSED",
    "HOOK_PRE_TASK_BLOCKED",
    "HOOK_SUBAGENT_STOP_PASSED",
    "HOOK_SUBAGENT_STOP_FAILED",
    "AGENT_USAGE_OBSERVED",
    "HEALTH_GATE_INSTALL_FRESHNESS_STALE",
    "HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT",
)


class TestAuditEventRefactoring:
    """Acceptance tests for AuditEvent field refactoring."""

    def test_ac1_audit_event_has_feature_name_field(self):
        """AC1: AuditEvent dataclass has feature_name field (str | None)."""
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00.000Z",
            event="PHASE_STARTED",
            feature_name="user-authentication",
        )
        assert hasattr(event, "feature_name")
        assert event.feature_name == "user-authentication"
        assert isinstance(event.feature_name, str)

    def test_ac2_audit_event_has_step_id_field(self):
        """AC2: AuditEvent dataclass has step_id field (str | None)."""
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00.000Z",
            event="PHASE_STARTED",
            step_id="01-02",
        )
        assert hasattr(event, "step_id")
        assert event.step_id == "01-02"
        assert isinstance(event.step_id, str)

    def test_ac3_step_path_field_removed(self):
        """AC3: step_path field is removed from AuditEvent dataclass."""
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00.000Z",
            event="PHASE_STARTED",
        )
        assert not hasattr(event, "step_path")

    def test_ac4_serialization_contains_feature_name_and_step_id(self):
        """AC4: AuditEvent serializes to dictionary containing feature_name and step_id keys."""
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00.000Z",
            event="PHASE_STARTED",
            feature_name="user-authentication",
            step_id="01-02",
        )
        serialized = event.to_dict()

        assert "feature_name" in serialized
        assert serialized["feature_name"] == "user-authentication"
        assert "step_id" in serialized
        assert serialized["step_id"] == "01-02"

    def test_ac5_deserialization_from_dictionary(self):
        """AC5: AuditEvent deserializes from dictionary containing feature_name and step_id keys."""
        data = {
            "timestamp": "2025-01-01T00:00:00.000Z",
            "event": "PHASE_STARTED",
            "feature_name": "user-authentication",
            "step_id": "01-02",
        }
        event = AuditEvent.from_dict(data)

        assert event.feature_name == "user-authentication"
        assert event.step_id == "01-02"

    def test_ac6_serialization_excludes_none_values(self):
        """AC6: AuditEvent serialization excludes None-valued feature_name and step_id fields."""
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00.000Z",
            event="PHASE_STARTED",
            feature_name=None,
            step_id=None,
        )
        serialized = event.to_dict()

        # None values should be excluded from serialization
        assert "feature_name" not in serialized
        assert "step_id" not in serialized
        # But required fields should be present
        assert "timestamp" in serialized
        assert "event" in serialized


class TestAuditEventDeadFieldRetirement:
    """Slice-03 (DDD-6): AuditEvent.duration_minutes / AuditEvent.outcome carry
    zero producers anywhere in the tree (F5) -- confirmed by `git grep -n
    "duration_minutes="` / `"outcome="` against every `AuditEvent(` call site
    in src/ and tests/, none passes either kwarg. Retired, not merely defaulted.

    Contract shape: pure-function, zero I/O. AuditEvent is a domain-layer
    value object (dataclass, no adapters/ports) -- direct construction via its
    public constructor IS the driving surface for this type, matching the
    5 pre-existing ATs in this same file (TestAuditEventRefactoring).
    """

    def test_duration_minutes_field_is_retired_from_the_dataclass(self):
        """duration_minutes has zero producers (F5) -- the attribute itself is gone."""
        event = AuditEvent(timestamp="2026-07-30T00:00:00.000Z", event="PHASE_STARTED")
        assert not hasattr(event, "duration_minutes")

    def test_outcome_field_is_retired_from_the_dataclass(self):
        """outcome (str, on AuditEvent) has zero producers (F5) -- the attribute itself is gone."""
        event = AuditEvent(timestamp="2026-07-30T00:00:00.000Z", event="PHASE_STARTED")
        assert not hasattr(event, "outcome")

    def test_constructor_rejects_duration_minutes_keyword(self):
        """Once retired, duration_minutes= is no longer an accepted constructor kwarg."""
        with pytest.raises(TypeError):
            AuditEvent(
                timestamp="2026-07-30T00:00:00.000Z",
                event="PHASE_STARTED",
                duration_minutes=5.0,
            )

    def test_constructor_rejects_outcome_keyword(self):
        """Once retired, outcome= is no longer an accepted constructor kwarg."""
        with pytest.raises(TypeError):
            AuditEvent(
                timestamp="2026-07-30T00:00:00.000Z",
                event="PHASE_STARTED",
                outcome="success",
            )

    def test_surviving_fields_are_unaffected_by_the_retirement(self):
        """Sibling-branch pin: the 8 surviving AuditEvent fields (Critical
        Rules) are untouched by retiring duration_minutes/outcome --
        construction and serialization of the rest of the shape must not
        regress. This scenario already holds true pre-DELIVER (a regression
        guard, not this slice's RED assertion).
        """
        event = AuditEvent(
            timestamp="2026-07-30T00:00:00.000Z",
            event="COMMIT_SUCCESS",
            feature_name="gate-outcome-record-seam",
            step_id="03-01",
            phase_name="GREEN",
            status="EXECUTED",
            reason="all ATs green",
            commit_hash="abc123",
            extra_context={"slice": "slice-03"},
        )
        serialized = event.to_dict()

        assert serialized["feature_name"] == "gate-outcome-record-seam"
        assert serialized["step_id"] == "03-01"
        assert serialized["phase_name"] == "GREEN"
        assert serialized["status"] == "EXECUTED"
        assert serialized["reason"] == "all ATs green"
        assert serialized["commit_hash"] == "abc123"
        assert serialized["extra_context"] == {"slice": "slice-03"}
        assert "duration_minutes" not in serialized
        assert "outcome" not in serialized


class TestEventTypeZeroAnywhereMemberDeletion:
    """Slice-03 (DDD-7): 8 EventType members measured ZERO-ANYWHERE on both
    axes (enum-construction reference AND literal-string reference) across
    src/, scripts/, tests/, nWave/ -- re-verified in this worktree 2026-07-30
    including tests/ per DDD-7's own stated precondition. Deleted, not merely
    deprecated.
    """

    @pytest.mark.parametrize("member_name", _RETIRED_EVENT_TYPE_MEMBERS)
    def test_zero_anywhere_member_is_never_constructible_by_attribute(
        self, member_name
    ):
        """Axis 1 (enum-construction reference): attribute access must fail."""
        with pytest.raises(AttributeError):
            getattr(EventType, member_name)

    @pytest.mark.parametrize("member_name", _RETIRED_EVENT_TYPE_MEMBERS)
    def test_zero_anywhere_member_is_never_constructible_by_value(self, member_name):
        """Axis 2 (literal-string reference): value lookup must fail too."""
        with pytest.raises(ValueError):
            EventType(member_name)

    @pytest.mark.negative_at
    def test_zero_anywhere_members_are_absent_from_the_members_map(self):
        surviving_names = set(EventType.__members__)
        assert surviving_names.isdisjoint(_RETIRED_EVENT_TYPE_MEMBERS)


class TestEventTypeDormantAndLiveMembersSurviveTheDeletion:
    """Sibling-branch pin (Critical Rules): the 8-member deletion above must
    not regress the 2 DORMANT-WITH-A-REASON members (test-referenced only,
    per DDD-7 explicitly NOT deleted this slice) or any surviving live member.
    """

    @pytest.mark.parametrize("member_name", _DORMANT_WITH_A_REASON_MEMBERS)
    def test_dormant_with_a_reason_member_still_constructible(self, member_name):
        assert getattr(EventType, member_name).value == member_name

    @pytest.mark.parametrize("member_name", _SURVIVING_LIVE_MEMBERS)
    def test_live_member_still_constructible(self, member_name):
        assert getattr(EventType, member_name).value == member_name
