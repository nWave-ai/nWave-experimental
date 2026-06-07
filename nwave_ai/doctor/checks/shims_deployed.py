"""ShimsDeployedCheck — verifies the consolidated des shim is present and executable."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    from nwave_ai.doctor.context import DoctorContext


EXPECTED_SHIMS: tuple[str, ...] = ("des",)


class ShimsDeployedCheck:
    """Check that the single des shim exists and is executable in claude_dir/bin/."""

    name: str = "shims_deployed"
    description: str = "The des shim script exists and is executable in ~/.claude/bin/"

    def run(self, context: DoctorContext) -> CheckResult:
        """Return passed=True when all shims are present and executable.

        Args:
            context: Filesystem roots — checks context.claude_dir / "bin".

        Returns:
            CheckResult with per-shim status in message.
        """
        bin_dir = context.claude_dir / "bin"
        if not bin_dir.exists():
            return CheckResult(
                passed=False,
                error_code="BIN_DIR_MISSING",
                message=f"{bin_dir} does not exist",
                remediation="Run `nwave-ai install` to deploy the shim scripts.",
            )

        issues: list[str] = []
        ok: list[str] = []
        for shim in EXPECTED_SHIMS:
            shim_path = bin_dir / shim
            if not shim_path.exists():
                issues.append(f"{shim}: missing")
            elif not os.access(shim_path, os.X_OK):
                issues.append(f"{shim}: not executable")
            else:
                ok.append(shim)

        if issues:
            issue_str = ", ".join(issues)
            return CheckResult(
                passed=False,
                error_code="SHIMS_INCOMPLETE",
                message=f"Shim issues: {issue_str}",
                remediation="Run `nwave-ai install` to redeploy the shim scripts.",
            )

        ok_str = ", ".join(ok)
        return CheckResult(
            passed=True,
            error_code=None,
            message=f"All shims present and executable: {ok_str}",
            remediation=None,
        )
