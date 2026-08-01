"""UnifiedEventStoreAdapter -- composition over AtCompletionLedger (DD-11).

Implements `EventStorePort` + `Probeable` by COMPOSITION over the existing
`AtCompletionLedger` singleton shape (DD-11 -- NOT inheritance, NOT a
rename: dozens of construction sites across dozens of files depend on the
current class, per feature-delta.md DD-11 / the Reuse Analysis).

Slice-02 shipped `append` / `append_derived` / `probe`. Slice-03 (this
module's `read()`) composes `LegacyEnvelopeNormalizer` (DD-10) +
`ReductionKeyDeduper` (DD-7/DD-8) over one family's raw JSONL to answer a
single-family query with an arity-safe `ReadResult` (DD-9) -- never a bare
total. `read_across` remains slice-04 scope (`CrossDomainReader`); this
slice's ATs do not exercise it.

DELIVER slice-02 wiring (recorded here so the shape survives context resets):

* `append` funnels onto a NEW `AtCompletionLedger.append_event(scope, event,
  **fields)` seam (Reuse Analysis row 2, beside the existing 39 public
  `append_*` methods) -- the SAME flock-serialised `_append_record` critical
  section every other write already uses (Correction 4). `append` validates
  DD-5 (`scope != "feature"` with an empty `partition_key` -> raise
  `PartitionKeyRequired`) BEFORE calling the ledger seam.
* `append_derived` validates DD-8 (`record.agent_id is None` -> raise
  `ReductionKeyIneligible`) BEFORE stamping `reduction_key`/`reducer_version`
  /`reduced_through_request` onto the appended record.
* `probe` DELEGATES to `StoreAvailabilityProbe` (never reimplements the
  canary logic -- witness-independence, GDP-8, the peer-review MEDIUM
  finding closed in feature-delta.md).

DELIVER slice-03 wiring (`read()`): resolves the family's JSONL via
`telemetry_paths.ledger_path(project_root, family, partition_key)`, reads it
line-by-line. A row already carrying `envelope_generation` is new-envelope
(post-cutover); a row without one is legacy and is normalized through
`LegacyEnvelopeNormalizer` (DD-10, always `measured`). A new-envelope row
carrying `reduction_key` is DERIVED and is routed through
`ReductionKeyDeduper.dedupe()` (DD-7 MAX-per-key, DD-8 null-agent_id
ineligibility); a new-envelope row with no `reduction_key` is PRIMARY and
counts directly (DD-15 -- a record is wholly emitter-knowable or wholly
derived, never both). The three counts (legacy + primary-new + dedup) sum
into `ReadResult.measured_count`; `could_not_verify_count`/`_reasons` come
straight from the dedup `Aggregate` (DD-9). An absent ledger file and an
unreadable ledger file are BOTH reported as `could_not_verify` with a named
reason -- never a raised exception, and never a silently-shrunk total
(GDP-8 arity corollary) -- and are told apart from a ledger file that
exists and genuinely holds zero rows. `read()` never writes to the
filesystem.

DELIVER round-4 wiring (DD-17, `docs/product/architecture/ADR-EVT-002-
row-recognition-contract.md`): `_classify_line` inverts from open-ended
"recognise known-bad, else accept" to closed "recognise known-good, else
`could_not_verify`". Gate 0 -- `isinstance(row, dict)`, applied to EVERY
parsed row before any branching -- replaces the prior accidental reliance on
`TypeError` bubbling out of `"envelope_generation" not in row` /
`LegacyEnvelopeNormalizer.normalize`'s own Mapping check; `{}` still passes
Gate 0 (DD-10 totality, unchanged). The primary-new branch then admits only
`agent_id in (None, str)`; the derived branch (after the existing
presence-only `_DERIVED_ROW_REQUIRED_KEYS` check) admits only
`agent_id in (None, str)`, `reduction_key` a non-empty `str`, and
`reduction_seq` with `type(value) is int` exactly (excluding `bool`, an
`int` subclass, and excluding `float`/`NaN`) -- all three checked in ONE
pass, every violated field named in a single reason. This closes the
row-shape layer by construction: no exception is raised or caught for it,
it is a value-driven predicate (enforced by
`tests/des/architecture/test_row_recognition_no_bare_except.py`, which
forbids a bare `except Exception`/`except BaseException` inside
`_classify_line`). The now-provably-dead `except TypeError` clause around
`_classify_line`'s body is removed (Gate 0 runs first, so nothing inside
the try body can raise `TypeError` for row shape any more).

Two SEPARATE boundary repairs, kept distinct from the row-shape gate and
from each other (different granularity, representation transition, and
control-flow mechanism -- ADR-EVT-002): the whole-file read widens its
`except` to `(OSError, UnicodeDecodeError)` (`UnicodeDecodeError` is a
`ValueError`/`UnicodeError` subclass, NOT an `OSError` subclass -- the old
clause structurally missed non-UTF-8 bytes); the per-line parse widens to
`(json.JSONDecodeError, RecursionError, ValueError)` (`JSONDecodeError` IS a
`ValueError` subclass, matched first for its own distinguishable reason; a
bare `ValueError` additionally catches CPython's int-string-conversion-limit
error for a >=4300-digit integer literal; `RecursionError` is a
`RuntimeError` subclass, unrelated to `ValueError`, raised by ~60k-deep JSON
nesting). Both stay a best-known-exhaustive exception enumeration, NOT a
closed-by-construction guarantee the way the row-shape gate is -- named as
such, not oversold (ADR-EVT-002 "An honest asymmetry").
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.logging.store_availability_probe import StoreAvailabilityProbe
from des.domain.event_store_aggregate import ReductionKeyDeduper
from des.domain.legacy_envelope_normalizer import LegacyEnvelopeNormalizer
from des.domain.telemetry_paths import ledger_path
from des.ports.driven_ports.event_store_port import (
    AppendedRecord,
    InvalidScope,
    PartitionKeyRequired,
    ReadResult,
    ReductionKeyIneligible,
)


if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from des.domain.telemetry_paths import LedgerFamily
    from des.ports.driven_ports.event_store_port import (
        EventRecord,
        ReductionKey,
    )
    from des.ports.driven_ports.probeable_port import ProbeResult


_VALID_SCOPES = ("feature", "session", "node")

# DD-7 requires every DERIVED row to carry `agent_id` (DD-8 eligibility) and
# `reduction_seq` (the MAX-per-key read rule) -- a row that reaches
# `_classify_line` as JSON-valid-object-with-envelope_generation-and-
# reduction_key but is missing either KEY ENTIRELY must degrade into a
# NAMED could_not_verify reason before it ever reaches
# `ReductionKeyDeduper.dedupe`, which is entitled to assume a well-shaped
# input and stays a pure function with no `.get()` defensiveness (round-3
# regression, D1 one layer deeper).
_DERIVED_ROW_REQUIRED_KEYS = ("agent_id", "reduction_seq")

# Each missing key gets its own distinguishing clause so the reported reason
# can never be mistaken for a sibling fault that also mentions the same key
# name (DD-8's null-agent_id reason for "agent_id"; the ambiguous tied-max
# reason for "reduction_seq").
_MISSING_KEY_DISTINCTION = {
    "agent_id": (
        "distinct from an agent_id key that is present but set to null, "
        "which is DD-8's already-handled dedup-ineligibility case"
    ),
    "reduction_seq": (
        "distinct from a duplicate-max grouping problem, which can only "
        "arise once reduction_seq is already present on every row in the "
        "group"
    ),
}


def _is_admissible_agent_id(value: Any) -> bool:
    """ADR-EVT-002 primary/derived branch gate: `agent_id` admits only
    `None` or `str` -- every other type (list, dict, int, float, bool) is
    inadmissible. `bool` is excluded here for free (`isinstance(True, str)`
    is `False`), no special-casing needed."""
    return value is None or isinstance(value, str)


def _is_admissible_reduction_key(value: Any) -> bool:
    """ADR-EVT-002 derived branch gate: `reduction_key` admits only a
    non-empty `str`. `None`/`""`/int/float/bool/list/dict are all
    inadmissible -- `bool` excluded for free (not a `str`)."""
    return isinstance(value, str) and value != ""


def _is_admissible_reduction_seq(value: Any) -> bool:
    """ADR-EVT-002 derived branch gate: `reduction_seq` admits only
    `type(value) is int` EXACTLY -- deliberately not `isinstance`, because
    `bool` is a Python `int` subclass (`isinstance(True, int) is True`).
    `type(value) is int` also excludes `float` (including `NaN`), removing
    the `NaN != NaN` self-contradiction inside `max()` by construction,
    never by a special-cased `NaN` branch."""
    return type(value) is int


class UnifiedEventStoreAdapter:
    """Composition over `AtCompletionLedger` (DD-11) -- see module docstring.

    Constructed with the target repo's `project_root`; owns a
    `StoreAvailabilityProbe` for its `probe()` delegation and an
    `AtCompletionLedger` (singleton shape) for its write surface -- both by
    COMPOSITION, never inheritance (DD-11).
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._probe = StoreAvailabilityProbe(project_root)
        self._ledger = AtCompletionLedger(project_root=project_root)

    # --- write surface (slice-02 scope) --------------------------------

    def append(self, record: EventRecord) -> AppendedRecord:
        """Append one PRIMARY record, validating DD-5 and the closed scope
        vocabulary before delegating to `AtCompletionLedger.append_event`."""
        self._validate_scope(record.scope)
        partition_key = self._resolve_partition_key(record)
        raw = self._ledger.append_event(
            record.scope,
            record.event,
            family=record.family,
            partition_key=partition_key,
            feature_id=record.feature_id,
            agent_id=record.agent_id,
            fields=dict(record.fields),
        )
        return self._to_appended_record(raw)

    def append_derived(
        self, record: EventRecord, reduction: ReductionKey
    ) -> AppendedRecord:
        """Append one DERIVED record, validating DD-8 before stamping
        `reduction_key`/`reducer_version` onto the write."""
        if record.agent_id is None:
            raise ReductionKeyIneligible(
                "WHAT: append_derived was called on a record with "
                "agent_id=None. "
                "WHY: reduction_key would collapse distinct facts under an "
                "unproven session-level identity (DD-8). "
                "HOW: write with determination=could_not_verify and omit "
                "reduction_key instead."
            )
        self._validate_scope(record.scope)
        partition_key = self._resolve_partition_key(record)
        derived_fields = dict(record.fields)
        derived_fields["reduction_key"] = reduction.reduction_key
        derived_fields["reducer_version"] = reduction.reducer_version
        raw = self._ledger.append_event(
            record.scope,
            record.event,
            family=record.family,
            partition_key=partition_key,
            feature_id=record.feature_id,
            agent_id=record.agent_id,
            fields=derived_fields,
        )
        return self._to_appended_record(raw)

    @staticmethod
    def _to_appended_record(raw: dict[str, Any]) -> AppendedRecord:
        return AppendedRecord(
            seq=raw["seq"],
            record_hash=raw["record_hash"],
            correlation_id=raw["correlation_id"],
            record=raw,
        )

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in _VALID_SCOPES:
            raise InvalidScope(
                f"WHAT: EventRecord.scope={scope!r} is not one of "
                f"{_VALID_SCOPES!r}. "
                "WHY: a typo must never silently write a record no consumer "
                "can ever query by its declared scope (DD-5/DD-6's own "
                "strongest formulation, applied to scope). "
                f"HOW: pass scope as one of {_VALID_SCOPES!r}."
            )

    @staticmethod
    def _resolve_partition_key(record: EventRecord) -> str:
        if record.scope != "feature":
            if not record.partition_key:
                raise PartitionKeyRequired(
                    f"WHAT: scope={record.scope!r} was given with an empty "
                    "partition_key. "
                    "WHY: session/node-scoped records need a partition_key "
                    "distinct from feature_id, or a later session/node "
                    "under the same absent key silently collides (DD-5). "
                    "HOW: pass partition_key= (e.g. session_id/node_id)."
                )
            return record.partition_key
        return record.partition_key or str(record.feature_id)

    # --- read surface (slice-03 scope) ----------------------------------

    def read(
        self, family: LedgerFamily, partition_key: str, **filters: Any
    ) -> ReadResult:
        """Single-family read (slice-03) -- see module docstring for the
        composition (`LegacyEnvelopeNormalizer` + `ReductionKeyDeduper`)."""
        path = ledger_path(self._project_root, family, partition_key)

        if not path.is_file():
            return ReadResult(
                records=[],
                measured_count=0,
                could_not_verify_count=1,
                could_not_verify_reasons=[
                    f"no ledger file found for family={family.value!r} "
                    f"partition_key={partition_key!r} at {path} -- absent, "
                    "never written, distinct from a ledger that exists and "
                    "genuinely holds zero records"
                ],
            )

        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ReadResult(
                records=[],
                measured_count=0,
                could_not_verify_count=1,
                could_not_verify_reasons=[
                    f"ledger file at {path} could not be read ({exc}) -- "
                    "the entire partition's rows are could_not_verify, "
                    "never silently reported as measured"
                ],
            )

        legacy_rows: list[dict[str, Any]] = []
        primary_new_rows: list[dict[str, Any]] = []
        derived_rows: list[dict[str, Any]] = []
        line_fault_reasons: list[str] = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            self._classify_line(
                stripped,
                path,
                legacy_rows=legacy_rows,
                primary_new_rows=primary_new_rows,
                derived_rows=derived_rows,
                line_fault_reasons=line_fault_reasons,
            )

        dedup = ReductionKeyDeduper.dedupe(derived_rows)

        return ReadResult(
            records=[*legacy_rows, *primary_new_rows, *derived_rows],
            measured_count=(
                len(legacy_rows) + len(primary_new_rows) + dedup.measured_count
            ),
            could_not_verify_count=(
                dedup.could_not_verify_count + len(line_fault_reasons)
            ),
            could_not_verify_reasons=[
                *dedup.could_not_verify_reasons,
                *line_fault_reasons,
            ],
        )

    @staticmethod
    def _classify_line(
        stripped_line: str,
        path: Path,
        *,
        legacy_rows: list[dict[str, Any]],
        primary_new_rows: list[dict[str, Any]],
        derived_rows: list[dict[str, Any]],
        line_fault_reasons: list[str],
    ) -> None:
        """Parse+classify ONE non-blank ledger line, appending to the
        caller's accumulators (DD-17, ADR-EVT-002 -- deny-by-default row
        recognition: a row becomes `measured`/eligible-for-dedup only if it
        POSITIVELY satisfies a declared, bounded field-type contract;
        everything else degrades into a NAMED `line_fault_reasons` entry,
        never a raised exception, never a silent accept).

        Two DISTINCT layers here, on purpose (ADR-EVT-002 "three separate
        boundaries"):

        1. Per-line PARSE (this method's `try`/`except`) -- exception-driven,
           best-known-exhaustive, NOT closed-by-construction. Catches
           `json.JSONDecodeError` (malformed JSON, e.g. a truncated
           mid-append write), `RecursionError` (~60k-deep JSON nesting,
           unrelated to `ValueError`), and a bare `ValueError` (CPython's
           int-string-conversion-limit error for a >=4300-digit integer
           literal -- `JSONDecodeError` IS a `ValueError` subclass, so it is
           matched first for its own distinguishable reason). Never a
           broader `Exception`/`BaseException` (enforced by
           `tests/des/architecture/test_row_recognition_no_bare_except.py`),
           which would convert a genuine fault into a clean-looking answer.
        2. Row-SHAPE gate (everything after `json.loads` succeeds) --
           VALUE-driven, closed-by-construction: Gate 0
           (`isinstance(row, dict)`, `{}` still accepted per DD-10), then a
           per-branch admissible-type contract for `agent_id`/
           `reduction_key`/`reduction_seq`. No exception is raised or
           caught for this layer at all.
        """
        try:
            row = json.loads(stripped_line)
        except json.JSONDecodeError as exc:
            line_fault_reasons.append(
                f"ledger line at {path} is malformed -- could not parse it "
                f"as JSON ({exc}) -- distinguishable from an unreadable "
                "file: the file itself opened fine, one line inside it "
                "did not"
            )
            return
        except RecursionError as exc:
            line_fault_reasons.append(
                f"ledger line at {path} exceeds the JSON parser's nesting "
                f"depth limit ({exc}) -- distinguishable from a malformed/"
                "unparsable JSON line: the line is syntactically valid "
                "JSON, only its nesting depth triggered Python's recursion "
                "limit during parsing"
            )
            return
        except ValueError as exc:
            line_fault_reasons.append(
                f"ledger line at {path} contains an integer literal beyond "
                f"CPython's int-string conversion limit ({exc}) -- "
                "distinguishable from a malformed/unparsable JSON line: the "
                "line is syntactically valid JSON, only one integer "
                "literal's digit count exceeded the conversion limit "
                "during parsing"
            )
            return

        if not isinstance(row, dict):
            line_fault_reasons.append(
                f"ledger row at {path} parsed as valid JSON but is not a "
                f"JSON object (got {type(row).__name__}) -- distinguishable "
                "from an unreadable file: the file itself opened fine, one "
                "row inside it had the wrong shape"
            )
            return

        if "envelope_generation" not in row:
            legacy_rows.append(LegacyEnvelopeNormalizer.normalize(row))
            return

        if "reduction_key" in row:
            UnifiedEventStoreAdapter._classify_derived_row(
                row,
                path,
                derived_rows=derived_rows,
                line_fault_reasons=line_fault_reasons,
            )
            return

        UnifiedEventStoreAdapter._classify_primary_new_row(
            row,
            path,
            primary_new_rows=primary_new_rows,
            line_fault_reasons=line_fault_reasons,
        )

    @staticmethod
    def _classify_primary_new_row(
        row: dict[str, Any],
        path: Path,
        *,
        primary_new_rows: list[dict[str, Any]],
        line_fault_reasons: list[str],
    ) -> None:
        """ADR-EVT-002 primary-branch gate: `agent_id`, if the key is
        present at all, must be `None` or `str`. An absent `agent_id` key
        fires no gate (kept conservative -- not a form observed in any of
        the four D1..D4 rounds)."""
        if "agent_id" in row and not _is_admissible_agent_id(row["agent_id"]):
            value = row["agent_id"]
            line_fault_reasons.append(
                f"primary-new ledger row at {path} has agent_id of type "
                f"{type(value).__name__} ({value!r}) -- admissible types "
                "are None or str (ADR-EVT-002 primary-branch gate), "
                "distinguishable from a derived row's agent_id reason"
            )
            return
        primary_new_rows.append(row)

    @staticmethod
    def _classify_derived_row(
        row: dict[str, Any],
        path: Path,
        *,
        derived_rows: list[dict[str, Any]],
        line_fault_reasons: list[str],
    ) -> None:
        """ADR-EVT-002 derived-branch gate: presence check first (DD-7,
        unchanged), then the full field-type contract for `agent_id`/
        `reduction_key`/`reduction_seq`, all three checked in ONE pass so a
        row violating more than one field is reported in a single reason
        (never a second round to discover the rest)."""
        missing_keys = [key for key in _DERIVED_ROW_REQUIRED_KEYS if key not in row]
        if missing_keys:
            line_fault_reasons.append(
                UnifiedEventStoreAdapter._missing_derived_key_reason(path, missing_keys)
            )
            return

        violations = UnifiedEventStoreAdapter._derived_row_type_violations(row)
        if violations:
            line_fault_reasons.append(
                UnifiedEventStoreAdapter._derived_type_violation_reason(
                    path, violations
                )
            )
            return

        derived_rows.append(row)

    @staticmethod
    def _derived_row_type_violations(row: dict[str, Any]) -> list[tuple[str, Any]]:
        """Return every `(field, value)` pair on `row` that fails
        ADR-EVT-002's derived-branch admissible-type contract -- evaluated
        for ALL three fields regardless of how many already failed, so the
        caller can name every violation from this one pass."""
        violations: list[tuple[str, Any]] = []
        if not _is_admissible_agent_id(row["agent_id"]):
            violations.append(("agent_id", row["agent_id"]))
        if not _is_admissible_reduction_key(row["reduction_key"]):
            violations.append(("reduction_key", row["reduction_key"]))
        if not _is_admissible_reduction_seq(row["reduction_seq"]):
            violations.append(("reduction_seq", row["reduction_seq"]))
        return violations

    @staticmethod
    def _derived_type_violation_reason(
        path: Path, violations: list[tuple[str, Any]]
    ) -> str:
        """Build ONE could_not_verify reason naming EVERY violated field
        (ADR-EVT-002 "all three fields checked in ONE pass"). Field-specific
        clauses stay distinguishable from their nearest sibling reason:
        `agent_id` here never says "null agent_id" (DD-8's own already-
        handled null case); `reduction_seq` here never says "ambiguous" or
        "tied" (the dedup tied-max reason)."""
        clauses = []
        for field, value in violations:
            type_name = type(value).__name__
            if field == "agent_id":
                clauses.append(
                    f"agent_id is type {type_name} ({value!r}) -- admissible "
                    "types are None or str"
                )
            elif field == "reduction_key":
                clauses.append(
                    f"reduction_key is {value!r} of type {type_name} -- "
                    "admissible is a non-empty str"
                )
            else:
                clauses.append(
                    f"reduction_seq is {value!r} of type {type_name} -- "
                    "admissible is exactly int, excluding bool and float"
                )
        return (
            f"derived ledger row at {path} has {len(violations)} "
            f"inadmissible field(s) (ADR-EVT-002 derived-branch gate): "
            + "; ".join(clauses)
        )

    @staticmethod
    def _missing_derived_key_reason(path: Path, missing_keys: list[str]) -> str:
        """Build a NAMED, distinguishable could_not_verify reason for a
        derived row that is well-formed JSON, IS an object, HAS
        `envelope_generation` and `reduction_key` -- so it is unambiguously
        DERIVED -- but is missing one of DD-7's required keys (`agent_id`,
        `reduction_seq`) ENTIRELY. Keeps `ReductionKeyDeduper.dedupe` a pure
        function of well-shaped input: the row is routed here instead of
        ever reaching the aggregate."""
        names = " and ".join(missing_keys)
        distinctions = "; ".join(_MISSING_KEY_DISTINCTION[key] for key in missing_keys)
        return (
            f"derived ledger row at {path} is missing its {names} key "
            f"entirely -- {distinctions}"
        )

    def read_across(
        self, families: Sequence[LedgerFamily], partition_key: str
    ) -> ReadResult:
        raise AssertionError(
            "__SCAFFOLD__: UnifiedEventStoreAdapter.read_across() is "
            "slice-04 scope (CrossDomainReader) -- not implemented by "
            "slice-02/slice-03, and this slice's ATs do not exercise it."
        )

    # --- Earned Trust probe (slice-02 scope) ----------------------------

    def probe(self) -> ProbeResult:
        """Delegate to `StoreAvailabilityProbe` -- never reimplement (GDP-8)."""
        return self._probe.probe()


__all__ = ["UnifiedEventStoreAdapter"]
