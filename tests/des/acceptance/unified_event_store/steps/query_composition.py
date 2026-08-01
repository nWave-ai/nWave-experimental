"""Composition root for the unified-event-store slice-03 acceptance ATs
(`des event-store-query --family` single-family mode, EXP-unified-event-store-2).

Driving-port-only (Mandate-13). NO new @walking_skeleton here -- the
feature's ONE subprocess-E2E walking skeleton already lives in slice-02
(the WS Strategy section forbids a second one). Every scenario drives
`des.cli.event_store_query.main(argv, output=CapturingOutput())`
IN-PROCESS (Mandate-13 L2 default, content facet, no interpreter fork).

DELIVER has since implemented `des.cli.event_store_query` for real (the
`__SCAFFOLD__` `AssertionError` path below is now dormant for the 7
originally-authored scenarios, which drive real production behaviour). This
composition still catches `AssertionError` narrowly for that historical
reason -- a stray future scaffold on this module would still surface the
same way. It ALSO catches any OTHER exception `main()` lets escape
(`unhandled_exception` on the observable) -- a REAL production bug class a
code-review pass surfaced: a malformed/corrupted ledger line (a truncated
write, or a valid-JSON-but-wrong-shape row) is not defended against inside
`UnifiedEventStoreAdapter.read()` today, so it raises uncaught
(`json.JSONDecodeError` / `TypeError`) instead of contributing to
`could_not_verify_count`. Catching it HERE, at the SUT-invocation boundary,
turns that crash into an observable a `Then` step fails against with a
clean, business-meaningful assertion -- never lets a bare traceback escape
the composition uncontrolled.

Fixture ledger rows are written as RAW JSONL lines directly to the
partition's ledger file (bypassing `AtCompletionLedger`/`UnifiedEventStoreAdapter`
entirely, both of which are themselves scaffolds for this read path) --
this is legitimate fixture setup (Given), never the feature's own write
surface under test.

Hexagonal-boundary note (peer-review finding, judgment call recorded --
Ale/orchestrator 2026-07-31): this module imports `des.domain.telemetry_paths`
(`LedgerFamily`, `ledger_path`, `telemetry_root`) directly. The already-committed
sibling `steps/composition.py:29` (slice-02) does the identical import, as do
11 other acceptance step packages in this repo -- a repo-wide precedent, not a
slice-03 regression. The CM-A hexagonal-boundary mandate exists to stop a test
from reaching into domain logic to BYPASS the driving port; this import is used
ONLY to LOCATE a fixture file on disk (the SAME path-construction SSOT the
production adapter itself will resolve through at DELIVER time), never to
invoke the feature's own behaviour directly -- every scenario still drives the
SUT exclusively via `event_store_query.main(argv, output=)`. Hardcoding the
`.nwave/telemetry/{family}/{partition_key}.jsonl` layout here instead would
duplicate telemetry_paths's own SSOT and silently drift the moment that layout
changes -- a worse failure mode (a drifted copy teaches a false contract) than
a fixture importing the path-resolution helper it needs.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli import event_store_query
from des.domain.telemetry_paths import LedgerFamily, ledger_path, telemetry_root
from des.testing.output_capture import CapturingOutput

from .query_domain_types import QueryObservable


def _legacy_row(*, feature_id: str, seq: int) -> dict[str, object]:
    """A minimal pre-cutover legacy record, matching the measured dominant
    shape (feature-delta.md Event-kind inventory): no `scope`/`determination`/
    `envelope_generation` -- those are the DD-10 overlay `LegacyEnvelopeNormalizer`
    is responsible for adding at READ time, never at rest."""
    return {
        "event": "SliceCommitVerified",
        "feature_id": feature_id,
        "record_hash": f"hash-legacy-{feature_id}-{seq}",
        "seq": seq,
        "slice_id": "slice-01",
        "timestamp": f"2026-07-30T00:00:{seq:02d}Z",
    }


def _derived_row(*, feature_id: str, seq: int) -> dict[str, object]:
    """A minimal new-envelope DERIVED record (DD-5/DD-7 fields) -- already
    carries `scope`/`determination`/`envelope_generation` because it was
    written post-cutover, unlike `_legacy_row` above."""
    return {
        "event": "SomeDerivedEvent",
        "feature_id": feature_id,
        "scope": "feature",
        "determination": "measured",
        "envelope_generation": "new",
        "reduction_key": f"rk-{feature_id}-{seq}",
        "reduction_seq": 1,
        "reduced_through_request": "req-1",
        "reducer_version": "v1",
        "agent_id": "agent-1",
        "seq": seq,
    }


# --- DD-17 round-4 fixture literals ------------------------------------
#
# ADR-EVT-002's Gate 0 / branch-type contract, stated as a closed vocabulary
# of Gherkin Examples-column tokens -> concrete JSON-serializable Python
# values. `float("nan")` round-trips through `json.dumps`/`json.loads`
# because the stdlib `json` module allows NaN by default (RFC-8259
# deviation, unchanged here) -- no raw-text hack needed for the NaN case.
_GATE0_NON_DICT_SHAPES: dict[str, object] = {
    "a JSON array": [1, 2, 3],
    "a bare number": 42,
    "a bare boolean": True,
    "a bare null": None,
}

_WRONG_TYPE_LITERALS: dict[str, object] = {
    "a list": [1],
    "a dict": {"a": 1},
    "an int": 7,
    "a float": 1.5,
    "a bool": True,
}

_REDUCTION_KEY_WRONG_LITERALS: dict[str, object] = {
    "null": None,
    "an empty string": "",
    "an int": 7,
    "a float": 1.5,
    "a bool": True,
    "a list": [1],
    "a dict": {"a": 1},
}

_REDUCTION_SEQ_WRONG_LITERALS: dict[str, object] = {
    "true": True,
    "false": False,
    "a float": 1.5,
    "NaN": float("nan"),
    "a string": "1",
    "null": None,
    "a list": [1],
    "a dict": {"a": 1},
}


class EventStoreQueryComposition:
    """Production-wired composition root driving the real event-store-query CLI."""

    def __init__(self) -> None:
        self._repo_root: Path | None = None
        self._observables: dict[str, QueryObservable] = {}
        self._query_counts: dict[str, int] = {}
        self._last_ledger_path: Path | None = None
        self._telemetry_listing_before: tuple[str, ...] | None = None
        self._made_unreadable: list[Path] = []
        # Round-4 (DD-17) conservation-law tracking (peer-review finding,
        # corrected): the OLD law (`measured + could_not_verify == raw
        # non-blank line count`) is FALSE in general -- DD-7 dedup
        # deliberately collapses N rows sharing one reduction_key into a
        # SINGLE accounting unit (1 measured winner, or 1 ambiguous-tie
        # could_not_verify reason), never one unit per row. Every row/line
        # this composition writes is tagged here as either "individual"
        # (legacy, primary-new, any line-level/row-shape fault that never
        # reaches the reduction-key grouping stage) or "grouped:{key}" (a
        # well-shaped, DD-8-eligible derived row that DOES reach grouping) --
        # `expected_conservation_population()` sums individual rows plus
        # DISTINCT grouped keys, which is the LAW THAT IS ACTUALLY TRUE.
        self._population_descriptors: list[str] = []

    # --- Given -----------------------------------------------------------

    def given_repo_root(self, tmp_path: Path) -> None:
        self._repo_root = tmp_path
        telemetry_root(tmp_path).mkdir(parents=True, exist_ok=True)

    def given_ledger(
        self,
        family: str,
        partition_key: str,
        legacy_count: int,
        derived_count: int,
    ) -> None:
        assert self._repo_root is not None, (
            "the sandbox must be armed (given_repo_root) before a ledger "
            "fixture can be written."
        )
        path = ledger_path(self._repo_root, LedgerFamily(family), partition_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy_rows = [
            _legacy_row(feature_id=partition_key, seq=i) for i in range(legacy_count)
        ]
        derived_rows = [
            _derived_row(feature_id=partition_key, seq=i) for i in range(derived_count)
        ]
        rows: list[dict[str, object]] = [*legacy_rows, *derived_rows]
        text = "".join(json.dumps(row) + "\n" for row in rows)
        path.write_text(text, encoding="utf-8")
        self._last_ledger_path = path
        self._population_descriptors.extend("individual" for _ in legacy_rows)
        self._population_descriptors.extend(
            f"grouped:{row['reduction_key']}" for row in derived_rows
        )

    def given_empty_ledger_file(self, family: str, partition_key: str) -> None:
        assert self._repo_root is not None, (
            "the sandbox must be armed (given_repo_root) before an empty "
            "ledger file can be written."
        )
        path = ledger_path(self._repo_root, LedgerFamily(family), partition_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self._last_ledger_path = path

    def given_no_ledger_file(self) -> None:
        """The absence itself IS the fixture -- no filesystem action needed
        beyond the sandbox already being armed."""
        assert self._repo_root is not None, "the sandbox must be armed first."

    def given_ledger_file_unreadable(self) -> None:
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before it "
            "can be made unreadable."
        )
        assert self._last_ledger_path.exists(), (
            "the ledger file must exist before it can be made unreadable."
        )
        self._made_unreadable.append(self._last_ledger_path)
        self._last_ledger_path.chmod(0o000)

    def given_malformed_line_appended(self) -> None:
        """Append ONE genuinely truncated JSON line to the last-written
        ledger file -- a half-written final line, e.g. from a process
        killed mid-append (earlyoom under memory contention is the
        concretely-observed cause on this box), not a syntactically-valid
        row with an unexpected shape (see `given_non_object_row_appended`,
        a distinct corruption class)."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "malformed line can be appended to it."
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            # Deliberately missing the closing quote/brace -- json.loads
            # must raise json.JSONDecodeError on this exact text.
            fh.write(
                '{"event": "TruncatedMidWrite", "feature_id": "unified-event-store", "seq"\n'
            )
        self._population_descriptors.append("individual")

    def given_non_object_row_appended(self) -> None:
        """Append ONE line that is syntactically VALID JSON but not a JSON
        OBJECT (a bare string) -- valid-JSON-wrong-shape, the sibling
        corruption class to a truncated line: `json.loads` succeeds, so
        the failure must surface one step later, at whatever code
        classifies/reads the row as a mapping."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "non-object row can be appended to it."
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write('"just-a-string-not-an-object"\n')
        self._population_descriptors.append("individual")

    def given_derived_row_missing_agent_id_appended(self) -> None:
        """Append ONE derived row that is well-formed JSON, IS a dict, HAS
        `envelope_generation` and `reduction_key` -- so it sails past
        `_classify_line` clean into `derived_rows` -- but is missing the
        `agent_id` KEY ENTIRELY (round-3 regression, one layer deeper than
        the malformed-line/non-object-row classes above). DISTINCT from
        DD-8's `agent_id: null` case (already covered, degrades correctly
        today): ABSENT is a different fault than NULL, deliberately no
        `agent_id` key at all here."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "derived row missing agent_id can be appended to it."
        )
        row = {
            "event": "SomeDerivedEvent",
            "feature_id": "unified-event-store",
            "scope": "feature",
            "determination": "measured",
            "envelope_generation": "new",
            "reduction_key": "rk-missing-agent-id",
            "reduction_seq": 1,
            "reduced_through_request": "req-missing-agent-id",
            "reducer_version": "v1",
            "seq": 99,
            # deliberately NO "agent_id" key at all.
        }
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_derived_row_missing_reduction_seq_appended(self) -> None:
        """Sibling to the above: a well-formed derived row (dict,
        `envelope_generation`, `reduction_key`, non-null `agent_id` --
        eligible per DD-8) missing the `reduction_seq` KEY ENTIRELY.
        Distinct code path from the agent_id case: this row passes the
        `agent_id is None` check and enters `eligible_groups`, then crashes
        the `max(r["reduction_seq"] for r in group)` comprehension."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "derived row missing reduction_seq can be appended to it."
        )
        row = {
            "event": "SomeDerivedEvent",
            "feature_id": "unified-event-store",
            "scope": "feature",
            "determination": "measured",
            "envelope_generation": "new",
            "reduction_key": "rk-missing-reduction-seq",
            "reduced_through_request": "req-missing-reduction-seq",
            "reducer_version": "v1",
            "agent_id": "agent-1",
            "seq": 98,
            # deliberately NO "reduction_seq" key at all.
        }
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    # --- DD-17 round-4 fixtures (Gate 0 + branch-type contract + the two
    # boundary-repair widenings) -------------------------------------------

    def given_gate0_non_dict_row_appended(self, shape: str) -> None:
        """Append ONE line whose top-level JSON value is not an object --
        Gate 0's full non-dict closure. The bare-STRING case already has its
        own fixture (`given_non_object_row_appended`, R31); this covers the
        remaining closed vocabulary (array/number/boolean/null) ADR-EVT-002
        names explicitly."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "Gate-0 non-dict row can be appended to it."
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_GATE0_NON_DICT_SHAPES[shape]) + "\n")
        self._population_descriptors.append("individual")

    def given_primary_new_row_with_wrong_type_agent_id_appended(
        self, wrong_type: str
    ) -> None:
        """Append ONE primary-new row (envelope_generation present, NO
        reduction_key) whose `agent_id` is a type outside the admissible
        `None | str` (ADR-EVT-002 primary-branch gate) -- today silently
        accepted as `measured` (SILENT-WRONG, the exact defect DD-17
        inverts)."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "primary-new row with a wrong-type agent_id can be appended."
        )
        row = {
            "event": "SomePrimaryEvent",
            "feature_id": "unified-event-store",
            "scope": "feature",
            "determination": "measured",
            "envelope_generation": "new",
            "agent_id": _WRONG_TYPE_LITERALS[wrong_type],
            "seq": 77,
            # deliberately NO "reduction_key" -- this is what makes the row
            # PRIMARY-new rather than DERIVED.
        }
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def _well_shaped_derived_row(self, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "event": "SomeDerivedEvent",
            "feature_id": "unified-event-store",
            "scope": "feature",
            "determination": "measured",
            "envelope_generation": "new",
            "reduction_key": "rk-wrong-type-fixture",
            "reduction_seq": 1,
            "reduced_through_request": "req-wrong-type",
            "reducer_version": "v1",
            "agent_id": "agent-1",
            "seq": 88,
        }
        row.update(overrides)
        return row

    def given_derived_row_with_wrong_type_agent_id_appended(
        self, wrong_type: str
    ) -> None:
        """Sibling to the primary-branch helper above, DERIVED branch: same
        admissible `None | str` contract, same silent-accept defect today."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "derived row with a wrong-type agent_id can be appended."
        )
        row = self._well_shaped_derived_row(agent_id=_WRONG_TYPE_LITERALS[wrong_type])
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_derived_row_with_wrong_reduction_key_appended(
        self, wrong_value: str
    ) -> None:
        """Derived-branch `reduction_key` admissible ONLY non-empty `str`
        (ADR-EVT-002) -- today silently accepted regardless of type/emptiness."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "derived row with a wrong reduction_key can be appended."
        )
        row = self._well_shaped_derived_row(
            reduction_key=_REDUCTION_KEY_WRONG_LITERALS[wrong_value]
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_derived_row_with_wrong_reduction_seq_appended(
        self, wrong_value: str
    ) -> None:
        """Derived-branch `reduction_seq` admissible ONLY `type(value) is
        int` exactly -- `bool` excluded despite being an `int` subclass,
        `float`/`NaN` excluded (removing the `NaN != NaN` self-contradiction
        by construction, DD-17). Today: non-NaN wrong types are silently
        accepted; NaN itself degrades via the self-contradictory "0 records
        tied" reason instead of a type-violation reason."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "derived row with a wrong reduction_seq can be appended."
        )
        row = self._well_shaped_derived_row(
            reduction_seq=_REDUCTION_SEQ_WRONG_LITERALS[wrong_value]
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_derived_row_with_all_three_fields_wrong_appended(self) -> None:
        """ONE row, THREE simultaneous violations -- ADR-EVT-002's "all three
        fields checked in ONE pass" requirement: every violating field must
        be reported from THIS single query, never requiring a second round
        (the round-1..4 pattern this whole ADR exists to stop)."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before a "
            "multi-violation derived row can be appended."
        )
        row = self._well_shaped_derived_row(
            agent_id=[1],
            reduction_key=123,
            reduction_seq="bad",
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_derived_row_alone_in_its_group_with_nan_reduction_seq_appended(
        self,
    ) -> None:
        """A group of size ONE whose sole member's `reduction_seq` is `NaN`
        -- the exact reproduction of the self-contradictory "ambiguous
        tied-max ... (0 records tied)" reason (`NaN != NaN` discards even
        the `max()` winner). DD-17 closes this by rejecting the row via the
        type contract BEFORE it can ever reach the tied-max grouping code,
        never by special-casing NaN inside `max()`."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before the "
            "NaN-reduction_seq row can be appended."
        )
        row = self._well_shaped_derived_row(
            reduction_key="rk-nan-alone", reduction_seq=float("nan")
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append("individual")

    def given_ledger_file_corrupted_with_invalid_utf8(self) -> None:
        """Widen the whole-file read boundary to `(OSError,
        UnicodeDecodeError)` (ADR-EVT-002): append raw, non-UTF-8 bytes to
        an otherwise-valid ledger file -- `path.read_text(encoding="utf-8")`
        reads the WHOLE file at once, so this is a whole-partition fault,
        granularity-distinct from a per-line fault."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before it "
            "can be corrupted with invalid UTF-8 bytes."
        )
        with self._last_ledger_path.open("ab") as fh:
            fh.write(b"\xff\xfe not valid utf-8 \x80\x81\n")

    def given_line_with_oversized_integer_literal_appended(self) -> None:
        """Widen the per-line parse boundary to include `ValueError`
        (ADR-EVT-002): a JSON integer literal with more digits than
        CPython's int-string conversion limit (default 4300) raises
        `ValueError` from `int()` during `json.loads` -- NOT a
        `json.JSONDecodeError` (syntactically the line is valid JSON), so it
        must be caught by a WIDER clause and reported with a reason
        distinguishable from the malformed-JSON-line reason (R30)."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before an "
            "oversized-integer line can be appended."
        )
        oversized_digits = "9" * 6000
        line = (
            '{"event": "OversizedIntLine", "feature_id": '
            f'"unified-event-store", "seq": {oversized_digits}}}'
        )
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        self._population_descriptors.append("individual")

    def given_line_with_extreme_nesting_depth_appended(self) -> None:
        """Widen the per-line parse boundary to include `RecursionError`
        (ADR-EVT-002): ~60k-deep JSON array nesting raises `RecursionError`
        (a `RuntimeError` subclass, unrelated to `ValueError`) during
        `json.loads` -- a SECOND, independent widening from the oversized-
        integer case above, reported with its own distinguishable reason."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before an "
            "extremely-nested line can be appended."
        )
        depth = 60_000
        line = ("[" * depth) + ("]" * depth)
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        self._population_descriptors.append("individual")

    def given_derived_rows_sharing_one_reduction_key_appended(self, count: int) -> None:
        """Append `count` well-formed, DD-8-eligible derived rows sharing
        ONE `reduction_key` with DISTINCT `reduction_seq` values (a single
        unambiguous winner) -- the corrected KEY-based conservation law's
        own witness: `count` raw ledger rows collapse into exactly ONE
        accounting unit, never `count` (DD-7's own already-shipped MAX-per-
        key rule, exercised here at the CLI surface for the first time)."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before "
            "shared-key derived rows can be appended."
        )
        shared_key = "rk-shared-key"
        with self._last_ledger_path.open("a", encoding="utf-8") as fh:
            for seq in range(count):
                row = self._well_shaped_derived_row(
                    reduction_key=shared_key,
                    reduction_seq=seq,
                    reduced_through_request=f"req-shared-{seq}",
                    seq=200 + seq,
                )
                fh.write(json.dumps(row) + "\n")
        self._population_descriptors.append(f"grouped:{shared_key}")

    def ledger_row_count(self) -> int:
        """The RAW population (peer-review finding, corrected): the number
        of non-blank lines actually written to the last-touched ledger
        file. NO LONGER what a conservation assertion pins against on its
        own (see `expected_conservation_population()` below) -- kept as a
        diagnostic figure, since a raw-row-count law is FALSE in general
        once a reduction_key group has more than one row."""
        assert self._last_ledger_path is not None, (
            "a ledger file must have been written (given_ledger) before its "
            "row population can be counted."
        )
        text = self._last_ledger_path.read_text(encoding="utf-8")
        return sum(1 for line in text.splitlines() if line.strip())

    def expected_conservation_population(self) -> int:
        """The KEY-based accounting population a conservation assertion
        pins against (round-4 correction): every "individual" row/line
        counts once; every DISTINCT `reduction_key` among well-shaped,
        grouped derived rows counts once TOTAL, however many raw rows share
        it -- this is the law DD-7's own MAX-per-key collapse actually
        obeys, unlike the old raw-row-count law it silently violated
        whenever a shared-key group held more than one row."""
        individual = sum(1 for d in self._population_descriptors if d == "individual")
        grouped_keys = {
            d.split(":", 1)[1]
            for d in self._population_descriptors
            if d.startswith("grouped:")
        }
        return individual + len(grouped_keys)

    def restore_permissions(self) -> None:
        """Undo every `chmod 0o000` this composition induced.

        pytest cannot remove an unreadable file cleanly on teardown without
        this, and the box is shared with other lanes -- never leave
        undeletable garbage behind."""
        while self._made_unreadable:
            path = self._made_unreadable.pop()
            try:
                path.chmod(0o644)
            except OSError:
                pass

    # --- When --------------------------------------------------------------

    def when_query(self, family: str, partition_key: str) -> None:
        assert self._repo_root is not None, (
            "the sandbox must be armed before the query can be driven."
        )
        self._telemetry_listing_before = self.telemetry_root_listing()

        fake = CapturingOutput()
        argv = [
            "--repo-root",
            str(self._repo_root),
            "--family",
            family,
            "--partition-key",
            partition_key,
        ]
        exit_code: int | None = None
        scaffold_error: str | None = None
        unhandled_exception: str | None = None
        try:
            exit_code = event_store_query.main(argv, output=fake)
        except AssertionError as exc:
            # Historical scaffold path (see module docstring): caught
            # NARROWLY so a genuine test-authoring bug elsewhere is never
            # masked by this branch specifically.
            scaffold_error = str(exc)
        except Exception as exc:
            # boundary is exactly where an uncontrolled crash (malformed
            # ledger line -> json.JSONDecodeError/TypeError today) must be
            # OBSERVED, not masked -- an explicit Then-step assertion, not
            # this except clause, decides pass/fail on it.
            unhandled_exception = f"{type(exc).__name__}: {exc}"
        self._observables[partition_key] = QueryObservable(
            exit_code=exit_code,
            captured_output=fake.captured_text(),
            scaffold_error=scaffold_error,
            unhandled_exception=unhandled_exception,
        )
        self._query_counts[partition_key] = self._query_counts.get(partition_key, 0) + 1

    # --- observable accessors ---------------------------------------------

    def observable(self, partition_key: str) -> QueryObservable:
        assert partition_key in self._observables, (
            f"partition key {partition_key!r} was never queried (When) "
            "before an observable was read for it."
        )
        return self._observables[partition_key]

    def query_count(self, partition_key: str) -> int:
        """How many times `when_query` was invoked for `partition_key` --
        the structural half of "the caller never has to issue a second
        query": THIS test itself must never have needed one either."""
        return self._query_counts.get(partition_key, 0)

    def diag(self, partition_key: str) -> str:
        obs = self._observables.get(partition_key)
        if obs is None:
            return f"(partition key {partition_key!r} was never queried)"
        return (
            f"(exit_code={obs.exit_code!r}, scaffold_error={obs.scaffold_error!r}, "
            f"unhandled_exception={obs.unhandled_exception!r}, "
            f"captured={obs.captured_output!r})"
        )

    # --- universe (Mandate 8 -- port-exposed observable snapshot) ---------

    def telemetry_root_listing(self) -> tuple[str, ...]:
        assert self._repo_root is not None
        root = telemetry_root(self._repo_root)
        try:
            if not root.exists():
                return ("<root-absent>",)
            if not root.is_dir():
                return ("<root-not-a-directory>",)
            return tuple(
                sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            )
        except PermissionError:
            return ("<permission-denied: cannot enumerate>",)

    def telemetry_root_listing_before(self) -> tuple[str, ...]:
        assert self._telemetry_listing_before is not None, (
            "the before-snapshot is only captured once a query has been driven."
        )
        return self._telemetry_listing_before


__all__ = ["EventStoreQueryComposition"]
