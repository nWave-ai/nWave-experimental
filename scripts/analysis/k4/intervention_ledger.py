"""Create-only, hash-chained evidence ledger for diagnostic interventions.

The ledger is a directory of immutable records: ``open.json``, one exclusive
file per event, and ``close.json``. A diagnostic ledger never produces a
comparison result. Bad lifecycle or chain evidence is ``INDETERMINATE``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Mapping


_OPEN_FILE = "open.json"
_CLOSE_FILE = "close.json"
_EVENTS_DIR = "events"
_EVENT_NAME = re.compile(r"^(?P<sequence>[0-9]{6})-(?P<hash>[0-9a-f]{64})\.json$")


def sha256_file(path: Path) -> str:
    """Return a content hash without replacing an unreadable path with a guess."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(record: dict[str, object]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _record_hash(record: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(record)).hexdigest()


def _exclusive_json(path: Path, record: dict[str, object]) -> None:
    """Write one record once. Existing evidence is never overwritten."""
    _publish_no_replace(path, _canonical(record) + b"\n")


def _write_all(descriptor: int, raw: bytes) -> None:
    written = 0
    while written < len(raw):
        count = os.write(descriptor, raw[written:])
        if count <= 0:
            raise OSError("could not write complete ledger record")
        written += count


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_no_replace(path: Path, raw: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, path)
        _sync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _load_record(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    try:
        loaded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{path} is not canonical JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} is not an object")
    if raw != _canonical(loaded) + b"\n":
        raise ValueError(f"{path} is not canonical")
    return loaded


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _unsigned(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if key != "hash"}


def _valid_hash(record: dict[str, object]) -> bool:
    stored = record.get("hash")
    return isinstance(stored, str) and stored == _record_hash(_unsigned(record))


@dataclass(frozen=True)
class LedgerVerification:
    classification: str
    problems: tuple[str, ...] = ()

    @property
    def is_indeterminate(self) -> bool:
        return self.classification == "INDETERMINATE"


class InterventionLedger:
    """One directory-backed, append-only diagnostic chain."""

    def __init__(self, root: Path):
        self.root = root
        self.events = root / _EVENTS_DIR
        self._closed = (root / _CLOSE_FILE).exists()

    @classmethod
    def create(
        cls, root: Path, *, bound_instruments: Mapping[str, Path]
    ) -> InterventionLedger:
        """Create a new ledger and bind the exact readable instruments."""
        if root.exists():
            raise FileExistsError(f"ledger destination already exists: {root}")
        instruments: dict[str, dict[str, str]] = {}
        for name, path in sorted(bound_instruments.items()):
            resolved = path.resolve()
            if not resolved.is_file():
                raise FileNotFoundError(f"bound instrument is not a file: {resolved}")
            instruments[name] = {"path": str(resolved), "sha256": sha256_file(resolved)}
        root.mkdir(parents=True)
        (root / _EVENTS_DIR).mkdir()
        ledger = cls(root)
        ledger._write_open(instruments)
        return ledger

    def _write_open(self, instruments: dict[str, dict[str, str]]) -> None:
        unsigned: dict[str, object] = {
            "sequence": 0,
            "kind": "open",
            "previous_hash": None,
            "payload": {"bound_instruments": instruments},
        }
        unsigned["hash"] = _record_hash(unsigned)
        _exclusive_json(self.root / _OPEN_FILE, unsigned)

    def event(self, kind: str, **payload: object) -> None:
        if self._closed or (self.root / _CLOSE_FILE).exists():
            self._closed = True
            raise RuntimeError("ledger is closed; events cannot follow close")
        if kind in {"open", "close"}:
            raise ValueError(f"{kind!r} is reserved for the ledger lifecycle")
        open_record, events = _read_chain_prefix(self.root)
        sequence = len(events) + 1
        previous = events[-1].get("hash") if events else open_record.get("hash")
        unsigned: dict[str, object] = {
            "sequence": sequence,
            "kind": kind,
            "previous_hash": previous,
            "payload": dict(payload),
        }
        event_hash = _record_hash(unsigned)
        unsigned["hash"] = event_hash
        _exclusive_json(self.events / f"{sequence:06d}-{event_hash}.json", unsigned)

    def close(self, *, classification: str) -> LedgerVerification:
        """Close once, checking bound bytes at this instant only."""
        if self._closed or (self.root / _CLOSE_FILE).exists():
            self._closed = True
            raise RuntimeError("ledger is already closed")
        if classification not in {"DIAGNOSTIC", "INDETERMINATE"}:
            raise ValueError(
                "diagnostic ledgers may only close DIAGNOSTIC or INDETERMINATE"
            )
        open_record, events = _read_chain_prefix(self.root)
        instruments = _bound_instruments(open_record)
        observed: dict[str, dict[str, str]] = {}
        changed = False
        for name, evidence in instruments.items():
            path, expected = evidence["path"], evidence["sha256"]
            try:
                actual = sha256_file(Path(path))
            except OSError:
                actual = "UNAVAILABLE"
            status = "UNCHANGED" if actual == expected else "CHANGED"
            observed[name] = {
                "expected_sha256": expected,
                "actual_sha256": actual,
                "status": status,
            }
            changed = changed or status != "UNCHANGED"
        final_classification = "INDETERMINATE" if changed else classification
        sequence = len(events) + 1
        previous = events[-1].get("hash") if events else open_record.get("hash")
        unsigned: dict[str, object] = {
            "sequence": sequence,
            "kind": "close",
            "previous_hash": previous,
            "payload": {
                "classification": final_classification,
                "instrument_check": observed,
            },
        }
        unsigned["hash"] = _record_hash(unsigned)
        _exclusive_json(self.root / _CLOSE_FILE, unsigned)
        self._closed = True
        return verify(self.root)


def _read_chain_prefix(root: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    open_record = _load_record(root / _OPEN_FILE)
    event_dir = root / _EVENTS_DIR
    if not event_dir.is_dir():
        raise ValueError("ledger events directory is missing")
    events: list[dict[str, object]] = []
    for path in sorted(event_dir.iterdir()):
        matched = _EVENT_NAME.fullmatch(path.name)
        if not matched or not path.is_file():
            raise ValueError(f"invalid ledger event path: {path.name}")
        record = _load_record(path)
        if record.get("hash") != matched.group("hash"):
            raise ValueError(f"event filename hash mismatch: {path.name}")
        events.append(record)
    return open_record, events


def _bound_instruments(open_record: dict[str, object]) -> dict[str, dict[str, str]]:
    payload = open_record.get("payload")
    raw = payload.get("bound_instruments") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("open event lacks bound instruments")
    instruments: dict[str, dict[str, str]] = {}
    for name, evidence in raw.items():
        if not isinstance(name, str) or not isinstance(evidence, dict):
            raise ValueError("invalid bound instrument")
        path, digest = evidence.get("path"), evidence.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError("invalid bound instrument")
        instruments[name] = {"path": path, "sha256": digest}
    return instruments


def verify(root: Path) -> LedgerVerification:
    """Verify stored records without rereading mutable bound instruments."""
    try:
        open_record, events = _read_chain_prefix(root)
        close_record = _load_record(root / _CLOSE_FILE)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return LedgerVerification("INDETERMINATE", (f"unreadable ledger: {exc}",))
    problems: list[str] = []
    records = [open_record, *events, close_record]
    for sequence, record in enumerate(records):
        if record.get("sequence") != sequence:
            problems.append(f"sequence gap at event {sequence}")
        expected_kind = (
            "open"
            if sequence == 0
            else "close"
            if sequence == len(records) - 1
            else None
        )
        if expected_kind is not None and record.get("kind") != expected_kind:
            problems.append(f"invalid lifecycle event at {sequence}")
        previous = records[sequence - 1].get("hash") if sequence else None
        if record.get("previous_hash") != previous:
            problems.append(f"previous hash mismatch at event {sequence}")
        if not _valid_hash(record):
            problems.append(f"hash mismatch at event {sequence}")
    if any(event.get("kind") in {"open", "close"} for event in events):
        problems.append("invalid lifecycle event in events directory")
    if any(
        event.get("sequence", 0) >= close_record.get("sequence", 0) for event in events
    ):
        problems.append("event follows close")
    close_payload = close_record.get("payload")
    classification = (
        close_payload.get("classification") if isinstance(close_payload, dict) else None
    )
    try:
        bound = _bound_instruments(open_record)
        close_payload = close_record.get("payload")
        checked = (
            close_payload.get("instrument_check")
            if isinstance(close_payload, dict)
            else None
        )
        if not isinstance(checked, dict):
            problems.append("close event lacks instrument check")
        else:
            for name, evidence in bound.items():
                check = checked.get(name)
                if (
                    not isinstance(check, dict)
                    or check.get("expected_sha256") != evidence["sha256"]
                ):
                    problems.append(f"close instrument check mismatch: {name}")
                    continue
                if check.get("status") not in {"UNCHANGED", "CHANGED"}:
                    problems.append(f"invalid close instrument status: {name}")
                if (
                    check.get("status") == "UNCHANGED"
                    and check.get("actual_sha256") != evidence["sha256"]
                ):
                    problems.append(f"close instrument bytes mismatch: {name}")
                if (
                    check.get("status") == "CHANGED"
                    and check.get("actual_sha256") == evidence["sha256"]
                ):
                    problems.append(f"close instrument status mismatch: {name}")
                if (
                    classification == "DIAGNOSTIC"
                    and check.get("status") != "UNCHANGED"
                ):
                    problems.append(f"bound instrument changed at close: {name}")
    except ValueError as exc:
        problems.append(str(exc))
    if classification not in {"DIAGNOSTIC", "INDETERMINATE"}:
        problems.append("invalid close classification")
    if problems:
        return LedgerVerification("INDETERMINATE", tuple(problems))
    return LedgerVerification(classification)


def read_closed_records(
    root: Path, *, require_closed: bool = True
) -> tuple[dict[str, object], ...]:
    """Read one verified ledger chain without rereading mutable instruments.

    D0 uses the open chain before close only to select its close classification;
    every public attribution decision uses the closed form.
    """
    if require_closed:
        verification = verify(root)
        if verification.is_indeterminate:
            raise ValueError(
                "ledger verification failed: " + "; ".join(verification.problems)
            )
        open_record, events = _read_chain_prefix(root)
        return (open_record, *events, _load_record(root / _CLOSE_FILE))
    open_record, events = _read_chain_prefix(root)
    return (open_record, *events)


def open_ledger(
    root: Path, *, bound_instruments: Mapping[str, Path]
) -> InterventionLedger:
    """Public verb form for callers that prefer lifecycle names."""
    return InterventionLedger.create(root, bound_instruments=bound_instruments)
