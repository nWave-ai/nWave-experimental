"""SkillTrackingService - Application service for skill loading observability.

Compose Method pattern: small, well-named methods for each responsibility.
Intercepts Read tool calls to skill files and logs tracking events.

Two entry points:
- maybe_track(): called per tool invocation (post-tool-use hook)
- track_from_transcript(): called at subagent-stop with full JSONL transcript

Fail-open: never raises exceptions that could block agent execution.
"""

from __future__ import annotations

import json
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

    # ------------------------------------------------------------------
    # Transcript-based tracking (SubagentStop hook)
    # ------------------------------------------------------------------

    def track_from_transcript(self, transcript_path: str) -> list[SkillLoadEvent]:
        """Extract and log skill loads from a sub-agent JSONL transcript.

        Scans transcript for Read tool calls targeting skill files.
        Each match is logged via the tracker port. Fail-open: returns
        empty list on any error.

        Args:
            transcript_path: Path to the sub-agent's JSONL transcript file.

        Returns:
            List of SkillLoadEvent objects extracted from the transcript.
        """
        try:
            tool_calls = self._read_transcript_tool_calls(transcript_path)
            skill_reads = self._filter_skill_reads(tool_calls)
            events = self._build_events(skill_reads)
            self._log_events(events)
            return events
        except Exception:
            return []  # Fail-open: tracking must never block

    def _read_transcript_tool_calls(self, transcript_path: str) -> list[dict]:
        """Read JSONL transcript and extract tool_use entries.

        Supports two formats:
        - Direct: {"type": "tool_use", "name": "Read", "input": {...}}
        - Content block: {"type": "content_block", "content_block": {"type": "tool_use", ...}}

        Malformed lines are silently skipped.
        """
        tool_calls: list[dict] = []
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tool_call = self._extract_tool_call(entry)
                if tool_call is not None:
                    tool_calls.append(tool_call)
        return tool_calls

    def _extract_tool_call(self, entry: dict) -> dict | None:
        """Extract tool_use dict from a transcript entry.

        Returns dict with 'name' and 'input' keys, or None.
        """
        entry_type = entry.get("type", "")
        if entry_type == "tool_use":
            return entry
        if entry_type == "content_block":
            block = entry.get("content_block", {})
            if block.get("type") == "tool_use":
                return block
        return None

    def _filter_skill_reads(self, tool_calls: list[dict]) -> list[dict]:
        """Filter to only Read calls targeting skill files."""
        return [
            tc
            for tc in tool_calls
            if self._is_skill_read(tc.get("name", ""), tc.get("input", {}))
        ]

    def _build_events(self, skill_reads: list[dict]) -> list[SkillLoadEvent]:
        """Build SkillLoadEvent objects from filtered skill Read calls."""
        events: list[SkillLoadEvent] = []
        for tc in skill_reads:
            file_path = tc.get("input", {}).get("file_path", "")
            agent_name, skill_name = self._parse_skill_info(file_path)
            estimated_tokens = self._estimate_tokens(file_path)
            event = SkillLoadEvent(
                timestamp=self._time.now_utc().isoformat(),
                agent_name=agent_name,
                skill_name=skill_name,
                file_path=file_path,
                estimated_tokens=estimated_tokens,
            )
            events.append(event)
        return events

    def _log_events(self, events: list[SkillLoadEvent]) -> None:
        """Log all events via the tracker port."""
        for event in events:
            self._tracker.log_skill_load(event)
