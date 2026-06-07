"""Domain types for the fix-d1-human-readable-gate-surfaces acceptance set.

F-D1-HUMAN-READABLE-GATE-SURFACES (Mandate-12 criterion 1). Every domain noun
used in the slice-01 Gherkin is expressed once here as a typed enum / NewType /
frozen dataclass. The composition root consumes these typed parameters; step
bodies coerce a Gherkin phrase to a typed value via the ``*_BY_PHRASE`` maps
and delegate — no raw ``str`` where a domain enum exists.

Vocabulary shared across the slice-01 feature file and the step module — the
SSOT for the human-readable-gate-surfaces domain language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HumanSurfaceVerdict(str, Enum):
    """The three-state verdict surface every gate CLI must emit.

    ``PASS`` -> green ✅ prefix, exit code 0.
    ``FAIL`` -> red ❌ prefix, exit code non-zero.
    ``DEGRADED`` -> yellow ⚠️ prefix, exit code other (partial / soft refusal).

    The verdict identifier IS the contract; the prefix glyph + ANSI color are
    documentation a stable contract surface caller never asserts on.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


class SuiteOutcome(str, Enum):
    """Whether the tmp_path pytest suite is configured to pass or fail.

    Slice-01 walking-skeleton AT routing: AT1 stages a passing suite (PASS
    verdict); AT2 stages a failing suite (FAIL verdict). DEGRADED is reserved
    for subsequent slices when gates surface partial / soft refusals.
    """

    PASSING = "passing"
    FAILING = "failing"


class StderrMode(str, Enum):
    """Whether the subprocess's stderr is bound to a TTY or to a pipe.

    AT1 + AT2 invoke under a TTY (the operator's terminal); AT3 invokes under
    a pipe (the CI / piped consumer surface). The helper detects the channel
    via ``isatty()`` and strips ANSI escapes when not a TTY.
    """

    TTY = "tty"
    PIPE = "pipe"


# --- Gherkin-phrase -> typed-value lookup (Mandate-12 criterion 3 enabler) ---


SUITE_OUTCOME_BY_PHRASE: dict[str, SuiteOutcome] = {
    "the minimal pytest suite is configured to pass": SuiteOutcome.PASSING,
    "the minimal pytest suite is configured to fail": SuiteOutcome.FAILING,
}


STDERR_MODE_BY_PHRASE: dict[str, StderrMode] = {
    "the operator runs the contract gate against the repository inside a real terminal": StderrMode.TTY,
    "the operator runs the contract gate against the repository under a non terminal stderr": StderrMode.PIPE,
}


# --- Color contract (the helper module SSOT mirrors these constants) ---------


@dataclass(frozen=True)
class ColorContract:
    """ANSI escape sequences the human-readable helper emits under a TTY.

    The strings here are the EXPECTED surface — the helper module under test
    MUST emit byte-identical escapes when stderr is a TTY. Under a pipe the
    helper emits the same prefix glyphs + summary text WITHOUT escapes.
    """

    green: str = "\x1b[32m"
    red: str = "\x1b[31m"
    yellow: str = "\x1b[33m"
    reset: str = "\x1b[0m"


COLOR = ColorContract()


# --- Verdict prefix glyph contract -------------------------------------------


PREFIX_BY_VERDICT: dict[HumanSurfaceVerdict, str] = {
    HumanSurfaceVerdict.PASS: "✅ PASS",
    HumanSurfaceVerdict.FAIL: "❌ FAIL",
    HumanSurfaceVerdict.DEGRADED: "⚠️ DEGRADED",
}


# --- JSON event contract (the existing structured surface) -------------------


# The single-line JSON event the existing contract gate emits on its default
# (run-suite) mode. Slice-01 ATs assert the event remains byte-content stable
# alongside the new human-readable line.
CONTRACT_GATE_EVENT_NAME = "ContractGateResult"


# ===========================================================================
# Slice-02: spine-triple extension (verify_slice_commit_completeness +
# carpaccio_slice_gate + at_review_verdict).
# ===========================================================================


class SpineGateCli(str, Enum):
    """The three D1 spine-triple CLIs slice-02 extends the surface to.

    Each CLI is a separate driving port (subprocess entry point). The Gherkin
    Examples table carries one row per value, parametrize-collapsing the
    decision-table cells into three Scenario Outlines (Mandate-12 + max-density
    per [[feedback_ats_max_pbt_parametrize_density_2026_05_19]]).
    """

    VERIFY_SLICE_COMMIT_COMPLETENESS = "verify-slice-commit-completeness"
    CARPACCIO_SLICE_GATE = "carpaccio-slice-gate"
    AT_REVIEW_VERDICT = "at-review-verdict"


# Per-CLI success-path JSON event names. Each gate emits a distinct success
# event the AT can extract from stderr to confirm the structured contract is
# preserved alongside the new human-readable line.
SUCCESS_EVENT_BY_CLI: dict[SpineGateCli, str] = {
    SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS: "SliceCommitComplete",
    SpineGateCli.CARPACCIO_SLICE_GATE: "SliceCleared",
    SpineGateCli.AT_REVIEW_VERDICT: "ATReviewVerdictCLI",
}


# Per-CLI negative-path JSON event names + verdict mapping. Each gate has a
# distinct negative-path event AND a distinct verdict semantic:
#   verify-slice-commit-completeness  -> SliceCommitIncomplete   -> FAIL
#   carpaccio-slice-gate              -> CARPACCIO_SLICE_TOO_LARGE -> FAIL
#   at-review-verdict (NEEDS_REVISION) -> ATReviewVerdictCLI      -> DEGRADED
# The at_review_verdict CLI exits 0 on both APPROVED + NEEDS_REVISION (soft
# refusal); the human line distinguishes the operator-facing outcome.
NEGATIVE_EVENT_BY_CLI: dict[SpineGateCli, str] = {
    SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS: "SliceCommitIncomplete",
    SpineGateCli.CARPACCIO_SLICE_GATE: "CARPACCIO_SLICE_TOO_LARGE",
    SpineGateCli.AT_REVIEW_VERDICT: "ATReviewVerdictCLI",
}


NEGATIVE_VERDICT_BY_CLI: dict[SpineGateCli, HumanSurfaceVerdict] = {
    SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS: HumanSurfaceVerdict.FAIL,
    SpineGateCli.CARPACCIO_SLICE_GATE: HumanSurfaceVerdict.FAIL,
    SpineGateCli.AT_REVIEW_VERDICT: HumanSurfaceVerdict.DEGRADED,
}


# Gherkin-phrase -> SpineGateCli lookup for the Examples table column.
SPINE_GATE_CLI_BY_PHRASE: dict[str, SpineGateCli] = {
    "verify-slice-commit-completeness": SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS,
    "carpaccio-slice-gate": SpineGateCli.CARPACCIO_SLICE_GATE,
    "at-review-verdict": SpineGateCli.AT_REVIEW_VERDICT,
}


# ===========================================================================
# Slice-03: gate-class-triple extension (verify_environmental_e2e +
# verify_coverage_map + check_robustness_density).
# ===========================================================================


class GateClassCli(str, Enum):
    """The three D1 gate-class CLIs slice-03 extends the human surface to.

    Each CLI is a separate driving port (subprocess entry point) with a
    DIFFERENT pre-existing structured surface:
      * VERIFY_ENVIRONMENTAL_E2E emits the L1.4 stdout token on stdout
      * VERIFY_COVERAGE_MAP emits a free-text refusal line on stderr
      * CHECK_ROBUSTNESS_DENSITY emits no structured payload (exit code only)
    The Gherkin Examples table carries one row per value, parametrize-
    collapsing the decision-table cells into three Scenario Outlines (Mandate-
    12 + max-density per
    [[feedback_ats_max_pbt_parametrize_density_2026_05_19]]).
    """

    VERIFY_ENVIRONMENTAL_E2E = "verify-environmental-e2e"
    VERIFY_COVERAGE_MAP = "verify-coverage-map"
    CHECK_ROBUSTNESS_DENSITY = "check-robustness-density"


# Per-CLI success-path human verdict. Unlike slice-01/02 where every CLI emits
# PASS on its happy path, verify_environmental_e2e in slice-03 scope can only
# reach the misscoped-detection branch under --mode verify-authored (the full
# authored+genuine PASS path lives in a later slice of the environmental gate
# feature). The misscoped branch IS a legitimate operator outcome — "this
# feature does not need env-e2e" — and maps to DEGRADED.
SUCCESS_VERDICT_BY_GATE_CLASS_CLI: dict[GateClassCli, HumanSurfaceVerdict] = {
    GateClassCli.VERIFY_ENVIRONMENTAL_E2E: HumanSurfaceVerdict.DEGRADED,
    GateClassCli.VERIFY_COVERAGE_MAP: HumanSurfaceVerdict.PASS,
    GateClassCli.CHECK_ROBUSTNESS_DENSITY: HumanSurfaceVerdict.PASS,
}


# Per-CLI negative-path human verdict. All three CLIs map to FAIL on the
# negative branch: env-e2e parse/IO is a structural refusal; coverage-map
# StructuralIncomplete is a structural refusal; robustness-density
# CHECK_FAILED is a coverage refusal.
NEGATIVE_VERDICT_BY_GATE_CLASS_CLI: dict[GateClassCli, HumanSurfaceVerdict] = {
    GateClassCli.VERIFY_ENVIRONMENTAL_E2E: HumanSurfaceVerdict.FAIL,
    GateClassCli.VERIFY_COVERAGE_MAP: HumanSurfaceVerdict.FAIL,
    GateClassCli.CHECK_ROBUSTNESS_DENSITY: HumanSurfaceVerdict.FAIL,
}


# Gherkin-phrase -> GateClassCli lookup for the Examples table column.
GATE_CLASS_CLI_BY_PHRASE: dict[str, GateClassCli] = {
    "verify-environmental-e2e": GateClassCli.VERIFY_ENVIRONMENTAL_E2E,
    "verify-coverage-map": GateClassCli.VERIFY_COVERAGE_MAP,
    "check-robustness-density": GateClassCli.CHECK_ROBUSTNESS_DENSITY,
}


# ===========================================================================
# Slice-04: closure pair (check_reuse_first_design + check_scorecard_freshness).
# ===========================================================================


class ClosureCli(str, Enum):
    """The two remaining D1 gate CLIs slice-04 closes the surface adoption on.

    Each CLI is a separate driving port (subprocess entry point). After
    slice-04 lands every D1 gate CLI emits the colored human-readable verdict
    line via ``print_human_summary`` — the 9-gate inventory closes.

    Pre-existing structured surface per CLI:
      * CHECK_REUSE_FIRST_DESIGN emits the L1.4 stdout token line
        ``reuse_first feature=... new_components=... justified=... verdict=...``
      * CHECK_SCORECARD_FRESHNESS emits the L1.4 stdout token line
        ``scorecard_freshness scorecard=... cells=... fresh=... stale=...
        missing=... verdict=...`` plus per-stale ``stale cell: <FID>`` lines.
    The Gherkin Examples table carries one row per CLI value, parametrize-
    collapsing the decision-table cells into three Scenario Outlines (Mandate-
    12 + max-density per
    [[feedback_ats_max_pbt_parametrize_density_2026_05_19]]).
    """

    CHECK_REUSE_FIRST_DESIGN = "check-reuse-first-design"
    CHECK_SCORECARD_FRESHNESS = "check-scorecard-freshness"


# Per-CLI success-path human verdict. Both closure CLIs map to PASS on their
# happy path (every NEW component justified; every cited F-id fresh).
SUCCESS_VERDICT_BY_CLOSURE_CLI: dict[ClosureCli, HumanSurfaceVerdict] = {
    ClosureCli.CHECK_REUSE_FIRST_DESIGN: HumanSurfaceVerdict.PASS,
    ClosureCli.CHECK_SCORECARD_FRESHNESS: HumanSurfaceVerdict.PASS,
}


# Per-CLI negative-path human verdict. Both closure CLIs map to FAIL on the
# negative branch: reuse-first detects an unjustified NEW component
# (exit 1); scorecard-freshness detects a stale cell (exit 1).
NEGATIVE_VERDICT_BY_CLOSURE_CLI: dict[ClosureCli, HumanSurfaceVerdict] = {
    ClosureCli.CHECK_REUSE_FIRST_DESIGN: HumanSurfaceVerdict.FAIL,
    ClosureCli.CHECK_SCORECARD_FRESHNESS: HumanSurfaceVerdict.FAIL,
}


# Gherkin-phrase -> ClosureCli lookup for the Examples table column.
CLOSURE_CLI_BY_PHRASE: dict[str, ClosureCli] = {
    "check-reuse-first-design": ClosureCli.CHECK_REUSE_FIRST_DESIGN,
    "check-scorecard-freshness": ClosureCli.CHECK_SCORECARD_FRESHNESS,
}
