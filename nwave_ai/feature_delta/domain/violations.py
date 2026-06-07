"""ValidationViolation and ValidationResult."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationViolation:
    rule: str
    severity: str
    file: str
    line: int
    offender: str
    remediation: str
    did_you_mean: str | None = field(default=None)


@dataclass(frozen=True)
class ValidationResult:
    violations: tuple[ValidationViolation, ...]
    duration_ms: int
    # Optional override exit code (65 = input error, 70 = startup refused).
    # When None the caller derives the code from violations presence (0 or 1).
    exit_code_hint: int | None = field(default=None)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0
