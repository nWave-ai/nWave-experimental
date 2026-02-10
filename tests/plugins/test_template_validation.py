#!/usr/bin/env python3
"""
Template Validation Tests

Validates that template variables are properly resolved during build processing
and that unresolved variables are caught by validation.
"""

import sys
from pathlib import Path

import pytest


# Add project root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.processors.command_processor import CommandProcessor  # noqa: E402
from tools.utils.file_manager import FileManager  # noqa: E402


class TestTemplateValidation:
    """Test template variable validation in command processor."""

    @pytest.fixture
    def command_processor(self):
        """Create CommandProcessor instance for testing."""
        source_dir = REPO_ROOT / "nWave"
        output_dir = REPO_ROOT / "dist"
        file_manager = FileManager()
        return CommandProcessor(source_dir, output_dir, file_manager)

    def test_validate_template_resolution_passes_with_no_variables(
        self, command_processor
    ):
        """Valid content with no template variables should pass validation."""
        content = "This is normal content without any template variables."
        # Should not raise
        command_processor.validate_template_resolution(content, "test.md")

    def test_validate_template_resolution_fails_with_unresolved_variables(
        self, command_processor
    ):
        """Content with unresolved {{SCHEMA_*}} variables should raise ValueError."""
        content = "Content with {{SCHEMA_UNDEFINED}} variable."

        with pytest.raises(ValueError, match="Unresolved template variables"):
            command_processor.validate_template_resolution(content, "test.md")

    def test_validate_template_resolution_error_message_includes_file_path(
        self, command_processor
    ):
        """Error message should include the file path for debugging."""
        content = "Content with {{SCHEMA_BAD_VAR}} here."

        with pytest.raises(ValueError, match="test.md"):
            command_processor.validate_template_resolution(content, "test.md")

    def test_validate_template_resolution_catches_multiple_variables(
        self, command_processor
    ):
        """Should catch multiple unresolved variables."""
        content = """
        Content with {{SCHEMA_VAR_ONE}} and {{SCHEMA_VAR_TWO}}.
        """

        with pytest.raises(
            ValueError,
            match=r"SCHEMA_VAR_ONE.*SCHEMA_VAR_TWO|SCHEMA_VAR_TWO.*SCHEMA_VAR_ONE",
        ):
            command_processor.validate_template_resolution(content, "test.md")

    def test_process_template_variables_replaces_known_variables(
        self, command_processor
    ):
        """Template processor should replace known {{SCHEMA_*}} variables."""
        # This test assumes the template processor is initialized
        if not command_processor.template_processor:
            pytest.skip("TemplateProcessor not initialized")

        content = "Phases: {{SCHEMA_PHASE_NAMES}}"
        processed = command_processor.process_template_variables(content)

        # Should not contain the placeholder anymore
        assert "{{SCHEMA_PHASE_NAMES}}" not in processed
        # Should contain actual phase names
        assert "PREPARE" in processed or "phase" in processed.lower()

    def test_integration_template_processing_and_validation(self, command_processor):
        """Integration test: process known variables, validate no unresolved remain."""
        if not command_processor.template_processor:
            pytest.skip("TemplateProcessor not initialized")

        # Content with valid template variables
        content = """
        Phase count: {{PHASE_COUNT}}
        Phases: {{SCHEMA_PHASE_NAMES}}
        """

        # Process template variables
        processed = command_processor.process_template_variables(content)

        # Validation should pass (no unresolved SCHEMA_* variables)
        command_processor.validate_template_resolution(processed, "test.md")

        # Verify replacements occurred
        assert "{{PHASE_COUNT}}" not in processed
        assert "{{SCHEMA_PHASE_NAMES}}" not in processed
