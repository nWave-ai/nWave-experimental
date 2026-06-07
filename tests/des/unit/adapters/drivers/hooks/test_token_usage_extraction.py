"""Unit tests for token-usage extraction from Claude transcripts.

The pure function `extract_token_usage_events` walks a parsed list of
transcript JSONL entries and emits one AgentUsageObservedEvent per
assistant message that carries a valid `message.usage` block.

Tested behaviors (test budget: 4 distinct behaviors x 2 = 8 max, actual: 5):
1. Extracts one event per assistant message with valid usage
2. Preserves all four token fields (input/cache_creation/cache_read/output)
3. Skips assistant messages missing the usage block (fail-open)
4. Skips non-assistant messages
5. Returns empty list on empty input
"""

from __future__ import annotations

from des.adapters.driven.logging.audit_events import AgentUsageObservedEvent
from des.adapters.drivers.hooks.token_usage_extractor import (
    extract_token_usage_events,
)


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _assistant_with_usage(
    msg_id: str,
    *,
    input_tokens: int = 10,
    cache_creation: int = 0,
    cache_read: int = 0,
    output_tokens: int = 100,
    model: str = "claude-opus-4-7-20251101",
) -> dict:
    return {
        "type": "assistant",
        "message": {
            "id": msg_id,
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output_tokens,
            },
        },
        "uuid": f"uuid-{msg_id}",
        "timestamp": "2026-04-27T10:00:00.000Z",
    }


def _assistant_without_usage(msg_id: str) -> dict:
    return {
        "type": "assistant",
        "message": {"id": msg_id, "model": "claude-opus-4-7-20251101"},
        "uuid": f"uuid-{msg_id}",
        "timestamp": "2026-04-27T10:00:00.000Z",
    }


def _user_message(content: str = "hello") -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": content},
        "uuid": "uuid-user",
        "timestamp": "2026-04-27T10:00:00.000Z",
    }


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------


class TestExtractsEventsFromAssistantMessages:
    """Pure function emits one event per assistant message with valid usage."""

    def test_extracts_one_event_per_assistant_with_usage(self) -> None:
        entries = [
            _user_message(),
            _assistant_with_usage("a1"),
            _assistant_with_usage("a2"),
        ]

        events = extract_token_usage_events(entries, agent_name="researcher")

        assert len(events) == 2
        assert all(isinstance(e, AgentUsageObservedEvent) for e in events)

    def test_preserves_all_four_token_fields_including_cache(self) -> None:
        entries = [
            _assistant_with_usage(
                "a1",
                input_tokens=12,
                cache_creation=8421,
                cache_read=24109,
                output_tokens=187,
            ),
        ]

        events = extract_token_usage_events(entries, agent_name="researcher")

        assert len(events) == 1
        event = events[0]
        assert event.input_tokens == 12
        assert event.cache_creation_input_tokens == 8421
        assert event.cache_read_input_tokens == 24109
        assert event.output_tokens == 187
        assert event.model == "claude-opus-4-7-20251101"
        assert event.agent_name == "researcher"


class TestFailOpenOnMissingOrMalformedUsage:
    """Per D4: missing/malformed usage is skipped silently, never raises."""

    def test_skips_assistant_messages_without_usage_block(self) -> None:
        entries = [
            _assistant_with_usage("a1"),
            _assistant_without_usage("a2"),
            _assistant_with_usage("a3"),
        ]

        events = extract_token_usage_events(entries, agent_name="researcher")

        assert len(events) == 2

    def test_skips_non_assistant_messages(self) -> None:
        entries = [
            _user_message("first"),
            _user_message("second"),
            {"type": "tool_use", "name": "Read"},
        ]

        events = extract_token_usage_events(entries, agent_name="researcher")

        assert events == []


class TestEmptyInput:
    """Edge case: empty input returns empty list."""

    def test_empty_list_returns_empty_list(self) -> None:
        events = extract_token_usage_events([], agent_name="researcher")
        assert events == []
