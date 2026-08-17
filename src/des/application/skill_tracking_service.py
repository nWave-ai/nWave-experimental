"""SkillTrackingService - Application service for skill loading observability.

Compose Method pattern: small, well-named methods for each responsibility.
Intercepts Read tool calls to skill files and logs tracking events.

Entry point: track_from_transcript() is called at subagent-stop with the
full JSONL transcript.

Fail-open: never raises exceptions that could block agent execution.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING

from des.domain.skill_load_event import SkillLoadEvent


if TYPE_CHECKING:
    from des.ports.driven_ports.skill_tracking_port import SkillTrackingPort
    from des.ports.driven_ports.time_provider_port import TimeProvider


MODE_SELECTION_PREFIX = "NW-MODE-SELECTED: "
VALID_MODE_SELECTIONS = frozenset(
    {
        "direct S",
        "human S",
        "human M",
        "human L",
        "auto M",
        "auto L",
    }
)


class RootModeState(StrEnum):
    """Total root-route state projected from one transcript read."""

    UNSELECTED = "unselected"
    INVALID = "invalid"
    SELECTED = "selected"
    AUTO_PENDING = "auto_pending"
    AUTO_ENGAGED = "auto_engaged"


def extract_tool_calls(entry: dict) -> list[dict]:
    """Extract every tool_use dict from a transcript entry.

    Stateless parse of the captured-trace JSONL shape. Supports three formats:
    - Direct: {"type": "tool_use", "name": "Read", "input": {...}}
    - Content block: {"type": "content_block", "content_block": {"type": "tool_use", ...}}
    - Real Claude Code transcript:
      {"type": "assistant", "message": {"content": [{"type": "tool_use", ...}, ...]}}
      — the actual shape SubagentStop/PreToolUse transcripts carry, mirroring the
      normalization `subagent_stop_handler.py::_normalize_message_content` already
      applies to the sibling text-content case.

    Returns the tool_use dicts (each with 'name' and 'input' keys); empty when none.

    Module-level so any consumer of the trace-JSONL shape (the skill tracker, the
    nw-agent-evals deterministic graders) reuses ONE parser — no parallel parser.
    """
    entry_type = entry.get("type", "")
    if entry_type == "tool_use":
        return [entry]
    if entry_type == "content_block":
        block = entry.get("content_block", {})
        return [block] if block.get("type") == "tool_use" else []
    if entry_type != "assistant":
        return []
    message = entry.get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        return [
            block
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]
    return []


def read_transcript_tool_calls(transcript_path: str) -> list[dict]:
    """Read a JSONL transcript and extract its tool_use entries.

    Stateless reuse surface for the captured-trace JSONL shape. Malformed lines are
    silently skipped. Shared by SkillTrackingService and the nw-agent-evals graders.
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
            tool_calls.extend(extract_tool_calls(entry))
    return tool_calls


def skill_observed_before_action(transcript_path: str, skill_name: str) -> bool:
    """True iff the transcript contains an actual `Skill(skill_name)` call.

    Only a real `Skill` tool_use whose input selects `skill_name` counts —
    prose mentioning the skill, a `Read` of an unrelated file, and other
    `Skill` names are all false. Fails closed (False) when the transcript is
    missing, unreadable, or not valid UTF-8/JSONL text, since callers use
    this to decide whether a mutation or a role transition may proceed.
    """
    try:
        tool_calls = read_transcript_tool_calls(transcript_path)
    except (OSError, UnicodeDecodeError):
        return False
    return any(
        tc.get("name") == "Skill" and tc.get("input", {}).get("skill") == skill_name
        for tc in tool_calls
    )


def mode_select_observed_before_mutation(transcript_path: str) -> bool:
    """True iff the transcript contains an actual `Skill(nw-mode-select)` call.

    Delegates to the shared `skill_observed_before_action` predicate --
    same authority rules, same fail-closed behavior on a missing/unreadable
    transcript, since the caller uses this to decide whether a mutation may
    proceed.
    """
    return skill_observed_before_action(transcript_path, "nw-mode-select")


def _read_root_mode_observations(
    transcript_path: str,
) -> tuple[bool, bool, list[str]] | None:
    """Read mode-select, nw-auto, and exact markers in one transcript pass."""
    observed_skill = False
    observed_auto = False
    selections: list[str] = []
    try:
        with open(transcript_path, encoding="utf-8") as transcript:
            for raw_line in transcript:
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                for tool_call in extract_tool_calls(entry):
                    if tool_call.get("name") != "Skill":
                        continue
                    skill = tool_call.get("input", {}).get("skill")
                    if skill == "nw-mode-select":
                        observed_skill = True
                    elif skill == "nw-auto":
                        observed_auto = True
                if entry.get("type") != "assistant":
                    continue
                message = entry.get("message", {})
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if not observed_skill or block.get("type") != "text":
                        continue
                    text = block.get("text")
                    if not isinstance(text, str):
                        continue
                    for line in text.splitlines():
                        marker = line.strip()
                        if not marker.startswith(MODE_SELECTION_PREFIX):
                            continue
                        selection = marker.removeprefix(MODE_SELECTION_PREFIX)
                        if selection not in VALID_MODE_SELECTIONS:
                            return observed_skill, observed_auto, []
                        selections.append(selection)
    except (OSError, UnicodeDecodeError):
        return None

    return observed_skill, observed_auto, selections


def resolved_mode_selection_before_action(transcript_path: str) -> str | None:
    """Return the one exact mode-selection marker after ``nw-mode-select``.

    The marker is accepted only from assistant text *after* a real
    ``Skill(nw-mode-select)`` tool call. User prose therefore cannot spoof the
    decision. Missing, malformed, or conflicting markers fail closed as
    ``None`` so root-action guards can refuse an ambiguous handoff.
    """
    observations = _read_root_mode_observations(transcript_path)
    if observations is None:
        return None
    observed_skill, _, selections = observations
    if not observed_skill:
        return None

    distinct = set(selections)
    return distinct.pop() if len(distinct) == 1 else None


def resolve_root_mode_state(transcript_path: str) -> RootModeState:
    """Resolve the root's route state without persistent workflow state.

    An observed ``nw-auto`` remains authoritative for the existing lockdown,
    including older transcripts that predate the marker. Otherwise a real
    mode-select call must be followed by one unambiguous exact marker.
    """
    observations = _read_root_mode_observations(transcript_path)
    if observations is None:
        return RootModeState.UNSELECTED
    observed_skill, observed_auto, selections = observations
    if observed_auto:
        return RootModeState.AUTO_ENGAGED
    if not observed_skill:
        return RootModeState.UNSELECTED
    distinct = set(selections)
    if len(distinct) != 1:
        return RootModeState.INVALID
    selection = distinct.pop()
    if selection in {"auto M", "auto L"}:
        return RootModeState.AUTO_PENDING
    return RootModeState.SELECTED


class SkillTrackingService:
    """Tracks skill file loads for observability.

    Entry point: track_from_transcript() is called from the SubagentStop
    hook with a sub-agent's full JSONL transcript.
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
        except (OSError, UnicodeDecodeError):
            # WHAT: file vanished/unreadable or has undecodable bytes between
            # the exists() check and read_text().
            # WHY: token estimation is best-effort observability, not
            # correctness-critical (see module docstring: "Fail-open").
            # HOW: safe to continue -- caller falls back to the 0 default.
            pass
        return 0

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

        Delegates to the module-level shared parser (one home for the trace-JSONL
        parse idiom). Malformed lines are silently skipped.
        """
        return read_transcript_tool_calls(transcript_path)

    def _extract_tool_calls(self, entry: dict) -> list[dict]:
        """Extract tool_use dicts from a transcript entry.

        Delegates to the module-level shared parser.
        """
        return extract_tool_calls(entry)

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
