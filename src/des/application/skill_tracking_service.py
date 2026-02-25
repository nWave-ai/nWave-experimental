"""SkillTrackingService - Application service for skill loading observability.

Compose Method pattern: small, well-named methods for each responsibility.
Intercepts Read tool calls to skill files and logs tracking events.

Fail-open: never raises exceptions that could block agent execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.skill_load_event import SkillLoadEvent


if TYPE_CHECKING:
    from des.ports.driven_ports.skill_tracking_port import SkillTrackingPort
    from des.ports.driven_ports.time_provider_port import TimeProvider


class SkillTrackingService:
    """Tracks skill file loads for observability.

    Entry point: maybe_track() is called from the post-tool-use hook
    for every tool invocation. It filters to skill Read calls only.
    """

    SKILL_PATH_MARKER = "/skills/nw/"

    def __init__(
        self,
        tracker: SkillTrackingPort,
        time_provider: TimeProvider,
        strategy: str = "token-tracking",
    ) -> None:
        """Initialize with dependencies.

        Args:
            tracker: Port for logging skill load events
            time_provider: Port for UTC timestamps
            strategy: Tracking strategy ("token-tracking" or "passive-logging")
        """
        self._tracker = tracker
        self._time = time_provider
        self._strategy = strategy

    def maybe_track(
        self,
        tool_name: str,
        tool_input: dict,
        des_context: dict | None = None,
    ) -> None:
        """Track skill load if this is a skill Read call.

        Entry point called for every tool invocation. Filters to
        Read calls targeting skill files under /skills/nw/.

        Args:
            tool_name: Name of the tool invoked (e.g., "Read", "Write")
            tool_input: Tool input parameters (must contain "file_path" for Read)
            des_context: Optional DES execution context with step_id
        """
        if not self._is_skill_read(tool_name, tool_input):
            return

        file_path = tool_input.get("file_path", "")
        agent_name, skill_name = self._parse_skill_info(file_path)
        estimated_tokens = self._estimate_tokens(file_path)
        step_id = self._extract_step_id(des_context)

        event = SkillLoadEvent(
            timestamp=self._time.now_utc().isoformat(),
            agent_name=agent_name,
            skill_name=skill_name,
            file_path=file_path,
            estimated_tokens=estimated_tokens,
            step_id=step_id,
        )
        self._tracker.log_skill_load(event)

    def _is_skill_read(self, tool_name: str, tool_input: dict) -> bool:
        """Check if this tool call is a Read of a skill file."""
        return tool_name == "Read" and self.SKILL_PATH_MARKER in tool_input.get(
            "file_path", ""
        )

    def _parse_skill_info(self, file_path: str) -> tuple[str, str]:
        """Extract agent name and skill name from skill file path.

        Expected path format: .../skills/nw/{agent-name}/{skill-name}.md

        Args:
            file_path: Full path to the skill file

        Returns:
            Tuple of (agent_name, skill_name)
        """
        marker_idx = file_path.index(self.SKILL_PATH_MARKER) + len(
            self.SKILL_PATH_MARKER
        )
        remainder = file_path[marker_idx:]
        parts = remainder.split("/")
        agent_name = parts[0] if len(parts) >= 2 else "unknown"
        skill_name = (
            parts[1].removesuffix(".md")
            if len(parts) >= 2
            else remainder.removesuffix(".md")
        )
        return agent_name, skill_name

    def _estimate_tokens(self, file_path: str) -> int:
        """Estimate token count from file size.

        Uses chars // 4 heuristic. Returns 0 if file cannot be read
        or strategy is not "token-tracking".

        Args:
            file_path: Full path to the skill file

        Returns:
            Estimated token count, or 0 if unavailable
        """
        if self._strategy != "token-tracking":
            return 0
        try:
            from pathlib import Path

            resolved = Path(file_path).expanduser()
            if resolved.exists():
                return len(resolved.read_text(encoding="utf-8")) // 4
        except Exception:
            pass
        return 0

    def _extract_step_id(self, des_context: dict | None) -> str | None:
        """Extract step_id from DES context if available.

        Args:
            des_context: Optional DES execution context

        Returns:
            Step identifier string or None
        """
        if des_context is None:
            return None
        return des_context.get("step_id")
