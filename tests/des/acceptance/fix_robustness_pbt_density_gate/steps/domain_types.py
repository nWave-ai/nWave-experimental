"""Domain types for the fix-robustness-pbt-density-gate acceptance slices.

Mandate-12 criterion 1 (ATDD SSOT via types): every domain noun used in the
Gherkin is expressed once here as a typed enum / NewType. Step bodies and the
composition service consume these typed parameters -- no raw ``str`` where a
domain enum exists.

CONTRACT SOURCE: the enums below mirror the feature-delta's
``check_robustness_density.py`` contract (slice-01 walking-skeleton) plus the
M-feature's ``component-manifest.schema.json`` for the
``unbounded-input-domains`` block shape.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-robustness-pbt-density-gate").
FeatureId = NewType("FeatureId", str)

# A kebab-case slice identifier (e.g. "slice-01").
SliceId = NewType("SliceId", str)

# A kebab-case unbounded-input-domain id (e.g. "tree-vs-commit-file-divergence").
DomainId = NewType("DomainId", str)


class RobustnessGateExit(int, Enum):
    """Exit codes of ``check_robustness_density.py`` (slice-01 + slice-02 + slice-04).

    Mirrors sibling gate CLIs (``carpaccio_slice_gate.py`` /
    ``at_review_verdict.py`` / ``reverify_slice_commit.py``). Slice-01 surface
    is the three-value subset {0, 1, 2}; slice-02 widens exit-1 semantics
    (``RobustnessDeclarationMissing`` / ``RobustnessProvenanceViolation``)
    without adding new exit codes; slice-03 widens exit-1 further with
    ``RobustnessPBTShallow``. Slice-04 introduces exit 3
    (``RobustnessLayer2Unavailable``) -- the V5 / R5 three-state cell that
    holds the feature out of ready when mutmut cannot answer truthfully,
    neither pass nor fail.
    """

    PASS = 0  # every declared domain has @given coverage / explicit-empty + rationale
    CHECK_FAILED = 1  # coverage miss OR missing declaration OR provenance violation OR shallow PBT OR kill-rate zero
    MALFORMED = 2  # YAML unparseable / schema-invalid declaration
    UNAVAILABLE = 3  # slice-04: Layer 2 untrustworthy (mutmut absent / report malformed / positive control failed)


class CoverageOutcome(str, Enum):
    """The slice-01 coverage outcome for a single declared domain id.

    Drives the slice-01 walking-skeleton AT trio: every declared domain id is
    either covered by a ``# domain: <id>``-tagged ``@given`` in the slice AT
    scope or it is not. Slice-02 extends the universe to absent-vs-empty
    declarations; slice-03/04 add genuineness layers.
    """

    COVERED = "covered"
    NOT_COVERED = "not covered"


class DeclarationShape(str, Enum):
    """The shape of the staged ``unbounded-domains.yaml`` projection.

    Slice-01 knows two well-formed shapes (single declared domain covered or
    not) plus malformed YAML. Slice-02 extends the universe to the
    declaration-state matrix: missing block, explicit-empty with rationale,
    and distill-authored manifest-absent.
    """

    SINGLE_DOMAIN = "a single declared domain"
    MALFORMED_YAML = "an unparseable declaration document"
    BLOCK_MISSING = "a missing unbounded-input-domains block"
    EXPLICIT_EMPTY_WITH_RATIONALE = "an explicitly empty block with a rationale"
    DISTILL_PROVENANCE_MANIFEST_ABSENT = (
        "a distill-authored domain absent from the design component manifest"
    )


class Slice02DeclarationState(str, Enum):
    """The slice-02 declaration-state matrix (C2 state coverage).

    Drives the slice-02 AT trio per the feature-delta § 6 slice plan row:
    AT1 missing-block-with-ATs -> exit 1; AT2 explicit-empty-with-rationale
    -> exit 0; AT3 distill-provenance-manifest-absent -> exit 1. The fourth
    cell (explicit-empty without rationale) is schema-invalid by the M
    schema's `oneOf`; it is not in slice-02's AT scope and is left for
    slice-03's malformed-shape coverage.
    """

    MISSING_BLOCK_WITH_ATS = "missing block with acceptance tests present"
    EXPLICIT_EMPTY_WITH_RATIONALE = "explicit empty block with one-line rationale"
    DISTILL_PROVENANCE_MANIFEST_ABSENT = (
        "distill-authored domain absent from the design component manifest"
    )


class Slice04Layer2State(str, Enum):
    """The slice-04 Layer-2 mutmut-delta proxy cells (R5 three-state coverage).

    Drives the slice-04 AT trio per the feature-delta § 4 (Layer 2 spec) +
    § 6 (slice-04 row). The mutmut-delta proxy reads a fixture mutmut
    report keyed by each declared domain's ``sut:`` symbol and classifies
    the run into one of three R5 cells. Each cell is a discriminating
    observable -- the gate emits a distinct diagnostic token on stdout so
    AT assertions are universe-wide (Mandate 8): exit code AND token.

    Per the M2 architect mandate, every cell is staged against a COMMITTED
    FIXTURE mutmut report -- the slice MUST NEVER invoke live mutmut, else
    it inherits the environment coupling the gate exists to bound. The
    enum cells therefore enumerate the fixture-report shapes the
    composition stages, not live mutmut outcomes.
    """

    # Layer-2 satisfied: positive control killed AND >=1 SUT mutant killed.
    KILL_RATE_POSITIVE = "kill-rate positive with positive control killed"
    # Layer-2 refused: positive control killed (mutmut discriminates) AND
    # zero SUT mutants killed. The PBT cannot tell a broken SUT from a
    # correct one -> RobustnessPBTNotFalsifiable.
    KILL_RATE_ZERO = "kill-rate zero while positive control was killed"
    # R5 unavailable: the JSON cannot be parsed. mutmut may have crashed
    # mid-run, OOMed, or the writer truncated -- the gate cannot decide
    # pass or fail.
    REPORT_MALFORMED = "fixture report cannot be parsed as JSON"
    # R5 unavailable: parseable but the mutants block is empty. mutmut may
    # have been configured against zero paths, or the cache was reset
    # without a re-run.
    REPORT_EMPTY = "fixture report parses but lists no mutants"
    # R5 unavailable: parseable, non-empty, but missing the declared sut
    # symbol entry. mutmut ran against a different paths_to_mutate scope
    # than the manifest declares.
    REPORT_PARTIAL_MISSING_SUT = (
        "fixture report parses but lacks the declared sut symbol entry"
    )
    # R5 unavailable: parseable, populated, but the positive control was
    # NOT killed -- mutmut is not discriminating in this environment, so
    # NO kill-rate-0 verdict from the same run can be trusted as "fail".
    POSITIVE_CONTROL_FAILED = (
        "fixture report parses but the positive control was not killed"
    )


class Slice05WiringSurface(str, Enum):
    """The slice-05 wiring-surface cells the SUT is driven through.

    Slice-05 is the WIRING slice (last by design per feature-delta § 6
    line 410). The SUT is the wiring substrate -- three distinct driving
    ports per Mandate-13 (driving-port-only boundary):

    * AT_REVIEW_VERDICT: the real ``scripts/cli/at_review_verdict.py``
      DISTILL-exit verdict producer. The robustness density gate CLI's
      exit code gates the producer's APPROVED ledger-record write. Layer 3
      subprocess driving port.

    * SUBAGENT_STOP_HOOK: the real ``SubagentStop`` hook chain a real
      sub-agent dispatch passes through. The robustness density gate is
      registered as an intercept; a CLI exit-one verdict mechanically
      blocks the dispatch outcome. Layer 4 wiring_e2e driving port -- B4
      mandate: live, NEVER mocked.

    * REAL_M_PRODUCER_MANIFEST: the real M slice-04
      manifest producer (the ``nw-design`` step) emits the
      ``component-manifest.yaml`` the gate runs against. Layer 3
      subprocess driving port -- B1 mandate: throwaway feature whose
      manifest is producer-emitted, NEVER a hand-authored fixture.
    """

    AT_REVIEW_VERDICT = (
        "the AT review verdict producer consulting the robustness density "
        "gate CLI exit code at DISTILL exit"
    )
    SUBAGENT_STOP_HOOK = (
        "the real SubagentStop hook chain a real sub agent dispatch passes "
        "through with the robustness density gate registered as an intercept"
    )
    REAL_M_PRODUCER_MANIFEST = (
        "the robustness density gate run against a component manifest "
        "emitted by the real design manifest producer for a throwaway feature"
    )


class Slice03GenuinenessKind(str, Enum):
    """The slice-03 genuineness-layer cells (C2/C6 state coverage).

    Drives the slice-03 AT trio per the feature-delta § 6 slice plan row.
    Genuineness layers 1+3 (anti-shallow-PBT) reject a tagged @given whose
    strategy is trivial-by-AST or whose body asserts a tautology, including
    one level of module-local indirection per B5. Layer 2 (mutmut kill-rate)
    is out of slice-03 scope (slice-04). The fourth cell is the adversarial
    AST robustness probe: the gate's own parser is the SUT; the indirect-
    parametrize-source case (V4) is the canonical adversarial input.
    """

    TRIVIAL_STRATEGY_DIRECT = "trivial strategy declared directly at the @given site"
    TRIVIAL_STRATEGY_VIA_HELPER = (
        "trivial strategy reached via a single-hop module-local helper"
    )
    TAUTOLOGY_ASSERT_DIRECT = "tautology-only assertion declared in the test body"
    TAUTOLOGY_ASSERT_VIA_HELPER = (
        "tautology-only assertion reached via a single-hop module-local helper"
    )
    ADVERSARIAL_AST_INDIRECT_PARAMETRIZE = (
        "adversarial test-file AST with an indirect parametrize source"
    )


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12: the DSL emerges from typed concepts. Each Gherkin literal maps
# to a typed enum here; parameterized step templates in ``common_steps.py``
# do a single dict lookup, never an ``if``-ladder.

COVERAGE_BY_PHRASE: dict[str, CoverageOutcome] = {c.value: c for c in CoverageOutcome}

EXIT_BY_MEANING: dict[str, RobustnessGateExit] = {
    "success": RobustnessGateExit.PASS,
    "check failed": RobustnessGateExit.CHECK_FAILED,
    "a malformed declaration": RobustnessGateExit.MALFORMED,
    # slice-02 widens exit-1 semantics without adding a new exit code; the
    # diagnostic distinction is carried in the human-surface stdout token
    # (RobustnessDeclarationMissing / RobustnessProvenanceViolation).
    "a missing declaration": RobustnessGateExit.CHECK_FAILED,
    "a provenance violation": RobustnessGateExit.CHECK_FAILED,
    # slice-03 widens exit-1 semantics further; genuineness layers 1 + 3
    # reject shallow-by-AST PBTs (trivial strategy / tautology-only assert,
    # both also resolved one hop via module-local helpers per B5) and the
    # adversarial-AST robustness probe gives a deterministic verdict
    # without crashing. The diagnostic token carried on stdout is the
    # discriminating observable (RobustnessPBTShallow).
    "a shallow property-based test": RobustnessGateExit.CHECK_FAILED,
    # slice-04 widens exit-1 semantics further; Layer 2 (mutmut-delta proxy)
    # refuses a PBT whose declared sut symbol kills zero mutants while the
    # positive control was killed. Same exit code, distinct stdout token
    # (RobustnessPBTNotFalsifiable).
    "a property-based test that is not falsifiable": RobustnessGateExit.CHECK_FAILED,
    # slice-04 R5 three-state: the new exit 3 holds the feature out of
    # ready when mutmut cannot answer truthfully -- neither pass nor fail.
    # Distinct from CHECK_FAILED because the gate does NOT have evidence of
    # a shallow PBT; it has evidence the dependency cannot be trusted.
    "the falsifiability layer is unavailable and the feature is held out of ready": RobustnessGateExit.UNAVAILABLE,
    # slice-04 happy-path phrasing: explicit Pillar-1 "Layer 2 satisfied".
    "the falsifiability layer was satisfied": RobustnessGateExit.PASS,
}
