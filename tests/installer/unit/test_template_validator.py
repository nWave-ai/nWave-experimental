"""
Unit Tests: TemplateValidator Components

Tests for des.validator module:
- TemplateValidator: Main entry point for validation
- MandatorySectionChecker: Validates 8 mandatory sections
- TDDPhaseValidator: Validates 7 TDD phases
- ValidationResult: Data class for validation results
"""


class TestValidationResultDataclass:
    """ValidationResult dataclass tests."""

    def test_validation_result_with_passed_status(self):
        """ValidationResult stores PASSED status with empty errors."""
        from des.application.validator import ValidationResult

        result = ValidationResult(
            status="PASSED", errors=[], task_invocation_allowed=True, duration_ms=45.3
        )

        assert result.status == "PASSED"
        assert result.errors == []
        assert result.task_invocation_allowed is True
        assert result.duration_ms == 45.3

    def test_validation_result_with_failed_status(self):
        """ValidationResult stores FAILED status with errors list."""
        from des.application.validator import ValidationResult

        errors = [
            "MISSING: Mandatory section 'TIMEOUT_INSTRUCTION' not found",
            "INCOMPLETE: TDD phase 'REFACTOR_CONTINUOUS' not mentioned",
        ]
        result = ValidationResult(
            status="FAILED",
            errors=errors,
            task_invocation_allowed=False,
            duration_ms=23.1,
        )

        assert result.status == "FAILED"
        assert len(result.errors) == 2
        assert result.task_invocation_allowed is False


class TestMandatorySectionChecker:
    """MandatorySectionChecker validates 8 mandatory sections."""

    def test_complete_prompt_validates_all_sections(self):
        """Prompt with all 8 sections passes validation."""
        from des.application.validator import MandatorySectionChecker

        prompt = """
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter

        # TASK_CONTEXT
        Implement UserRepository

        # TDD_7_PHASES
        PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN_UNIT

        # QUALITY_GATES
        G1: One test active

        # OUTCOME_RECORDING
        Update step file

        # BOUNDARY_RULES
        Scope defined

        # TIMEOUT_INSTRUCTION
        50 turns
        """

        checker = MandatorySectionChecker()
        errors = checker.validate(prompt)

        assert errors == []

    def test_missing_timeout_instruction_section(self):
        """Prompt missing TIMEOUT_INSTRUCTION returns error."""
        from des.application.validator import MandatorySectionChecker

        prompt = """
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter

        # TASK_CONTEXT
        Implement UserRepository

        # TDD_7_PHASES
        PREPARE, RED_ACCEPTANCE

        # QUALITY_GATES
        G1: One test active

        # OUTCOME_RECORDING
        Update step file

        # BOUNDARY_RULES
        Scope defined
        """

        checker = MandatorySectionChecker()
        errors = checker.validate(prompt)

        assert len(errors) > 0
        assert any("TIMEOUT_INSTRUCTION" in error for error in errors)

    def test_missing_multiple_sections(self):
        """Prompt missing multiple sections returns multiple errors."""
        from des.application.validator import MandatorySectionChecker

        prompt = """
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter

        # TASK_CONTEXT
        Implement UserRepository
        """

        checker = MandatorySectionChecker()
        errors = checker.validate(prompt)

        assert len(errors) >= 5  # Missing TDD_7_PHASES, QUALITY_GATES, etc.


class TestTDDPhaseValidator:
    """TDDPhaseValidator validates 7 TDD phases."""

    def test_all_7_phases_present(self):
        """Prompt mentioning all 7 phases passes validation."""
        from des.application.validator import TDDPhaseValidator

        prompt = """
        # TDD_7_PHASES
        Execute in order:
        1. PREPARE
        2. RED_ACCEPTANCE
        3. RED_UNIT
        4. GREEN
        5. REVIEW
        6. REFACTOR_CONTINUOUS
        7. COMMIT
        """

        validator = TDDPhaseValidator()
        errors = validator.validate(prompt)

        assert errors == []

    def test_missing_refactor_continuous_phase(self):
        """Prompt missing REFACTOR_CONTINUOUS returns error."""
        from des.application.validator import TDDPhaseValidator

        prompt = """
        # TDD_7_PHASES
        1. PREPARE
        2. RED_ACCEPTANCE
        3. RED_UNIT
        4. GREEN
        5. REVIEW
        6. COMMIT
        """

        validator = TDDPhaseValidator()
        errors = validator.validate(prompt)

        assert len(errors) > 0
        assert any("REFACTOR_CONTINUOUS" in error for error in errors)

    def test_missing_multiple_phases(self):
        """Prompt missing multiple phases returns multiple errors."""
        from des.application.validator import TDDPhaseValidator

        prompt = """
        # TDD_7_PHASES
        1. PREPARE
        2. RED_ACCEPTANCE
        3. RED_UNIT
        """

        validator = TDDPhaseValidator()
        errors = validator.validate(prompt)

        assert len(errors) >= 4  # Missing GREEN, REVIEW, REFACTOR_CONTINUOUS, COMMIT


class TestTemplateValidator:
    """TemplateValidator: Main entry point."""

    def test_validator_accepts_complete_prompt(self):
        """Complete prompt with all sections and phases returns PASSED."""
        from des.application.validator import TemplateValidator

        prompt = """
        <!-- DES-VALIDATION: required -->
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter

        # TASK_CONTEXT
        Implement UserRepository

        # TDD_7_PHASES
        1. PREPARE
        2. RED_ACCEPTANCE
        3. RED_UNIT
        4. GREEN
        5. REVIEW
        6. REFACTOR_CONTINUOUS
        7. COMMIT

        # QUALITY_GATES
        G1: One test active

        # OUTCOME_RECORDING
        Update step file

        # BOUNDARY_RULES
        Scope defined

        # TIMEOUT_INSTRUCTION
        50 turns
        """

        validator = TemplateValidator()
        result = validator.validate_prompt(prompt)

        assert result.status == "PASSED"
        assert result.errors == []
        assert result.task_invocation_allowed is True

    def test_validator_rejects_incomplete_prompt(self):
        """Incomplete prompt returns FAILED with errors."""
        from des.application.validator import TemplateValidator

        prompt = """
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter
        """

        validator = TemplateValidator()
        result = validator.validate_prompt(prompt)

        assert result.status == "FAILED"
        assert len(result.errors) > 0
        assert result.task_invocation_allowed is False

    def test_validator_validates_duration(self):
        """Validation includes duration_ms measurement."""
        from des.application.validator import TemplateValidator

        prompt = """
        # DES_METADATA
        Step: 01-01.json

        # AGENT_IDENTITY
        Agent: software-crafter

        # TASK_CONTEXT
        Implement UserRepository

        # TDD_7_PHASES
        1. PREPARE
        2. RED_ACCEPTANCE
        3. RED_UNIT
        4. GREEN
        5. REVIEW
        6. REFACTOR_CONTINUOUS
        7. COMMIT

        # QUALITY_GATES
        G1: One test active

        # OUTCOME_RECORDING
        Update step file

        # BOUNDARY_RULES
        Scope defined

        # TIMEOUT_INSTRUCTION
        50 turns
        """

        validator = TemplateValidator()
        result = validator.validate_prompt(prompt)

        assert result.duration_ms is not None
        assert result.duration_ms >= 0
