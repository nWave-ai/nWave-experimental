"""Composition root for the unified-event-store slice-04
cross-domain-timeline AT.

Driving surface (Owns-row correction, feature-delta.md [REF] Staging Plan,
human-authorized by Ale 2026-07-31): drives `des event-store-query`'s
default (no `--family`) cross-domain mode via
`des.cli.event_store_query.main(argv, output=CapturingOutput())`
IN-PROCESS -- the composition-root driving port (Mandate-16), never
`CrossDomainReader.read_across()` directly. The correction is explicit:
the AT must drive "the subcommand itself, not the internal composition
helper". Shape mirrors `EventStoreQueryComposition` (slice-03,
`query_composition.py`) deliberately -- both drive the SAME CLI module now,
just its two different modes.

active-RED scaffold (atdd_pure -- NOT `@skip`): the CLI's default-mode
branch is itself a thin wiring scaffold (argv/dispatch only, no business
logic) that constructs `CrossDomainReader` and calls `read_across()`
uncaught -- every scenario drives it and fails for that reason today, a
semantic `AssertionError`, never a collection/CLI-argument error. This
composition catches that ONE exception class narrowly and records it on the
observable (`scaffold_error`), and separately catches any OTHER exception
`main()` lets escape (`unhandled_exception`) -- a real production bug,
never the intentional `__SCAFFOLD__` marker, mirroring `QueryObservable`.

Fixture records are seeded DIRECTLY into each family's JSONL file (this AT
tests `read_across`'s MERGE behaviour, not the write path) -- every seeded
"legacy-shaped" record carries a `seq` field for all three families, i.e.
the POST-migration shape the Reuse-Analysis-row-3 migration of
`record_examine_verdict.py`/`record_review_verdict.py` onto `append_event`
will produce.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from des.cli import event_store_query
from des.domain.telemetry_paths import ledger_path
from des.testing.output_capture import CapturingOutput

from .cross_domain_domain_types import CrossDomainObservable


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.telemetry_paths import LedgerFamily


def _legacy_row(
    *, event: str, feature_id: str, seq: int, timestamp: object, **extra: object
) -> dict[str, object]:
    """A minimal pre-cutover legacy-shaped record (no `envelope_generation`)
    -- the DD-17 branch discriminator classifies it `legacy`, never dedup-
    eligible, matching the measured dominant shape of the 3 real writers
    this slice's Owns row migrates."""
    return {
        "event": event,
        "feature_id": feature_id,
        "seq": seq,
        "timestamp": timestamp,
        **extra,
    }


def _well_shaped_derived_row(
    *,
    feature_id: str,
    seq: int,
    timestamp: str,
    reduction_key: str,
    reduction_seq: int,
    agent_id: object = "agent-1",
) -> dict[str, object]:
    """A well-formed new-envelope DERIVED record (DD-5/DD-7/DD-17 fields)."""
    return {
        "event": "SomeDerivedEvent",
        "feature_id": feature_id,
        "scope": "feature",
        "determination": "measured",
        "envelope_generation": "new",
        "reduction_key": reduction_key,
        "reduction_seq": reduction_seq,
        "reduced_through_request": f"req-{reduction_key}-{reduction_seq}",
        "reducer_version": "v1",
        "agent_id": agent_id,
        "seq": seq,
        "timestamp": timestamp,
    }


class CrossDomainReaderComposition:
    """Seeds a fixture repo's per-family ledgers, then drives
    `des event-store-query`'s default cross-domain mode in-process."""

    def __init__(self) -> None:
        self._project_root: Path | None = None
        self._feature_id: str | None = None
        self._observable: CrossDomainObservable | None = None
        self._made_unreadable: list[Path] = []

    # --- Given -----------------------------------------------------------

    def given_fixture_repo(self, project_root: Path, feature_id: str) -> None:
        self._project_root = project_root
        self._feature_id = feature_id

    def _ledger_path(self, family: LedgerFamily) -> Path:
        assert self._project_root is not None and self._feature_id is not None, (
            "given_fixture_repo() must run before a ledger path can be resolved."
        )
        return ledger_path(self._project_root, family, self._feature_id)

    def _append_line(self, family: LedgerFamily, text: str) -> None:
        path = self._ledger_path(family)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    def seed_record(
        self,
        family: LedgerFamily,
        *,
        event: str,
        seq: int,
        timestamp: str,
        **extra: object,
    ) -> None:
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row = _legacy_row(
            event=event,
            feature_id=self._feature_id,
            seq=seq,
            timestamp=timestamp,
            **extra,
        )
        self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_record_without_timestamp(
        self, family: LedgerFamily, *, event: str, seq: int, **extra: object
    ) -> None:
        """A legacy-shaped row deliberately missing the `timestamp` KEY
        entirely -- read_across's own declared sort key `(timestamp, seq)`
        has no meaning here, so this must degrade to could_not_verify
        rather than crash the merge's sort or silently order arbitrarily."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row: dict[str, object] = {
            "event": event,
            "feature_id": self._feature_id,
            "seq": seq,
            **extra,
            # deliberately NO "timestamp" key at all.
        }
        self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_record_with_timestamp_value(
        self,
        family: LedgerFamily,
        *,
        event: str,
        seq: int,
        timestamp: object,
        **extra: object,
    ) -> None:
        """A legacy-shaped row whose `timestamp` value can be ANY
        JSON-serializable value (e.g. an int) -- the wrong-typed-timestamp
        fixture, distinct from the missing-key fixture above."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row = _legacy_row(
            event=event,
            feature_id=self._feature_id,
            seq=seq,
            timestamp=timestamp,
            **extra,
        )
        self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_record_with_seq_value(
        self,
        family: LedgerFamily,
        *,
        event: str,
        timestamp: str,
        seq: object,
        **extra: object,
    ) -> None:
        """A legacy-shaped row whose `seq` value can be ANY
        JSON-serializable value (e.g. a `str` where an `int` is expected)
        -- the wrong-typed-seq fixture (R58), distinct from the
        wrong-typed-timestamp fixture above."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row = _legacy_row(
            event=event,
            feature_id=self._feature_id,
            seq=seq,
            timestamp=timestamp,
            **extra,
        )
        self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_record_without_seq(
        self, family: LedgerFamily, *, event: str, timestamp: str, **extra: object
    ) -> None:
        """A legacy-shaped row deliberately missing the `seq` KEY entirely
        -- `seq` is an OPTIONAL secondary sort key on `read_across`'s
        declared `(timestamp, seq)` order: an absent `seq` must still be a
        legitimate measured record, defaulting deterministically to `0`
        for ordering purposes (R59), never a could-not-verify on that
        ground alone."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row: dict[str, object] = {
            "event": event,
            "feature_id": self._feature_id,
            "timestamp": timestamp,
            **extra,
            # deliberately NO "seq" key at all.
        }
        self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_derived_rows_sharing_key(
        self,
        family: LedgerFamily,
        *,
        reduction_key: str,
        count: int,
        seq_start: int = 200,
        timestamp_prefix: str = "2026-07-31T11:",
    ) -> None:
        """`count` well-formed, DD-8-eligible derived rows sharing ONE
        `reduction_key` with distinct `reduction_seq` values (a single
        unambiguous winner) -- DD-7's own already-shipped MAX-per-key rule,
        exercised at the cross-domain merge for the first time (R49)."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        for i in range(count):
            row = _well_shaped_derived_row(
                feature_id=self._feature_id,
                seq=seq_start + i,
                timestamp=f"{timestamp_prefix}{i:02d}:00Z",
                reduction_key=reduction_key,
                reduction_seq=i,
            )
            self._append_line(family, json.dumps(row, sort_keys=True))

    def seed_derived_row_with_wrong_type_agent_id(
        self,
        family: LedgerFamily,
        *,
        seq: int,
        timestamp: str,
        reduction_key: str,
    ) -> None:
        """A well-formed-except-for-one-field derived row: `agent_id` is a
        `list` instead of `None | str` (ADR-EVT-002 derived-branch gate) --
        DD-17 deny-by-default degrades it to could_not_verify with a named
        reason, distinct from its well-formed siblings (R53)."""
        assert self._feature_id is not None, "given_fixture_repo() must run first."
        row = _well_shaped_derived_row(
            feature_id=self._feature_id,
            seq=seq,
            timestamp=timestamp,
            reduction_key=reduction_key,
            reduction_seq=1,
            agent_id=["not-a-string"],
        )
        self._append_line(family, json.dumps(row, sort_keys=True))

    def make_family_ledger_unreadable(self, family: LedgerFamily) -> None:
        path = self._ledger_path(family)
        assert path.exists(), (
            f"the {family.value} ledger file must exist before it can be made unreadable."
        )
        self._made_unreadable.append(path)
        path.chmod(0o000)

    def restore_permissions(self) -> None:
        """Undo every `chmod 0o000` this composition induced -- the box is
        shared with other lanes, never leave undeletable garbage behind."""
        while self._made_unreadable:
            path = self._made_unreadable.pop()
            try:
                path.chmod(0o644)
            except OSError:
                pass

    def raw_line_count(self, family: LedgerFamily) -> int:
        path = self._ledger_path(family)
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())

    # --- When ------------------------------------------------------------

    def when_read_across(self) -> None:
        """Drive `des event-store-query`'s default (no `--family`) mode --
        always merges the 3 timeline families (`_TIMELINE_FAMILIES` in
        `event_store_query.py`); this AT names only `--partition-key`."""
        assert self._project_root is not None and self._feature_id is not None, (
            "given_fixture_repo() must run before read_across can be driven."
        )
        fake = CapturingOutput()
        argv = [
            "--repo-root",
            str(self._project_root),
            "--partition-key",
            self._feature_id,
        ]
        exit_code: int | None = None
        scaffold_error: str | None = None
        unhandled_exception: str | None = None
        try:
            exit_code = event_store_query.main(argv, output=fake)
        except AssertionError as exc:
            # RED at HEAD: the CLI's default-mode wiring calls the
            # CrossDomainReader scaffold uncaught. Caught NARROWLY so a
            # genuine test-authoring bug elsewhere is never masked.
            scaffold_error = str(exc)
        except Exception as exc:
            unhandled_exception = f"{type(exc).__name__}: {exc}"

        records: list[dict[str, object]] | None = None
        measured_count: int | None = None
        could_not_verify_count: int | None = None
        could_not_verify_reasons: list[str] | None = None
        if exit_code is not None:
            payload = json.loads(fake.captured_text())
            records = payload["records"]
            measured_count = payload["measured_count"]
            could_not_verify_count = payload["could_not_verify_count"]
            could_not_verify_reasons = payload["could_not_verify_reasons"]

        self._observable = CrossDomainObservable(
            exit_code=exit_code,
            captured_output=fake.captured_text(),
            records=records,
            measured_count=measured_count,
            could_not_verify_count=could_not_verify_count,
            could_not_verify_reasons=could_not_verify_reasons,
            scaffold_error=scaffold_error,
            unhandled_exception=unhandled_exception,
        )

    # --- observable accessors -------------------------------------------

    def observable(self) -> CrossDomainObservable:
        assert self._observable is not None, (
            "read_across must have been driven (When) before an observable is read."
        )
        return self._observable

    def diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "(read_across was never driven)"
        return (
            f"(exit_code={obs.exit_code!r}, scaffold_error={obs.scaffold_error!r}, "
            f"unhandled_exception={obs.unhandled_exception!r}, "
            f"captured={obs.captured_output!r})"
        )


__all__ = ["CrossDomainReaderComposition"]
