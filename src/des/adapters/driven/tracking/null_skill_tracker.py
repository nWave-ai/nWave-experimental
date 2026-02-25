"""NullSkillTracker - NullObject pattern for SkillTrackingPort.

Used when skill tracking is disabled. Accepts all log_skill_load calls
without performing any I/O.
"""

from des.domain.skill_load_event import SkillLoadEvent
from des.ports.driven_ports.skill_tracking_port import SkillTrackingPort


class NullSkillTracker(SkillTrackingPort):
    """No-op implementation of SkillTrackingPort for disabled tracking."""

    def log_skill_load(self, event: SkillLoadEvent) -> None:
        """Accept event without writing. No-op."""
