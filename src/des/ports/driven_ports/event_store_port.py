"""EventStorePort -- the driving contract for the unified event store (D80).

Slice-02 absorbs BOTH the type declarations AND the adapter (carry-forward
finding, feature-delta.md [REF] Driving Ports): the Staging Plan assigned
"types only" to slice-01, but slice-01 shipped only the `telemetry_paths.py`
prefactor -- this module and `UnifiedEventStoreAdapter` did not exist on disk
until this slice.

`append`/`append_derived` are slice-02 scope (composition over
`AtCompletionLedger`, DD-11). `read`/`read_across` are declared here as part
of the FULL port contract (so the Protocol is complete and a future adapter
implementation can be mypy-structurally-checked against it, per the
Architecture-Tests row in feature-delta.md), but their IMPLEMENTATION is
slice-03 (`LegacyEnvelopeNormalizer` + `ReductionKeyDeduper` + `Aggregate`)
and slice-04 (`CrossDomainReader`) scope respectively -- slice-02's adapter
scaffold raises for both, and slice-02's ATs do not exercise them.

DELIVER routing note (measured finding, recorded here so the crafter does not
have to rediscover it): `AtCompletionLedger` is FAMILY-BLIND today --
`_append_record` writes to `self.ledger_path()`, which is fixed at
construction time (`feature_id is None` selects singleton vs legacy shape)
and never consults `telemetry_paths.ledger_path(repo, family, partition_key)`.
Threading `EventRecord.family` through to a real per-family destination
requires DELIVER to add an explicit target-path parameter to the shared
`_append_record` critical section (e.g. `target_path: Path | None = None`,
defaulting to `self.ledger_path()` so all 39 existing `append_*` call sites
stay byte-identical) and have the new `append_event` seam resolve it via
`telemetry_paths.ledger_path(project_root, family, partition_key)`. Without
this, `family` validates syntactically and has ZERO effect on where a record
physically lands -- the exact `LedgerFamily.RED_GREEN` failure class D80
exists to kill, reintroduced one layer up (see
`tests/des/unit/adapters/test_unified_event_store_adapter.py`
`TestAppendRoutesToPerFamilyDestination`, which pins the LITERAL destination
path for two distinct families rather than recomputing it through the same
resolver the implementation would call -- the tautology class constraint 10
names, applied to the destination path rather than the record content).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol


if TYPE_CHECKING:
    from collections.abc import Sequence

    from des.domain.telemetry_paths import LedgerFamily


#: DD-5's closed scope vocabulary. A bare `str` would let `scope="nodes"`
#: (a typo) write a record no consumer can ever query -- the same
#: "validates and means nothing" class DD-6 exists to prevent for
#: `tool_use_id`. Checkable locally, on one record, without the population
#: (DD-6's own strongest formulation, GDP-8 witness corollary).
EventScope = Literal["feature", "session", "node"]


@dataclass(frozen=True)
class EventRecord:
    """One record a caller wants appended to the unified event store.

    `scope` is one of `"feature"`, `"session"`, `"node"` (DD-5, `EventScope`).
    A value outside this closed set is refused with `InvalidScope` --
    `EventRecord` itself does not validate at construction (frozen dataclass,
    no `__post_init__` validation by design: a caller may legitimately
    construct one from untyped input, e.g. deserialized JSON, before handing
    it to `append`), so `append`/`append_derived` are the enforcement point.
    `feature_id` is nullable -- valid null only when `scope != "feature"`.
    `partition_key` is REQUIRED (non-empty) whenever `scope != "feature"` --
    an empty `partition_key` on a session/node-scoped record is refused with
    `PartitionKeyRequired` (DD-5), never silently defaulted.

    `agent_id` is nullable; a null `agent_id` makes the record
    dedup-ineligible for `append_derived` (DD-8) -- `append` (the PRIMARY
    write) accepts a null `agent_id` unconditionally, only `append_derived`
    (the DERIVED write) refuses it.

    `fields` carries the record-specific payload (the `event` name plus any
    extra keys) -- the SAME shape `AtCompletionLedger._append_record` already
    accepts, so the eventual `append_event` seam threads this straight
    through with zero reshaping.
    """

    family: LedgerFamily
    event: str
    scope: str
    feature_id: str | None = None
    partition_key: str | None = None
    agent_id: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppendedRecord:
    """The record the store actually wrote, with its assigned identity.

    `seq` is the gap-free monotonic sequence assigned by the shared
    `_append_record` critical section (Correction 4 -- ONE write primitive).
    `correlation_id` is the emitter-generated, unique-by-construction
    parent/child join key (DD-6, DD-15) -- never `tool_use_id`.
    """

    seq: int
    record_hash: str
    correlation_id: str
    record: dict[str, Any]


@dataclass(frozen=True)
class ReductionKey:
    """The DD-7 derived-record stamp `append_derived` applies on success.

    `reduction_key` requires the source record's `agent_id` to be non-null
    (DD-8) -- `append_derived` raises `ReductionKeyIneligible` before this
    value is ever used when that precondition fails, so a `ReductionKey`
    only ever exists attached to a record that legitimately earned one.
    """

    reduction_key: str
    reducer_version: str


@dataclass(frozen=True)
class ReadResult:
    """The arity-safe rollup every read/aggregate over the store returns.

    `could_not_verify_count` is NEVER omitted / defaulted-to-zero by a caller
    forgetting to ask (DD-9, GDP-8 arity corollary) -- it is a REQUIRED field
    on this type, so a caller cannot construct a `ReadResult` that silently
    drops it.
    """

    records: list[dict[str, Any]]
    measured_count: int
    could_not_verify_count: int
    could_not_verify_reasons: list[str]


class PartitionKeyRequired(TypeError):
    """DD-5: `scope != "feature"` with an empty/missing `partition_key`."""


class ReductionKeyIneligible(TypeError):
    """DD-8: `append_derived` called on a record whose `agent_id` is null."""


class InvalidScope(TypeError):
    """`EventRecord.scope` is outside the closed `EventScope` vocabulary.

    `append`/`append_derived` refuse a record whose `scope` is not one of
    `"feature"`, `"session"`, `"node"` (DD-5) -- a typo (`"nodes"`) or an
    arbitrary caller-chosen string must never silently write a record no
    consumer can ever query by its declared scope.
    """


class EventStorePort(Protocol):
    """The driving contract DD-1 gates/hooks/reducers call IN through.

    Named under `driven_ports/` by existing repo convention even though it is
    DRIVING relative to this component (the sibling `at_completion_ledger_port.py`
    already occupies this package for the identical reason).
    """

    def append(self, record: EventRecord) -> AppendedRecord:
        """Append one PRIMARY (emitter-knowable) record. DD-1 gates/hooks."""
        ...

    def append_derived(
        self, record: EventRecord, reduction: ReductionKey
    ) -> AppendedRecord:
        """Append one DERIVED record, stamped with `reduction_key` (DD-7).

        D71 reducer. D70 closure-attestation is PRIMARY, never DERIVED
        (ADR-D70 D70-2): its population is 100% null-`agent_id` by
        construction, and DD-8 refuses every `append_derived` call for a
        null `agent_id` -- it uses `append()` instead.
        """
        ...

    def read(
        self, family: LedgerFamily, partition_key: str, **filters: Any
    ) -> ReadResult:
        """Read one family's records for `partition_key`. slice-03 scope."""
        ...

    def read_across(
        self, families: Sequence[LedgerFamily], partition_key: str
    ) -> ReadResult:
        """Merge N families for one `partition_key`, one timeline. slice-04 scope."""
        ...


__all__ = [
    "AppendedRecord",
    "EventRecord",
    "EventScope",
    "EventStorePort",
    "InvalidScope",
    "PartitionKeyRequired",
    "ReadResult",
    "ReductionKey",
    "ReductionKeyIneligible",
]
