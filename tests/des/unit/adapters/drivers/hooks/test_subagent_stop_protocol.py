"""Tests for SubagentStop hook protocol translation.

The SubagentStop hook receives Claude Code's protocol:
    {"agent_id", "agent_type", "agent_transcript_path", "cwd", "session_id", ...}

NOT the custom DES fields that SubagentStopService expects:
    {"executionLogPath", "projectId", "stepId"}

The adapter must:
1. Read the agent transcript to find the original Task prompt
2. Extract DES markers (project_id, step_id) via DesMarkerParser
3. Non-DES agents (no markers) -> allow passthrough
4. DES agents -> derive execution-log path and validate via SubagentStopService

State-delta migration summary
------------------------------
CONVERTED (2 tests) — state-delta + implicit-unchanged invariant:
  - test_des_subagent_with_incomplete_execution_log_blocked: multi-slot
    response universe (response.decision, response.reason); set_to("block")
    on decision; containing("Missing phases") on reason; implicit-unchanged
    enforces no unexpected fields appear in the block response.
  - test_des_subagent_missing_execution_log_blocked: same universe;
    set_to("block") on decision; containing("not found") on reason.

KEPT as-is (10 tests) — no state-delta benefit:
  - TestExtractDesContextFromTranscript (7 tests): pure return-value tests
    on a stateless function; no mutable universe to exploit.
  - test_non_des_subagent_allowed: exit-code + empty-stdout check only;
    single-slot, no hidden-mutation surface.
  - test_classic_des_transcript_is_refused_without_consuming_execution_log:
    parameterized refusal + execution-log byte-preservation check for both
    legacy artifact bases.
  - test_block_response_contains_only_claude_code_recognized_fields:
    structural protocol allowlist check (set algebra on response.keys());
    state-delta does not improve the key-set constraint.

Hidden mutations found: none. Block response universe is tightly constrained
to {decision, reason} — no undeclared slots observed.

Tests: 12 total. Hit rate update: 5/10 files exposed hidden mutations.
"""

import json
import os

import pytest

from des.adapters.drivers.hooks.claude_code_hook_adapter import (
    extract_des_context_from_transcript,
    handle_subagent_stop,
)


# ---------------------------------------------------------------------------
# State-delta universe
# ---------------------------------------------------------------------------

#: Slots tracked for SubagentStop block-response assertions.
BLOCK_RESPONSE_UNIVERSE: frozenset[str] = frozenset(
    ["response.decision", "response.reason"]
)


def _capture_block_response(captured: list) -> dict[str, object]:
    """Return a flat state dict for a block response captured via print-monkeypatch.

    Slots:
      "response.decision"  — value of response["decision"] (empty str if absent)
      "response.reason"    — value of response["reason"] (empty str if absent)

    Returns an absent-state dict (empty strings) when no output was captured.
    """
    if not captured:
        return {"response.decision": "", "response.reason": ""}
    response = json.loads(captured[0])
    return {
        "response.decision": response.get("decision", ""),
        "response.reason": response.get("reason", ""),
    }


def _make_transcript(tmp_dir: str, prompt: str) -> str:
    """Create a minimal JSONL transcript with a user message containing the prompt."""
    transcript_path = os.path.join(tmp_dir, "agent-test.jsonl")
    user_msg = {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "uuid": "test-uuid",
        "timestamp": "2026-02-06T21:00:00Z",
    }
    with open(transcript_path, "w") as f:
        f.write(json.dumps(user_msg) + "\n")
    return transcript_path


class TestExtractDesContextFromTranscript:
    """Tests for extracting DES markers from agent transcript."""

    def test_extracts_project_id_and_step_id_from_des_markers(self, tmp_path):
        prompt = (
            "<!-- DES-VALIDATION: required -->\n"
            "<!-- DES-PROJECT-ID: audit-log-refactor -->\n"
            "<!-- DES-STEP-ID: 02-01 -->\n"
            "# DES_METADATA\ntest"
        )
        transcript = _make_transcript(str(tmp_path), prompt)

        context = extract_des_context_from_transcript(transcript)

        assert context is not None
        assert context["project_id"] == "audit-log-refactor"
        assert context["step_id"] == "02-01"

    def test_returns_none_for_non_des_transcript(self, tmp_path):
        prompt = "Find all Python files in the codebase"
        transcript = _make_transcript(str(tmp_path), prompt)

        context = extract_des_context_from_transcript(transcript)

        assert context is None

    def test_returns_none_for_missing_transcript_file(self):
        context = extract_des_context_from_transcript("/nonexistent/path.jsonl")

        assert context is None

    def test_returns_none_for_empty_transcript(self, tmp_path):
        transcript_path = str(tmp_path / "empty.jsonl")
        with open(transcript_path, "w") as f:
            f.write("")

        context = extract_des_context_from_transcript(transcript_path)

        assert context is None

    def test_returns_none_when_project_id_marker_missing(self, tmp_path):
        prompt = (
            "<!-- DES-VALIDATION: required -->\n"
            "<!-- DES-STEP-ID: 02-01 -->\n"
            "# DES_METADATA\ntest"
        )
        transcript = _make_transcript(str(tmp_path), prompt)

        context = extract_des_context_from_transcript(transcript)

        assert context is None

    def test_returns_none_when_step_id_marker_missing(self, tmp_path):
        prompt = (
            "<!-- DES-VALIDATION: required -->\n"
            "<!-- DES-PROJECT-ID: audit-log-refactor -->\n"
            "# DES_METADATA\ntest"
        )
        transcript = _make_transcript(str(tmp_path), prompt)

        context = extract_des_context_from_transcript(transcript)

        assert context is None

    def test_handles_content_as_list_of_blocks(self, tmp_path):
        """Claude Code sometimes sends content as list of text blocks."""
        transcript_path = str(tmp_path / "agent.jsonl")
        user_msg = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "<!-- DES-VALIDATION: required -->\n"
                            "<!-- DES-PROJECT-ID: my-project -->\n"
                            "<!-- DES-STEP-ID: 01-01 -->\n"
                            "Do something"
                        ),
                    }
                ],
            },
            "uuid": "test",
            "timestamp": "2026-02-06T21:00:00Z",
        }
        with open(transcript_path, "w") as f:
            f.write(json.dumps(user_msg) + "\n")

        context = extract_des_context_from_transcript(transcript_path)

        assert context is not None
        assert context["project_id"] == "my-project"
        assert context["step_id"] == "01-01"


class TestSubagentStopWithClaudeCodeProtocol:
    """Integration tests: handle_subagent_stop() with Claude Code's actual protocol."""

    def _make_hook_input(self, agent_transcript_path: str, cwd: str) -> str:
        """Build Claude Code SubagentStop protocol JSON."""
        return json.dumps(
            {
                "session_id": "test-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "test-agent-123",
                "agent_type": "software-crafter",
                "agent_transcript_path": agent_transcript_path,
                "stop_hook_active": False,
                "cwd": cwd,
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )

    def test_non_des_subagent_allowed(self, tmp_path, monkeypatch):
        """Non-DES agent (no markers) should be allowed through."""
        prompt = "Find all Python files"
        transcript = _make_transcript(str(tmp_path), prompt)
        hook_input = self._make_hook_input(transcript, str(tmp_path))

        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(hook_input))

        captured = []
        monkeypatch.setattr("builtins.print", captured.append)

        exit_code = handle_subagent_stop()

        assert exit_code == 0
        # Allow path: no stdout (Claude Code protocol)
        assert len(captured) == 0, (
            f"Allow path should produce no output. Got: {captured}"
        )

    @pytest.mark.parametrize(
        "feature_base",
        ["feature", "nwave/feature"],
        ids=["default-base", "override-base"],
    )
    def test_classic_des_transcript_is_refused_without_consuming_execution_log(
        self, tmp_path, monkeypatch, feature_base
    ):
        """A retired classic transcript is refused without reading either legacy log."""
        project_id = "test-project"
        prompt = (
            "<!-- DES-VALIDATION: required -->\n"
            f"<!-- DES-PROJECT-ID: {project_id} -->\n"
            "<!-- DES-STEP-ID: 01-01 -->\n"
            "Execute step"
        )
        transcript = _make_transcript(str(tmp_path), prompt)

        deliver_dir = tmp_path / "docs" / feature_base / project_id / "deliver"
        deliver_dir.mkdir(parents=True)
        exec_log = deliver_dir / "execution-log.json"
        log_bytes = b'{"classic": "must remain untouched"}\n'
        exec_log.write_bytes(log_bytes)

        hook_input = self._make_hook_input(transcript, str(tmp_path))
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(hook_input))

        captured = []
        monkeypatch.setattr("builtins.print", captured.append)

        exit_code = handle_subagent_stop()

        assert exit_code == 2
        assert len(captured) == 1
        response = json.loads(captured[0])
        assert {
            key: response[key] for key in ("outcome", "reason_code", "effective_mode")
        } == {
            "outcome": "CLASSIC_MODE_REMOVED",
            "reason_code": "MIGRATION_REQUIRED",
            "effective_mode": None,
        }
        assert "retired classic" in response["diagnostic"]
        assert (
            "des convert-to-atdd-pure --workspace <project-dir>"
            in response["diagnostic"]
        )
        assert exec_log.read_bytes() == log_bytes
