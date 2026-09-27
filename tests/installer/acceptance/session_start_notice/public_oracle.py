"""Public oracle: session start carries the route notice into the agent's context.

Authority: docs/product/architecture/brief.md#Session Start Carries the Route
Notice Into the Agent's Own Context.

An agent beginning a session in a project where nWave is installed and enabled
must find, in its OWN starting context, a short notice naming the available
routes and what each one leaves behind -- without opening any project file.

Driving port: the real installed Claude Code SessionStart hook command, read
back out of the published ``<CLAUDE_CONFIG_DIR>/settings.json`` and executed as
a real process through a shell (the published command is a shell string
carrying a literal ``$HOME``). Nothing here imports a production symbol, reads
a template from the source tree, or inspects a handler module: the oracle only
observes the bytes the host would hand to the agent.

Two boundary facts this journey honours, both load-bearing:

* the installer refuses under a non-virtualenv interpreter, so the child
  process is ``sys.executable`` -- the interpreter running these tests;
* ``HOME``, ``CLAUDE_CONFIG_DIR``, ``NWAVE_AGENTS_HOME`` and ``CODEX_HOME`` are
  all pinned inside a throwaway sandbox, which is what keeps an operator's real
  ``~/.claude`` out of the observation.

The handler's failure algebra is fail-open by mandate: every degradation
(fragment absent, ambiguous, unreadable or empty) yields NO stdout and exit 0.
Because every assertion below demands the PRESENCE of the notice, each of those
degradations surfaces here as a failed observation and never as a silent pass.

The SSOT for the notice wording is secured observationally: the injected
``additionalContext`` must appear BYTE-FOR-BYTE inside the CLAUDE.md the very
same journey published into the project. A drifted asset path or a second,
hand-written wording fails this chain.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from tests.installer.acceptance.session_start_notice.session_journey import (
    HOOK_EVENT_NAME,
    REPOSITORY_ROOT,
    environment_for,
    injected_context,
    installed_session_start_registration,
    process_diagnostic,
    run_cli,
    run_installed_hook,
)


# The journey through the real driving port is shared, unchanged, with the
# notice-budget oracle: one implementation describes the port, so the two
# observations can never disagree about how a session is actually started.
_environment = environment_for
_cli = run_cli
_process_diagnostic = process_diagnostic
_installed_session_start_registration = installed_session_start_registration
_run_installed_hook = run_installed_hook
_injected_context = injected_context

__all__ = ["HOOK_EVENT_NAME", "REPOSITORY_ROOT"]

# The three routes, each named with what it leaves behind. These are questions
# asked of the INJECTED bytes, so the agent's own context -- not some file it
# might open -- is what carries them.
ROUTE_NAMES = ("spine waves", "des ", "working directly")
ROUTE_CONSEQUENCES = ("independent review", "public oracle", "gate")


def observe_session_start_notice() -> dict[str, Any]:
    """Run the complete operator journey and return its public observations."""
    with tempfile.TemporaryDirectory(prefix="nwave-session-start-notice-") as temporary:
        root = Path(temporary)
        system_home = root / "system-home"
        agents_home = root / "selected-nwave-home"
        project_root = root / "some-user-project"
        for directory in (system_home, agents_home, project_root):
            directory.mkdir()
        environment = _environment(system_home=system_home, agents_home=agents_home)

        install = _cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )

        settings_path = system_home / ".claude" / "settings.json"
        registration: dict[str, Any] | None = None
        command: str | None = None
        discovery_failure: str | None = None
        try:
            registration, command = _installed_session_start_registration(settings_path)
        except (
            LookupError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ) as error:
            discovery_failure = f"hook-discovery: {error}"

        # 1. Installed but NOT yet enabled: nWave's opt-in-per-repository
        #    contract must keep the agent's context untouched.
        before_enable = (
            _run_installed_hook(command, environment, project_root)
            if command is not None
            else None
        )

        enable = _cli(environment, project_root, "project", "enable", "--yes")

        # 2. Enabled: the same published command now carries the notice.
        after_enable = (
            _run_installed_hook(command, environment, project_root)
            if command is not None
            else None
        )
        if after_enable is None:
            context, shape, contract_failure = (
                None,
                {
                    "stdout_is_exactly_one_json_object": False,
                    "hook_event_name": None,
                    "carries_system_message": None,
                    "additional_context_is_nonempty_text": None,
                },
                "hook command was not discoverable",
            )
        else:
            context, shape, contract_failure = _injected_context(after_enable)

        try:
            guidance = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
            guidance_failure = None
        except (OSError, UnicodeDecodeError) as error:
            guidance = ""
            guidance_failure = f"guidance-read: {error}"

        lowered = (context or "").lower()
        cli_argv = [sys.executable, "-m", "nwave_ai.cli"]
        diagnostics: dict[str, Any] = {
            "install": _process_diagnostic(
                "install",
                install,
                [*cli_argv, "install", "--yes", "--platform", "claude-code"],
            ),
            "enable": _process_diagnostic(
                "enable", enable, [*cli_argv, "project", "enable", "--yes"]
            ),
            "published_command": command,
            "published_registration": registration,
            "hook_discovery_failure": discovery_failure,
            "host_contract_failure": contract_failure,
            "guidance_failure": guidance_failure,
            "injected_context": context,
        }
        if before_enable is not None:
            diagnostics["hook_before_enable"] = _process_diagnostic(
                "session-start-before-enable",
                before_enable,
                ["/bin/sh", "-c", command or ""],
            )
        if after_enable is not None:
            diagnostics["hook_after_enable"] = _process_diagnostic(
                "session-start-after-enable",
                after_enable,
                ["/bin/sh", "-c", command or ""],
            )

        return {
            "semantic": {
                "install_exit_code": install.returncode,
                "enable_exit_code": enable.returncode,
                # The registration is published without a matcher, so the notice
                # also reaches resume/clear/compact sessions.
                "registration_declares_no_matcher": (
                    registration is not None and "matcher" not in registration
                ),
                "command_is_uniquely_discoverable": command is not None,
                # Opt-in per repository, using the existing activation gate.
                "inactive_project_leaves_context_untouched": (
                    before_enable is not None
                    and before_enable.returncode == 0
                    and before_enable.stdout.strip() == ""
                ),
                "hook_exit_code": (
                    after_enable.returncode if after_enable is not None else None
                ),
                "host_contract": shape,
                # The agent reads the notice without opening any project file.
                "notice_names_every_route": (
                    all(name in lowered for name in ROUTE_NAMES) if context else False
                ),
                "notice_states_what_each_route_leaves_behind": (
                    all(token in lowered for token in ROUTE_CONSEQUENCES)
                    if context
                    else False
                ),
                # One wording, one source: the injected bytes are the published
                # bytes. A second hand-written notice cannot satisfy this.
                "notice_matches_published_guidance_byte_for_byte": (
                    bool(context) and context.strip() in guidance
                ),
            },
            "diagnostics": diagnostics,
        }


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "enable_exit_code": 0,
    "registration_declares_no_matcher": True,
    "command_is_uniquely_discoverable": True,
    "inactive_project_leaves_context_untouched": True,
    "hook_exit_code": 0,
    "host_contract": {
        "stdout_is_exactly_one_json_object": True,
        "hook_event_name": HOOK_EVENT_NAME,
        "carries_system_message": False,
        "additional_context_is_nonempty_text": True,
    },
    "notice_names_every_route": True,
    "notice_states_what_each_route_leaves_behind": True,
    "notice_matches_published_guidance_byte_for_byte": True,
}


def test_session_start_carries_the_route_notice_into_the_agents_context() -> None:
    observed = observe_session_start_notice()
    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: an agent beginning a session in an nWave project did not receive the "
        f"route notice in its own starting context. Observed: {observed!r}.\n"
        "WHY: the routes and what each one leaves behind must reach the agent "
        "before it opens any project file, through the one published wording.\n"
        "HOW: publish one matcher-less SessionStart registration whose command "
        "prints exactly one wrapped hookSpecificOutput object carrying the shipped "
        "delivery-route notice, only for an enabled project."
    )


if __name__ == "__main__":
    observation = observe_session_start_notice()
    print(json.dumps(observation, indent=2, sort_keys=True, default=str))
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit(
            "public session-start notice observation differs from contract"
        )
