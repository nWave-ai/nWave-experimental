"""Skill loading tracking for hook handlers.

Intercepts Read tool calls to skill files and logs them for token cost analysis.
All tracking is fail-open — never blocks agent execution.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition (step 4d).
"""

from des.adapters.driven.time.system_time import SystemTimeProvider


def maybe_track_skill_load(hook_input: dict) -> None:
    """Track skill file reads for observability. Fail-open, never blocks.

    Intercepts Read tool calls to skill files under /skills/nw/ and logs
    them to .nwave/skill-loading-log.jsonl for token cost analysis.

    Args:
        hook_input: Raw hook input dict with tool_name and tool_input
    """
    try:
        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig()
        if not config.skill_tracking_enabled:
            return

        from des.adapters.driven.tracking.jsonl_skill_tracker import JsonlSkillTracker
        from des.application.skill_tracking_service import SkillTrackingService

        tracker = JsonlSkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=SystemTimeProvider(),
            strategy=config.skill_tracking_strategy,
        )

        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        service.maybe_track(tool_name, tool_input)
    except Exception:
        pass  # Fail-open: tracking must never block agent execution


def maybe_track_skill_loads(transcript_path: str) -> None:
    """Track skill file reads from a sub-agent JSONL transcript. Fail-open.

    Scans the transcript for Read tool calls targeting /skills/nw/ paths
    and logs each as a SkillLoadEvent.

    Args:
        transcript_path: Path to the sub-agent's JSONL transcript file.
    """
    try:
        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig()
        if not config.skill_tracking_enabled:
            return

        from des.adapters.driven.tracking.jsonl_skill_tracker import JsonlSkillTracker
        from des.application.skill_tracking_service import SkillTrackingService

        tracker = JsonlSkillTracker()
        service = SkillTrackingService(
            tracker=tracker,
            time_provider=SystemTimeProvider(),
            strategy=config.skill_tracking_strategy,
        )

        service.track_from_transcript(transcript_path)
    except Exception:
        pass  # Fail-open: tracking must never block sub-agent completion
