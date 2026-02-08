"""
Test that execute.md TDD phases stay in sync with validator source of truth.

The source file uses {{MANDATORY_PHASES}} template variable which the build
system replaces from step-tdd-cycle-schema.json. This test verifies:
1. Source contains the template variable (not hardcoded phases)
2. Built output contains resolved phases matching the validator
"""

from pathlib import Path

from des.application.validator import TDDPhaseValidator


class TestExecuteTemplateSync:
    """Verify execute.md TDD phases use build-time template injection."""

    def test_source_uses_template_variable(self):
        """
        GIVEN execute.md source file
        WHEN we check the build-system TDD_7_PHASES section (## heading)
        THEN it contains {{MANDATORY_PHASES}} template variable, not hardcoded phases
        """
        with open("nWave/tasks/nw/execute.md") as f:
            content = f.read()

        # Find the build-system section (## heading), not the DES prompt template
        # (# heading inside a code block). The build-system section uses ## TDD_7_PHASES.
        tdd_section_start = content.find("\n## TDD_7_PHASES")
        assert tdd_section_start != -1, (
            "## TDD_7_PHASES section not found in execute.md"
        )

        section = content[tdd_section_start : tdd_section_start + 500]

        assert "{{MANDATORY_PHASES}}" in section, (
            "execute.md source must use {{MANDATORY_PHASES}} template variable"
        )

    def test_source_declares_schema_v3(self):
        """
        GIVEN execute.md source file
        WHEN we check the build-system TDD_7_PHASES section comment (## heading)
        THEN it declares Schema v3.0 and references TDDPhaseValidator
        """
        with open("nWave/tasks/nw/execute.md") as f:
            content = f.read()

        # Find the build-system section (## heading), not the DES prompt template
        tdd_section_start = content.find("\n## TDD_7_PHASES")
        assert tdd_section_start != -1, "## TDD_7_PHASES section not found"

        section = content[tdd_section_start : tdd_section_start + 300]

        assert "Schema v3.0" in section, (
            "execute.md must declare 'Schema v3.0' in TDD_7_PHASES section"
        )

        assert "TDDPhaseValidator.MANDATORY_PHASES_V3" in section, (
            "execute.md must reference TDDPhaseValidator.MANDATORY_PHASES_V3"
        )

    def test_built_output_has_resolved_phases(self):
        """
        GIVEN execute.md processed through the build system
        WHEN we check the built output
        THEN {{MANDATORY_PHASES}} is resolved to actual phase list from schema
        """
        built_path = Path("dist/ide/commands/nw/execute.md")
        if not built_path.exists():
            return  # Skip if not built yet

        content = built_path.read_text()

        # Built output should NOT contain unresolved template variable
        assert "{{MANDATORY_PHASES}}" not in content, (
            "Built execute.md still contains unresolved {{MANDATORY_PHASES}}"
        )

        # Built output should contain phase names from validator
        validator = TDDPhaseValidator()
        for phase in validator.MANDATORY_PHASES:
            assert phase in content, f"Built execute.md missing phase: {phase}"
