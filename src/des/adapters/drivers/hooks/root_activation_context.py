"""Shared subagent identity resolution for identity-aware hooks.

An ordinary `PreToolUse` envelope carries neither
`agent_id` nor `agent_type` reliably -- those fields are documented (Claude
Code's own hooks reference) as specific to the SubagentStart/SubagentStop
lifecycle events. The identity-keyed decision in `pre_tool_use_handler.py`
(the nWave subagent host-scan guard) resolves identity HERE rather than
re-deriving it at the call site.

The second axis is the platform's own durable `subagents/agent-<id>.meta.json`
sidecar, written once at spawn time next to each dispatched subagent's own
transcript. Root's own transcript never sits inside a `subagents/` directory,
so root is never mistaken for a subagent.
"""

from __future__ import annotations

import json
from pathlib import Path


_NWAVE_AGENT_PREFIX = "nw-"


def _agent_type_from_transcript_meta_sidecar(transcript_path: str) -> str | None:
    """The `agentType` recorded in a subagent transcript's `.meta.json` sidecar.

    `None` when the path is not a `subagents/agent-<id>.jsonl` transcript, when
    no readable sidecar sits next to it, or when its JSON carries no string
    `agentType`.
    """
    path = Path(transcript_path)
    if path.parent.name != "subagents" or not path.name.startswith("agent-"):
        return None
    meta_path = path.parent / f"{path.stem}.meta.json"
    try:
        meta_text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        meta = json.loads(meta_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(meta, dict):
        return None
    sidecar_agent_type = meta.get("agentType")
    return sidecar_agent_type if isinstance(sidecar_agent_type, str) else None


def resolve_subagent_own_transcript_path(hook_input: dict[str, object]) -> str | None:
    """The dispatched subagent's OWN transcript file.

    A dispatched subagent's `transcript_path` usually names the ROOT session log
    (`<session-id>.jsonl`), a sibling of the `<session-id>/subagents/` directory
    that holds each dispatched subagent's own transcript -- not the subagent's
    own file. Returns `transcript_path` unchanged when it already has the
    subagent shape, otherwise derives the real file from that structural
    convention plus `agent_id`, using it only when it exists on disk. Falls
    through to `transcript_path` unchanged when neither succeeds, so a caller
    that resolved identity another way is never refused outright.
    """
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    path = Path(transcript_path)
    if path.parent.name == "subagents" and path.name.startswith("agent-"):
        return transcript_path
    agent_id = hook_input.get("agent_id")
    if isinstance(agent_id, str) and agent_id and path.suffix == ".jsonl":
        derived = path.parent / path.stem / "subagents" / f"agent-{agent_id}.jsonl"
        if derived.is_file():
            return str(derived)
    return transcript_path


def resolve_subagent_agent_type(hook_input: dict[str, object]) -> str | None:
    """The dispatched nw-* subagent's own declared role name.

    Resolved from the live envelope's `agent_type` field first (cheap, no I/O),
    falling back to the transcript meta-sidecar (one extra read) only when that
    field is absent or names a non-`nw-` role. `None` for root/user (no
    resolvable identity from either source) and for a non-nWave agent.
    """
    agent_type = hook_input.get("agent_type")
    if isinstance(agent_type, str) and agent_type.startswith(_NWAVE_AGENT_PREFIX):
        return agent_type
    own_transcript_path = resolve_subagent_own_transcript_path(hook_input)
    if own_transcript_path is None:
        return None
    sidecar_agent_type = _agent_type_from_transcript_meta_sidecar(own_transcript_path)
    if isinstance(sidecar_agent_type, str) and sidecar_agent_type.startswith(
        _NWAVE_AGENT_PREFIX
    ):
        return sidecar_agent_type
    return None
