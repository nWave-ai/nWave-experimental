"""Domain types for the fix-oss-environmental-e2e-gate acceptance slices.

Mandate-12 criterion 1 (ATDD SSOT via types): every domain noun used in the
Gherkin is expressed once here as a typed enum / NewType. Step bodies and the
composition service consume these typed parameters -- no raw ``str`` where a
domain enum exists.

CONTRACT SOURCE: the enums below mirror the NORMATIVE-FROZEN L1.4 contract
(``docs/architecture/methodology/gate-family-implementation-2026-05-21.md``
section L1.4, v5) -- the single SSOT for the ``verify_environmental_e2e``
cross-tree contract. The feature-delta's pre-freeze spec diverges; L1.4 governs.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-oss-environmental-e2e-gate").
FeatureId = NewType("FeatureId", str)


class GateMode(str, Enum):
    """The five frozen ``--mode`` values of ``verify_environmental_e2e`` (L1.4)."""

    VERIFY_AUTHORED = "verify-authored"
    VERIFY_PRESENT = "verify-present"
    RUN = "run"
    VERIFY_MERGE_READY = "verify-merge-ready"
    AUDIT = "audit"


class GateVerdict(str, Enum):
    """The frozen stdout-token ``verdict`` closed enum (L1.4)."""

    PASS = "pass"
    FAIL = "fail"
    FLAKY = "flaky"
    BROKEN = "broken"
    MISSCOPED = "misscoped"
    XPASS_STALE = "xpass-stale"


class GateExit(int, Enum):
    """The four frozen exit codes, uniform across modes (L1.4)."""

    PASS = 0  # authored+genuine / present+genuine / verdict=pass stable / merge-ready
    CHECK_FAILED = (
        1  # fail / flaky / broken / stale-xfail-XPASS / JSON absent / xfail-still-on
    )
    PARSE_IO = 2  # parse/IO failure / marker not registered / build-install / hermeticity probe
    MISSCOPED = 3  # no `## Environmental E2E` block


class E2eSituation(str, Enum):
    """The condition the feature's environmental e2e is in for a ``run`` mode call.

    Maps each Scenario Outline ``situation`` literal onto a (verdict, exit) pair.
    """

    GREEN = "green against the installed artifact"
    RED = "red against the installed artifact"
    UNSTABLE = "unstable across reruns"
    UNCOLLECTABLE = "uncollectable at the declared path"
    NO_BLOCK = "declared on a feature with no environmental e2e block"


class FeatureEndRecord(str, Enum):
    """Feature-end ledger record types the done-gate and U4 enforcer check."""

    HEARTBEAT = "EnvironmentalE2eGateRan"
    VERIFIED = "EnvironmentalE2eVerified"


class LedgerRecords(str, Enum):
    """The four powerset cells of {HEARTBEAT, VERIFIED} the done-gate sweeps.

    Mandate-12 / Mandate 9 + 11: the done-gate decision table is finite (2^2
    cells). At layer 2 (in-memory acceptance) the universe-sweep is example-
    pinned via parametrize-collapse, one row per cell -- never PBT-generated.
    Each enum value maps via `LEDGER_RECORDS_BY_PHRASE` to the matching
    `frozenset[FeatureEndRecord]` the composition stages.
    """

    BOTH = "heartbeat+verified"
    HEARTBEAT_ONLY = "heartbeat only"
    VERIFIED_ONLY = "verified only"
    NONE = "none"


class DoneGateVerdict(str, Enum):
    """The closed verdict enum returned by the feature-end done-gate.

    One row per cell of the {HEARTBEAT, VERIFIED} powerset: the success row
    (`PERMITTED`) plus three named missing-record diagnostics. The diagnostic
    names which record(s) are absent -- not a generic boolean blocker -- so
    the AT asserts both the gate's go/no-go AND its diagnostic shape from the
    single port-exposed verdict token.
    """

    PERMITTED = "permitted"
    BLOCKED_MISSING_VERIFICATION = "blocked-missing-verification"
    BLOCKED_MISSING_HEARTBEAT = "blocked-missing-heartbeat"
    BLOCKED_MISSING_BOTH = "blocked-missing-both"


class GateRunFailCondition(str, Enum):
    """A way a `--mode run` gate invocation can fail to complete its proof.

    Both conditions are fail-closed: the gate must leave NO trusted positive
    verification record (a truncated record counts as absent), so the
    feature-end done-gate still blocks.

    NO_PREFIX    -- fail-mode D: no clean prefix can be provisioned.
    INTERRUPTED  -- C7b: the run is killed mid build-install before the
                    verdict; a truncated `EnvironmentalE2eVerified` record must
                    be treated as ABSENT, never as proof.
    """

    NO_PREFIX = "cannot provision any clean prefix to install into"
    INTERRUPTED = "is interrupted mid build-install before the verdict"


class GitState(str, Enum):
    """Whether the install environment has git available."""

    HAS = "has"
    LACKS = "lacks"


class Interactivity(str, Enum):
    """How the install runs -- governs whether the optional hook is offered."""

    INTERACTIVE = "interactively"
    NON_INTERACTIVE = "non-interactively"
    NO_GIT_HOOKS_OPT_OUT = "with the no-git-hooks opt-out"


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12: the DSL emerges from typed concepts. Each Gherkin literal maps to
# a typed enum here; the parameterized step templates in `common_steps.py` do a
# single dict lookup, never an `if`-ladder.

SITUATION_BY_PHRASE: dict[str, E2eSituation] = {s.value: s for s in E2eSituation}

VERDICT_BY_PHRASE: dict[str, GateVerdict] = {v.value: v for v in GateVerdict}

# The frozen L1.4 exit-code grid keyed by the human exit_meaning literal.
EXIT_BY_MEANING: dict[str, GateExit] = {
    "success": GateExit.PASS,
    "check failed": GateExit.CHECK_FAILED,
    "a parse or environment failure": GateExit.PARSE_IO,
    "mis-scoped": GateExit.MISSCOPED,
    "a mis-scoped feature": GateExit.MISSCOPED,
}

GIT_STATE_BY_PHRASE: dict[str, GitState] = {g.value: g for g in GitState}

INTERACTIVITY_BY_PHRASE: dict[str, Interactivity] = {i.value: i for i in Interactivity}

# Whether the optional git pre-push hook is offered, keyed by the Gherkin
# hook_outcome literal -- the offer-never-mandate decision table (slice-04).
HOOK_OFFERED_BY_OUTCOME: dict[str, bool] = {
    "offered": True,
    "not offered": False,
}

FAIL_CONDITION_BY_PHRASE: dict[str, GateRunFailCondition] = {
    c.value: c for c in GateRunFailCondition
}

# slice-02 powerset-sweep tables: each Gherkin `records` literal maps to the
# `frozenset[FeatureEndRecord]` the composition stages; each `verdict` literal
# maps to the typed `DoneGateVerdict` the done-gate returns.
LEDGER_RECORDS_BY_PHRASE: dict[str, frozenset[FeatureEndRecord]] = {
    LedgerRecords.BOTH.value: frozenset(
        {FeatureEndRecord.HEARTBEAT, FeatureEndRecord.VERIFIED}
    ),
    LedgerRecords.HEARTBEAT_ONLY.value: frozenset({FeatureEndRecord.HEARTBEAT}),
    LedgerRecords.VERIFIED_ONLY.value: frozenset({FeatureEndRecord.VERIFIED}),
    LedgerRecords.NONE.value: frozenset(),
}

DONE_GATE_VERDICT_BY_PHRASE: dict[str, DoneGateVerdict] = {
    v.value: v for v in DoneGateVerdict
}
