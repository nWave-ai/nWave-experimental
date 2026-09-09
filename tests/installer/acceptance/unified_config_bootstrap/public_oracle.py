"""Public oracle for first-install unified configuration bootstrap.

This deliberately uses only the process CLI, files it publishes, and the hook
command installed into the user's settings.  It must remain source-blind: the
recovery is valuable only if its public composition works for an operator.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _environment(*, system_home: Path, agents_home: Path) -> dict[str, str]:
    """Declare every ambient location the public process is allowed to use."""
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


def _installed_pre_tool_use_command(settings_path: Path) -> str:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})
    candidates: list[str] = []
    for registration in hooks.get("PreToolUse", []):
        if registration.get("matcher") != "Bash":
            continue
        for hook in registration.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str) and " pre-tool-use" in command:
                candidates.append(command)
    assert len(candidates) == 1, (
        "WHAT: the installed Bash PreToolUse hook was not uniquely discoverable.\n"
        "WHY: a live installed hook is the consumer of global activation mode.\n"
        "HOW: install exactly one public nWave pre-tool-use command in settings.json."
    )
    return candidates[0]


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read one published JSON document without hiding its failure mode."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return None, f"file-read: {error}"
    except json.JSONDecodeError as error:
        return None, f"json-decode: {error}"
    if not isinstance(value, dict):
        return None, f"json-shape: expected object, got {type(value).__name__}"
    return value, None


def _process_diagnostic(
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


def _malformed_hook_protocol(
    hook: subprocess.CompletedProcess[str] | None,
) -> tuple[dict[str, Any], str | None]:
    """Project the documented malformed-event response into stable semantics.

    The installed PreToolUse protocol documents malformed JSON as exit 1 with a
    JSON error response whose ``reason`` begins ``Invalid JSON:``.  Raw output
    remains in phase diagnostics so a missing launcher or interpreter is not
    mistaken for that response.
    """
    if hook is None:
        return {
            "exit_code": None,
            "response_status": None,
            "reason_prefix": None,
        }, "hook-command was not discoverable"
    try:
        response = json.loads(hook.stdout)
    except json.JSONDecodeError as error:
        return {
            "exit_code": hook.returncode,
            "response_status": None,
            "reason_prefix": None,
        }, f"protocol-json-decode: {error}"
    if not isinstance(response, dict):
        return {
            "exit_code": hook.returncode,
            "response_status": None,
            "reason_prefix": None,
        }, f"protocol-json-shape: expected object, got {type(response).__name__}"
    reason = response.get("reason")
    return {
        "exit_code": hook.returncode,
        "response_status": response.get("status"),
        "reason_prefix": "Invalid JSON:"
        if isinstance(reason, str) and reason.startswith("Invalid JSON:")
        else None,
    }, None


def _bootstrap_defaults(document: dict[str, Any] | None) -> dict[str, Any]:
    """Project only the installer-owned defaults from the published document.

    The installer may retain additional canonical bookkeeping.  This projection
    keeps those bytes observable in diagnostics while declaring the independent
    defaults this journey owns.
    """
    document = document or {}
    attribution = document.get("attribution")
    documentation = document.get("documentation")
    return {
        "schema_version_is_integer_1": (
            type(document.get("schema-version")) is int
            and document["schema-version"] == 1
        ),
        "attribution_enabled": (
            attribution.get("enabled") if isinstance(attribution, dict) else None
        ),
        "attribution_trailer": (
            attribution.get("trailer") if isinstance(attribution, dict) else None
        ),
        "documentation_density": (
            documentation.get("density") if isinstance(documentation, dict) else None
        ),
        "documentation_expansion_prompt": (
            documentation.get("expansion_prompt")
            if isinstance(documentation, dict)
            else None
        ),
    }


def _mode_all_preserves_unrelated_fields(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> bool:
    """State the public transition law: mode all changes only activation.mode."""
    if before is None or after is None:
        return False
    expected = copy.deepcopy(before)
    activation = expected.get("activation")
    if activation is None:
        expected["activation"] = {"mode": "all"}
    elif isinstance(activation, dict):
        expected["activation"] = {**activation, "mode": "all"}
    else:
        return False
    return after == expected


def _guidance_has_attribution_on(guidance: str) -> bool:
    """Read the published communication line without binding its label spelling."""
    return bool(
        re.search(
            r"(?im)^-\s+.*\battribution\b.*\*\*(?:enabled|on)\*\*\s*$",
            guidance,
        )
    )


def observe_first_install() -> dict[str, Any]:
    """Run the complete operator journey and return its public observations."""
    with tempfile.TemporaryDirectory(prefix="nwave-unified-config-") as temporary:
        root = Path(temporary)
        system_home = root / "system-home"
        agents_home = root / "selected-nwave-home"
        project_root = root / "actual-project"
        system_home.mkdir()
        agents_home.mkdir()
        project_root.mkdir()
        environment = _environment(system_home=system_home, agents_home=agents_home)

        install = _cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )

        global_config = agents_home / ".nwave" / "config.json"
        bootstrap_document, bootstrap_failure = _read_json(global_config)

        mode = _cli(environment, project_root, "mode", "all")
        configured_document, configured_failure = _read_json(global_config)

        status = _cli(environment, project_root, "status")

        doctor = _cli(environment, project_root, "doctor", "--json")
        doctor_failure: str | None = None
        try:
            doctor_payload = json.loads(doctor.stdout)
            config_check = next(
                check
                for check in doctor_payload["checks"]
                if check.get("name") == "config_ssot"
            )
            if not isinstance(config_check, dict):
                raise TypeError("config_ssot check is not an object")
        except json.JSONDecodeError as error:
            config_check = {}
            doctor_failure = f"doctor-json-decode: {error}"
        except (AttributeError, KeyError, StopIteration, TypeError) as error:
            config_check = {}
            doctor_failure = f"doctor-config-ssot-discovery: {error}"

        try:
            guidance = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
            guidance_failure = None
        except (OSError, UnicodeDecodeError) as error:
            guidance = ""
            guidance_failure = f"guidance-read: {error}"
        try:
            installed_command = _installed_pre_tool_use_command(
                system_home / ".claude" / "settings.json"
            )
            hook_discovery_failure = None
        except (
            AssertionError,
            AttributeError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
        ) as error:
            installed_command = None
            hook_discovery_failure = f"hook-discovery: {error}"
        # A malformed event uses the installed command's documented protocol
        # response.  Its exit and JSON response distinguish dispatch from an
        # inactive gate as well as from shell/interpreter launch failures.
        hook = (
            subprocess.run(
                installed_command,
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
            if installed_command is not None
            else None
        )
        hook_protocol, hook_protocol_failure = _malformed_hook_protocol(hook)

        cli_argv = [sys.executable, "-m", "nwave_ai.cli"]
        diagnostics: dict[str, Any] = {
            "install": _process_diagnostic(
                "install",
                install,
                [*cli_argv, "install", "--yes", "--platform", "claude-code"],
            ),
            "mode": _process_diagnostic("mode", mode, [*cli_argv, "mode", "all"]),
            "status": _process_diagnostic("status", status, [*cli_argv, "status"]),
            "doctor": _process_diagnostic(
                "doctor", doctor, [*cli_argv, "doctor", "--json"]
            ),
            "files": {
                "global_bootstrap": bootstrap_failure,
                "global_after_mode": configured_failure,
                "guidance": guidance_failure,
                "hook_discovery": hook_discovery_failure,
            },
            "doctor_config_ssot_failure": doctor_failure,
            "hook_protocol_failure": hook_protocol_failure,
            "canonical_documents": {
                "bootstrap": bootstrap_document,
                "after_mode": configured_document,
            },
        }
        if hook is not None:
            diagnostics["hook"] = _process_diagnostic(
                "installed-pre-tool-use",
                hook,
                ["/bin/sh", "-c", installed_command or ""],
            )

        return {
            "semantic": {
                "install_exit_code": install.returncode,
                "global_bootstrap_defaults": _bootstrap_defaults(bootstrap_document),
                "mode_exit_code": mode.returncode,
                "mode_all_preserves_unrelated_fields": _mode_all_preserves_unrelated_fields(
                    bootstrap_document, configured_document
                ),
                "status_exit_code": status.returncode,
                "status": status.stdout.strip().splitlines(),
                "doctor_exit_code": doctor.returncode,
                "doctor_config_ssot": {
                    "passed": config_check.get("passed"),
                    "message": config_check.get("message"),
                },
                "guidance_has_standard_verbosity": "Communication verbosity: **standard**"
                in guidance,
                "guidance_has_attribution_on": _guidance_has_attribution_on(guidance),
                "malformed_hook_protocol": hook_protocol,
            },
            "diagnostics": diagnostics,
        }


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "global_bootstrap_defaults": {
        "schema_version_is_integer_1": True,
        "attribution_enabled": True,
        "attribution_trailer": "Co-Authored-By: nWave <nwave@nwave.ai>",
        "documentation_density": "lean",
        "documentation_expansion_prompt": "ask-intelligent",
    },
    "mode_exit_code": 0,
    "mode_all_preserves_unrelated_fields": True,
    "status_exit_code": 0,
    "status": ["Global activation mode: all", "This project is active."],
    "doctor_exit_code": 0,
    "doctor_config_ssot": {
        "passed": True,
        "message": "Effective config: enabled=False, verbosity='standard', attribution=True",
    },
    "guidance_has_standard_verbosity": True,
    "guidance_has_attribution_on": True,
    "malformed_hook_protocol": {
        "exit_code": 1,
        "response_status": "error",
        "reason_prefix": "Invalid JSON:",
    },
}


def test_first_install_bootstraps_one_global_config_across_public_consumers() -> None:
    observed = observe_first_install()
    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: the first-install public configuration observation differed from the "
        f"approved contract. Observed: {observed!r}.\n"
        "WHY: bootstrap, global mode, doctor, installed guidance, and the live hook "
        "must consume one selected-home configuration authority.\n"
        "HOW: restore the approved ConfigWriter/NWaveLocations composition without "
        "adding a new install or config command."
    )


if __name__ == "__main__":
    observation = observe_first_install()
    print(json.dumps(observation, indent=2, sort_keys=True))
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit(
            "public unified-config bootstrap observation differs from contract"
        )
