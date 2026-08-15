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

ARCHITECT = (AGENTS_DIR / "nw-solution-architect.md").read_text(encoding="utf-8")
ACCEPTANCE_DESIGNER = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(
    encoding="utf-8"
)
PBT_PYTHON_SKILL = (SKILLS_DIR / "nw-pbt-python" / "SKILL.md").read_text(
    encoding="utf-8"
)
ADR = ADR_PATH.read_text(encoding="utf-8")

SUBSTRATE_FACT_MARKERS = [
    "driving port",
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
        # All ADR-named facts (driving port, test helper, fixture, manifest,
        # declaration, runtime, verification argv, install argv) are projected
        # into the subsection. Framing is facts only (never a test case,
        # scenario, assert, def test_, or @given), never a specific language
        # (pytest, hypothesis, django, jest, cargo test).
        section_start = ARCHITECT.index("Test substrate (RED_TO_GREEN only)")
        section = _norm(ARCHITECT[section_start : section_start + 2000]).lower()

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


class TestAtdConsumesFactsImportsBaseSymbolsDrivingPortBrokenOnSetup:
    """ATD consumes brief facts, base-revision symbols only, driving port, collection/setup failure BROKEN."""

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


class TestDeclarationRuntimeDeltaInstallForbidsWholeManifest:
    """Declaration/runtime distinction + direct delta-only install survives BROAD_INPUT and Closure phases."""

    def test_broad_input_domain_explicit_runtime_missing_delta_install_argv(self):
        # BROAD_INPUT_DOMAIN paragraph names declaration-vs-runtime distinction
        # and "named direct dependency-delta install argv", forbidding whole
        # test-dependency manifest reinstall. Old authorization for full install
        # (pre-2026-08-15) is gone.
        marker = "`BROAD_INPUT_DOMAIN` is this agent's own obligation"
        idx = ACCEPTANCE_DESIGNER.index(marker)
        paragraph = _norm(ACCEPTANCE_DESIGNER[idx : idx + 1100])

        assert (
            "declaration-vs-runtime" in paragraph
            or "declared but runtime-missing" in paragraph
        )
        assert "named direct dependency-delta install argv" in paragraph
        assert "whole test-dependency" in paragraph
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
