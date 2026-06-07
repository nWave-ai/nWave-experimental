"""Domain types for the walking-skeleton-production-like-gate acceptance suite.

Mandate-12 criterion 1: every domain noun used in the Gherkin of the seven
slice `.feature` files is expressed once here as a typed enum or NewType. Step
bodies and the per-slice composition services consume these typed parameters --
no raw `str` where a domain enum exists.

The feature implements RCA root-cause A: a feature-end gate that runs the
feature's `@walking-skeleton @wiring_e2e` AT against the *delivered artifact*
installed into a clean prefix, at the highest provisionable environment tier,
and fail-closes (via a deferral marker) when no tier is provisionable.

Shared vocabulary contract (Mandate 10): the same step-method names are used
across all seven slice step files; the types below are the single SSOT for the
parameters those step methods accept.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-installer-private-skill-leak").
FeatureId = NewType("FeatureId", str)

# A slice identifier as carried by a `Slice-Id:` commit trailer (e.g. "slice-01").
SliceId = NewType("SliceId", str)

# A SHA-256 content hash of the built artifact, "sha256:..." form.
ArtifactHash = NewType("ArtifactHash", str)


# --- Tier ladder (DESIGN: Tiered Gate Architecture) --------------------------


class Tier(str, Enum):
    """The fidelity level at which the walking-skeleton AT runs.

    T0  -- `src/` tree; the proxy form. NOT a walking skeleton (D6 facet-1).
    T1  -- delivered artifact installed into a clean prefix via
           `pip install --target`. Mandatory floor; catches the F-11 class.
    T2  -- delivered artifact in a clean container image. Ceiling; Docker only.
    T3  -- artifact on real staging/prod. Explicitly out of scope.
    """

    T0 = "t0"
    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class TierCapability(str, Enum):
    """What the `EnvironmentProbe` reports the host can provision.

    NONE        -- not even T1: no writable tmp / no pip / build incapable.
    PIP_ONLY    -- Python+pip work, no Docker -- T1 is the ceiling.
    DOCKER      -- Docker reachable (`docker info` exit 0) -- T2 reachable,
                   T1 still run first as the prerequisite floor.
    """

    NONE = "none"
    PIP_ONLY = "pip_only"
    DOCKER = "docker"


class GateVerdict(str, Enum):
    """The user-observable verdict of the walking-skeleton gate.

    PASS            -- the AT ran green at the tier of record;
                       a `WalkingSkeletonTierVerified` record was written.
    FAIL            -- the AT ran red, OR a `@walking-skeleton` AT is absent
                       for an installer-shipped feature, OR a D6 facet was
                       violated, OR a zero-subprocess `@walking-skeleton` AT.
    NOT_APPLICABLE  -- the feature ships no installer-shipped artifact;
                       a `WalkingSkeletonNotApplicable` record was written.
    UNVERIFIED      -- no provisionable tier; a deferral marker was written.
    """

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"


# Gate CLI exit codes (DESIGN: CLI contract).
class ExitCode(int, Enum):
    OK = 0  # PASS or NOT_APPLICABLE
    FAIL = 1  # AT red / missing AT / facet violation
    USAGE = 2  # malformed input
    UNVERIFIED = 3  # no provisionable tier; marker written


# --- D6 three-facet disqualification (DESIGN) --------------------------------


class FacetResult(str, Enum):
    """The outcome of one of the three D6 mechanical facet checks."""

    OK = "ok"
    VIOLATION = "violation"
    NOT_CHECKED = "not_checked"


class FacetViolationKind(str, Enum):
    """The specific D6 facet a `@walking-skeleton` AT failed.

    FACET1_ENTRY_POINT_ABSENT  -- an entry point the AT invokes does not
                                  physically resolve within the staged prefix
                                  (the F-11 script-mode class). B2 fix.
    FACET1_RESOLVED_OUTSIDE    -- `des.__file__` resolves OUTSIDE the staged
                                  prefix at AT runtime (src/-shadowed import).
    FACET2_NO_SUBPROCESS       -- a `@walking-skeleton` AT with zero subprocess
                                  invocation of the installed entry point.
    FACET3_NO_TRANSFORM        -- the staged tree lacks the build-transform
                                  signature (a `from src.des` import survived,
                                  or the file set is a superset of the
                                  whitelist-projection). B1 fix.
    """

    FACET1_ENTRY_POINT_ABSENT = "facet-1-violation:entry-point-absent"
    FACET1_RESOLVED_OUTSIDE = "facet-1-violation:resolved-outside-prefix"
    FACET2_NO_SUBPROCESS = "facet-2-violation:no-subprocess"
    FACET3_NO_TRANSFORM = "facet-3-violation:no-transform-signature"


# --- Fail-mode D — deferral marker (DESIGN) ----------------------------------


class DeferralReason(str, Enum):
    """The closed `reason` enum carried by the deferral marker.

    A free-prose reason is forbidden -- D4 ("never a silent prose pass")
    applies to the marker's own fields. RM-6 extends the enum with the
    fixture-failure classifications.
    """

    NO_PROVISIONABLE_TIER = "no-provisionable-tier"
    BUILD_FAILED = "build-failed"
    NO_WRITABLE_PREFIX = "no-writable-prefix"
    PREFIX_NOEXEC = "prefix-noexec"
    DISK_EXHAUSTED = "disk-exhausted"
    PREFIX_NOT_CLEAN = "prefix-not-clean"
    FIXTURE_INTERNAL_ERROR = "fixture-internal-error"
    MARKER_WRITE_FAILED = "marker-write-failed"


class MarkerKind(str, Enum):
    """The two parametrised variants of the `DeferralMarker` file.

    UNVERIFIED  -- `.nwave/markers/walking-skeleton-unverified/{feature}.json`;
                   fail-mode D; blocks "feature done".
    TIER_DEBT   -- `.nwave/markers/walking-skeleton-tier-debt/{feature}.json`;
                   RM-4; T1-only on an OS-sensitive feature; NOT a block.
    """

    UNVERIFIED = "walking-skeleton-unverified"
    TIER_DEBT = "walking-skeleton-tier-debt"


class MarkerReadState(str, Enum):
    """What the done-gate sees when it reads the marker directory.

    ABSENT       -- no marker file for the feature.
    PRESENT      -- a well-formed marker is present.
    UNPARSEABLE  -- a malformed / empty / unknown-`schema_version` marker;
                    the done-gate treats this as a BLOCK (RM-3 ST-20).
    """

    ABSENT = "absent"
    PRESENT = "present"
    UNPARSEABLE = "unparseable"


# --- AT-completion ledger record types (DESIGN: Reuse — AtCompletionLedger) --


class LedgerRecordType(str, Enum):
    """The five new ledger record types the gate appends (RM-1, RM-3, B3).

    GATE_RAN          -- `WalkingSkeletonGateRan` heartbeat (RM-1); emitted
                         BEFORE the verdict. Absence => integrity FAIL.
    TIER_VERIFIED     -- `WalkingSkeletonTierVerified` positive proof (RM-3);
                         the done-gate's trust anchor.
    NOT_APPLICABLE    -- `WalkingSkeletonNotApplicable` (B3); names paths
                         checked + why none matched the predicate.
    APPLICABILITY     -- `WalkingSkeletonApplicability` (B3); the SSOT
                         installer-shipped predicate, written by the carpaccio
                         entry-gate, consumed by the feature-end gate.
    DEFERRED          -- `WalkingSkeletonDeferred`; records the fail-mode-D
                         deferral event.
    """

    GATE_RAN = "WalkingSkeletonGateRan"
    TIER_VERIFIED = "WalkingSkeletonTierVerified"
    NOT_APPLICABLE = "WalkingSkeletonNotApplicable"
    APPLICABILITY = "WalkingSkeletonApplicability"
    DEFERRED = "WalkingSkeletonDeferred"


# --- Feature shape — the installer-shipped predicate (B3) --------------------


class FeatureArtifactShape(str, Enum):
    """Whether a feature ships an installer-distributed artifact.

    SHIPS_CLI        -- `files_to_modify` touch `src/des/cli/` -- a packaged
                        `des.cli.*` module.
    SHIPS_HOOK       -- touches a hook module.
    SHIPS_SCRIPT_CLI -- touches `scripts/cli/` -- the F-11 script-mode path
                        (only shipped if whitelisted in `UTILITY_SCRIPTS`).
    SHIPS_INSTALLER  -- touches `scripts/install/`.
    DOCS_ONLY        -- touches no installer-shipped path; the gate records
                        NOT_APPLICABLE.
    """

    SHIPS_CLI = "ships_cli"
    SHIPS_HOOK = "ships_hook"
    SHIPS_SCRIPT_CLI = "ships_script_cli"
    SHIPS_INSTALLER = "ships_installer"
    DOCS_ONLY = "docs_only"


class OsSensitivity(str, Enum):
    """Whether a feature's correctness depends on OS-level fidelity (RM-4).

    OS_SENSITIVE  -- touches paths, file modes, subprocess, or native deps;
                     a T1-only run leaves an OS-fidelity gap -> tier-debt.
    OS_NEUTRAL    -- pure-logic feature; a T1-only run owes no T2 debt.
    """

    OS_SENSITIVE = "os_sensitive"
    OS_NEUTRAL = "os_neutral"


# --- Distribution-completeness arch test (US-04) -----------------------------


class DistributionVerdict(str, Enum):
    """The verdict of one `DistributionCompleteness` assertion (US-04).

    SHIPPED_AND_WIRED  -- the hook-invoked CLI is in the shipped set and is
                          exercised by >=1 `@wiring_e2e` test.
    ABSENT_FROM_SHIP   -- the CLI is hook-invoked but absent from the shipped
                          set (the direct F-11 catch).
    SHIPPED_UNWIRED    -- the CLI ships but no `@wiring_e2e` test exercises it.
    """

    SHIPPED_AND_WIRED = "shipped_and_wired"
    ABSENT_FROM_SHIP = "absent_from_ship"
    SHIPPED_UNWIRED = "shipped_unwired"


# --- Hook-exit contract (RM-1) -----------------------------------------------


class HookSubprocessOutcome(str, Enum):
    """How the feature-end `SubagentStop` branch sees the gate subprocess exit.

    EXIT_ZERO     -- the gate subprocess exited 0.
    EXIT_NONZERO  -- the gate subprocess exited non-zero.
    EXIT_ABSENT   -- no exit at all (CLI not shipped, swallowed
                     ModuleNotFoundError, empty argv) -- treated as FAIL.
    TIMEOUT       -- Claude Code killed the hook -- treated as UNVERIFIED,
                     deferral marker written.
    """

    EXIT_ZERO = "exit_zero"
    EXIT_NONZERO = "exit_nonzero"
    EXIT_ABSENT = "exit_absent"
    TIMEOUT = "timeout"


# --- Gherkin-phrase -> typed-value lookups -----------------------------------
# Module-level dicts keep each step body a single typed lookup + a single
# composition call (Mandate-12 criterion 3: no control flow in step bodies).

TIER_CAPABILITY_BY_PHRASE: dict[str, TierCapability] = {
    "no provisionable environment": TierCapability.NONE,
    "only Python and pip": TierCapability.PIP_ONLY,
    "Docker available": TierCapability.DOCKER,
}

TIER_BY_PHRASE: dict[str, Tier] = {
    "T1": Tier.T1,
    "T2": Tier.T2,
}

VERDICT_BY_PHRASE: dict[str, GateVerdict] = {
    "PASS": GateVerdict.PASS,
    "FAIL": GateVerdict.FAIL,
    "NOT_APPLICABLE": GateVerdict.NOT_APPLICABLE,
    "UNVERIFIED": GateVerdict.UNVERIFIED,
    "passes": GateVerdict.PASS,
    "fails": GateVerdict.FAIL,
}

FEATURE_SHAPE_BY_PHRASE: dict[str, FeatureArtifactShape] = {
    "ships a packaged CLI module": FeatureArtifactShape.SHIPS_CLI,
    "ships a hook": FeatureArtifactShape.SHIPS_HOOK,
    "ships a script-mode CLI": FeatureArtifactShape.SHIPS_SCRIPT_CLI,
    "ships an installer change": FeatureArtifactShape.SHIPS_INSTALLER,
    "ships only documentation": FeatureArtifactShape.DOCS_ONLY,
}

OS_SENSITIVITY_BY_PHRASE: dict[str, OsSensitivity] = {
    "OS-sensitive": OsSensitivity.OS_SENSITIVE,
    "OS-neutral": OsSensitivity.OS_NEUTRAL,
}

FACET_VIOLATION_BY_PHRASE: dict[str, FacetViolationKind] = {
    "an entry point absent from the installed tree": (
        FacetViolationKind.FACET1_ENTRY_POINT_ABSENT
    ),
    "a subject resolved outside the installed prefix": (
        FacetViolationKind.FACET1_RESOLVED_OUTSIDE
    ),
    "no real entry-point invocation": FacetViolationKind.FACET2_NO_SUBPROCESS,
    "a tree missing the build-transform signature": (
        FacetViolationKind.FACET3_NO_TRANSFORM
    ),
}

DEFERRAL_REASON_BY_PHRASE: dict[str, DeferralReason] = {
    "no environment can be provisioned": DeferralReason.NO_PROVISIONABLE_TIER,
    "the artifact build fails": DeferralReason.BUILD_FAILED,
    "the install prefix is not writable": DeferralReason.NO_WRITABLE_PREFIX,
    "the install prefix forbids execution": DeferralReason.PREFIX_NOEXEC,
    "the disk is exhausted": DeferralReason.DISK_EXHAUSTED,
    "the install prefix is not clean": DeferralReason.PREFIX_NOT_CLEAN,
    "the marker cannot be written": DeferralReason.MARKER_WRITE_FAILED,
}

MARKER_STATE_BY_PHRASE: dict[str, MarkerReadState] = {
    "an unverified marker": MarkerReadState.PRESENT,
    "no marker": MarkerReadState.ABSENT,
    "an unparseable marker": MarkerReadState.UNPARSEABLE,
}

HOOK_OUTCOME_BY_PHRASE: dict[str, HookSubprocessOutcome] = {
    "exits non-zero": HookSubprocessOutcome.EXIT_NONZERO,
    "never exits": HookSubprocessOutcome.EXIT_ABSENT,
    "times out": HookSubprocessOutcome.TIMEOUT,
}


# --- Authoring-side propagation (DESIGN slices 08-09 -> carpaccio 15-16) ------


class AuthoringArtifact(str, Enum):
    """An authoring artifact the tiered walking-skeleton discipline propagates into.

    TEST_DESIGN_SKILL  -- the `nw-test-design-mandates` skill: the T0/T1/T2
                          tier rows, the three D6 facets, the
                          `@walking-skeleton @wiring_e2e` tagging contract,
                          fail-mode-D deferral.
    DISTILL_COMMAND    -- the `/nw-distill` command guidance.
    AGENT_LOADING_TABLE -- an authoring agent's `Skill Loading Strategy` table
                          referencing the tier-discipline skill -- the
                          operative dispatch contract.
    """

    TEST_DESIGN_SKILL = "test_design_skill"
    DISTILL_COMMAND = "distill_command"
    AGENT_LOADING_TABLE = "agent_loading_table"


AUTHORING_ARTIFACT_BY_PHRASE: dict[str, AuthoringArtifact] = {
    "the test-design mandates": AuthoringArtifact.TEST_DESIGN_SKILL,
    "the distill command guidance": AuthoringArtifact.DISTILL_COMMAND,
    "an authoring agent's skill-loading table": AuthoringArtifact.AGENT_LOADING_TABLE,
    "the authoring agent's skill-loading table": AuthoringArtifact.AGENT_LOADING_TABLE,
    "every authoring agent's skill-loading table": AuthoringArtifact.AGENT_LOADING_TABLE,
}
