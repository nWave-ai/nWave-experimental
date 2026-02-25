"""SkillTrackingPort - driven port for skill loading observability.

Abstract interface defining how the application layer logs skill load events.

Defined by: Application layer observability requirements.
Implemented by: JsonlSkillTracker (infrastructure adapter), NullSkillTracker (no-op).
"""

from abc import ABC, abstractmethod

from des.domain.skill_load_event import SkillLoadEvent


class SkillTrackingPort(ABC):
    """Driven port: logs skill load events for observability.

    Events are append-only. Implementations must be fail-silent
    (never raise exceptions that could block agent execution).
    """

    @abstractmethod
    def log_skill_load(self, event: SkillLoadEvent) -> None:
        """Log a skill load event.

        Args:
            event: The skill load event to log
        """
        ...
