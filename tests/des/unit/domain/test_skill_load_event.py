"""Unit tests for SkillLoadEvent domain value object.

Test Budget: 2 behaviors x 2 = 4 max. Actual: 2 tests.

Behaviors:
1. Frozen dataclass (immutable)
2. Optional step_id (None is valid)
"""

import pytest

from des.domain.skill_load_event import SkillLoadEvent


class TestSkillLoadEventImmutability:
    """SkillLoadEvent is a frozen dataclass — fields cannot be mutated."""

    def test_frozen_dataclass_rejects_mutation(self) -> None:
        """Attempting to set a field on a frozen SkillLoadEvent raises FrozenInstanceError."""
        event = SkillLoadEvent(
            timestamp="2026-02-25T10:00:00+00:00",
            agent_name="software-crafter",
            skill_name="tdd-methodology",
            file_path="/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md",
            estimated_tokens=250,
        )

        with pytest.raises(AttributeError):
            event.agent_name = "other-agent"  # type: ignore[misc]


class TestSkillLoadEventOptionalFields:
    """SkillLoadEvent accepts None for optional fields."""

    def test_optional_step_id_defaults_to_none(self) -> None:
        """step_id defaults to None and is excluded from to_dict() output."""
        event = SkillLoadEvent(
            timestamp="2026-02-25T10:00:00+00:00",
            agent_name="software-crafter",
            skill_name="tdd-methodology",
            file_path="/home/user/.claude/skills/nw/software-crafter/tdd-methodology.md",
            estimated_tokens=250,
        )

        assert event.step_id is None
        assert "step_id" not in event.to_dict()
