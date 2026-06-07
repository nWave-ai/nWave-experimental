"""Token-usage extraction from Claude Code transcripts.

Pure function that walks a list of parsed transcript JSONL entries and
emits one AgentUsageObservedEvent per assistant message that carries a
valid `message.usage` block (per Anthropic transcript schema).

Per D4 (fail-open): assistant messages missing or with malformed usage
are skipped silently. The function MUST NOT raise on malformed input.

Per D5: per-message granularity. Aggregation deferred to analytics layer.

This module lives next to subagent_stop_handler.py — same code path that
already walks transcripts for DES markers (D2: additive only).
"""

from __future__ import annotations

import logging

from des.adapters.driven.logging.audit_events import AgentUsageObservedEvent


_logger = logging.getLogger(__name__)

_REQUIRED_USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def extract_token_usage_events(
    transcript_entries: list[dict],
    *,
    agent_name: str,
    feature_id: str | None = None,
    wave: str | None = None,
) -> list[AgentUsageObservedEvent]:
    """Extract per-message token-usage events from parsed transcript entries.

    Args:
        transcript_entries: Parsed JSONL entries from the Claude transcript.
            Each entry is the dict produced by json.loads on one line.
        agent_name: Claude Code sub-agent type (e.g., "researcher").
        feature_id: Optional feature identifier for traceability.
        wave: Optional wave name for traceability.

    Returns:
        One AgentUsageObservedEvent per assistant message with valid usage.
        Empty list when no eligible messages found. Never raises.
    """
    return [
        event
        for event in (
            _maybe_event_from_entry(
                entry,
                agent_name=agent_name,
                feature_id=feature_id,
                wave=wave,
            )
            for entry in transcript_entries
        )
        if event is not None
    ]


def _maybe_event_from_entry(
    entry: dict,
    *,
    agent_name: str,
    feature_id: str | None,
    wave: str | None,
) -> AgentUsageObservedEvent | None:
    """Return an event for a valid assistant entry, otherwise None.

    Fail-open: any structural mismatch (wrong type, missing fields,
    non-int token counts) yields None and a debug log line — never raises.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("type") != "assistant":
        return None

    message = entry.get("message")
    if not isinstance(message, dict):
        return None

    usage = message.get("usage")
    if not isinstance(usage, dict):
        # Fail-open: assistant message without usage block (e.g., interrupted,
        # tool-only). Skip silently per D4.
        return None

    try:
        input_tokens = int(usage["input_tokens"])
        cache_creation = int(usage["cache_creation_input_tokens"])
        cache_read = int(usage["cache_read_input_tokens"])
        output_tokens = int(usage["output_tokens"])
    except (KeyError, TypeError, ValueError):
        _logger.debug(
            "skipping assistant message with malformed usage block",
            extra={"entry_uuid": entry.get("uuid")},
        )
        return None

    model = message.get("model")
    if not isinstance(model, str):
        _logger.debug(
            "skipping assistant message with missing/invalid model field",
            extra={"entry_uuid": entry.get("uuid")},
        )
        return None

    timestamp = entry.get("timestamp")
    if not isinstance(timestamp, str):
        timestamp = ""

    return AgentUsageObservedEvent(
        agent_name=agent_name,
        model=model,
        timestamp=timestamp,
        input_tokens=input_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        output_tokens=output_tokens,
        feature_id=feature_id,
        wave=wave,
    )
