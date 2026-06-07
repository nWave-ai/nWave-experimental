"""HookPythonPathCheck — verifies the python binary in hook commands is resolvable."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nwave_ai.common.check_result import CheckResult
from nwave_ai.doctor.checks._settings import read_settings


if TYPE_CHECKING:
    from nwave_ai.doctor.context import DoctorContext


def _extract_hook_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk the hooks dict and collect all hook entry dicts."""
    entries: list[dict[str, Any]] = []
    for hook_list in data.get("hooks", {}).values():
        if not isinstance(hook_list, list):
            continue
        for matcher_entry in hook_list:
            if not isinstance(matcher_entry, dict):
                continue
            for hook in matcher_entry.get("hooks", []):
                if isinstance(hook, dict) and "command" in hook:
                    entries.append(hook)
    return entries


def _extract_binary(command: str, home_dir: Path) -> str | None:
    """Extract the python binary name or path from a hook command string.

    Expands $HOME to home_dir.  Tokenises the command, skips KEY=VALUE
    env-var assignments, then returns the first token whose final path
    component starts with 'python' — whether it is a bare name (e.g.
    'python3') or an absolute path (e.g. '/usr/bin/python3').

    Args:
        command: The full hook command string.
        home_dir: Resolved home directory from DoctorContext.

    Returns:
        Binary token (bare name or absolute path string), or None.
    """
    command_expanded = command.replace("$HOME", str(home_dir))
    try:
        tokens = shlex.split(command_expanded)
    except ValueError:
        tokens = command_expanded.split()

    for token in tokens:
        if "=" in token and not token.startswith("/"):
            continue
        name = Path(token).name
        if name.startswith("python"):
            return token
    return None


def _env_path_from_hook(hook_entry: dict[str, Any]) -> str | None:
    """Extract PATH from the hook entry's env dict, if present."""
    env = hook_entry.get("env")
    if isinstance(env, dict):
        return env.get("PATH")
    return None


def _binary_resolvable(binary_token: str, env_path: str | None) -> bool:
    """Return True if binary_token points to an executable.

    For absolute paths: verify the file exists.
    For bare names: use shutil.which with env_path (falling back to the
    process PATH when env_path is None).

    Args:
        binary_token: Bare name (e.g. 'python3') or absolute path.
        env_path: PATH string from settings.json env, or None.

    Returns:
        True if the binary is reachable at runtime.
    """
    if Path(binary_token).is_absolute():
        return Path(binary_token).exists()
    resolved = shutil.which(binary_token, path=env_path)
    return resolved is not None


class HookPythonPathCheck:
    """Check that the python binary referenced in hook commands is resolvable."""

    name: str = "hook_python_path"
    description: str = "Python binary referenced in hook commands is resolvable"

    def run(self, context: DoctorContext) -> CheckResult:
        """Return passed=True when every hook binary is resolvable.

        Accepts both absolute paths (verified by file existence) and bare
        binary names (verified via shutil.which with the settings env PATH).

        Args:
            context: Filesystem roots — reads context.settings_path.

        Returns:
            CheckResult with binary resolution details in message.
        """
        data, error = read_settings(context.settings_path)
        if error is not None:
            return error

        hook_entries = _extract_hook_entries(data)
        if not hook_entries:
            return CheckResult(
                passed=False,
                error_code="NO_HOOK_COMMANDS",
                message="No hook commands found in settings.json",
                remediation="Run `nwave-ai install` to register hook commands.",
            )

        missing: list[str] = []
        found: list[str] = []
        for hook_entry in hook_entries:
            command = hook_entry["command"]
            binary = _extract_binary(command, context.home_dir)
            if binary is None:
                continue
            env_path = _env_path_from_hook(hook_entry)
            if _binary_resolvable(binary, env_path):
                found.append(binary)
            else:
                missing.append(binary)

        if missing:
            return CheckResult(
                passed=False,
                error_code="HOOK_BINARY_MISSING",
                message=f"Hook binary not resolvable: {', '.join(missing)}",
                remediation=(
                    "Re-run `nwave-ai install` to reinstall the Python binary, "
                    "or ensure your virtual environment is active."
                ),
            )

        if not found:
            return CheckResult(
                passed=False,
                error_code="NO_BINARY_IN_COMMANDS",
                message="No python binary detected in hook commands",
                remediation="Run `nwave-ai install` to register hook commands with a valid binary.",
            )

        return CheckResult(
            passed=True,
            error_code=None,
            message=f"Hook binary verified: {found[0]}",
            remediation=None,
        )
