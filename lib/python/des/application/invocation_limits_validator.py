"""
Invocation Limits Validator

Validates that turn and timeout limits are configured in step files before
invoking sub-agents. This prevents execution with unconfigured limits and
provides clear error guidance.

BUSINESS VALUE:
- Fail fast: Catch missing configuration before wasting agent turns
- Clear guidance: Error messages tell developers exactly how to fix
- Enforce discipline: Require explicit limit configuration per TDD methodology
"""

from dataclasses import dataclass, field
from pathlib import Path

from des.ports.driven_ports.filesystem_port import FileSystemPort


@dataclass
class InvocationLimitsResult:
    """Result of invocation limits validation.

    Attributes:
        is_valid: True if limits are properly configured
        errors: List of validation error messages
        guidance: List of actionable guidance for fixing errors
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)


class InvocationLimitsValidator:
    """Validates turn and timeout configuration before sub-agent invocation.

    Pre-invocation validation that ensures:
    1. max_turns is configured and positive
    2. duration_minutes is configured and positive

    Example usage:
        validator = InvocationLimitsValidator(filesystem=real_filesystem)
        result = validator.validate_limits(step_file_path)
        if not result.is_valid:
            print("Validation failed:", result.errors)
            print("Guidance:", result.guidance)
    """

    def __init__(self, filesystem: FileSystemPort):
        """Initialize validator with filesystem adapter.

        Args:
            filesystem: FileSystemPort adapter for file operations.
        """
        self._filesystem = filesystem

    def validate_limits(self, step_file_path: Path | str) -> InvocationLimitsResult:
        """Validate turn and timeout limits in step file.

        Args:
            step_file_path: Path to step JSON file

        Returns:
            InvocationLimitsResult with validation status, errors, and guidance
        """
        if isinstance(step_file_path, str):
            step_file_path = Path(step_file_path)

        step_data = self._filesystem.read_json(step_file_path)
        tdd_cycle = step_data.get("tdd_cycle", {})

        errors: list[str] = []
        guidance: list[str] = []

        self._validate_positive_int_field(
            tdd_cycle,
            "max_turns",
            missing_guidance="Add 'max_turns' field to tdd_cycle section with a positive integer value. Example: \"max_turns\": 50",
            invalid_guidance="Set 'max_turns' to a positive integer value. Typical values: 50 for simple tasks, 100 for complex refactoring",
            errors=errors,
            guidance=guidance,
        )
        self._validate_positive_int_field(
            tdd_cycle,
            "duration_minutes",
            missing_guidance="Add 'duration_minutes' field to tdd_cycle section with a positive integer value. Example: \"duration_minutes\": 30",
            invalid_guidance="Set 'duration_minutes' to a positive integer value. Typical values: 30 for simple tasks, 60-120 for complex refactoring",
            errors=errors,
            guidance=guidance,
        )

        if errors:
            guidance.insert(
                0,
                "Configure turn and timeout limits in step file under tdd_cycle section. "
                "These limits enforce TDD discipline and prevent unbounded execution.",
            )

        return InvocationLimitsResult(
            is_valid=not errors, errors=errors, guidance=guidance
        )

    @staticmethod
    def _validate_positive_int_field(
        tdd_cycle: dict,
        field_name: str,
        missing_guidance: str,
        invalid_guidance: str,
        errors: list[str],
        guidance: list[str],
    ) -> None:
        """Validate that a tdd_cycle field is a present positive integer."""
        value = tdd_cycle.get(field_name)
        if value is None:
            errors.append(f"MISSING: {field_name} not configured in step file")
            guidance.append(missing_guidance)
        elif not isinstance(value, int) or value <= 0:
            errors.append(
                f"INVALID: {field_name} must be a positive integer (got: {value})"
            )
            guidance.append(invalid_guidance)
