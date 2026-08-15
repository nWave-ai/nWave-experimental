"""K4 test-substrate handoff regression (2026-08-15, ADR-SSOT-002 §4b Axis 1).

Confirmed defect: a K4 run with compact evidence still invented helper
imports, assumed fixture attributes, used a plain Django `TestCase` under
`@given`, and imported a not-yet-existing production symbol, making RED
uncollectable; a whole-manifest dev-dependency reinstall also failed on an
unrelated package. The ADR correction makes DESIGN's existing architecture
brief authority (Section 3/4b) name the minimum exact test substrate ATD
cannot safely invent -- no new carrier, no second artifact.

Source-level projections only: this module reads the checked-in prose of the
three consumer files plus the ADR and asserts textual properties. It never
hard-codes a line number and never inspects AST/implementation shape.
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
AGENTS_DIR = NWAVE_DIR / "agents"
SKILLS_DIR = NWAVE_DIR / "skills"
ADR_PATH = (
    PROJECT_ROOT
    / "docs"
    / "product"
    / "architecture"
    / "ADR-SSOT-002-canonical-delivery-model.md"
)
CONTRACT_SCHEMA_PATH = NWAVE_DIR / "schemas" / "thin-delivery-contract.schema.json"

ARCHITECT = (AGENTS_DIR / "nw-solution-architect.md").read_text(encoding="utf-8")
ACCEPTANCE_DESIGNER = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(
    encoding="utf-8"
)
PBT_PYTHON_SKILL = (SKILLS_DIR / "nw-pbt-python" / "SKILL.md").read_text(
    encoding="utf-8"
)
ADR = ADR_PATH.read_text(encoding="utf-8")
OBLIGATION_ENUM = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))["$defs"][
    "obligations"
]["items"]["enum"]

SUBSTRATE_FACT_MARKERS = [
    "driving or observing port",
    "test helper",
    "fixture",
    "executor",
    "manifest",
    "declaration",
    "runtime",
    "verification argv",
    "install argv",
]


def _norm(text: str) -> str:
    return " ".join(text.split())


class TestBriefCarriesFactsLanguageAgnosticNoNewArtifact:
    """ADR is the single brief carrier naming all ratified facts, no new artifact."""

    def test_architect_test_substrate_subsection_sole_carrier_no_schema_field(self):
        # Substrate facts live in the existing "Test substrate (RED_TO_GREEN
        # only)" subsection of architect, never a new DeliveryContract field or
        # separately authored file. Positioning: listed with other durable-brief
        # subsections in the "Durable write target:" paragraph.
        assert "Test substrate (RED_TO_GREEN only)" in ARCHITECT
        durable_target_start = ARCHITECT.index("Durable write target:")
        subsection_mention = ARCHITECT.index(
            "Test substrate (RED_TO_GREEN only)", durable_target_start
        )
        never_both_marker = ARCHITECT.index("never both", durable_target_start)
        assert durable_target_start < subsection_mention < never_both_marker

        # No schema field or second artifact introduced.
        for forbidden_field in (
            "test_substrate",
            "test-substrate-facts",
            "substrateFacts",
        ):
            assert forbidden_field not in ARCHITECT
            assert forbidden_field not in ACCEPTANCE_DESIGNER


class TestArchitectProjectsFactsLanguageAgnosticGreenToGreenKeepsOracle:
    """Architect projects all ADR facts, language-agnostic, facts only, GREEN_TO_GREEN omits."""

    def test_all_substrate_fact_markers_present_never_cases_language_agnostic(self):
        # All ADR-named facts (driving/observing port, test helper, fixture,
        # manifest, declaration, runtime, verification argv, install argv) are
        # projected into the subsection. Framing is facts only (never a test case,
        # scenario, assert, def test_, or @given), never a specific language
        # (pytest, hypothesis, django, jest, cargo test).
        section_start = ARCHITECT.index("Test substrate (RED_TO_GREEN only)")
        section_end = ARCHITECT.index("This is the sole carrier", section_start)
        section = _norm(ARCHITECT[section_start:section_end]).lower()

        missing = [m for m in SUBSTRATE_FACT_MARKERS if m not in section]
        assert not missing, f"substrate subsection is missing facts: {missing}"

        assert (
            "never a test case" in section or "never a test case, scenario" in section
        )
        for forbidden in ("assert ", "def test_", "@given"):
            assert forbidden not in section

        for language_specific in (
            "pytest",
            "hypothesis",
            "django",
            "jest",
            "cargo test",
        ):
            assert language_specific not in section

        # GREEN_TO_GREEN omits separate substrate facts and keeps its named oracle.
        assert "green_to_green" in section
        assert "omit" in section or "no separate facts" in section

    def test_port_bindings_and_specialized_lifecycle_are_total_before_handoff(self):
        section_start = ARCHITECT.index("Test substrate (RED_TO_GREEN only)")
        section_end = ARCHITECT.index("This is the sole carrier", section_start)
        section = _norm(ARCHITECT[section_start:section_end])

        assert "exact repository-native executable binding" in section
        assert "route/call-builder identity and literal arguments" in section
        assert "response selector or stable lookup key" in section
        assert "never a hand-assembled path" in section
        assert "specialized property-test lifecycle overrides" in section
        assert "Never claim one concrete helper applies uniformly" in section
        assert "executable binding/selector" in section


class TestAtdConsumesFactsImportsBaseSymbolsRealPortsBrokenOnSetup:
    """ATD consumes brief facts, base symbols, real ports, setup failure BROKEN."""

    def test_atd_red_to_green_never_guesses_imports_base_revision_only(self):
        # RED_TO_GREEN branch states facts are consumed (never guessed/invented)
        # from the brief. Initial RED file imports only base-revision production
        # symbols via the driving port; planned feature symbols are forbidden
        # (not yet existing). Import/collection/setup failure is BROKEN by
        # construction.
        branch_start = ACCEPTANCE_DESIGNER.index("### RED_TO_GREEN branch")
        branch = ACCEPTANCE_DESIGNER[branch_start : branch_start + 6000]

        assert "never guess" in branch or "never guess, invent" in branch
        assert "brief" in branch.lower()
        assert "base revision" in branch
        assert "driving port" in branch
        assert "does not yet exist" in branch
        assert "BROKEN by construction" in ACCEPTANCE_DESIGNER
        assert (
            "collection" in ACCEPTANCE_DESIGNER
            and "setup failure" in ACCEPTANCE_DESIGNER
        )

    def test_atd_compiles_minimal_spatial_portfolio_without_binding_guesses(self):
        marker = "Before the first Write, compile one spatial portfolio"
        idx = ACCEPTANCE_DESIGNER.index(marker)
        paragraph = _norm(ACCEPTANCE_DESIGNER[idx : idx + 1400])

        assert (
            "one scenario when one real interaction honestly observes several clauses"
            in paragraph
        )
        assert (
            "equivalent invalid inputs into one parameterized/table-driven test"
            in paragraph
        )
        assert "one property per distinct universal law" in paragraph
        assert "A clause count never becomes a test count" in paragraph
        assert "brief's executable port and selector" in paragraph
        assert (
            "specialized property lifecycle overrides the generic repository helper"
            in paragraph
        )
        assert "never a literal URL/key or concrete base guessed" in paragraph
        assert "EVIDENCE_GAP" in paragraph


class TestDeclarationRuntimeDeltaInstallForbidsWholeManifest:
    """Declaration/runtime distinction + direct delta-only install survives BROAD_INPUT and Closure phases."""

    def test_broad_input_domain_explicit_runtime_missing_delta_install_argv(self):
        # BROAD_INPUT_DOMAIN paragraph names declaration-vs-runtime distinction
        # and "named direct dependency-delta install argv", forbidding whole
        # test-dependency manifest reinstall. Old authorization for full install
        # (pre-2026-08-15) is gone.
        marker = "`BROAD_INPUT_DOMAIN` is DESIGN's obligation, never this"
        idx = ACCEPTANCE_DESIGNER.index(marker)
        paragraph_end = ACCEPTANCE_DESIGNER.index(
            "**Spatial-first materialization (HARD):**", idx
        )
        paragraph = _norm(ACCEPTANCE_DESIGNER[idx:paragraph_end])

        assert (
            "declaration-vs-runtime" in paragraph
            or "declared but runtime-missing" in paragraph
        )
        assert "named direct dependency-delta install argv" in paragraph
        assert "whole-manifest reinstall" in paragraph
        assert "never" in paragraph

        assert (
            "a missing PBT library is this agent's dependency to\ndeclare and install here"
            not in ACCEPTANCE_DESIGNER
        )

        # Closure-only phase (HARD) enforces named direct dependency-delta
        # install argv, forbids whole test-dependency manifest reinstall and
        # invented tools. Same atomic-operation boundary applies: manifest
        # declaration edit, explicit runtime-missing, exact named direct
        # dependency-delta install argv.
        marker = "**Closure-only phase (HARD):**"
        idx = ACCEPTANCE_DESIGNER.index(marker)
        closure = _norm(ACCEPTANCE_DESIGNER[idx : idx + 1200])

        assert "whole test dependency manifest" in closure
        assert "named direct dependency-delta install argv" in closure
        assert "never an invented tool" in closure


class TestArchitectSoleOwnershipAndFourStateAcrossArtifacts:
    """Architect owns obligation semantics; ATD compiles all four states."""

    @staticmethod
    def _atd_broad_input_paragraph() -> str:
        start = ACCEPTANCE_DESIGNER.index(
            "`BROAD_INPUT_DOMAIN` is DESIGN's obligation, never this"
        )
        end = ACCEPTANCE_DESIGNER.index(
            "**Spatial-first materialization (HARD):**", start
        )
        return _norm(ACCEPTANCE_DESIGNER[start:end])

    def test_architect_owns_obligations_and_defines_broad_input(self):
        assert "DESIGN is the sole semantic owner of obligation tokens" in ARCHITECT
        assert "every applicable existing schema token" in ARCHITECT
        marker = "`BROAD_INPUT_DOMAIN` names an externally sourced"
        idx = ARCHITECT.index(marker)
        definition = _norm(ARCHITECT[idx : idx + 400])
        assert "infinite" in definition
        assert "non-enumerable" in definition
        assert "finite enumerable" in definition

    def test_semantic_trigger_cannot_be_waived_by_test_precedent_or_dependency(self):
        marker = "Obligation applicability is a semantic deduction"
        idx = ARCHITECT.index(marker)
        paragraph = _norm(ARCHITECT[idx : idx + 1000])

        assert "before selecting the test substrate or dependencies" in paragraph
        assert "the token MUST fire" in paragraph
        for non_veto in (
            "existing example-based tests",
            "repository convention",
            "dependency absence",
            "thin wrapper around a library",
        ):
            assert non_veto in paragraph
        assert "they never erase the law" in paragraph
        assert "name the factual predicate that is false" in paragraph
        assert (
            "never justify non-applicability from the current test style" in paragraph
        )

    def test_schema_enum_is_read_before_obligation_derivation_and_write(self):
        locator = (
            "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/"
            "thin-delivery-contract.schema.json"
        )
        assert locator in ARCHITECT
        schema_read = ARCHITECT.index("Before deriving obligations")
        obligation_authority = ARCHITECT.index(
            "`$defs.obligations.items.enum` is the sole authority"
        )
        durable_write = ARCHITECT.index("Durable write target:")
        assert schema_read < obligation_authority < durable_write
        assert "there is no fallback or second candidate" in ARCHITECT
        assert "unavailable,\nunreadable, invalid, missing, or empty enum" in ARCHITECT
        assert OBLIGATION_ENUM

    def test_only_closed_enum_members_are_tokens_not_cross_cutting_labels(self):
        assert "Emit only exact enum members" in ARCHITECT
        assert "forbidden\nas obligation tokens" in ARCHITECT
        for non_schema_label in (
            "data:consumer-known-before-produced",
            "gate:design-principles-gdp-1-9",
            "gate:self-explaining-what-why-how",
        ):
            assert non_schema_label not in OBLIGATION_ENUM

    def test_dependency_state_and_single_action_are_final_before_write(self):
        section_start = ARCHITECT.index("Test substrate (RED_TO_GREEN only)")
        section_end = ARCHITECT.index("This is the sole carrier", section_start)
        section = _norm(ARCHITECT[section_start:section_end])

        assert "select exactly one matching branch and emit only its action" in section
        assert (
            "never emit alternatives, optional extra commands, or duplicate routes"
            in section
        )
        assert "bind the repository's evidenced interpreter/environment" in section
        assert "never a bare `pip`/`python` command" in section
        assert "whole-manifest `-r` install" in section
        assert (
            "All dependency declaration/runtime states and actions must be final before durable Write"
            in section
        )
        assert "`confirm later`, maybe, unresolved, or ambiguous evidence" in section
        assert "ARCHITECTURE-BLOCKED" in section

    def test_atd_compiles_verbatim_without_self_ownership(self):
        assert "is this agent's own obligation" not in ACCEPTANCE_DESIGNER
        paragraph = self._atd_broad_input_paragraph()
        assert "compiles it verbatim" in paragraph
        assert "never deriving, inventing, or dropping it" in paragraph

    def test_four_states_present_in_architect_atd_and_closure(self):
        four_states = (
            "declared and present",
            "declared and missing",
            "undeclared and present",
            "undeclared and missing",
        )
        closure_start = ACCEPTANCE_DESIGNER.index("**Closure-only phase (HARD):**")
        closure_end = ACCEPTANCE_DESIGNER.index(
            "Missing or ambiguous test-dependency ownership", closure_start
        )
        closure = _norm(ACCEPTANCE_DESIGNER[closure_start:closure_end])
        for state in four_states:
            assert state in ARCHITECT
            assert state in ACCEPTANCE_DESIGNER
            assert state in closure
        assert "named direct dependency-delta install argv" in closure
        assert "never new discovery" in closure

    def test_missing_evidence_blocks_before_skill_or_write(self):
        paragraph = self._atd_broad_input_paragraph()
        assert "EVIDENCE_GAP" in paragraph
        assert "before any" in paragraph

    def test_ad_hoc_install_and_examples_fallback_forbidden(self):
        paragraph = self._atd_broad_input_paragraph()
        assert "No ad-hoc" in paragraph
        assert "whole-manifest reinstall" in paragraph
        assert "undeclared import" in paragraph
        assert "examples-only" in paragraph


class TestPbtPythonComposesHypothesisDjangoBasePreservesSetupConstructsMissing:
    """Python PBT rule composes repository helper with Hypothesis Django base, preserves setup, constructs missing state."""

    def test_django_integration_hypothesis_extra_django_testcase_composition(self):
        # Django Integration section mandates: never runs @given under plain
        # Django TestCase; must compose hypothesis.extra.django.TestCase with
        # repository helper (RepositoryPropertyTestCase / HypothesisDjangoTestCase).
        # Preserves existing helper setup. Never assumes fixture attributes;
        # explicitly constructs missing state.
        assert "## Django Integration" in PBT_PYTHON_SKILL

        section_start = PBT_PYTHON_SKILL.index("## Django Integration")
        section = PBT_PYTHON_SKILL[section_start:]

        assert "never runs directly under a plain" in section
        assert "django.test.TestCase" in section
        assert "hypothesis.extra.django" in section
        assert "class RepositoryPropertyTestCase" in section
        assert "HypothesisDjangoTestCase" in section
        assert "preserving the documented setup/fixtures" in section
        assert "never blindly multiple-inherit two concrete" in section
        assert "one `@given` method in each leaf" in section
        assert "manual database flushing" in section
        assert "never assume" in section.lower()
        assert "construct" in section.lower()
