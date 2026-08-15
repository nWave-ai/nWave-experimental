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
#     decide which ``Layer`` values it applies at (``AUDITED_LAYERS``);
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
