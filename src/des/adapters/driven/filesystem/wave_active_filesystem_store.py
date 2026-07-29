"""Filesystem adapter for the wave-active store (slice-04, nwave-flow-v2-enforcement).

Implements both driven ports (``WaveActiveReader`` + ``WaveActiveWriter``) over a
single JSON floor file at the DESIGN-PINNED fixed path
``{project_root}/.nwave/wave-active/active.json`` (git-free, Python stdlib only).

The FORMAT + PATH are the design-owned contract (one SSOT shared with the
AT-seed and the reader); only the write MECHANICS (atomic temp-then-rename +
fsync) are this adapter's choice.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from des.domain.wave_active import (
    WAVE_VOCABULARY,
    NoWaveActive,
    WaveActiveRecord,
    WaveProvenance,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.driven_ports.wave_active_store import (
    WaveActiveReader,
    WaveActiveWriter,
)


# DESIGN-PINNED floor location: a single record per project at this fixed
# relative path -- the AT-seed, the writer, and the reader all resolve the
# identical location with no discovery negotiation.
_FLOOR_REL_DIR = (".nwave", "wave-active")
_FLOOR_FILE_NAME = "active.json"

_PROVENANCE_VALUES: frozenset[str] = frozenset(p.value for p in WaveProvenance)


def floor_path(project_root: Path) -> Path:
    """The single floor file's absolute path under ``project_root`` (SSOT).

    Public (no leading underscore) so a REFUSAL that already re-read this same
    file can NAME it rather than re-deriving the ``.nwave/wave-active/
    active.json`` literal a second time (defect-3, docs/mikado/EXECUTION-SSOT-
    des-optimization.md -- "the rifiuto tace su DOVE").
    """
    return project_root.joinpath(*_FLOOR_REL_DIR, _FLOOR_FILE_NAME)


# Back-compat alias: the module previously exposed this helper as private.
# Kept so any external private-name reach-in (none found in this tree at the
# time of the rename) does not silently break.
_floor_path = floor_path


class WaveActiveFilesystemStore(WaveActiveReader, WaveActiveWriter):
    """Single filesystem floor implementing the read/write split contract."""

    def read(
        self, project_root: Path
    ) -> WaveActiveRecord | NoWaveActive | Indeterminate:
        """Read the pinned floor record (degrade-LOUD on corruption)."""
        floor = _floor_path(project_root)
        if not floor.exists():
            return NoWaveActive()
        try:
            payload = json.loads(floor.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return Indeterminate(
                reason=f"wave-active floor {floor} is not readable JSON: {exc!s}"
            )
        if not isinstance(payload, dict):
            return Indeterminate(
                reason=f"wave-active floor {floor} is not a JSON object"
            )
        wave = payload.get("wave")
        if wave not in WAVE_VOCABULARY:
            return Indeterminate(
                reason=(
                    f"wave-active floor {floor} carries wave={wave!r} outside the "
                    f"closed vocabulary {sorted(WAVE_VOCABULARY)!r}"
                )
            )
        provenance = payload.get("provenance")
        if provenance not in _PROVENANCE_VALUES:
            return Indeterminate(
                reason=(
                    f"wave-active floor {floor} carries provenance={provenance!r} "
                    f"outside the closed set {sorted(_PROVENANCE_VALUES)!r}"
                )
            )
        scope = payload.get("scope")
        # Floor v1.1 (slice-07c): optional key, omitted <=> False; a non-bool
        # value is a CORRUPT floor -> Indeterminate (degrade-LOUD, never coerced).
        entry_pending = payload.get("entry_pending", False)
        if not isinstance(entry_pending, bool):
            return Indeterminate(
                reason=(
                    f"wave-active floor {floor} carries a non-bool "
                    f"entry_pending={entry_pending!r} -- corrupt floor "
                    "(floor v1.1: bool or omitted, never coerced)"
                )
            )
        # Floor v1.2 (RC3): optional Unix timestamp, omitted <=> None; a present
        # non-number (or a bool, which is an int subclass) is a CORRUPT floor ->
        # Indeterminate (degrade-LOUD, mirrors entry_pending; never coerced).
        armed_at = payload.get("armed_at")
        if armed_at is not None and (
            isinstance(armed_at, bool) or not isinstance(armed_at, (int, float))
        ):
            return Indeterminate(
                reason=(
                    f"wave-active floor {floor} carries a non-numeric "
                    f"armed_at={armed_at!r} -- corrupt floor "
                    "(floor v1.2: number or omitted, never coerced)"
                )
            )
        return WaveActiveRecord(
            wave=wave,
            provenance=WaveProvenance(provenance),
            scope=scope,
            entry_pending=entry_pending,
            armed_at=float(armed_at) if armed_at is not None else None,
        )

    def arm(self, project_root: Path, record: WaveActiveRecord) -> None:
        """Write the single floor record; I3: INFERRED never clobbers COMMAND."""
        if record.provenance is WaveProvenance.INFERRED:
            existing = self.read(project_root)
            if (
                isinstance(existing, WaveActiveRecord)
                and existing.provenance is WaveProvenance.COMMAND
            ):
                return
        self._atomic_write(project_root, self._serialize(record))

    def clear(self, project_root: Path) -> None:
        """Clear the floor record (idempotent; absent floor = success)."""
        _floor_path(project_root).unlink(missing_ok=True)

    def clear_entry(self, project_root: Path) -> None:
        """Clear ONLY the entry_pending flag (bounded change; idempotent).

        The wave record itself stays armed -- only the flag clears (clear-on-
        allow NORMATIVE, slice-07c). Already-cleared / absent / unreadable
        floor = no-op success (an unclearable flag fails toward MORE
        enforcement: the next dispatch re-runs the idempotent entry gate).
        """
        existing = self.read(project_root)
        if not isinstance(existing, WaveActiveRecord) or not existing.entry_pending:
            return
        cleared = replace(existing, entry_pending=False)
        self._atomic_write(project_root, self._serialize(cleared))

    def probe(self, project_root: Path) -> None:
        """Earned-trust probe: round-trip a COMMAND record + corrupt-floor degrade.

        Writes a COMMAND record to a probe subdirectory, reads it back, asserts
        round-trip + provenance fidelity, then injects a corrupt floor and asserts
        the reader degrades to ``Indeterminate`` (not ``NoWaveActive``). A failed
        probe refuses startup with ``health.startup.refused``.
        """
        probe_root = project_root / ".nwave" / "wave-active" / "_probe"
        probe_root.mkdir(parents=True, exist_ok=True)
        try:
            record = WaveActiveRecord(wave="discuss", provenance=WaveProvenance.COMMAND)
            self.arm(probe_root, record)
            roundtrip = self.read(probe_root)
            if roundtrip != record:
                raise RuntimeError(
                    f"health.startup.refused: wave-active probe round-trip mismatch "
                    f"(wrote {record!r}, read {roundtrip!r})"
                )
            # slice-07d (F4) extension: the fallback path against a floor
            # armed COMMAND -- an INFERRED arm must no-op (I3 dominance
            # verified EMPIRICALLY, not assumed from store docs).
            self.arm(
                probe_root,
                WaveActiveRecord(wave="design", provenance=WaveProvenance.INFERRED),
            )
            after_inferred = self.read(probe_root)
            if after_inferred != record:
                raise RuntimeError(
                    "health.startup.refused: an INFERRED arm over a COMMAND "
                    "floor must be a no-op (I3 dominance); the floor became "
                    f"{after_inferred!r}"
                )
            # slice-07c (floor v1.1) extension: entry_pending round-trip +
            # clear_entry bounded change + non-bool corruption degrade-LOUD.
            pending = WaveActiveRecord(
                wave="discuss",
                provenance=WaveProvenance.COMMAND,
                entry_pending=True,
            )
            self.arm(probe_root, pending)
            pending_read = self.read(probe_root)
            if pending_read != pending:
                raise RuntimeError(
                    "health.startup.refused: entry_pending round-trip mismatch "
                    f"(wrote {pending!r}, read {pending_read!r})"
                )
            self.clear_entry(probe_root)
            cleared_read = self.read(probe_root)
            if (
                not isinstance(cleared_read, WaveActiveRecord)
                or cleared_read.entry_pending
                or cleared_read.wave != pending.wave
            ):
                raise RuntimeError(
                    "health.startup.refused: clear_entry must clear ONLY the "
                    "entry flag and keep the wave record armed (got "
                    f"{cleared_read!r})"
                )
            _floor_path(probe_root).write_text(
                '{"wave": "discuss", "provenance": "command", "entry_pending": "yes"}',
                encoding="utf-8",
            )
            non_bool = self.read(probe_root)
            if not isinstance(non_bool, Indeterminate):
                raise RuntimeError(
                    "health.startup.refused: non-bool entry_pending did not "
                    f"degrade to Indeterminate (got {non_bool!r})"
                )
            _floor_path(probe_root).write_text("{not json", encoding="utf-8")
            corrupt = self.read(probe_root)
            if not isinstance(corrupt, Indeterminate):
                raise RuntimeError(
                    "health.startup.refused: corrupt wave-active floor did not "
                    f"degrade to Indeterminate (got {corrupt!r})"
                )
        finally:
            self.clear(probe_root)

    @staticmethod
    def _serialize(record: WaveActiveRecord) -> dict[str, str | bool | float]:
        payload: dict[str, str | bool | float] = {
            "wave": record.wave,
            "provenance": record.provenance.value,
        }
        if record.scope is not None:
            payload["scope"] = record.scope
        # Floor v1.1: key written only when True (omitted <=> False, mirrors scope).
        if record.entry_pending:
            payload["entry_pending"] = True
        # Floor v1.2 (RC3): key written only when set (omitted <=> None, mirrors scope).
        if record.armed_at is not None:
            payload["armed_at"] = record.armed_at
        return payload

    @staticmethod
    def _atomic_write(
        project_root: Path, payload: dict[str, str | bool | float]
    ) -> None:
        floor = _floor_path(project_root)
        floor.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(floor.parent), suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(floor)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
