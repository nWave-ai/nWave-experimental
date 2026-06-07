"""Shared CheckResult dataclass for nwave_ai checks.

Extracted from scripts/install/preflight_checker so that both the installer
preflight layer and the doctor diagnostic command share the same type without
a cross-boundary import.
"""

from dataclasses import dataclass


@dataclass
class CheckResult:
    """Result of a single check.

    Invariant: when passed=True, both error_code and remediation MUST be None.
    Violated states are rejected at construction time.

    Attributes:
        passed: Whether the check passed successfully.
        error_code: Short error code (None if passed).
        message: Human-readable description of the check result.
        remediation: Instructions to fix the issue (None if passed).
        check_name: Identifier of the check that produced this result (set by runner).
    """

    passed: bool
    error_code: str | None
    message: str
    remediation: str | None
    check_name: str = ""

    def __post_init__(self) -> None:
        if self.passed and self.error_code is not None:
            raise ValueError(
                f"CheckResult invariant violated: passed=True but error_code={self.error_code!r}"
            )
        if self.passed and self.remediation is not None:
            raise ValueError(
                "CheckResult invariant violated: passed=True but remediation is set"
            )
