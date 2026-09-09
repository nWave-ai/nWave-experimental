"""Public oracle for typed project configuration overrides.

The only driving surface here is the installed ``nwave-ai`` process.  It
observes files actually published by that process, its doctor output, managed
project guidance, and the installed hook command; it deliberately imports no
production implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _environment(*, system_home: Path, agents_home: Path) -> dict[str, str]:
    """Declare each ambient location available to the public process."""
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


def _cli(
    environment: dict[str, str], project_root: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "nwave_ai.cli", *arguments],
        cwd=project_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return None, f"file-read: {error}"
    except json.JSONDecodeError as error:
        return None, f"json-decode: {error}"
    if not isinstance(value, dict):
        return None, f"json-shape: expected object, got {type(value).__name__}"
    return value, None


def _snapshot_bytes(path: Path) -> tuple[bytes | None, str | None]:
    """Capture a published artifact exactly; absence is an observation, not a skip."""
    try:
        return path.read_bytes(), None
    except OSError as error:
        return None, f"file-read: {error}"


def _bytes_unchanged(
    before: tuple[bytes | None, str | None], after: tuple[bytes | None, str | None]
) -> bool:
    """Require both snapshots to exist before declaring preservation."""
    before_bytes, before_failure = before
    after_bytes, after_failure = after
    return (
        before_failure is None
        and after_failure is None
        and before_bytes is not None
        and after_bytes is not None
        and before_bytes == after_bytes
    )


def _installed_pre_tool_use_command(settings_path: Path) -> str:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    commands: list[str] = []
    for registration in settings.get("hooks", {}).get("PreToolUse", []):
        if registration.get("matcher") != "Bash":
            continue
        for hook in registration.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str) and " pre-tool-use" in command:
                commands.append(command)
    assert len(commands) == 1, (
        "WHAT: the installed Bash PreToolUse hook was not uniquely discoverable.\n"
        "WHY: this public journey needs one live hook consumer of project enablement.\n"
        "HOW: install exactly one public nWave pre-tool-use command in settings.json."
    )
    return commands[0]


def _run_hook(
    command: str | None,
    *,
    environment: dict[str, str],
    project_root: Path,
) -> subprocess.CompletedProcess[str] | None:
    if command is None:
        return None
    # Invalid JSON is the discriminator: an active hook reaches its documented
    # protocol error, whereas an inactive project is silently allowed by the
    # activation gate before the handler can parse the input.
    return subprocess.run(
        command,
        shell=True,
        executable="/bin/sh",
        cwd=project_root,
        env=environment,
        input="{",
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _hook_protocol(
    hook: subprocess.CompletedProcess[str] | None,
) -> tuple[dict[str, Any], str | None]:
    if hook is None:
        return {
            "exit_code": None,
            "status": None,
            "invalid_json": False,
        }, "missing command"
    try:
        response = json.loads(hook.stdout)
    except json.JSONDecodeError as error:
        return {
            "exit_code": hook.returncode,
            "status": None,
            "invalid_json": False,
        }, f"protocol-json-decode: {error}"
    if not isinstance(response, dict):
        return {
            "exit_code": hook.returncode,
            "status": None,
            "invalid_json": False,
        }, f"protocol-json-shape: expected object, got {type(response).__name__}"
    reason = response.get("reason")
    return {
        "exit_code": hook.returncode,
        "status": response.get("status"),
        "invalid_json": isinstance(reason, str) and reason.startswith("Invalid JSON:"),
    }, None


def _doctor_config_observation(
    process: subprocess.CompletedProcess[str],
) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(process.stdout)
        row = next(
            check for check in payload["checks"] if check.get("name") == "config_ssot"
        )
        if not isinstance(row, dict):
            raise TypeError("config_ssot check is not an object")
    except (
        AttributeError,
        KeyError,
        StopIteration,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        return {"passed": None, "message": None}, f"doctor-config-ssot: {error}"
    return {"passed": row.get("passed"), "message": row.get("message")}, None


def _process_diagnostic(
    process: subprocess.CompletedProcess[str], argv: list[str]
) -> dict[str, Any]:
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def observe_project_override() -> dict[str, Any]:
    """Exercise one project override and a distinct untouched project."""
    with tempfile.TemporaryDirectory(
        prefix="nwave-project-config-override-"
    ) as temporary:
        root = Path(temporary)
        system_home = root / "system-home"
        agents_home = root / "selected-nwave-home"
        project_a = root / "actual-project-a"
        project_b = root / "actual-project-b"
        for directory in (system_home, agents_home, project_a, project_b):
            directory.mkdir()
        environment = _environment(system_home=system_home, agents_home=agents_home)
        global_config_path = agents_home / ".nwave" / "config.json"
        project_config_path = project_a / ".nwave" / "config.json"
        guidance_path = project_a / "CLAUDE.md"

        install = _cli(
            environment, project_a, "install", "--yes", "--platform", "claude-code"
        )
        mode_all = _cli(environment, project_a, "mode", "all")
        global_after_mode_all = _snapshot_bytes(global_config_path)
        set_verbosity = _cli(
            environment, project_a, "project", "set", "verbosity", "terse", "--yes"
        )
        set_attribution = _cli(
            environment, project_a, "project", "set", "attribution", "off", "--yes"
        )
        doctor = _cli(environment, project_a, "doctor", "--json")

        project_config, project_config_failure = _read_json(project_config_path)
        try:
            guidance = guidance_path.read_text(encoding="utf-8")
            guidance_failure = None
        except (OSError, UnicodeDecodeError) as error:
            guidance = ""
            guidance_failure = f"guidance-read: {error}"
        try:
            hook_command = _installed_pre_tool_use_command(
                system_home / ".claude" / "settings.json"
            )
            hook_discovery_failure = None
        except (
            AssertionError,
            AttributeError,
            OSError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            hook_command = None
            hook_discovery_failure = f"hook-discovery: {error}"

        malformed_argvs = {
            "invalid_typed_value": ["project", "set", "verbosity", "loud", "--yes"],
            "duplicate_value": ["project", "set", "enabled", "false", "false", "--yes"],
            "extra_argument": [
                "project",
                "set",
                "attribution",
                "off",
                "unexpected",
                "--yes",
            ],
        }
        malformed: dict[str, dict[str, Any]] = {}
        malformed_diagnostics: dict[str, Any] = {}
        for name, argv in malformed_argvs.items():
            before_project = _snapshot_bytes(project_config_path)
            before_global = _snapshot_bytes(global_config_path)
            before_guidance = _snapshot_bytes(guidance_path)
            refusal = _cli(environment, project_a, *argv)
            after_project = _snapshot_bytes(project_config_path)
            after_global = _snapshot_bytes(global_config_path)
            after_guidance = _snapshot_bytes(guidance_path)
            malformed[name] = {
                "refused_nonzero": refusal.returncode != 0,
                "project_config_bytes_unchanged": _bytes_unchanged(
                    before_project, after_project
                ),
                "global_config_bytes_unchanged": _bytes_unchanged(
                    before_global, after_global
                ),
                "guidance_bytes_unchanged": _bytes_unchanged(
                    before_guidance, after_guidance
                ),
            }
            malformed_diagnostics[name] = {
                "refusal": _process_diagnostic(refusal, argv),
                "project_config_before": before_project,
                "project_config_after": after_project,
                "global_config_before": before_global,
                "global_config_after": after_global,
                "guidance_before": before_guidance,
                "guidance_after": after_guidance,
            }

        set_disabled = _cli(
            environment, project_a, "project", "set", "enabled", "false", "--yes"
        )
        global_after_project_mutations = _snapshot_bytes(global_config_path)
        disabled_hook = _run_hook(
            hook_command, environment=environment, project_root=project_a
        )
        untouched_hook = _run_hook(
            hook_command, environment=environment, project_root=project_b
        )
        doctor_config, doctor_failure = _doctor_config_observation(doctor)
        untouched_hook_protocol, untouched_hook_failure = _hook_protocol(untouched_hook)

        disabled_hook_is_silent = disabled_hook is not None and (
            disabled_hook.returncode == 0
            and disabled_hook.stdout == ""
            and disabled_hook.stderr == ""
        )
        attribution = project_config.get("attribution") if project_config else None
        return {
            "semantic": {
                "install_exit_code": install.returncode,
                "mode_all_exit_code": mode_all.returncode,
                "set_verbosity_exit_code": set_verbosity.returncode,
                "set_attribution_exit_code": set_attribution.returncode,
                "doctor_exit_code": doctor.returncode,
                "doctor_config_ssot": doctor_config,
                "project_config": {
                    "schema_version_is_integer_1": bool(project_config)
                    and type(project_config.get("schema-version")) is int
                    and project_config["schema-version"] == 1,
                    "verbosity": project_config.get("verbosity")
                    if project_config
                    else None,
                    "attribution_enabled": attribution.get("enabled")
                    if isinstance(attribution, dict)
                    else None,
                },
                "guidance_has_terse_verbosity": "Communication verbosity: **terse**"
                in guidance,
                "guidance_has_attribution_off": "Commit attribution: **disabled**"
                in guidance,
                "set_enabled_false_exit_code": set_disabled.returncode,
                "global_config_bytes_unchanged_after_project_mutations": _bytes_unchanged(
                    global_after_mode_all, global_after_project_mutations
                ),
                "malformed_project_sets": malformed,
                "disabled_project_hook_is_silent": disabled_hook_is_silent,
                "untouched_project_hook": untouched_hook_protocol,
            },
            "diagnostics": {
                "install": _process_diagnostic(
                    install, ["install", "--yes", "--platform", "claude-code"]
                ),
                "mode_all": _process_diagnostic(mode_all, ["mode", "all"]),
                "set_verbosity": _process_diagnostic(
                    set_verbosity, ["project", "set", "verbosity", "terse", "--yes"]
                ),
                "set_attribution": _process_diagnostic(
                    set_attribution, ["project", "set", "attribution", "off", "--yes"]
                ),
                "doctor": _process_diagnostic(doctor, ["doctor", "--json"]),
                "set_enabled_false": _process_diagnostic(
                    set_disabled, ["project", "set", "enabled", "false", "--yes"]
                ),
                "global_config_after_mode_all": global_after_mode_all,
                "global_config_after_project_mutations": global_after_project_mutations,
                "malformed_project_sets": malformed_diagnostics,
                "project_config_failure": project_config_failure,
                "guidance_failure": guidance_failure,
                "hook_discovery_failure": hook_discovery_failure,
                "doctor_failure": doctor_failure,
                "untouched_hook_failure": untouched_hook_failure,
                "disabled_hook": None
                if disabled_hook is None
                else _process_diagnostic(disabled_hook, ["installed-pre-tool-use"]),
                "untouched_hook": None
                if untouched_hook is None
                else _process_diagnostic(untouched_hook, ["installed-pre-tool-use"]),
                "project_config": project_config,
            },
        }


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "mode_all_exit_code": 0,
    "set_verbosity_exit_code": 0,
    "set_attribution_exit_code": 0,
    "doctor_exit_code": 0,
    "doctor_config_ssot": {
        "passed": True,
        "message": "Effective config: enabled=False, verbosity='terse', attribution=False",
    },
    "project_config": {
        "schema_version_is_integer_1": True,
        "verbosity": "terse",
        "attribution_enabled": False,
    },
    "guidance_has_terse_verbosity": True,
    "guidance_has_attribution_off": True,
    "set_enabled_false_exit_code": 0,
    "global_config_bytes_unchanged_after_project_mutations": True,
    "malformed_project_sets": {
        "invalid_typed_value": {
            "refused_nonzero": True,
            "project_config_bytes_unchanged": True,
            "global_config_bytes_unchanged": True,
            "guidance_bytes_unchanged": True,
        },
        "duplicate_value": {
            "refused_nonzero": True,
            "project_config_bytes_unchanged": True,
            "global_config_bytes_unchanged": True,
            "guidance_bytes_unchanged": True,
        },
        "extra_argument": {
            "refused_nonzero": True,
            "project_config_bytes_unchanged": True,
            "global_config_bytes_unchanged": True,
            "guidance_bytes_unchanged": True,
        },
    },
    "disabled_project_hook_is_silent": True,
    "untouched_project_hook": {
        "exit_code": 1,
        "status": "error",
        "invalid_json": True,
    },
}


def test_project_config_override_reaches_doctor_guidance_and_hooks() -> None:
    observed = observe_project_override()
    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: the public project-override observation differed from the approved "
        f"contract. Observed: {observed!r}.\n"
        "WHY: a typed project declaration must override global values for doctor and "
        "managed guidance, while explicit disablement silences only that project.\n"
        "HOW: make `nwave-ai project set` publish its typed field through ConfigWriter, "
        "refresh owned guidance after success, and retain the unified read/gate chain."
    )


if __name__ == "__main__":
    observation = observe_project_override()
    print(
        json.dumps(
            observation,
            indent=2,
            sort_keys=True,
            default=lambda value: (
                value.hex() if isinstance(value, bytes) else str(value)
            ),
        )
    )
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit(
            "public project-config override observation differs from contract"
        )
