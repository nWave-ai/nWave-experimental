"""PathEnvCheck — verifies $HOME/.claude/bin is in the env.PATH of settings.json."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nwave_ai.common.check_result import CheckResult
from nwave_ai.doctor.checks._settings import read_settings


if TYPE_CHECKING:
    from nwave_ai.doctor.context import DoctorContext


class PathEnvCheck:
    """Check that claude_dir/bin is present in settings.json env.PATH."""

    name: str = "path_env"
    description: str = "$HOME/.claude/bin is included in env.PATH in settings.json"

    def run(self, context: DoctorContext) -> CheckResult:
        """Return passed=True when claude_dir/bin is a member of env.PATH entries.

        Uses colon-split set membership to avoid substring false positives.

        Args:
            context: Filesystem roots — reads context.settings_path.

        Returns:
            CheckResult with PATH details in message.
        """
        data, error = read_settings(context.settings_path)
        if error is not None:
            return error

        env_section = data.get("env", {})
        if not isinstance(env_section, dict) or "PATH" not in env_section:
            return CheckResult(
                passed=False,
                error_code="ENV_PATH_MISSING",
                message="settings.json env.PATH key is absent",
                remediation=(
                    "Run `nwave-ai install` to add ~/.claude/bin to env.PATH "
                    "in settings.json."
                ),
            )

        expected_bin = str(context.claude_dir / "bin")
        path_entries = set(env_section["PATH"].split(":"))

        if expected_bin in path_entries:
            return CheckResult(
                passed=True,
                error_code=None,
                message=f"env.PATH contains {expected_bin}",
                remediation=None,
            )

        return CheckResult(
            passed=False,
            error_code="CLAUDE_BIN_NOT_IN_PATH",
            message=f"{expected_bin} is not in env.PATH",
            remediation=(
                f"Add {expected_bin} to env.PATH in settings.json, "
                "or run `nwave-ai install` to fix automatically."
            ),
        )
