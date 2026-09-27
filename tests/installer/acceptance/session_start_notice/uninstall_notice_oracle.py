"""Public oracle: uninstall removes the session-start injection entirely.

Authority: docs/product/architecture/brief.md#Uninstall Removes The Session-Start
Injection Entirely.

Uninstalling nWave from a project must remove the session-start injection the
way the retirement path already removes the two historical arrays: a session
started afterwards carries no injected notice and no residual hook entry.

Driving port: the published ``nwave-ai uninstall --force`` process, plus the
published SessionStart command read back out of
``<CLAUDE_CONFIG_DIR>/settings.json``. Driven port: that one ``settings.json``.
Nothing here imports a production symbol, reads a template from the source
tree, or inspects a handler module -- the oracle observes only published bytes.

Three properties make this observation falsifiable rather than vacuous:

* The BASELINE leg runs first. Before uninstalling, the published command must
  inject a non-empty ``additionalContext``. Without it, a green post-uninstall
  result could be produced by an install that never injected anything.
* Foreign SessionStart entries -- the operator's and other tools' -- are
  captured before uninstall and required to survive BYTE-FOR-BYTE in published
  order. The SessionStart array is a shared, user-owned contract; nWave owns
  exactly one positively identified entry in it.
* The post-uninstall session leg executes what the published array REGISTERS,
  because that is all a real session dispatches. Re-running the command string
  remembered from before the uninstall would observe a dangling invocation the
  host no longer makes -- something production can never close.
* An EMPTY SessionStart array is explicitly tolerated. Emptied event keys
  survive uninstall for every event, so pruning them is a different observation
  spanning all events and is not asserted here.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from tests.installer.acceptance.session_start_notice.session_journey import (
    DES_SESSION_START_TOKEN,
    REPOSITORY_ROOT,
    environment_for,
    injected_context,
    installed_session_start_registration,
    process_diagnostic,
    run_cli,
    run_installed_hook,
    session_start_commands,
)


__all__ = [
    "EXPECTED_SEMANTIC_OBSERVATION",
    "REPOSITORY_ROOT",
    "observe_uninstall_removes_session_start_injection",
]


# Foreign SessionStart entries seeded into the shared, user-owned array before
# uninstall. The second is a deliberate near-match: a withdrawn nWave shell
# marker that a user has since modified and now owns. Removing it would breach
# the preserve-foreign contract.
FOREIGN_SESSION_START_COMMANDS = (
    "python3 -m lyra.session_start",
    "# des-hook:orchestrator-affordance-refresh-standalone\n"
    "python3 /opt/operator/session_start.py --keep",
)


def _seed_foreign_session_start_entries(settings_path: Path) -> None:
    """Append the foreign entries to the published array, preserving nWave's."""
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = settings.setdefault("hooks", {})
    entries = hooks.setdefault("SessionStart", [])
    for command in FOREIGN_SESSION_START_COMMANDS:
        entries.append({"hooks": [{"type": "command", "command": command}]})
    settings_path.write_text(json.dumps(settings), encoding="utf-8")


def observe_uninstall_removes_session_start_injection() -> dict[str, Any]:
    """Run the complete operator journey and return its public observations."""
    with tempfile.TemporaryDirectory(prefix="nwave-uninstall-notice-") as temporary:
        root = Path(temporary)
        system_home = root / "system-home"
        agents_home = root / "selected-nwave-home"
        project_root = root / "some-user-project"
        for directory in (system_home, agents_home, project_root):
            directory.mkdir()
        environment = environment_for(system_home=system_home, agents_home=agents_home)
        settings_path = system_home / ".claude" / "settings.json"

        install = run_cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        enable = run_cli(environment, project_root, "project", "enable", "--yes")

        # --- Baseline leg: the injection must actually exist before removal. ---
        command: str | None = None
        discovery_failure: str | None = None
        try:
            _registration, command = installed_session_start_registration(settings_path)
        except (
            LookupError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ) as error:
            discovery_failure = f"hook-discovery: {error}"

        before = (
            run_installed_hook(command, environment, project_root)
            if command is not None
            else None
        )
        baseline_context: str | None = None
        baseline_failure: str | None = None
        if before is not None:
            baseline_context, _shape, baseline_failure = injected_context(before)
        else:
            baseline_failure = "hook command was not discoverable"

        # The foreign entries share the array with nWave's own registration.
        seed_failure: str | None = None
        try:
            _seed_foreign_session_start_entries(settings_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            seed_failure = f"seed: {error}"

        # --- The act under observation. ---
        uninstall = run_cli(environment, project_root, "uninstall", "--force")

        commands_after = session_start_commands(settings_path)
        owned_after = [c for c in commands_after if DES_SESSION_START_TOKEN in c]
        foreign_after = [c for c in commands_after if DES_SESSION_START_TOKEN not in c]

        # --- A session started after uninstall carries no injected notice. ---
        # A session runs exactly what the published array REGISTERS, so that is
        # what is executed here -- not the command string remembered from before
        # the uninstall, which the host would no longer dispatch at all. Foreign
        # entries may legitimately fail in this sandbox; the only thing asserted
        # of them is that none of them injects an nWave notice.
        after_runs: list[dict[str, Any]] = []
        injecting_after: list[str] = []
        for registered in commands_after:
            run = run_installed_hook(registered, environment, project_root)
            context, shape, failure = injected_context(run)
            after_runs.append(
                {
                    **process_diagnostic(
                        "session-start-after-uninstall",
                        run,
                        ["/bin/sh", "-c", registered],
                    ),
                    "contract_shape": shape,
                    "contract_failure": failure,
                }
            )
            if failure is None and isinstance(context, str) and context.strip() != "":
                injecting_after.append(registered)

        cli_argv = [sys.executable, "-m", "nwave_ai.cli"]
        diagnostics: dict[str, Any] = {
            "install": process_diagnostic(
                "install",
                install,
                [*cli_argv, "install", "--yes", "--platform", "claude-code"],
            ),
            "enable": process_diagnostic(
                "enable", enable, [*cli_argv, "project", "enable", "--yes"]
            ),
            "uninstall": process_diagnostic(
                "uninstall", uninstall, [*cli_argv, "uninstall", "--force"]
            ),
            "published_command": command,
            "hook_discovery_failure": discovery_failure,
            "baseline_contract_failure": baseline_failure,
            "seed_failure": seed_failure,
            "baseline_injected_context": baseline_context,
            "session_start_commands_after_uninstall": commands_after,
            "settings_file_exists_after_uninstall": settings_path.exists(),
            "hooks_after_uninstall": after_runs,
        }
        if before is not None:
            diagnostics["hook_before_uninstall"] = process_diagnostic(
                "session-start-before-uninstall",
                before,
                ["/bin/sh", "-c", command or ""],
            )

        return {
            "semantic": {
                "install_exit_code": install.returncode,
                "enable_exit_code": enable.returncode,
                # Baseline: there really was an injection to remove.
                "notice_was_injected_before_uninstall": (
                    baseline_failure is None
                    and isinstance(baseline_context, str)
                    and baseline_context.strip() != ""
                ),
                "foreign_entries_were_seeded": seed_failure is None,
                "uninstall_exit_code": uninstall.returncode,
                # The whole point: nWave's own entry is gone from the array.
                "installer_owned_session_start_commands_after_uninstall": owned_after,
                # The shared array's other producers are untouched, in order.
                "foreign_session_start_commands_survive_in_order": (
                    foreign_after == list(FOREIGN_SESSION_START_COMMANDS)
                ),
                # A session started now carries no injected notice at all: no
                # registered SessionStart command produces additionalContext.
                "session_start_commands_injecting_a_notice_after_uninstall": (
                    injecting_after
                ),
            },
            "diagnostics": diagnostics,
        }


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "enable_exit_code": 0,
    "notice_was_injected_before_uninstall": True,
    "foreign_entries_were_seeded": True,
    "uninstall_exit_code": 0,
    # Zero installer-owned commands remain. An EMPTY array satisfies this: it is
    # pre-existing convention across every event, not this slice's residue.
    "installer_owned_session_start_commands_after_uninstall": [],
    "foreign_session_start_commands_survive_in_order": True,
    # No registered SessionStart command injects a notice any more.
    "session_start_commands_injecting_a_notice_after_uninstall": [],
}
