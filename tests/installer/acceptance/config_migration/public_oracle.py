"""Public oracle for one-shot migration to the unified configuration files.

The only driving port is the installed ``nwave-ai`` process.  This oracle
creates pre-upgrade operator state, invokes that process, and observes only
the files it publishes plus its public status and doctor commands.
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


def _bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _doctor_effective(process: subprocess.CompletedProcess[str]) -> str | None:
    try:
        payload = json.loads(process.stdout)
        check = next(
            item for item in payload["checks"] if item.get("name") == "config_ssot"
        )
    except (AttributeError, KeyError, StopIteration, TypeError, json.JSONDecodeError):
        return None
    return check.get("message") if isinstance(check, dict) else None


def _public_process_observation(
    process: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    """Keep the externally visible result used for cutover comparisons."""
    return {
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def _installed_pre_tool_use_command(settings_path: Path) -> str | None:
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        commands = [
            hook["command"]
            for registration in settings.get("hooks", {}).get("PreToolUse", [])
            if registration.get("matcher") == "Bash"
            for hook in registration.get("hooks", [])
            if isinstance(hook.get("command"), str)
            and " pre-tool-use" in hook["command"]
        ]
    except (AttributeError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return commands[0] if len(commands) == 1 else None


def _run_hook(
    command: str | None, *, environment: dict[str, str], project_root: Path
) -> subprocess.CompletedProcess[str] | None:
    if command is None:
        return None
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


def _config_snapshot(paths: tuple[Path, ...]) -> dict[str, bytes | None]:
    return {str(path): _bytes(path) for path in paths}


def _migration_paths(agents_home: Path, project_root: Path) -> dict[str, Path]:
    global_dir = agents_home / ".nwave"
    project_dir = project_root / ".nwave"
    return {
        "legacy_global": global_dir / "global-config.json",
        "canonical_global": global_dir / "config.json",
        "legacy_project": project_dir / "des-config.json",
        "legacy_marker": project_dir / "local-config.json",
        "canonical_project": project_dir / "config.json",
    }


def _backup(path: Path) -> Path:
    return path.with_name(f"{path.name}.unified-config.bak")


def _valid_migration_observation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="nwave-config-migration-valid-"
    ) as temporary:
        root = Path(temporary)
        system_home, agents_home, project_root = (
            root / "system-home",
            root / "selected-nwave-home",
            root / "project",
        )
        for directory in (system_home, agents_home, project_root):
            directory.mkdir()
        environment = _environment(system_home=system_home, agents_home=agents_home)
        paths = _migration_paths(agents_home, project_root)
        paths["legacy_global"].parent.mkdir()
        paths["legacy_project"].parent.mkdir()

        global_legacy = b'{\n  "schema-version": 1,\n  "verbosity": "verbose",\n  "attribution": "off"\n}\n'
        project_legacy = b'{\n  "schema-version": 1,\n  "verbosity": "terse",\n  "audit_logging_enabled": false\n}\n'
        marker_legacy = b'{\n  "enabled_for_repo": false\n}\n'
        paths["legacy_global"].write_bytes(global_legacy)
        paths["legacy_project"].write_bytes(project_legacy)
        paths["legacy_marker"].write_bytes(marker_legacy)

        install = _cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        canonical_global = _json_object(paths["canonical_global"])
        canonical_project = _json_object(paths["canonical_project"])
        migrated_paths = tuple(paths.values())
        after_first_install = _config_snapshot(
            (*migrated_paths, *(_backup(path) for path in migrated_paths))
        )
        retired_files_removed_after_first_install = {
            name: not paths[name].exists()
            for name in ("legacy_global", "legacy_project", "legacy_marker")
        }
        retry = _cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        after_retry = _config_snapshot(
            (*migrated_paths, *(_backup(path) for path in migrated_paths))
        )

        # Establish what the canonical configuration publicly means before any
        # retired filenames are reintroduced with deliberately conflicting data.
        canonical_status = _cli(environment, project_root, "status")
        canonical_doctor = _cli(environment, project_root, "doctor", "--json")

        # A retired filename that would be malformed if read must not affect
        # ordinary post-cutover consumers, nor may those consumers retire it.
        paths["legacy_global"].write_bytes(b"{ malformed retired input")
        paths["legacy_project"].write_bytes(b'{"enabled": true}')
        paths["legacy_marker"].write_bytes(b'{"enabled_for_repo": true}')
        retired_before_consumers = _config_snapshot(
            (paths["legacy_global"], paths["legacy_project"], paths["legacy_marker"])
        )
        status = _cli(environment, project_root, "status")
        doctor = _cli(environment, project_root, "doctor", "--json")
        hook = _run_hook(
            _installed_pre_tool_use_command(system_home / ".claude" / "settings.json"),
            environment=environment,
            project_root=project_root,
        )
        retired_after_consumers = _config_snapshot(
            (paths["legacy_global"], paths["legacy_project"], paths["legacy_marker"])
        )
        try:
            project_gitignore = (project_root / ".nwave" / ".gitignore").read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeDecodeError):
            project_gitignore = ""

        return {
            "install_exit_code": install.returncode,
            "global_preferences_preserved": {
                "verbosity": canonical_global.get("verbosity")
                if canonical_global
                else None,
                "attribution": canonical_global.get("attribution")
                if canonical_global
                else None,
            },
            "project_preferences_preserved": {
                "verbosity": canonical_project.get("verbosity")
                if canonical_project
                else None,
                "enabled": canonical_project.get("enabled")
                if canonical_project
                else None,
                "audit_logging_enabled": canonical_project.get("audit_logging_enabled")
                if canonical_project
                else None,
            },
            "retired_files_removed": retired_files_removed_after_first_install,
            "byte_preserving_backups": {
                "global": _bytes(_backup(paths["legacy_global"])) == global_legacy,
                "project": _bytes(_backup(paths["legacy_project"])) == project_legacy,
                "marker": _bytes(_backup(paths["legacy_marker"])) == marker_legacy,
            },
            "retry_exit_code": retry.returncode,
            "retry_is_byte_noop": after_first_install == after_retry,
            "post_cutover_status_exit_code": status.returncode,
            "post_cutover_doctor_exit_code": doctor.returncode,
            "post_cutover_effective_config": _doctor_effective(doctor),
            "reintroduced_retired_files_leave_status_canonical": (
                _public_process_observation(status)
                == _public_process_observation(canonical_status)
            ),
            "reintroduced_retired_files_leave_doctor_canonical": (
                _public_process_observation(doctor)
                == _public_process_observation(canonical_doctor)
            ),
            "post_cutover_disabled_hook_is_silent": hook is not None
            and (hook.returncode == 0 and hook.stdout == "" and hook.stderr == ""),
            "retired_files_ignored_and_unmodified_by_consumers": (
                retired_before_consumers == retired_after_consumers
            ),
            "canonical_project_config_is_trackable": (
                "!config.json" in project_gitignore
                and "!local-config.json" not in project_gitignore
            ),
        }


def _refusal_observation(
    *, malformed: str | None = None, conflict: str | None = None, future: bool = False
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="nwave-config-migration-refusal-"
    ) as temporary:
        root = Path(temporary)
        system_home, agents_home, project_root = (
            root / "system-home",
            root / "selected-nwave-home",
            root / "project",
        )
        for directory in (system_home, agents_home, project_root):
            directory.mkdir()
        environment = _environment(system_home=system_home, agents_home=agents_home)
        paths = _migration_paths(agents_home, project_root)
        paths["legacy_global"].parent.mkdir()
        paths["legacy_project"].parent.mkdir()

        if conflict == "canonical-versus-des-config":
            paths["canonical_project"].write_bytes(
                b'{"schema-version": 1, "enabled": true}\n'
            )
            paths["legacy_project"].write_bytes(
                b'{"schema-version": 1, "enabled": false}\n'
            )
        elif conflict == "local-config-versus-des-config":
            paths["legacy_project"].write_bytes(
                b'{"schema-version": 1, "enabled": false}\n'
            )
            paths["legacy_marker"].write_bytes(b'{"enabled_for_repo": true}\n')
        elif malformed == "global":
            paths["legacy_global"].write_bytes(b"{ not valid JSON")
        elif malformed == "marker_after_global":
            # A writer that replaces the valid global source before parsing the
            # later marker would visibly violate the all-inputs-before-writes
            # cutover contract.
            paths["legacy_global"].write_bytes(
                b'{"schema-version": 1, "verbosity": "verbose"}\n'
            )
            paths["legacy_marker"].write_bytes(b"{ not valid JSON")
        elif future:
            paths["legacy_global"].write_bytes(
                b'{"schema-version": 1, "verbosity": "verbose"}\n'
            )
            paths["legacy_project"].write_bytes(
                b'{"schema-version": 2, "enabled": false}\n'
            )
        else:
            raise ValueError(
                "a refusal observation needs a malformed, conflicting, or future source"
            )
        observed_paths = (
            paths["canonical_global"],
            paths["canonical_project"],
            paths["legacy_global"],
            paths["legacy_project"],
            paths["legacy_marker"],
            *(_backup(path) for path in paths.values()),
        )
        before = _config_snapshot(observed_paths)
        install = _cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        after = _config_snapshot(observed_paths)
        return {
            "refused_nonzero": install.returncode != 0,
            "all_canonical_legacy_and_backup_bytes_unchanged": before == after,
        }


def observe_config_migration() -> dict[str, Any]:
    """Observe migration, refusal, recovery, retry, and consumer cutover."""
    return {
        "valid_migration": _valid_migration_observation(),
        "malformed_refusal": _refusal_observation(malformed="global"),
        "late_malformed_refusal": _refusal_observation(malformed="marker_after_global"),
        "unsupported_version_refusal": _refusal_observation(future=True),
        "conflicting_refusal": _refusal_observation(
            conflict="canonical-versus-des-config"
        ),
        "local_config_enabled_conflicting_refusal": _refusal_observation(
            conflict="local-config-versus-des-config"
        ),
    }


EXPECTED_SEMANTIC_OBSERVATION = {
    "valid_migration": {
        "install_exit_code": 0,
        "global_preferences_preserved": {"verbosity": "verbose", "attribution": "off"},
        "project_preferences_preserved": {
            "verbosity": "terse",
            "enabled": False,
            "audit_logging_enabled": False,
        },
        "retired_files_removed": {
            "legacy_global": True,
            "legacy_project": True,
            "legacy_marker": True,
        },
        "byte_preserving_backups": {"global": True, "project": True, "marker": True},
        "retry_exit_code": 0,
        "retry_is_byte_noop": True,
        "post_cutover_status_exit_code": 0,
        "post_cutover_doctor_exit_code": 0,
        "post_cutover_effective_config": "Effective config: enabled=False, verbosity='terse', attribution=False",
        "reintroduced_retired_files_leave_status_canonical": True,
        "reintroduced_retired_files_leave_doctor_canonical": True,
        "post_cutover_disabled_hook_is_silent": True,
        "retired_files_ignored_and_unmodified_by_consumers": True,
        "canonical_project_config_is_trackable": True,
    },
    "malformed_refusal": {
        "refused_nonzero": True,
        "all_canonical_legacy_and_backup_bytes_unchanged": True,
    },
    "late_malformed_refusal": {
        "refused_nonzero": True,
        "all_canonical_legacy_and_backup_bytes_unchanged": True,
    },
    "unsupported_version_refusal": {
        "refused_nonzero": True,
        "all_canonical_legacy_and_backup_bytes_unchanged": True,
    },
    "conflicting_refusal": {
        "refused_nonzero": True,
        "all_canonical_legacy_and_backup_bytes_unchanged": True,
    },
    "local_config_enabled_conflicting_refusal": {
        "refused_nonzero": True,
        "all_canonical_legacy_and_backup_bytes_unchanged": True,
    },
}


def test_legacy_configuration_migrates_once_or_refuses_without_mutation() -> None:
    observed = observe_config_migration()
    assert observed == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: the public configuration-migration observation differed from the "
        f"approved contract. Observed: {observed!r}.\n"
        "WHY: an upgrade must preserve valid preferences exactly once, keep "
        "recoverable source bytes, and reject every unsafe cutover before mutation.\n"
        "HOW: route migration only through ConfigWriter; validate and reconcile all "
        "sources before replacement, then make runtime consumers use config.json only."
    )


if __name__ == "__main__":
    observation = observe_config_migration()
    print(json.dumps(observation, indent=2, sort_keys=True))
    if observation != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit(
            "public configuration-migration observation differs from contract"
        )
