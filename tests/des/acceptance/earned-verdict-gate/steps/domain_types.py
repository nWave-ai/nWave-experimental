"""Domain types for the oss-earned-verdict-gate acceptance slices.

Mandate-12 criterion 1 (ATDD SSOT via types): every domain noun used in the
Gherkin is expressed once here as a typed enum / NewType. Step bodies and the
composition service consume these typed parameters -- no raw ``str`` where a
domain enum exists.

CONTRACT SOURCE: the enums below mirror the two cross-tree FROZEN contracts
``nWave/schemas/nwave.test_result.v1.schema.json`` (the RUN result, input to
the CORE) and ``nWave/schemas/nwave.earned_verdict.v1.schema.json`` (the
VERDICT, output of the CORE). The frozen ``status`` and ``reason`` closed enums
are reproduced verbatim; the deterministic rule that maps two RUN results onto
a VERDICT lives in the production CORE only (never the LLM, never this module).

target-blind: NONE of these types names a language or a test runner literal.
``runner`` is carried opaquely on the RUN envelope (it is a frozen field of
``nwave.test_result.v1``), but the CORE's verdict computation never branches on
it -- the CORE operates on the counts + exit code alone.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A node identifier for the acceptance test under perturbation (frozen field
# ``at_id`` of ``nwave.earned_verdict.v1``). Opaque to the CORE.
AtId = NewType("AtId", str)

# The named dependency broken at the seam (frozen field ``seam_id`` of
# ``nwave.earned_verdict.v1``). Opaque to the CORE in slice-01 (no injection
# yet); carried through onto the emitted verdict envelope.
SeamId = NewType("SeamId", str)


class VerdictStatus(str, Enum):
    """The frozen ``status`` closed enum of ``nwave.earned_verdict.v1``.

    GREEN  -- the perturbation flipped the run: theater is disproven, the AT is
              causally bound to the thing it asserts (reason=verdict-flipped).
    RED    -- the perturbation did NOT flip the run: the AT held green against
              broken code, i.e. it is theater (reason=theater-held).
    ABSTAIN -- the CORE cannot make a trustworthy judgement (baseline not
              green, no nameable seam, runner absent) -- fail-safe, never a
              false GREEN nor a false RED.
    """

    GREEN = "GREEN"
    RED = "RED"
    ABSTAIN = "ABSTAIN"


class VerdictReason(str, Enum):
    """The frozen ``reason`` closed enum of ``nwave.earned_verdict.v1``."""

    VERDICT_FLIPPED = "verdict-flipped"
    THEATER_HELD = "theater-held"
    NO_NAMEABLE_SEAM = "no-nameable-seam"
    RUNNER_ABSENT = "runner-absent"
    BASELINE_NOT_GREEN = "baseline-not-green"


class RunHealth(str, Enum):
    """The condition a single ``nwave.test_result.v1`` run is in.

    A domain shorthand the Gherkin uses to name a baseline/perturbed run by its
    observable shape, instead of spelling out raw counts in the scenario prose
    (Pillar 1). Each value maps via ``RUN_SHAPE_BY_HEALTH`` to a concrete
    ``RunShape`` the composition stages into a ``test_result.v1`` envelope.

    GREEN          -- passed>0, failed==0, exit_code==0  (a healthy run).
    FAILED         -- failed>0                            (a run that failed).
    NONZERO_EXIT   -- failed==0 but exit_code!=0          (the run errored at
                      the process level without a counted failure -- e.g. a
                      collection error, a crashed runner).
    NOTHING_PASSED -- passed==0, failed==0                (vacuous: nothing ran
                      green, the canonical baseline-not-green bug magnet).
    """

    GREEN = "green"
    FAILED = "failed"
    NONZERO_EXIT = "errored with a nonzero exit code"
    NOTHING_PASSED = "vacuous with nothing passing"


class RunShape:
    """A concrete count/exit tuple for one ``nwave.test_result.v1`` run.

    Captures exactly the fields the CORE's deterministic rule reads
    (``passed``, ``failed``, ``exit_code``). The remaining frozen fields
    (``collected``, ``xfailed``, ``xpassed``, ``skipped``, ``deselected``,
    ``error``, ``runner``) are filled with neutral defaults by the composition
    -- the CORE never branches on them.
    """

    __slots__ = ("exit_code", "failed", "passed")

    def __init__(self, passed: int, failed: int, exit_code: int) -> None:
        self.passed = passed
        self.failed = failed
        self.exit_code = exit_code


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12: the DSL emerges from typed concepts. Each Gherkin literal maps to
# a typed value here; the parameterized step templates in ``common_steps.py``
# do a single dict lookup, never an ``if``-ladder.

# Each ``RunHealth`` maps to the canonical ``RunShape`` the composition stages.
# GREEN baseline uses passed=3 (a plural healthy run). FAILED carries one
# counted failure. NONZERO_EXIT keeps failed==0 but exit_code=2 (process-level
# error with no counted failure -- the OR branch of the GREEN rule). The two
# baseline-not-green witnesses are FAILED (failed>0) and NOTHING_PASSED
# (passed==0).
RUN_SHAPE_BY_HEALTH: dict[str, RunShape] = {
    RunHealth.GREEN.value: RunShape(passed=3, failed=0, exit_code=0),
    RunHealth.FAILED.value: RunShape(passed=2, failed=1, exit_code=1),
    RunHealth.NONZERO_EXIT.value: RunShape(passed=0, failed=0, exit_code=2),
    RunHealth.NOTHING_PASSED.value: RunShape(passed=0, failed=0, exit_code=0),
}

STATUS_BY_PHRASE: dict[str, VerdictStatus] = {s.value: s for s in VerdictStatus}

REASON_BY_PHRASE: dict[str, VerdictReason] = {r.value: r for r in VerdictReason}


# --- slice-02 (TestRunnerPort) domain types -----------------------------------
# The TestRunnerPort runs a real test target and emits a `nwave.test_result.v1`.
# A "target" is named by its observable run shape (Pillar 1): all-passing, or
# carrying a failing test, or one whose runner cannot be invoked at all.


class TargetHealth(str, Enum):
    """The condition a staged test TARGET is in, named by its observable run.

    A domain shorthand the slice-02 Gherkin uses to name the target the
    TestRunnerPort runs, instead of spelling out the staged test bodies in the
    scenario prose (Pillar 1). The composition stages a real pytest target on a
    tmp path for each value.

    ALL_PASS      -- the staged target's tests all pass (a faithful green run:
                     passed>0, failed==0, exit_code==0).
    HAS_FAILURE   -- the staged target carries at least one failing test
                     (failed>0, nonzero exit -- the proof counts come from the
                     RUN, not a hard-coded green template).
    RUNNER_ABSENT -- the runner named for the target cannot be invoked (R-1:
                     the port must abstain, never fabricate a green run).
    """

    ALL_PASS = "all pass"
    HAS_FAILURE = "at least one failing test"
    RUNNER_ABSENT = "cannot be invoked"


TARGET_HEALTH_BY_PHRASE: dict[str, TargetHealth] = {t.value: t for t in TargetHealth}


# --- slice-03 (SeamInjectionPort) domain types --------------------------------
# The SeamInjectionPort reads NWAVE_PERTURB=<seam-id> and swaps the named
# dependency at the seam in a generated AT scaffold. A scaffold exposes one or
# more NAMED seams; injection resolves a named seam to a fault implementation
# instead of the real one. A seam name the scaffold cannot resolve -> ABSTAIN
# reason=no-nameable-seam.
#
# SWAP MECHANISM (design note, FLAGGED for orchestrator): the feature-delta
# specifies the BEHAVIOUR ("swaps the named dependency at the seam") but not the
# MECHANISM. The seam model below is the minimal observable contract the ATs
# need -- a named-seam registry whose post-injection resolution is observable --
# and is deliberately mechanism-independent. DELIVER picks the concrete swap
# mechanism (monkeypatch / factory-lookup-by-name / DI-registry override /
# conftest fixture override) once DESIGN confirms it. These domain types name
# the seam and its post-injection resolution, NOT the swap technique.

# A named seam in a generated AT scaffold (the dependency point NWAVE_PERTURB
# targets). Opaque to the verdict CORE; meaningful to the scaffold + the
# injection port.
SeamName = NewType("SeamName", str)

# The implementation a seam resolves to after the port has (or has not) acted.
DepImpl = NewType("DepImpl", str)


class InjectionOutcome(str, Enum):
    """The observable outcome of one ``SeamInjectionPort`` invocation.

    PERTURBED -- the named seam was nameable and resolvable; after injection the
                 seam resolves to the FAULT implementation (the swap took
                 effect -- the dependency the scaffold depends on is now broken).
    ABSTAIN   -- the seam name is not nameable/resolvable in the scaffold; the
                 port abstains (reason=no-nameable-seam), never silently
                 leaving the real dependency in place while reporting success.
    """

    PERTURBED = "perturbed"
    ABSTAIN = "abstain"


INJECTION_OUTCOME_BY_PHRASE: dict[str, InjectionOutcome] = {
    o.value: o for o in InjectionOutcome
}


# --- slice-04 (PreToolUse commit gate + self-test) domain types ---------------
# The installed PreToolUse hook fires on a `git commit`. For each GREEN AT in the
# slice being committed it perturbs the AT and demands the verdict flip; an AT
# whose verdict is theater-held (RED) denies the commit. The SELF-TEST perturbs
# the CORE itself and demands the gate's OWN verdict flips RED.


class SliceHealth(str, Enum):
    """The honesty of the slice's ATs as the commit gate sees them.

    ALL_EARNED -- every GREEN AT in the slice flips when its dependency is
                  broken (each verdict GREEN/verdict-flipped) -- the commit is
                  allowed.
    HAS_THEATER -- at least one GREEN AT holds green against broken code (a
                  verdict RED/theater-held) -- the commit is denied.
    """

    ALL_EARNED = "all earned"
    HAS_THEATER = "a theater AT"


class CommitGateDecision(str, Enum):
    """The observable PreToolUse decision on a ``git commit``.

    ALLOWED -- the gate permits the commit (no theater AT in the slice).
    DENIED  -- the gate blocks the commit via ``permissionDecision:deny`` /
               ``{decision:block}`` (a theater AT, or the self-test, flipped
               the verdict to RED).
    """

    ALLOWED = "allowed"
    DENIED = "denied"


SLICE_HEALTH_BY_PHRASE: dict[str, SliceHealth] = {s.value: s for s in SliceHealth}

COMMIT_DECISION_BY_PHRASE: dict[str, CommitGateDecision] = {
    d.value: d for d in CommitGateDecision
}
