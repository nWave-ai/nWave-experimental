"""Acceptance test for command template validator.

Phase 2 (RED_ACCEPTANCE): Validates that the command template validator
correctly identifies violations in non-compliant command files.
"""

import sys
from pathlib import Path


# Add scripts validators to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.validation.validate_commands import (
    CommandTemplateValidator,
    SeverityLevel,
    validate_command,
)


def test_reviewer_validates_command_template_compliance():
    """
    Scenario: Agent-builder-reviewer validates command template compliance

    Given agent-builder creates a new command using command template
    When agent-builder-reviewer performs peer review
    Then the reviewer validates command size is 50-60 lines
    And the reviewer ensures zero workflow duplication
    And the reviewer confirms explicit context bundling is present
    And the reviewer verifies agent invocation pattern is used
    And critical violations block approval
    And the reviewer provides actionable feedback for non-compliant commands
    """

    # Given: agent-builder creates a new command using command template
    test_command_file = Path(__file__).parent / "test_command_noncompliant.md"
    assert test_command_file.exists(), (
        f"Test command file not found: {test_command_file}"
    )

    # When: agent-builder-reviewer performs peer review
    result = validate_command(str(test_command_file))

    # Then: the reviewer validates command size is 50-60 lines
    assert result.size_metrics is not None, "Size metrics not computed"
    assert result.size_metrics.total_lines > 60, (
        f"Expected size > 60, got {result.size_metrics.total_lines}"
    )
    assert result.size_metrics.violation_factor > 1.0, "Expected violation factor > 1.0"
    print(
        f"✓ Size validation: {result.size_metrics.total_lines} lines (violation factor: {result.size_metrics.violation_factor:.2f}x)"
    )

    # And: the reviewer ensures zero workflow duplication
    assert len(result.embedded_workflows) > 0, "Expected to detect embedded workflows"
    assert "procedural_steps" in result.embedded_workflows, (
        "Expected to detect procedural steps"
    )
    assert "progress_tracking" in result.embedded_workflows, (
        "Expected to detect progress tracking"
    )
    assert "orchestration" in result.embedded_workflows, (
        "Expected to detect orchestration logic"
    )
    assert "parameter_parsing" in result.embedded_workflows, (
        "Expected to detect parameter parsing"
    )
    print(f"✓ Workflow duplication detection: {list(result.embedded_workflows.keys())}")

    # And: the reviewer confirms explicit context bundling is present
    # This should fail because the test file has implicit context
    context_violations = [
        v for v in result.violations if v.category == "context_bundling"
    ]
    assert len(context_violations) > 0, "Expected context bundling violations"
    print(
        f"✓ Context bundling validation: {len(context_violations)} violation(s) detected"
    )

    # And: the reviewer verifies agent invocation pattern is used
    # This should pass because the test file has @software-crafter
    invocation_violations = [
        v for v in result.violations if v.category == "invocation_pattern"
    ]
    assert len(invocation_violations) == 0, "Expected no invocation pattern violations"
    print("✓ Agent invocation pattern validation: No violations")

    # And: critical violations block approval
    blocker_violations = [
        v for v in result.violations if v.severity == SeverityLevel.BLOCKER
    ]
    assert len(blocker_violations) > 0, "Expected BLOCKER violations"
    assert result.approval_decision == "REJECTED_PENDING_REVISIONS", (
        f"Expected REJECTED_PENDING_REVISIONS, got {result.approval_decision}"
    )
    assert result.compliance_status == "BLOCKED", (
        f"Expected BLOCKED status, got {result.compliance_status}"
    )
    print(
        f"✓ Critical violations block approval: {len(blocker_violations)} BLOCKER violation(s)"
    )
    print(f"  - Approval decision: {result.approval_decision}")
    print(f"  - Compliance status: {result.compliance_status}")

    # And: the reviewer provides actionable feedback for non-compliant commands
    assert len(result.feedback) > 0, "Expected feedback to be generated"
    assert any("✗" in fb for fb in result.feedback), (
        "Expected critical feedback indicators"
    )

    # Verify feedback contains remediation guidance
    has_remediation = any("→" in fb for fb in result.feedback)
    assert has_remediation, "Expected remediation guidance in feedback"
    print(f"✓ Actionable feedback provided: {len(result.feedback)} feedback items")
    for fb in result.feedback[:3]:  # Show first 3 items
        print(f"  - {fb}")

    return result


def main():
    """Execute acceptance test."""
    print("=" * 70)
    print("PHASE 2 (RED_ACCEPTANCE): Command Template Validator Acceptance Test")
    print("=" * 70)
    print()

    try:
        result = test_reviewer_validates_command_template_compliance()

        print()
        print("=" * 70)
        print("ACCEPTANCE TEST RESULT: PASSED")
        print("=" * 70)
        print()
        print("Detailed Validation Report:")
        validator = CommandTemplateValidator(
            str(Path(__file__).parent / "test_command_noncompliant.md")
        )
        print(validator.format_report(result))

        return 0
    except AssertionError as e:
        print()
        print("=" * 70)
        print("ACCEPTANCE TEST RESULT: FAILED")
        print("=" * 70)
        print(f"Assertion Error: {e}")
        return 1
    except Exception as e:
        print()
        print("=" * 70)
        print("ACCEPTANCE TEST RESULT: ERROR")
        print("=" * 70)
        print(f"Exception: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
