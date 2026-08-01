"""H0 preservation contract for the pre-extraction Claude hook surface.

@feature-codex-host-parity
@slice-01

This is an active regression guard, not a Codex implementation test.  The
baseline is the current Claude installer output: all 17 registrations over six
event names.  Any semantic/native split must keep this emitted artifact
byte-equivalent under the fixed portable-command fixture.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest
from nwave_ai.state_delta import assert_state_delta, set_to

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


pytestmark = [pytest.mark.slice_01]


_EXPECTED_REGISTRATIONS = (
    ("PreToolUse", "Agent", "pre-task"),
    ("PreToolUse", "Write", "pre-write"),
    ("PreToolUse", "Edit", "pre-edit"),
    ("PreToolUse", "Bash", "pre-bash"),
    ("PreToolUse", "Bash", "pre-bash-spine-ledger"),
    ("PreToolUse", "Bash", "pre-bash-spine-ledger-gate-installed"),
    ("PreToolUse", "Bash", "pre-bash-git-stash-guard"),
    ("PreToolUse", "Bash", "pre-bash-no-verify-reminder"),
    ("PostToolUse", "Agent", "post-tool-use"),
    ("SubagentStop", None, "subagent-stop"),
    ("SubagentStop", None, "deliver-progress"),
    ("SubagentStop", None, "subagent-stop-spine-detector"),
    ("SessionStart", "startup", "session-start"),
    ("SubagentStart", None, "subagent-start"),
    ("UserPromptSubmit", None, "user-prompt-submit"),
    ("SessionStart", None, "orchestrator-affordance-refresh-standalone"),
    ("UserPromptSubmit", None, "orchestrator-affordance-refresh-standalone"),
)

_EXPECTED_EVENT_TYPES = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "SubagentStop",
        "SessionStart",
        "SubagentStart",
        "UserPromptSubmit",
    }
)

# sha256(json.dumps({"hooks": emitted_hooks}, indent=2) + "\\n") under the
# fixed portable-command fixture.  It seals every command byte, matcher, list
# order, nesting shape, and event grouping; identities above make a drift
# actionable without deriving the oracle from the implementation under test.
_EXPECTED_HOOK_DOCUMENT_SHA256 = (
    "5082403e10bc40ec4d81e2fa43aa1851502294582052e20419799f9aa10be3ba"
)


def _settings_state(settings_file: Path) -> dict[str, str]:
    """Snapshot the installer-visible settings surface for state-delta checks."""
    document = json.loads(settings_file.read_text(encoding="utf-8"))
    hooks = document.get("hooks", {})
    return {
        **{
            f"hooks.{event}": json.dumps(hooks.get(event, []), sort_keys=True)
            for event in _EXPECTED_EVENT_TYPES
        },
        "env.SLASH_COMMAND_TOOL_CHAR_BUDGET": document.get("env", {}).get(
            "SLASH_COMMAND_TOOL_CHAR_BUDGET", ""
        ),
        "nwave_hook_version": document.get("nwave_hook_version", ""),
        "permissions": json.dumps(document.get("permissions", {}), sort_keys=True),
    }


def _emitted_hook_document_bytes(settings_file: Path) -> bytes:
    """Return the exact canonical bytes of the Claude hook artifact only."""
    document = json.loads(settings_file.read_text(encoding="utf-8"))
    return json.dumps({"hooks": document["hooks"]}, indent=2).encode() + b"\\n"


def test_slice_01_h0_hooks_preservation_freezes_all_claude_registrations_and_emitted_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Property: host-neutral extraction preserves Claude's current hook output."""
    claude_home = tmp_path / "home"
    claude_dir = claude_home / ".claude"
    claude_dir.mkdir(parents=True)
    settings_file = claude_dir / "settings.json"
    settings_file.write_text(
        json.dumps({"permissions": {"allow": ["Read"]}}, indent=2) + "\\n",
        encoding="utf-8",
    )
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=Path.cwd() / "scripts" / "install",
        templates_dir=Path.cwd() / "nWave" / "templates",
        logger=logging.getLogger("h0-hooks-preservation"),
        project_root=Path.cwd(),
        framework_source=Path.cwd() / "nWave",
        dry_run=False,
    )
    plugin = DESPlugin()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: claude_home))
    monkeypatch.setattr(plugin, "_resolve_python_path", lambda: "python3")

    before = _settings_state(settings_file)
    result = plugin._install_des_hooks(context)
    after = _settings_state(settings_file)

    assert result.success, result.message
    assert_state_delta(
        before,
        after,
        universe=set(before),
        expected={
            **{f"hooks.{event}": set_to(after[f"hooks.{event}"]) for event in _EXPECTED_EVENT_TYPES},
            "env.SLASH_COMMAND_TOOL_CHAR_BUDGET": set_to("100000"),
            "nwave_hook_version": set_to(after["nwave_hook_version"]),
        },
        strict=True,
    )

    from scripts.shared.hook_definitions import HOOK_EVENTS

    observed_registrations = tuple(
        (registration.event, registration.matcher, registration.action)
        for registration in HOOK_EVENTS
    )
    assert observed_registrations == _EXPECTED_REGISTRATIONS
    assert len(observed_registrations) == 17
    assert {registration.event for registration in HOOK_EVENTS} == _EXPECTED_EVENT_TYPES

    artifact_digest = hashlib.sha256(
        _emitted_hook_document_bytes(settings_file)
    ).hexdigest()
    assert artifact_digest == _EXPECTED_HOOK_DOCUMENT_SHA256, (
        "Claude hook artifact drifted from the H0 preservation baseline; "
        "keep all registrations and emitted command bytes identical before "
        "adding host-neutral or Codex behavior. "
        f"expected={_EXPECTED_HOOK_DOCUMENT_SHA256}, actual={artifact_digest}"
    )
