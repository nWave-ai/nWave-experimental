"""
Unit tests for template validator with canonical schema v4.0.

Tests validate that validator uses canonical 5-phase TDD cycle from
step-tdd-cycle-schema.json (single source of truth).

Schema v4.0 (CURRENT): 5 phases - loaded from canonical template
- REVIEW and REFACTOR_CONTINUOUS moved to deliver level

These tests ensure validator stays synchronized with canonical template.
"""

from des.application.tdd_template_loader import (
    get_expected_phase_count,
    get_schema_version,
    get_valid_tdd_phases,
)
from des.application.validator import (
    ExecutionLogValidator,
    TDDPhaseValidator,
)


class TestTDDPhaseValidatorSchemaV4Current:
    """Tests for current schema v4.0 loaded from Single Source of Truth."""

    def test_validate_v4_0_phases_from_canonical_template(self):
        """
        GIVEN v4.0 schema prompt with phases from canonical template
        WHEN validate() called
        THEN checks for all phases from Single Source of Truth

        This test loads the canonical phase count from nWave/templates/step-tdd-cycle-schema.json
        ensuring validator and tests stay synchronized with template changes.
        """
        # GIVEN: Load canonical phase definitions from template
        canonical_phases = get_valid_tdd_phases()
        phase_count = get_expected_phase_count()
        schema_version = get_schema_version()

        # Build prompt dynamically from canonical template
        tdd_section = "# TDD_PHASES\n"
        tdd_section += f"Execute all {phase_count} phases (schema v{schema_version}):\n"
        for i, phase in enumerate(canonical_phases, 1):
            tdd_section += f"{i}. {phase}\n"

        prompt = f"""
        {tdd_section}
        """
        validator = TDDPhaseValidator()

        # WHEN: Validation performed
        errors = validator.validate(prompt)

        # THEN: No errors when all canonical phases present
        assert len(errors) == 0

    def test_validate_v4_0_execution_log_from_template(self):
        """
        GIVEN v4.0 schema execution log with phases from canonical template
        WHEN validate() called with current schema version
        THEN validates successfully

        This test builds the phase log dynamically from the canonical template.
        """
        # GIVEN: Load canonical phase definitions
        canonical_phases = get_valid_tdd_phases()
        schema_version = get_schema_version()

        # Build phase log dynamically from canonical template
        phase_log = [
            {"phase_name": phase, "status": "EXECUTED", "outcome": "PASS"}
            for phase in canonical_phases
        ]

        validator = ExecutionLogValidator()

        # WHEN: Validation with current schema version
        errors = validator.validate(phase_log, schema_version=schema_version)

        # THEN: No errors for valid current schema log
        assert len(errors) == 0

    def test_canonical_template_has_expected_phase_count(self):
        """
        GIVEN canonical template loaded
        WHEN get_expected_phase_count() called
        THEN returns 5 phases for schema v4.0

        This test verifies the template loader is working correctly.
        If this fails, the canonical template may have changed or is not loading properly.
        """
        # GIVEN/WHEN: Load canonical phase count
        phase_count = get_expected_phase_count()

        # THEN: Current schema v4.0 has 5 phases
        assert phase_count == 5

    def test_canonical_template_has_schema_v4(self):
        """
        GIVEN canonical template loaded
        WHEN get_schema_version() called
        THEN returns "4.0"

        This test verifies we're using the correct schema version.
        """
        # GIVEN/WHEN: Load schema version
        schema_version = get_schema_version()

        # THEN: Current schema is v4.0
        assert schema_version == "4.0"


class TestTDDPhaseValidatorMissingContext:
    """``_is_missing_context`` distinguishes a phase named in a missing-context.

    The function decides whether a line mentions a phase ONLY in a "missing"
    framing -- a parenthetical aside ``(missing COMMIT)``, descriptive text
    ``without COMMIT``, or a ``# MISSING: COMMIT`` comment. When it returns
    True the caller treats the phase as NOT present in the prompt.

    Regression: the parenthetical branch was greedy on both sides
    (``\\(.*\\bPHASE\\b.*\\)``) and spanned ACROSS unrelated groups -- on a line
    carrying two parenthesised asides it matched from the first ``(`` to the
    last ``)``, swallowing a phase that lives OUTSIDE parens and falsely
    reporting it as missing-context. The fix anchors the phase inside a SINGLE
    group with no nested parens (``\\([^()]*\\bPHASE\\b[^()]*\\)``).
    """

    @staticmethod
    def _is_missing(phase: str, line: str) -> bool:
        from des.application.validator import TDDPhaseValidator

        return TDDPhaseValidator._is_missing_context(phase, line)

    def test_phase_outside_parens_with_other_groups_is_not_missing_context(self):
        """tsunami case: phase sits OUTSIDE parens that wrap unrelated text.

        The greedy regex spanned ``(cucumber) ... (missing implementation)`` and
        falsely classified COMMIT (which is outside both groups) as
        missing-context. The non-greedy fix confines each group, so COMMIT --
        present in the line proper -- is NOT missing-context.
        """
        line = (
            "Given the feature file (cucumber) drives the COMMIT phase "
            "(missing implementation)"
        )
        assert self._is_missing("COMMIT", line) is False

    def test_phase_inside_its_own_group_with_other_groups_is_not_missing(self):
        """A phase outside parens stays present even when another group exists.

        ``setup (fixtures) then COMMIT`` -- COMMIT is bare; the lone group wraps
        unrelated text. Non-greedy matching does not reach across to it.
        """
        assert self._is_missing("COMMIT", "setup (fixtures) then COMMIT") is False

    def test_parenthesised_missing_phase_is_missing_context(self):
        """The legitimate ``(missing COMMIT)`` aside still reads as missing."""
        assert self._is_missing("COMMIT", "the prompt omits (missing COMMIT) here") is (
            True
        )

    def test_nested_parens_missing_phase_is_missing_context(self):
        """``((missing COMMIT))`` still reads as missing -- via the descriptive branch.

        The new parenthetical regex deliberately rejects nested parens
        (``[^()]`` excludes them), so it no longer matches this line. The
        classification survives because the descriptive branch
        ``\\b(without|missing|no)\\s+COMMIT\\b`` covers it -- pinning that the
        two branches together keep nested-paren asides classified as missing.
        """
        assert self._is_missing("COMMIT", "the prompt has ((missing COMMIT))") is True

    def test_descriptive_without_phase_is_missing_context(self):
        """``without COMMIT`` descriptive framing reads as missing (unchanged)."""
        assert self._is_missing("COMMIT", "the cycle proceeds without COMMIT") is True

    def test_comment_missing_phase_is_missing_context(self):
        """``# MISSING: COMMIT`` comment framing reads as missing (unchanged)."""
        assert self._is_missing("COMMIT", "phases here  # MISSING: COMMIT") is True
