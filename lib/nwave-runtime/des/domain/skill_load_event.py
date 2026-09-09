"""SkillLoadEvent - Domain value object for skill loading observability.

Represents a skill file being loaded by an agent via Read tool call.
Frozen dataclass ensures immutability after creation.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SkillLoadEvent:
    """Value object representing a skill file being loaded by an agent.

    Attributes:
        timestamp: ISO 8601 UTC timestamp of the load event
        agent_name: Agent that loaded the skill (e.g., "software-crafter")
        skill_name: Name of the skill loaded (e.g., "tdd-methodology")
        file_path: Full path to the skill file
        estimated_tokens: Estimated token count (chars // 4)
        step_id: DES step identifier, if available
    """

    timestamp: str
    agent_name: str
    skill_name: str
    file_path: str
    estimated_tokens: int
    step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Excludes None values for cleaner JSONL output.
        """
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}
