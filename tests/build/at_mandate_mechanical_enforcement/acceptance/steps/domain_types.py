"""Domain types for the at-mandate-mechanical-enforcement acceptance suite.

Mandate-12 (criterion 1): every domain noun used in the Gherkin and the Python
ATs is expressed once here as a typed enum / NewType / dataclass. Step methods
and the composition service consume these types — never raw ``str`` where a
domain enum exists.

slice-01 vocabulary — the M1 driving-port-boundary gate (walking skeleton).
The domain nouns:

  * a *step suite* under audit (a golden-fixture corpus file the gate scans);
  * its *boundary verdict* (clean vs flagged) — the port-exposed observable;
  * the *kind* of corpus (planted-violation vs clean) the gate is asked about.

The slice-01 self-AT closes the loop: ``detect(violation) == flagged`` AND
``detect(clean) == clean`` (ADR-TEST-002 D-E golden-fixture-AT meta-rule).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import NewType


# --- domain nouns ----------------------------------------------------------

# The name of a ``@when`` step function as the gate reports it, e.g.
# "when_operator_runs_the_install".
StepFunctionName = NewType("StepFunctionName", str)

# A dotted driven-adapter module path the gate flags, e.g.
# "des.adapters.driven.logging.jsonl_audit_log_writer".
DrivenAdapterModule = NewType("DrivenAdapterModule", str)


class CorpusKind(Enum):
    """Which golden-fixture corpus the gate is being asked to classify.

    PLANTED_VIOLATION — a step file with a ``@when`` body importing a driven
                        adapter. The gate MUST flag it (the recall half).
    CLEAN             — a well-formed step file (driving-port entry, with the
                        module-level + ``@given`` near-miss imports). The gate
                        MUST NOT flag it (the precision half).
    """

    PLANTED_VIOLATION = "planted_violation"
    CLEAN = "clean"


class BoundaryOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one ``@when`` step imports a driven adapter.
    CLEAN   — no driving-port-boundary breach found.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


# --- canonical fixtures of record ------------------------------------------

_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "driving_port_boundary"
)

# The planted-violation corpus + the exact (function, module) breach it carries.
VIOLATION_CORPUS: Path = _FIXTURES_DIR / "violation_when_imports_driven_adapter.py"
EXPECTED_OFFENDING_FUNCTION: StepFunctionName = StepFunctionName(
    "when_operator_runs_the_install"
)
EXPECTED_OFFENDING_MODULE: DrivenAdapterModule = DrivenAdapterModule(
    "des.adapters.driven.logging.jsonl_audit_log_writer"
)

# The clean corpus the gate must pass (carrying the two near-miss imports).
CLEAN_CORPUS: Path = _FIXTURES_DIR / "clean_when_uses_driving_port.py"


# ===========================================================================
# slice-02 vocabulary — the adapter-capability-registry SSOT (@infrastructure)
# ===========================================================================
#
# The domain nouns of the registry contract:
#
#   * the *required capabilities* — the complete contract every per-language
#     adapter must implement (the SSOT a new-language implementer reads);
#   * a *conformance verdict* (conformant vs non-conformant) — the port-exposed
#     observable when an adapter is checked against the contract;
#   * the *consumed-so-far* subset — the capabilities the gates authored to date
#     actually consume (the reference Python adapter must cover at least these);
#   * the *missing capability* the verdict names when an adapter is incomplete.

from des.testarch.capabilities import _REGISTRY, Capability
from des.testarch.rules import (  # noqa: F401  (import-for-side-effect: register)
    assert_state_delta,
    composition_root,
    driving_port_boundary,
    pbt_layer_mode,
    sad_path_pbt,
    seam_tag_honesty,
    technical_call_smell,
)


# The complete capability contract of record (ADR-TEST-002 D-C). The registry's
# required_capabilities() must enumerate exactly this set — the single checklist.
EXPECTED_REQUIRED_CONTRACT: frozenset[Capability] = frozenset(Capability)

# The capabilities the gates authored to date actually consume — DERIVED from the
# live ``_REGISTRY`` (the union of every ``@requires_capabilities``-registered
# rule's declared consumption), NOT a hand-frozen list (feature-end deep-review
# D1: a transcribed subset drifts as gates are added; the live registry is the
# SSOT). The rule modules above are imported for their registration side-effect so
# the union is populated. The reference Python adapter must be judged conformant
# for at least these.
CONSUMED_SO_FAR: frozenset[Capability] = frozenset().union(*_REGISTRY.values())

# The capability the planted-gap adapter fixture deliberately omits — the gate
# MUST name it as the missing capability (the recall half of the conformance
# check; ADR-TEST-002 D-E golden-fixture meta-rule).
PLANTED_MISSING_CAPABILITY: Capability = Capability.IMPORTS_IN_FUNCTION


class ConformanceOutcome(Enum):
    """The port-exposed verdict the registry returns for an adapter.

    CONFORMANT     — the adapter implements every required capability.
    NON_CONFORMANT — at least one required capability is missing.
    """

    CONFORMANT = "conformant"
    NON_CONFORMANT = "non_conformant"


# ===========================================================================
# slice-03 vocabulary — the M8 universe-bound-assertion gate (@infrastructure)
# ===========================================================================
#
# The domain nouns of the universe-guard contract:
#
#   * a *test suite* under audit (a golden-fixture corpus file the gate scans);
#   * its *guard verdict* (clean vs flagged) — the port-exposed observable;
#   * the *kind* of corpus (missing-guard / private-leak / clean) the gate is
#     asked about;
#   * the *breach kind* the verdict names — a missing universe guard, or a
#     private (``_``-prefixed) field leaked into the ``universe=`` argument;
#   * the named offenders: the unguarded test, the leaking test, the leaked
#     private field.


class GuardCorpusKind(Enum):
    """Which golden-fixture corpus the universe-guard gate classifies.

    MISSING_GUARD  — a state-mutating layer-1-3 test with NO assert_state_delta
                     call. The gate MUST flag it (recall half #1).
    PRIVATE_LEAK   — a state-mutating test that calls assert_state_delta but
                     names a ``_``-prefixed field in ``universe=``. The gate MUST
                     flag it (recall half #2).
    CLEAN          — a suite that guards every mutation over port-observable
                     names, carrying the near-miss traps (a read-only test with
                     no guard; a higher-layer test with no guard). The gate MUST
                     NOT flag it (the precision half).
    """

    MISSING_GUARD = "missing_guard"
    PRIVATE_LEAK = "private_leak"
    CLEAN = "clean"


class GuardOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one state-mutating test fails the universe guard.
    CLEAN   — every state-mutating layer-1-3 test guards over port-observable
              names; no breach found.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


class BreachKind(Enum):
    """The kind of universe-guard breach the verdict names.

    MISSING_ASSERT        — a state-mutating test has no assert_state_delta call.
    PRIVATE_UNIVERSE_LEAK — a ``_``-prefixed name appears in ``universe=``.
    """

    MISSING_ASSERT = "missing_assert"
    PRIVATE_UNIVERSE_LEAK = "private_universe_leak"


# --- canonical slice-03 fixtures of record ---------------------------------

_GUARD_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "universe_bound_assertion"
)

# The missing-guard corpus + the exact unguarded test it carries.
MISSING_GUARD_CORPUS: Path = _GUARD_FIXTURES_DIR / "violation_missing_universe_guard.py"
EXPECTED_UNGUARDED_TEST: StepFunctionName = StepFunctionName(
    "test_operator_changes_email_without_guard"
)

# The private-leak corpus + the exact (test, leaked private field) breach.
PRIVATE_LEAK_CORPUS: Path = _GUARD_FIXTURES_DIR / "violation_private_universe_leak.py"
EXPECTED_LEAKING_TEST: StepFunctionName = StepFunctionName(
    "test_operator_changes_email_leaking_private_field"
)
EXPECTED_LEAKED_PRIVATE_FIELD: str = "_audit_rows"

# The clean corpus the gate must pass (carrying the read-only + higher-layer
# near-miss traps).
GUARD_CLEAN_CORPUS: Path = _GUARD_FIXTURES_DIR / "clean_universe_guarded.py"


# ===========================================================================
# slice-04 vocabulary — the M9/9-v2 PBT-layer-mode gate (@infrastructure)
# ===========================================================================
#
# The domain nouns of the PBT-layer-mode contract:
#
#   * a *test file* under audit (a golden-fixture corpus file the gate scans);
#   * its *layer mode verdict* (clean vs flagged) — the port-exposed observable;
#   * the *kind* of corpus (given-at-layer-3+ / state-machine-at-layer-3+ /
#     clean) the gate is asked about;
#   * the *breach kind* the verdict names — a @given test at a layer-3+ file, or
#     a RuleBasedStateMachine import/subclass at a layer-3+ file;
#   * the *representative layer* a corpus is classified at — a layer-3+ file
#     (PBT forbidden) vs a layer-1-2 file (PBT's home);
#   * the named offenders: the @given test construct, the state-machine construct.


# The name of a PBT construct as the gate reports it — a @given test function
# name (e.g. "test_install_plan_is_total_at_integration") or the
# RuleBasedStateMachine symbol.
PbtConstructName = NewType("PbtConstructName", str)


class PbtCorpusKind(Enum):
    """Which golden-fixture corpus the PBT-layer-mode gate classifies.

    GIVEN_AT_LAYER_3PLUS         — a @given property test classified at a
                                   layer-3+ file. The gate MUST flag it
                                   (recall half #1).
    STATE_MACHINE_AT_LAYER_3PLUS — a RuleBasedStateMachine import/subclass
                                   classified at a layer-3+ file. The gate MUST
                                   flag it (recall half #2).
    CLEAN_PBT_AT_LAYER_1_2       — a @given + RuleBasedStateMachine corpus
                                   classified at a layer-1-2 file (PBT's home).
                                   The gate MUST NOT flag it (precision half #1).
    CLEAN_EXAMPLE_AT_LAYER_3PLUS — an example-based test classified at a layer-3+
                                   file, carrying the textual near-miss trap. The
                                   gate MUST NOT flag it (precision half #2).
    """

    GIVEN_AT_LAYER_3PLUS = "given_at_layer_3plus"
    STATE_MACHINE_AT_LAYER_3PLUS = "state_machine_at_layer_3plus"
    CLEAN_PBT_AT_LAYER_1_2 = "clean_pbt_at_layer_1_2"
    CLEAN_EXAMPLE_AT_LAYER_3PLUS = "clean_example_at_layer_3plus"


class PbtLayerOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one PBT construct sits at a PBT-forbidden (layer-3+) file.
    CLEAN   — every PBT construct sits at layers 1-2, or the file carries none;
              no breach found.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


class PbtBreachKind(Enum):
    """The kind of PBT-layer-mode breach the verdict names.

    GIVEN_AT_LAYER_3PLUS         — a @given-decorated test in a layer-3+ file.
    STATE_MACHINE_AT_LAYER_3PLUS — a RuleBasedStateMachine in a layer-3+ file.
    """

    GIVEN_AT_LAYER_3PLUS = "given_at_layer_3plus"
    STATE_MACHINE_AT_LAYER_3PLUS = "state_machine_at_layer_3plus"


# --- canonical slice-04 fixtures of record ---------------------------------

_PBT_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "pbt_layer_mode"
)

# The @given-at-layer-3+ corpus + the exact offending construct it carries. The
# representative path declares the layer (an ``integration`` segment → layer 4,
# in the PBT-forbidden set); the fixture content is read off the real disk path.
GIVEN_AT_LAYER_CORPUS: Path = _PBT_FIXTURES_DIR / "violation_given_at_layer_3plus.py"
GIVEN_AT_LAYER_REPRESENTATIVE_PATH = (
    "tests/des/integration/install/test_install_plan_property.py"
)
EXPECTED_GIVEN_CONSTRUCT: PbtConstructName = PbtConstructName(
    "test_install_plan_is_total_at_integration"
)

# The state-machine-at-layer-3+ corpus + the exact offending construct. The
# representative path declares the layer (an ``e2e`` segment → layer 6).
STATE_MACHINE_AT_LAYER_CORPUS: Path = (
    _PBT_FIXTURES_DIR / "violation_state_machine_at_layer_3plus.py"
)
STATE_MACHINE_AT_LAYER_REPRESENTATIVE_PATH = (
    "tests/des/e2e/install/test_install_journey_state_machine.py"
)
EXPECTED_STATE_MACHINE_CONSTRUCT: PbtConstructName = PbtConstructName(
    "RuleBasedStateMachine"
)

# The clean PBT-at-layer-1-2 corpus (PBT at its home layer). The representative
# path declares the layer (a ``unit`` segment → layer 1, NOT in the forbidden
# set).
CLEAN_PBT_AT_LAYER_CORPUS: Path = _PBT_FIXTURES_DIR / "clean_pbt_at_layer_1_2.py"
CLEAN_PBT_AT_LAYER_REPRESENTATIVE_PATH = "tests/des/unit/totals/test_totals_property.py"

# The clean example-at-layer-3+ near-miss corpus (example test, no PBT construct,
# at a layer-3+ file). The representative path declares the layer (an
# ``integration`` segment → layer 4).
CLEAN_EXAMPLE_AT_LAYER_CORPUS: Path = (
    _PBT_FIXTURES_DIR / "clean_example_at_layer_3plus.py"
)
CLEAN_EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH = (
    "tests/des/integration/install/test_install_plan_example.py"
)


# ===========================================================================
# slice-05 vocabulary — the CM-I seam-tag-honesty gate (@infrastructure)
# ===========================================================================
#
# The domain nouns of the seam-tag-honesty contract (CM-I, ADR-TEST-001 D-8):
#
#   * a *test suite* under audit (a golden-fixture corpus file the gate scans);
#   * a test's *tag claim* — the real-subprocess marker tags it carries
#     (``@wiring_e2e`` / ``@subprocess``), the CLAIM about what it spawns;
#   * a test's *spawn shape* — what the body ACTUALLY spawns (nothing / an
#     in-process ``main(argv)`` / a real subprocess);
#   * its *honesty verdict* (honest vs flagged) — the port-exposed observable;
#   * the *breach kind* the verdict names — a test claiming a real subprocess
#     whose body runs ``main(argv)`` in-process;
#   * the named offender: the dishonest test + the claim tag it carries.


# The name of a test function as the gate reports it, e.g.
# "test_install_reports_plan".
SeamTestName = NewType("SeamTestName", str)


class SeamCorpusKind(Enum):
    """Which golden-fixture corpus the CM-I seam-tag-honesty gate classifies.

    DISHONEST_WIRING_E2E — a test tagged ``@wiring_e2e`` whose body drives
                           ``main(argv)`` in-process (no real spawn). The gate
                           MUST flag it (the recall half).
    HONEST_TAGS          — a suite with honest tags: a ``@wiring_e2e`` test that
                           genuinely spawns a real subprocess, AND the precision
                           near-miss (an in-process ``main(argv)`` body honestly
                           tagged ``@component``). The gate MUST NOT flag it (the
                           precision half).
    """

    DISHONEST_WIRING_E2E = "dishonest_wiring_e2e"
    HONEST_TAGS = "honest_tags"


class SeamHonestyOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one test's real-subprocess tag claim mismatches its
              in-process body (a dishonest seam tag).
    HONEST  — every test's tag matches its spawn shape; no breach found.
    """

    FLAGGED = "flagged"
    HONEST = "honest"


class SeamBreachKind(Enum):
    """The kind of seam-tag-honesty breach the verdict names.

    TAG_CLAIMS_SUBPROCESS_BUT_RUNS_IN_PROCESS — a test tagged
        ``@wiring_e2e``/``@subprocess`` whose body drives ``main(argv)``
        in-process (or spawns nothing), so the shared seam is never exercised.
    """

    TAG_CLAIMS_SUBPROCESS_BUT_RUNS_IN_PROCESS = (
        "tag_claims_subprocess_but_runs_in_process"
    )


# --- canonical slice-05 fixtures of record ---------------------------------

_SEAM_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "seam_tag_honesty"
)

# The dishonest corpus + the exact (test, claim tag) breach it carries.
DISHONEST_CORPUS: Path = _SEAM_FIXTURES_DIR / "violation_wiring_e2e_runs_in_process.py"
EXPECTED_DISHONEST_TEST: SeamTestName = SeamTestName("test_install_reports_plan")
EXPECTED_DISHONEST_CLAIM_TAG: str = "wiring_e2e"

# The honest corpus the gate must pass (a real-subprocess @wiring_e2e test plus
# the in-process @component precision near-miss).
SEAM_HONEST_CORPUS: Path = _SEAM_FIXTURES_DIR / "clean_honest_tags.py"


# ===========================================================================
# slice-06 vocabulary — the dispatcher registration-contract gate (@component)
# ===========================================================================
#
# The domain nouns of the registration contract (F-DES-SINGLE-ENTRY-POINT-
# CONSOLIDATION; feature-delta slice-plan row 223, DDD-6):
#
#   * a *subcommand registry* under audit — the live ``des`` ``_REGISTRY`` or a
#     golden-fixture registry of rows (each row = name + module path + entry attr);
#   * a *registration verdict* (conformant vs non-conformant) — the port-exposed
#     observable when a registry is checked against the contract;
#   * the *breach kind* the verdict names — a row whose module is unimportable, or
#     whose entry attribute is missing / non-callable;
#   * the named offenders: the dropped-module row, the missing-``main`` row;
#   * the *row count* the gate checked — proof the gate is count-agnostic (it
#     scales to whatever rows the registry exposes, no per-subcommand authoring).
#
# DDD-6 (HARD): the count-agnostic scenario parametrizes over the LIVE
# ``des.cli.__main__._REGISTRY`` (read at runtime), NOT the drifting
# SUBCOMMAND_TABLE mirror — reading live is auto-extending as subcommands are
# added.


# The operator-visible name of a registry row as the gate reports it.
SubcommandRowName = NewType("SubcommandRowName", str)


class RegistryCorpusKind(Enum):
    """Which golden-fixture registry the registration-contract gate classifies.

    DROPPED_OR_BROKEN — a registry carrying a wired row PLUS two planted
                        breaches: a row whose module is unimportable, and a row
                        whose module imports but exposes no callable ``main``.
                        The gate MUST flag it and name BOTH (the recall half).
    FULLY_WIRED       — a registry whose every row resolves, imports, and exposes
                        a callable ``main``. The gate MUST NOT flag it (the
                        precision half).
    LIVE              — the live ``des.cli.__main__._REGISTRY`` itself, read at
                        runtime. The gate MUST clear it AND report a row count
                        matching the live registry's length — proof the gate is
                        count-agnostic / auto-extending (DDD-6).
    """

    DROPPED_OR_BROKEN = "dropped_or_broken"
    FULLY_WIRED = "fully_wired"
    LIVE = "live"


class RegistrationOutcome(Enum):
    """The port-exposed verdict the gate returns for a registry.

    FLAGGED     — at least one row fails to resolve / import / expose a callable
                  entry (a dropped or half-wired registration).
    CONFORMANT  — every row resolves, imports, and exposes a callable entry; no
                  breach found.
    """

    FLAGGED = "flagged"
    CONFORMANT = "conformant"


# The two row names the planted-violation registry deliberately breaks — the gate
# MUST name BOTH so a dropped-registration regression is pinpointed (recall half).
EXPECTED_UNIMPORTABLE_ROW: SubcommandRowName = SubcommandRowName("dropped-module")
EXPECTED_MAIN_MISSING_ROW: SubcommandRowName = SubcommandRowName("main-missing")


# ===========================================================================
# slice-07 vocabulary — the M11 integration-sad-path gate (@infrastructure)
# ===========================================================================
#
# The domain nouns of the M11 contract (Mandate 11, SKILL.md :300-307):
#
#   * a *sad-path test file* under audit (a golden-fixture corpus the gate scans),
#     classified at a representative layer (3+ forbidden vs 1-2 home);
#   * its *sad-path verdict* (clean vs flagged) — the port-exposed observable;
#   * the *kind* of corpus the gate is asked about (PBT-stranded-at-layer-3+ /
#     example-based-at-layer-3+ / PBT-at-home-layer / uncovered-failure-mode /
#     covered-failure-mode / R6-adversarial);
#   * the *breach kind* the verdict names — a PBT construct stranded in a
#     layer-3+ sad-path file, or a manifest failure-mode entry with no covering
#     named test;
#   * the named offenders: the stranded PBT construct, the uncovered failure mode.
#
# The PBT-layer half flags property machinery where only enumerated example-based
# sad paths belong (each generated example is real-I/O-heavy at layer 3+). The
# coverage half flags a ``failure_modes`` entry declared in a component manifest
# that no named test covers — a declared-but-untested failure mode.

from des.testarch.rules.sad_path_pbt import (
    PBT_IN_LAYER3_SAD_PATH_BREACH,
    UNCOVERED_FAILURE_MODE_BREACH,
)
from des.testarch.rules.technical_call_smell import (
    TECHNICAL_CALL_IN_STEP_BODY as TECHNICAL_CALL_IN_STEP_BODY_BREACH,
)


# The name of an offending construct as the gate reports it — a stranded
# ``@given`` test function name (e.g. "test_install_fails_when_disk_full"), or the
# RuleBasedStateMachine symbol, or an uncovered ``failure_modes`` entry id.
SadPathOffenderName = NewType("SadPathOffenderName", str)


class SadPathCorpusKind(Enum):
    """Which golden-fixture corpus the M11 integration-sad-path gate classifies.

    PBT_STRANDED_AT_LAYER_3PLUS — a ``@given`` (or stateful-PBT-import) sad-path
                                  test classified at a layer-3+ file. The gate
                                  MUST flag it (the PBT-half recall).
    EXAMPLE_AT_LAYER_3PLUS      — an example-based sad-path test at a layer-3+
                                  file, carrying the textual near-miss trap. The
                                  gate MUST NOT flag it (precision half #1).
    PBT_AT_HOME_LAYER           — a ``@given`` + stateful-PBT corpus at a
                                  layer-1-2 file (PBT's home). The gate MUST NOT
                                  flag it (precision half #2).
    UNCOVERED_FAILURE_MODE      — a component manifest declaring a ``failure_modes``
                                  entry that no named test covers. The gate MUST
                                  flag it (the coverage-half recall).
    COVERED_FAILURE_MODE        — a manifest whose every ``failure_modes`` entry
                                  has a matching named test. The gate MUST NOT
                                  flag it (the coverage-half precision).
    R6_ADVERSARIAL              — the dormant ``check_robustness_density.py`` R6
                                  self-dogfood case: an adversarial test-file shape
                                  the gate's own parser cannot classify. The gate
                                  MUST survive it deterministically (no crash) —
                                  the gate's parser is the SUT here.
    """

    PBT_STRANDED_AT_LAYER_3PLUS = "pbt_stranded_at_layer_3plus"
    EXAMPLE_AT_LAYER_3PLUS = "example_at_layer_3plus"
    PBT_AT_HOME_LAYER = "pbt_at_home_layer"
    UNCOVERED_FAILURE_MODE = "uncovered_failure_mode"
    COVERED_FAILURE_MODE = "covered_failure_mode"
    R6_ADVERSARIAL = "r6_adversarial"


class SadPathOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one PBT construct sits in a layer-3+ sad-path file, OR at
              least one manifest failure mode is uncovered.
    CLEAN   — every sad path at layer 3+ is example-based, every PBT construct is
              at its home layer, and every declared failure mode is covered.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


class SadPathBreachKind(Enum):
    """The kind of integration-sad-path breach the verdict names.

    PBT_IN_LAYER3_SAD_PATH — a ``@given`` / stateful-PBT construct in a layer-3+
                             sad-path file (Mandate 11: sad paths stay
                             example-based, never PBT-generated, at layers 3+).
    UNCOVERED_FAILURE_MODE — a ``failure_modes`` entry declared in a component
                             manifest with no covering named test.
    """

    PBT_IN_LAYER3_SAD_PATH = PBT_IN_LAYER3_SAD_PATH_BREACH
    UNCOVERED_FAILURE_MODE = UNCOVERED_FAILURE_MODE_BREACH


# --- canonical slice-07 fixtures of record ---------------------------------

_SAD_PATH_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "sad_path_pbt"
)

# The PBT-stranded-at-layer-3+ corpus + the exact offending construct. The
# representative path declares the layer (an ``integration`` segment → layer 4,
# in the PBT-forbidden set the adapter CAN emit); the fixture content is read off
# the real disk path.
PBT_STRANDED_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "violation_pbt_sad_path_at_layer_3plus.py"
)
PBT_STRANDED_REPRESENTATIVE_PATH = (
    "tests/des/integration/install/test_install_failures_property.py"
)
EXPECTED_STRANDED_PBT_CONSTRUCT: SadPathOffenderName = SadPathOffenderName(
    "test_install_fails_when_disk_full"
)

# The clean example-based-at-layer-3+ near-miss corpus (enumerated sad paths, no
# PBT construct, at a layer-3+ file). The representative path declares the layer.
EXAMPLE_AT_LAYER_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "clean_example_sad_path_at_layer_3plus.py"
)
EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH = (
    "tests/des/integration/install/test_install_failures_example.py"
)

# The clean PBT-at-home-layer corpus (PBT at layers 1-2 — its home). The
# representative path declares the layer (a ``unit`` segment → layer 1, NOT in
# the forbidden set).
PBT_AT_HOME_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "clean_pbt_sad_path_at_home_layer.py"
)
PBT_AT_HOME_REPRESENTATIVE_PATH = (
    "tests/des/unit/install/test_install_failures_property.py"
)

# The uncovered-failure-mode manifest + the exact declared mode no named test
# covers. The covered-mode manifest pairs with the covering test names.
UNCOVERED_MANIFEST_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "violation_manifest_uncovered_failure_mode.yaml"
)
EXPECTED_UNCOVERED_FAILURE_MODE: SadPathOffenderName = SadPathOffenderName(
    "disk_full_during_write"
)
COVERED_MANIFEST_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "clean_manifest_covered_failure_modes.yaml"
)
# The named tests that cover every entry in the covered-mode manifest (the
# precision corpus feeds these to the coverage cross-check).
COVERED_FAILURE_MODE_TEST_NAMES: tuple[str, ...] = (
    "test_install_fails_when_disk_full",
    "test_install_fails_when_permission_denied",
)

# The R6 self-dogfood adversarial corpus — the dormant check_robustness_density
# parser's own unclassifiable shape (an indirect ``parametrize`` value source via
# a helper Call). Promoted to a golden adversarial fixture: the gate MUST survive
# it deterministically without crashing (the gate's own parser is the SUT).
R6_ADVERSARIAL_CORPUS: Path = (
    _SAD_PATH_FIXTURES_DIR / "adversarial_r6_indirect_parametrize_source.py"
)
R6_ADVERSARIAL_REPRESENTATIVE_PATH = (
    "tests/des/integration/install/test_install_failures_adversarial.py"
)


# ===========================================================================
# slice-08 vocabulary — the M2 technical-call-smell gate (@component)
# ===========================================================================
#
# The domain nouns of the M2 contract (Mandate 2, test-smell denylist half):
#
#   * a *step suite* under audit (a golden-fixture corpus the gate scans) whose
#     pytest-bdd step bodies are checked for technical calls;
#   * its *smell verdict* (clean vs flagged) — the port-exposed observable;
#   * the *kind* of corpus the gate is asked about (technical-calls /
#     technical-assertion / clean-domain-delegation);
#   * the *breach kind* the verdict names — a technical call (HTTP / DB) issued
#     inside a step body, where only domain delegation belongs;
#   * the named offenders: the offending step + the technical callee it issues.
#
# The gate keys ONLY on the call-shape DENYLIST (the mechanizable half). The
# ubiquitous-language SEMANTIC judgment ("does the step speak the domain?") stays
# Tier-J agent-audit and is out of scope. The mechanism is the dotted callee of
# each call site in a step body (Capability.CALLS_IN_FUNCTION, already produced
# by the production adapter — NO new capability is added by this slice).


# The name of an offending step function as the gate reports it, e.g.
# "when_the_customer_submits_the_order".
TechnicalCallStepName = NewType("TechnicalCallStepName", str)

# A denylisted technical dotted callee the gate flags, e.g. "requests.post" or
# "db.execute".
TechnicalCallee = NewType("TechnicalCallee", str)


class TechnicalCallCorpusKind(Enum):
    """Which golden-fixture corpus the M2 technical-call-smell gate classifies.

    TECHNICAL_CALLS       — step bodies issuing an HTTP client call
                            (``requests.post``) and a DB call (``db.execute``).
                            The gate MUST flag it and name BOTH (the recall half).
    TECHNICAL_ASSERTION   — a step body whose assertion is driven by a technical
                            HTTP call (``assert client.get(url).status_code ==
                            200``). The gate MUST flag it (the assertion-variant
                            recall half).
    CLEAN_DOMAIN          — a step suite that always delegates to domain services
                            and asserts domain outcomes, carrying the precision
                            near-misses (a ``.place``/``.judge`` domain method; a
                            ``.status`` domain-outcome attribute read). The gate
                            MUST NOT flag it (the precision half — the slice-08
                            learning-hypothesis guard).
    """

    TECHNICAL_CALLS = "technical_calls"
    TECHNICAL_ASSERTION = "technical_assertion"
    CLEAN_DOMAIN = "clean_domain"


class TechnicalCallOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one step body issues a denylisted technical call.
    CLEAN   — every step body delegates only to domain services; no breach found.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


class TechnicalCallBreachKind(Enum):
    """The kind of M2 technical-call-smell breach the verdict names.

    TECHNICAL_CALL_IN_STEP_BODY — a step body issues a denylisted technical call
        (an HTTP ``requests.*``/``httpx.*`` call, or a DB ``db.execute`` /
        ``cursor.execute`` / ``session.execute`` call), including one nested in an
        assertion, where only domain-language delegation belongs (Mandate 2).
    """

    TECHNICAL_CALL_IN_STEP_BODY = TECHNICAL_CALL_IN_STEP_BODY_BREACH


# --- canonical slice-08 fixtures of record ---------------------------------

_TECHNICAL_CALL_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "technical_call_smell"
)

# The technical-calls corpus + the exact (step, callee) breaches it carries — the
# gate MUST name BOTH so a regression is pinpointed (recall half).
TECHNICAL_CALLS_CORPUS: Path = (
    _TECHNICAL_CALL_FIXTURES_DIR / "violation_step_issues_technical_calls.py"
)
EXPECTED_HTTP_CALL_STEP: TechnicalCallStepName = TechnicalCallStepName(
    "when_the_customer_submits_the_order"
)
EXPECTED_HTTP_CALLEE: TechnicalCallee = TechnicalCallee("requests.post")
EXPECTED_DB_CALL_STEP: TechnicalCallStepName = TechnicalCallStepName(
    "then_the_order_is_recorded"
)
EXPECTED_DB_CALLEE: TechnicalCallee = TechnicalCallee("db.execute")

# The technical-assertion corpus + the exact (step, callee) breach — an HTTP call
# driving an assertion.
TECHNICAL_ASSERTION_CORPUS: Path = (
    _TECHNICAL_CALL_FIXTURES_DIR / "violation_step_asserts_on_technical_call.py"
)
EXPECTED_ASSERTION_STEP: TechnicalCallStepName = TechnicalCallStepName(
    "then_the_response_is_ok"
)
EXPECTED_ASSERTION_CALLEE: TechnicalCallee = TechnicalCallee("requests.get")

# The clean corpus the gate must pass (carrying the domain-method + domain-outcome
# near-miss traps) — the precision-half / learning-hypothesis guard.
CLEAN_DOMAIN_CORPUS: Path = (
    _TECHNICAL_CALL_FIXTURES_DIR / "clean_step_delegates_to_domain.py"
)


# ===========================================================================
# slice-09 vocabulary — the P3 composition-root gate (@component)
# ===========================================================================
#
# The domain nouns of the P3 contract (Pillar 3, "app as in production"):
#
#   * a *step suite* under audit (a golden-fixture corpus the gate scans) whose
#     pytest-bdd step bodies are checked for hand-wired SUT construction;
#   * its *composition verdict* (clean vs flagged) — the port-exposed observable;
#   * the *kind* of corpus the gate is asked about (hand-wired-SUT /
#     composition-root-call);
#   * the *breach kind* the verdict names — a step body that assembles the SUT's
#     collaborator object graph by hand where a composition-root entry call belongs;
#   * the named offenders: the offending step + the collaborator type it hand-wires.
#
# The gate keys ONLY on the structural Pillar — P3 (composition-root). P1
# (domain-language) and P2 (chained-narrative) are SEMANTIC judgments that stay
# Tier-J agent-audit and are out of scope. The mechanism is the
# collaborator-constructing assignments of each step body
# (Capability.ASSIGNMENTS_CONSTRUCTING_TYPE) cross-checked against the
# presence/absence of a composition-root entry call (Capability.CALLS_IN_FUNCTION).

from des.testarch.rules.composition_root import (
    HAND_WIRED_SUT_IN_STEP_BODY as HAND_WIRED_SUT_IN_STEP_BODY_BREACH,
)


# The name of an offending step function as the gate reports it, e.g.
# "given_a_customer_with_an_order".
CompositionStepName = NewType("CompositionStepName", str)

# A hand-wired SUT-collaborator type the gate names, e.g. "OrderService".
CompositionConstructedType = NewType("CompositionConstructedType", str)


class CompositionCorpusKind(Enum):
    """Which golden-fixture corpus the P3 composition-root gate classifies.

    HAND_WIRED_SUT      — step bodies that construct SUT-collaborator types inline
                          (``repo = InMemoryRepo()``;
                          ``svc = OrderService(repo, FakeClock(), ...)``) instead
                          of reaching a composition-root entry. The gate MUST flag
                          it and name the offending step + the collaborator type
                          (the recall half).
    COMPOSITION_ROOT    — a step suite that builds the SUT through a production
                          composition-root entry call (``app = build_application()``
                          / ``compose_root()``) and drives it, carrying the
                          precision near-misses (a domain VALUE-OBJECT construction
                          that is NOT a SUT collaborator; an attribute read on the
                          composed app). The gate MUST NOT flag it (the precision
                          half — the slice-09 learning-hypothesis guard).
    """

    HAND_WIRED_SUT = "hand_wired_sut"
    COMPOSITION_ROOT = "composition_root"


class CompositionOutcome(Enum):
    """The port-exposed verdict the gate returns for a corpus.

    FLAGGED — at least one step body hand-wires the SUT's collaborator graph.
    CLEAN   — every step body builds the SUT through a composition-root entry call
              (or constructs no SUT collaborator); no breach found.
    """

    FLAGGED = "flagged"
    CLEAN = "clean"


class CompositionBreachKind(Enum):
    """The kind of P3 composition-root breach the verdict names.

    HAND_WIRED_SUT_IN_STEP_BODY — a step body constructs one or more known
        SUT-collaborator types inline (``InMemoryRepo`` / ``FakeClock`` /
        ``OrderService``) with no production composition-root entry call present,
        assembling the application's object graph by hand where the production
        composition root belongs (Pillar 3).
    """

    HAND_WIRED_SUT_IN_STEP_BODY = HAND_WIRED_SUT_IN_STEP_BODY_BREACH


# --- canonical slice-09 fixtures of record ---------------------------------

_COMPOSITION_ROOT_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "composition_root"
)

# The hand-wired-SUT corpus + the exact (step, constructed-type) breach it carries
# — the gate MUST name the offending step + the collaborator type it assembles so a
# regression is pinpointed (recall half).
HAND_WIRED_CORPUS: Path = (
    _COMPOSITION_ROOT_FIXTURES_DIR / "violation_step_hand_wires_sut.py"
)
EXPECTED_HAND_WIRED_STEP: CompositionStepName = CompositionStepName(
    "when_the_customer_submits_the_order"
)
EXPECTED_HAND_WIRED_TYPE: CompositionConstructedType = CompositionConstructedType(
    "OrderService"
)

# The clean corpus the gate must pass (carrying the value-object + composed-app
# read near-miss traps) — the precision-half / learning-hypothesis guard.
COMPOSITION_ROOT_CLEAN_CORPUS: Path = (
    _COMPOSITION_ROOT_FIXTURES_DIR / "clean_step_uses_composition_root.py"
)


# ---------------------------------------------------------------------------
# slice-11 vocabulary — the Tier-M golden-fixture-completeness meta-gate.
#
# The meta-gate is the Earned-Trust self-application: every shipped Tier-S gate
# must carry its OWN golden fixtures + a self-AT, or it is untrustworthy. The
# domain nouns:
#
#   * a *gate under inspection* (one gate fixture dir + its sibling self-AT);
#   * its *completeness outcome* (complete vs incomplete) — the port-exposed
#     observable the meta-gate reports;
#   * the *kind* of gate corpus the meta-gate is asked to judge (the real
#     shipped gates, a planted-complete exemplar, a planted-incomplete orphan).
# ---------------------------------------------------------------------------


class GateCorpusKind(Enum):
    """Which gate corpus the meta-gate is asked to judge for golden coverage.

    REAL_SHIPPED        — the 9 real Tier-S gates under the feature's
                          ``acceptance/fixtures/`` tree (all complete on disk).
    PLANTED_COMPLETE    — a synthetic gate carrying its full golden triad
                          (precision control: meta-gate must clear it).
    PLANTED_INCOMPLETE  — a synthetic gate missing part of its triad
                          (recall target: meta-gate must flag it).
    """

    REAL_SHIPPED = "real_shipped"
    PLANTED_COMPLETE = "planted_complete"
    PLANTED_INCOMPLETE = "planted_incomplete"


class GateCompletenessOutcome(Enum):
    """The port-exposed verdict the meta-gate reports for one inspected gate."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


# Canonical locations the meta-gate composition walks. The real fixtures tree is
# the SSOT for "which gates shipped" (NOT the production rule modules, NOT
# ``capabilities.py`` — the meta-gate consumes no capability).
_ACCEPTANCE_DIR: Path = Path(__file__).resolve().parent.parent
META_REAL_FIXTURES_DIR: Path = _ACCEPTANCE_DIR / "fixtures"

# Planted recall + precision corpus (off the real fixtures tree, under
# ``tests/build/_meta_gate_fixtures/``, so the meta-gate never enumerates its
# own planted corpus as a real shipped gate).
_META_FIXTURES_ROOT: Path = Path(__file__).resolve().parents[3] / "_meta_gate_fixtures"
META_COMPLETE_ACCEPTANCE: Path = _META_FIXTURES_ROOT / "complete_gate" / "acceptance"
META_INCOMPLETE_ACCEPTANCE: Path = (
    _META_FIXTURES_ROOT / "incomplete_gate" / "acceptance"
)


# ===========================================================================
# slice-12 vocabulary — the drift-guard conformance gate (@component)
# ===========================================================================
#
# The domain nouns of the drift-guard self-conformance contract (ADR-TEST-002
# D-C/D-E, Earned-Trust self-application; feature-delta slice-plan row 229):
#
#   * a *rule classification set* under audit — a set a gate-rule references to
#     decide which ``Layer`` values it applies at (``PBT_FORBIDDEN_LAYERS``,
#     ``AUDITED_LAYERS``);
#   * a *producible layer value* — a ``Layer`` value the reference adapter can
#     actually emit (present in ``_SEGMENT_TO_LAYER.values()``);
#   * a *registered capability* — a ``Capability`` enum member;
#   * a *realized capability* — one with a backing method on the REAL adapter;
#   * a *conformance verdict* (conformant vs flagged) — the port-exposed
#     observable when the testarch substrate is checked against itself;
#   * the *breach kind* the verdict names — a layer value a rule references that
#     the adapter cannot produce, or a registered capability the real adapter
#     does not realize;
#   * the named offenders: the non-producible layer value (and the set that
#     references it), the unrealized registered capability.
#
# The gate reads the testarch package's OWN rule classification sets + the real
# adapter's method surface as DATA (a self-conformance check of this package's
# vocabulary, NOT a Tier-S AST rule over foreign source — so it imports
# ``capabilities`` + ``adapters.python_ast`` + the rule modules to introspect; the
# ADR-TEST-002 D-A no-``import ast`` constraint binds the Tier-S source-scanning
# rules, not this self-conformance gate).


class ConformanceCorpusKind(Enum):
    """Which corpus the drift-guard gate is asked to classify (D-E recall/precision).

    DRIFTED_SNAPSHOT — the FROZEN golden-fixture snapshot that PERMANENTLY carries
                       both drift facets (a non-producible layer reference + a
                       registered-but-unrealized capability). The gate MUST flag it
                       and name both offenders (the recall half — green forever,
                       proving the gate CAN bite).
    LIVE_SUBSTRATE   — the LIVE production surface read at runtime (the actual rule
                       classification sets + reference-adapter producible layers +
                       registered ``Capability`` values + real ``PythonAstAdapter``
                       method surface). The gate MUST clear it (the precision half).
                       RED NOW (live carries ``fs_acceptance`` + the dead caps),
                       GREEN after A_GREEN drops them — the scenario the drops flip
                       RED→GREEN.
    """

    DRIFTED_SNAPSHOT = "drifted_snapshot"
    LIVE_SUBSTRATE = "live_substrate"


class ConformanceOutcomeKind(Enum):
    """The port-exposed verdict the drift-guard gate returns for a dimension.

    FLAGGED    — at least one referenced layer value is non-producible, OR at
                 least one registered capability is unrealized on the real adapter.
    CONFORMANT — every referenced layer value is adapter-producible AND every
                 registered capability is realized on the real adapter; no breach.
    """

    FLAGGED = "flagged"
    CONFORMANT = "conformant"


class ConformanceBreachKind(Enum):
    """The kind of drift-guard conformance breach the verdict names.

    LAYER_VALUE_NOT_ADAPTER_PRODUCIBLE — a rule classification set references a
        ``Layer`` value the reference adapter never emits (unreachable-by-
        construction classification).
    CAPABILITY_NOT_REALIZED_ON_REAL_ADAPTER — a registered ``Capability`` has no
        backing method on the production ``PythonAstAdapter`` (method-name-blind
        for production: green against the fixture, non-conformant in production).
    """

    LAYER_VALUE_NOT_ADAPTER_PRODUCIBLE = "layer_value_not_adapter_producible"
    CAPABILITY_NOT_REALIZED_ON_REAL_ADAPTER = "capability_not_realized_on_real_adapter"


# --- canonical slice-12 RECALL expectations (frozen fixture, green forever) -
#
# The drifted snapshot fixture permanently carries both facets and is the SSOT for
# the planted-offender values the recall scenario pins (the EXACT offender each
# detector must name, not just "flagged"). The step file imports
# ``PLANTED_NON_PRODUCIBLE_LAYER_VALUE`` + ``PLANTED_UNREALIZED_CAPABILITY`` directly
# from ``fixtures/registry_conformance/violation_drifted_snapshot.py`` — the fixture
# is the one source, so they are NOT duplicated here.


# --- canonical slice-12 PRECISION facts of record --------------------------
#
# The live substrate is RED NOW because it carries this exact drift; A_GREEN drops
# both so the precision scenario flips RED→GREEN. These are NOT asserted directly
# (the precision scenario asserts CONFORMANT — zero violations); they document the
# RED-now cause + the A_GREEN target. The same recall→precision shape every Tier-S
# gate's golden fixtures encode, here applied to the substrate itself.

# The non-producible ``Layer.value`` the two LIVE rule sets reference but the
# reference adapter never emits (``acceptance`` segments map to
# ``IN_MEMORY_ACCEPTANCE``). A_GREEN drops it → precision scenario GREEN.
LIVE_DRIFT_NON_PRODUCIBLE_LAYER_VALUE: str = "fs_acceptance"

# The two registered-but-unrealized ``Capability.value`` strings in the LIVE enum —
# members with no backing ``PythonAstAdapter`` method and no consuming rule (dead).
# A_GREEN removes them → precision scenario GREEN.
LIVE_DRIFT_UNREALIZED_CAPABILITY_VALUES: frozenset[str] = frozenset(
    {"string_literals_in_call", "parametrize_arg_source"}
)
