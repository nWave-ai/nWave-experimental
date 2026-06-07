"""Domain types for the fix-atdd-pure-common-audit-log-ssot slice-01 suite.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): every domain
noun used in the Gherkin is expressed once here as a typed enum / NewType /
frozen dataclass. Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

CONTRACT SOURCE: the SSOT for the common audit log is the new singleton-shape
``AtCompletionLedger(project_root)`` API at
``src/des/adapters/driven/logging/at_completion_ledger.py`` (slice-01
refactor target). The new audit substrate path is
``.nwave/audit/atdd-pure-events.jsonl``; the per-feature ban pattern is
``.nwave/telemetry/atdd-pure/*.jsonl`` (with the ``_archive`` subdirectory
exempt per design D5).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-atdd-pure-common-audit-log-ssot").
FeatureId = NewType("FeatureId", str)

# A slice identifier (e.g. "slice-01"). Empty-string for feature-scoped events.
SliceId = NewType("SliceId", str)

# A monotonic per-(feature_id, slice_id) dispatch counter (1, 2, 3, ...).
DispatchSeq = NewType("DispatchSeq", int)


class EventKind(str, Enum):
    """The atdd_pure spine event kinds the common audit log writer records.

    Each kind maps 1:1 to an existing ``append_*`` method on the singleton-
    shape ``AtCompletionLedger`` API. Slice-01 exercises three representative
    kinds; the full set is documented in design D2 (frozen schema 2.0.0).
    """

    CARPACCIO_GATE_CLEARED = "CarpaccioGateCleared"
    SLICE_COMMIT_VERIFIED = "SliceCommitVerified"
    WALKING_SKELETON_GATE_RAN = "WalkingSkeletonGateRan"
    # slice-02b additions: aggregate-reader feature-filter ATs seed an
    # environmental-e2e heartbeat to prove the env-e2e reader's filter works.
    ENVIRONMENTAL_E2E_GATE_RAN = "EnvironmentalE2eGateRan"


class ArchTestVerdict(str, Enum):
    """The two outcomes the per-feature ledger ban arch test can report.

    ``FAIL`` means the arch test detected a forbidden per-feature-path write
    (the SSOT ban gate fired). ``PASS`` means no forbidden caller exists in
    the scanned tree.
    """

    FAIL = "fail"
    PASS = "pass"


class ArchTestCallerScenario(str, Enum):
    """The three caller-shape scenarios the arch-test gate must classify.

    Each scenario describes the call-site shape the test seeds into a
    temporary source tree before invoking the arch test as a subprocess.
    """

    PER_FEATURE_PATTERN = "a caller that writes a path under the per-feature pattern"
    ARCHIVE_SUBDIRECTORY = "a caller that writes a path under the archive subdirectory"
    COMMON_AUDIT_LOG = "a caller that uses only the common audit log path"


# --- slice-02: caller-migration identifiers (paths used in parametrize) ------
# Mandate-12 criterion 1: every caller file the slice-02 migration covers is
# named here as a typed CallerId NewType. The parametrize matrix in
# `slice-02-caller-migration.feature` enumerates the eleven canonical caller
# paths; this NewType pins the type and prevents raw `str` drift in the
# composition root's dispatch table.
CallerId = NewType("CallerId", str)


class MigratedCallerId(str, Enum):
    """The eleven grep-verified caller files migrated by slice-02.

    Source: empirical `grep -rln "AtCompletionLedger(" src/ scripts/
    --include="*.py" | grep -v at_completion_ledger.py` on 2026-05-25 (the
    Atlas peer-review verified caller set, refined by the Phase-1 empirical
    read for the actual file path of conversion_planner).

    Each member maps to a production driving-port invocation in the
    composition root's dispatch table -- the eleven entries are the
    SSOT for what slice-02 must migrate. Adding or removing a caller
    requires editing this enum AND the dispatch table.
    """

    SUBAGENT_STOP_HANDLER = "src/des/adapters/drivers/hooks/subagent_stop_handler.py"
    REVERIFY_SLICE_COMMIT = "src/des/cli/reverify_slice_commit.py"
    VERIFY_DELIVER_INTEGRITY = "src/des/cli/verify_deliver_integrity.py"
    VERIFY_SLICE_COMMIT_COMPLETENESS = "src/des/cli/verify_slice_commit_completeness.py"
    WALKING_SKELETON_GATE = "src/des/cli/walking_skeleton_gate.py"
    CONVERSION_PLANNER = "src/des/domain/conversion_planner.py"
    COVERAGE_MAP_SIGNOFF_WRITER = (
        "src/des/adapters/driven/ledger/coverage_map_signoff_writer.py"
    )
    CARPACCIO_INTERCEPT = "src/des/adapters/drivers/hooks/carpaccio_intercept.py"
    VERIFY_COVERAGE_MAP = "scripts/cli/verify_coverage_map.py"
    VERIFY_SLICE_LEDGER_RECORD = "scripts/hooks/verify_slice_ledger_record.py"
    AT_REVIEW_VERDICT = "scripts/cli/at_review_verdict.py"


CALLER_ID_BY_PATH: dict[str, MigratedCallerId] = {c.value: c for c in MigratedCallerId}


# --- slice-02b: aggregate-reader-method identifiers (parametrize over readers)
# Mandate-12 criterion 1: every aggregate reader the slice-02b filter cascade
# covers is named here as a typed enum. The parametrize matrix in
# `slice-02b-reader-feature-filter.feature` enumerates the FIVE readers that
# must accept the new `feature_id=` kw-only parameter; this enum pins the type
# and prevents raw `str` drift in the composition root's dispatch table.
#
# Source: empirical `grep -n "self.read_records()" src/des/adapters/driven/
# logging/at_completion_ledger.py` on 2026-05-25 -- the five aggregate readers
# that iterate read_records without a filter are verified_slices,
# feature_end_events, environmental_e2e_events, walking_skeleton_events, and
# coverage_map_touchpoint_events. M36 amendment #2 (cascade coverage gap):
# slice-02b ATs cover ALL FIVE readers, not three; the "lock-step" deferral
# for walking_skeleton_events + coverage_map_touchpoint_events created
# regression risk (a crafter could mechanically drop the kwarg on those two
# without any AT failing). Full five-reader parametrize-collapse closes the
# class.


class AggregateReaderMethod(str, Enum):
    """The aggregate reader methods slice-02b extends with a feature filter.

    Each member is the public method name on the singleton-shape
    ``AtCompletionLedger(project_root)`` API. The composition root dispatches
    on this enum to invoke the named reader; the parametrize matrix in the
    ``.feature`` file iterates over all five members (M36 amendment #2).
    """

    VERIFIED_SLICES = "verified_slices"
    FEATURE_END_EVENTS = "feature_end_events"
    ENVIRONMENTAL_E2E_EVENTS = "environmental_e2e_events"
    WALKING_SKELETON_EVENTS = "walking_skeleton_events"
    COVERAGE_MAP_TOUCHPOINT_EVENTS = "coverage_map_touchpoint_events"


READER_METHOD_BY_PHRASE: dict[str, AggregateReaderMethod] = {
    r.value: r for r in AggregateReaderMethod
}


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12 criterion 3: the DSL emerges from typed concepts. Each Gherkin
# literal maps to a typed enum here; the parameterized step templates in
# `common_steps.py` do a single dict lookup, never an `if`-ladder.

EVENT_KIND_BY_PHRASE: dict[str, EventKind] = {k.value: k for k in EventKind}

ARCH_VERDICT_BY_PHRASE: dict[str, ArchTestVerdict] = {
    v.value: v for v in ArchTestVerdict
}

ARCH_CALLER_SCENARIO_BY_PHRASE: dict[str, ArchTestCallerScenario] = {
    s.value: s for s in ArchTestCallerScenario
}


# --- slice-02c-A: gate-event affinity bundle (M51 + M58) ---------------------
# Per M51 H3 SUBSTRATE-AFFINITY decomposition (commit b5e647e1b): the
# gate-event affinity bundle migrates 6 production callsites in 3 files atomic
# with their fixture-fanout. The six callsites share substrate
# `AtCompletionLedger.append_gate_event` writer + `verified_slices()` reader
# (the affinity-A read-path identity).
#
# Mandate-12 criterion 1: every fully-qualified production callsite is named
# here as a typed enum member. The bare `A` token is FORBIDDEN per M56 HIGH-1
# substrate-naming mandate (every identifier in this bundle uses the
# `slice-02c-A` prefix). Per-callsite empirical line numbers verified by
# `grep -n "AtCompletionLedger(" src/` on 2026-05-25 (post-M51 dispatch).


class Slice02cAProductionCallsite(str, Enum):
    """The six gate-event-affinity production callsites Bundle A migrates.

    Each value is the `<relpath>:<lineno>` callsite identifier used as a stable
    parametrize id (the cascade-detector arch test already uses this format
    for its caller_id rows). Members are alphabetical by relpath then ascending
    by lineno -- deterministic across runs.

    Source: M51 amendment line 1085 (gate-event affinity bundle: N1+N2+N4+N5+N9).
    Empirical verification 2026-05-25:
      - subagent_stop_handler.py:529 (`_record_gate_event_to_ledger`, writer)
      - subagent_stop_handler.py:738 (`_resolve_shipped_slice_set`, `verified_slices()` reader)
      - carpaccio_intercept.py:217 (`_record_gate_event`)
      - carpaccio_intercept.py:322 (`_record_gate_event` cleanup path)
      - reverify_slice_commit.py:199 (`verified_slices()` reader)
      - reverify_slice_commit.py:452 (ledger writer)
    """

    CARPACCIO_INTERCEPT_L217 = (
        "src/des/adapters/drivers/hooks/carpaccio_intercept.py:217"
    )
    CARPACCIO_INTERCEPT_L322 = (
        "src/des/adapters/drivers/hooks/carpaccio_intercept.py:322"
    )
    REVERIFY_SLICE_COMMIT_L199 = "src/des/cli/reverify_slice_commit.py:199"
    REVERIFY_SLICE_COMMIT_L452 = "src/des/cli/reverify_slice_commit.py:452"
    SUBAGENT_STOP_HANDLER_L529 = (
        "src/des/adapters/drivers/hooks/subagent_stop_handler.py:529"
    )
    SUBAGENT_STOP_HANDLER_L738 = (
        "src/des/adapters/drivers/hooks/subagent_stop_handler.py:738"
    )


SLICE_02C_A_CALLSITE_BY_PHRASE: dict[str, Slice02cAProductionCallsite] = {
    c.value: c for c in Slice02cAProductionCallsite
}
