"""The real session-start journey through the published driving port.

This module holds NO observation and NO expected result. It is the single
implementation of the operator journey both session-start oracles drive:
install nWave into a throwaway sandbox, enable a project, discover the
installer-published SessionStart command out of ``settings.json``, and execute
that command as a real process exactly as the host would.

Nothing here imports a production symbol, reads a template from the source
tree, or inspects a handler module. Two boundary facts are load-bearing:

* the installer refuses under a non-virtualenv interpreter, so the child
  process is ``sys.executable`` -- the interpreter running these tests;
* ``HOME``, ``CLAUDE_CONFIG_DIR``, ``NWAVE_AGENTS_HOME`` and ``CODEX_HOME`` are
  all pinned inside a throwaway sandbox, which is what keeps an operator's real
  ``~/.claude`` out of every observation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

# The published host contract: exactly one JSON object on stdout, wrapped.
HOOK_EVENT_NAME = "SessionStart"

# The installer-owned SessionStart command is positively identified by the
# subcommand it dispatches. Foreign SessionStart entries carry no such token.
DES_SESSION_START_TOKEN = " session-start"


def environment_for(*, system_home: Path, agents_home: Path) -> dict[str, str]:
    """Declare every ambient location the public processes are allowed to use."""
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(system_home),
            "NWAVE_AGENTS_HOME": str(agents_home),
            "CLAUDE_CONFIG_DIR": str(system_home / ".claude"),
            "CODEX_HOME": str(system_home / ".codex"),
            "PYTHONPATH": str(REPOSITORY_ROOT),
            "NO_COLOR": "1",
        }
    )
    return environment


def run_cli(
    environment: dict[str, str], project_root: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "nwave_ai.cli", *arguments],
        cwd=project_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )


def process_diagnostic(
    phase: str, process: subprocess.CompletedProcess[str], argv: list[str]
) -> dict[str, Any]:
    """Preserve the public process evidence without making it an oracle value."""
    return {
        "phase": phase,
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def installed_session_start_registration(
    settings_path: Path,
) -> tuple[dict[str, Any], str]:
    """The single installer-owned SessionStart registration, as published.

    Returns the registration object together with its command string, so the
    absence of a ``matcher`` key -- load-bearing, because SessionStart also
    fires on resume/clear/compact -- stays observable.
    """
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    found: list[tuple[dict[str, Any], str]] = []
    for registration in settings.get("hooks", {}).get(HOOK_EVENT_NAME, []):
        for hook in registration.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str) and DES_SESSION_START_TOKEN in command:
                found.append((registration, command))
    if len(found) != 1:
        raise LookupError(
            f"expected exactly one installer-owned {HOOK_EVENT_NAME} command, "
            f"found {len(found)}"
        )
    return found[0]


def session_start_commands(settings_path: Path) -> list[str]:
    """Every published SessionStart command, in published order.

    Unlike :func:`installed_session_start_registration` this reader demands
    nothing: it reports what the array actually holds, so an oracle can ask for
    the ABSENCE of installer-owned entries while still observing that foreign
    entries survive byte-for-byte. A missing file or a missing event key is an
    empty list -- emptied event arrays are pre-existing uninstall convention
    across every event, not residue specific to any one of them.
    """
    if not settings_path.exists():
        return []
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    entries = hooks.get(HOOK_EVENT_NAME)
    if not isinstance(entries, list):
        return []
    commands: list[str] = []
    for registration in entries:
        if not isinstance(registration, dict):
            continue
        # Both published shapes: a nested ``hooks`` list, and the flat form an
        # older install wrote directly on the registration.
        for hook in registration.get("hooks", []) or []:
            if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
        if isinstance(registration.get("command"), str):
            commands.append(registration["command"])
    return commands


def run_installed_hook(
    command: str, environment: dict[str, str], project_root: Path
) -> subprocess.CompletedProcess[str]:
    """Execute the published hook command exactly as the host would.

    The command is a shell string containing a literal ``$HOME``, so it must go
    through a shell with the sandbox ``HOME`` pinned in the environment.
    """
    envelope = json.dumps(
        {
            "hook_event_name": HOOK_EVENT_NAME,
            "source": "startup",
            "cwd": str(project_root),
            "session_id": "public-oracle-session",
        }
    )
    return subprocess.run(
        command,
        shell=True,
        executable="/bin/sh",
        cwd=project_root,
        env=environment,
        input=envelope,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def injected_context(
    hook: subprocess.CompletedProcess[str],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Project the host contract out of stdout.

    Several ``print(json.dumps(...))`` calls in one invocation would leave
    stdout invalid as a whole and silently drop every contribution but the
    first, so stdout is parsed as EXACTLY ONE JSON object -- never as the first
    of several.
    """
    shape: dict[str, Any] = {
        "stdout_is_exactly_one_json_object": False,
        "hook_event_name": None,
        "carries_system_message": None,
        "additional_context_is_nonempty_text": None,
    }
    try:
        payload = json.loads(hook.stdout)
    except json.JSONDecodeError as error:
        return None, shape, f"stdout-json-decode: {error}"
    if not isinstance(payload, dict):
        return (
            None,
            shape,
            f"stdout-shape: expected object, got {type(payload).__name__}",
        )
    shape["stdout_is_exactly_one_json_object"] = True
    shape["carries_system_message"] = "systemMessage" in payload
    specific = payload.get("hookSpecificOutput")
    if not isinstance(specific, dict):
        return (
            None,
            shape,
            "stdout-shape: the bare additionalContext form is not honored by the "
            "host; hookSpecificOutput must wrap it",
        )
    shape["hook_event_name"] = specific.get("hookEventName")
    context = specific.get("additionalContext")
    shape["additional_context_is_nonempty_text"] = (
        isinstance(context, str) and context.strip() != ""
    )
    return (context if isinstance(context, str) else None), shape, None
