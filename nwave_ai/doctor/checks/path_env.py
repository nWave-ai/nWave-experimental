"""PathEnvCheck — verifies a Claude Code session can resolve $HOME/.claude/bin.

A session takes its PATH from settings.json env.PATH when that key is present
(Claude Code REPLACES the inherited PATH with it), otherwise from the PATH
inherited from the user's shell. The platform is reached through the
module-global ``os`` at call time (separator, normalization, directory probe).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from nwave_ai.common.check_result import CheckResult
from nwave_ai.doctor.checks._settings import read_settings


if TYPE_CHECKING:
    from nwave_ai.doctor.context import DoctorContext


class PathEnvCheck:
    """Check that claude_dir/bin is on the PATH a Claude Code session will use."""

    name: str = "path_env"
    description: str = "$HOME/.claude/bin is on the PATH of Claude Code sessions"

    def run(self, context: DoctorContext) -> CheckResult:
        """Return passed=True when claude_dir/bin is on the session's PATH.

        env.PATH present: it alone decides. Entries are split on
        ``os.pathsep`` and compared after normpath/normcase, so trailing
        separators, redundant segments and Windows case differences match.
        A non-matching ``.../<claude_dir name>/bin`` entry whose directory
        does not exist here marks a PATH frozen on another machine.

        env.PATH absent: the inherited process PATH decides.

        Args:
            context: Filesystem roots — reads context.settings_path.

        Returns:
            CheckResult with PATH details in message.
        """
        data, error = read_settings(context.settings_path)
        if error is not None:
            return error

        expected_bin = str(context.claude_dir / "bin")
        env_section = data.get("env", {})
        if isinstance(env_section, dict) and "PATH" in env_section:
            return _check_env_path(env_section["PATH"], expected_bin)
        return _check_inherited_path(expected_bin)


def _normalize(entry: str) -> str:
    return os.path.normcase(os.path.normpath(entry))


def _entries(path_value: str) -> list[str]:
    return [entry for entry in path_value.split(os.pathsep) if entry]


def _contains(path_value: str, expected_bin: str) -> bool:
    target = _normalize(expected_bin)
    return any(_normalize(entry) == target for entry in _entries(path_value))


def _tail(entry: str) -> tuple[str, str]:
    """Return the last two components, e.g. ``(".claude", "bin")``."""
    parent, leaf = os.path.split(_normalize(entry))
    return os.path.split(parent)[1], leaf


def _foreign_bin_entry(path_value: str, expected_bin: str) -> str | None:
    """Return a claude-bin-shaped entry whose directory is missing on this host."""
    expected_tail = _tail(expected_bin)
    for entry in _entries(path_value):
        if _tail(entry) == expected_tail and not os.path.isdir(entry):
            return entry
    return None


def _check_env_path(path_value: str, expected_bin: str) -> CheckResult:
    if _contains(path_value, expected_bin):
        return CheckResult(
            passed=True,
            error_code=None,
            message=f"env.PATH contains {expected_bin}",
            remediation=None,
        )

    foreign_entry = _foreign_bin_entry(path_value, expected_bin)
    if foreign_entry is not None:
        return CheckResult(
            passed=False,
            error_code="ENV_PATH_FROM_ANOTHER_MACHINE",
            message=(
                f"env.PATH looks like it came from another machine: {foreign_entry} "
                "does not exist here, and env.PATH replaces the session PATH"
            ),
            remediation=(
                "Remove env.PATH from settings.json and add "
                f"{expected_bin} to PATH in your shell profile "
                "(for example ~/.zshenv or ~/.bashrc)."
            ),
        )

    return CheckResult(
        passed=False,
        error_code="CLAUDE_BIN_NOT_IN_PATH",
        message=f"{expected_bin} is not in env.PATH",
        remediation=(
            f"Add {expected_bin} to env.PATH in settings.json, or remove env.PATH "
            "and add it to PATH in your shell profile."
        ),
    )


def _check_inherited_path(expected_bin: str) -> CheckResult:
    if _contains(os.environ.get("PATH", ""), expected_bin):
        return CheckResult(
            passed=True,
            error_code=None,
            message=f"inherited PATH contains {expected_bin}",
            remediation=None,
        )

    return CheckResult(
        passed=False,
        error_code="ENV_PATH_MISSING",
        message=(
            f"settings.json has no env.PATH and {expected_bin} is not on the "
            "inherited PATH"
        ),
        remediation=(
            f"Add {expected_bin} to PATH in your shell profile "
            "(for example ~/.zshenv or ~/.bashrc; on Windows, the user "
            "environment variables)."
        ),
    )
