"""RC3 (Ale 2026-06-26): INFERRED-floor TTL — read-side GC of a stale guess.

The behaviour, end to end:
  * ``arm_inferred`` stamps ``armed_at`` on the INFERRED floor it writes.
  * ``is_inferred_floor_expired`` retires ONLY an INFERRED floor older than the
    TTL; a COMMAND floor (explicit /nw-<wave>) never expires, and an un-stamped
    INFERRED floor (legacy v1.1) has no TTL basis and stays live.
  * the store round-trips ``armed_at`` (optional key, omitted <=> None) and
    degrades LOUD on a non-numeric value.
  * the two gating reads (service ``arm_inferred`` self-heal + CLI
    ``_read_active_floor``) treat an expired floor as absent.
"""

from __future__ import annotations

import json

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.application.wave_activation_service import WaveActivationService
from des.cli.verify_wave_dispatch import _read_active_floor
from des.domain.wave_active import (
    INFERRED_FLOOR_TTL_SECONDS,
    WaveActiveRecord,
    WaveProvenance,
    is_inferred_floor_expired,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


_FLOOR_REL = ".nwave/wave-active/active.json"


def _inferred(armed_at: float | None) -> WaveActiveRecord:
    return WaveActiveRecord(
        wave="design", provenance=WaveProvenance.INFERRED, armed_at=armed_at
    )


# --- domain helper -------------------------------------------------------


def test_command_floor_never_expires() -> None:
    cmd = WaveActiveRecord(
        wave="design", provenance=WaveProvenance.COMMAND, armed_at=1.0
    )
    assert is_inferred_floor_expired(cmd, now=1e12) is False


def test_unstamped_inferred_floor_never_expires() -> None:
    """A legacy v1.1 INFERRED floor (no armed_at) has no TTL basis -> stays live."""
    assert is_inferred_floor_expired(_inferred(None), now=1e12) is False


def test_inferred_floor_within_ttl_is_live() -> None:
    rec = _inferred(1000.0)
    assert is_inferred_floor_expired(rec, now=1000.0 + INFERRED_FLOOR_TTL_SECONDS) is (
        False
    )


def test_inferred_floor_past_ttl_is_expired() -> None:
    rec = _inferred(1000.0)
    assert (
        is_inferred_floor_expired(rec, now=1000.0 + INFERRED_FLOOR_TTL_SECONDS + 1)
        is True
    )


# --- store round-trip (floor v1.2) --------------------------------------


def test_store_round_trips_armed_at(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    store.arm(tmp_path, _inferred(1234.5))
    read = store.read(tmp_path)
    assert isinstance(read, WaveActiveRecord)
    assert read.armed_at == 1234.5


def test_store_omits_armed_at_when_none(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    store.arm(
        tmp_path, WaveActiveRecord(wave="design", provenance=WaveProvenance.COMMAND)
    )
    payload = json.loads((tmp_path / _FLOOR_REL).read_text())
    assert "armed_at" not in payload  # omitted <=> None


def test_store_degrades_loud_on_non_numeric_armed_at(tmp_path) -> None:
    floor = tmp_path / _FLOOR_REL
    floor.parent.mkdir(parents=True, exist_ok=True)
    floor.write_text(
        json.dumps({"wave": "design", "provenance": "inferred", "armed_at": "soon"})
    )
    assert isinstance(WaveActiveFilesystemStore().read(tmp_path), Indeterminate)


def test_store_degrades_loud_on_bool_armed_at(tmp_path) -> None:
    """A bool is an int subclass — must NOT be coerced into a timestamp."""
    floor = tmp_path / _FLOOR_REL
    floor.parent.mkdir(parents=True, exist_ok=True)
    floor.write_text(
        json.dumps({"wave": "design", "provenance": "inferred", "armed_at": True})
    )
    assert isinstance(WaveActiveFilesystemStore().read(tmp_path), Indeterminate)


# --- service arm_inferred: stamp + self-heal ----------------------------


def test_arm_inferred_stamps_armed_at(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    svc = WaveActivationService(store, store, clock=lambda: 4242.0)
    assert svc.arm_inferred(tmp_path, "design") is True
    read = store.read(tmp_path)
    assert isinstance(read, WaveActiveRecord)
    assert read.armed_at == 4242.0


def test_arm_inferred_self_heals_expired_floor(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    # arm at t=1000 ...
    WaveActivationService(store, store, clock=lambda: 1000.0).arm_inferred(
        tmp_path, "design"
    )
    # ... then a fresh dispatch well past the TTL re-arms (expired = absent).
    later = 1000.0 + INFERRED_FLOOR_TTL_SECONDS + 10
    armed = WaveActivationService(store, store, clock=lambda: later).arm_inferred(
        tmp_path, "deliver"
    )
    assert armed is True
    read = store.read(tmp_path)
    assert isinstance(read, WaveActiveRecord)
    assert read.wave == "deliver"
    assert read.armed_at == later


def test_arm_inferred_noop_on_live_floor(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    WaveActivationService(store, store, clock=lambda: 1000.0).arm_inferred(
        tmp_path, "design"
    )
    # within the TTL a second declaration is a no-op (I3 / not-yet-stale)
    armed = WaveActivationService(store, store, clock=lambda: 1100.0).arm_inferred(
        tmp_path, "deliver"
    )
    assert armed is False
    read = store.read(tmp_path)
    assert isinstance(read, WaveActiveRecord)
    assert read.wave == "design"  # original floor intact


# --- CLI _read_active_floor: expired floor -> None ----------------------


def test_cli_read_floor_drops_expired_inferred(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    store.arm(tmp_path, _inferred(1.0))  # armed in 1970 -> long expired
    assert _read_active_floor(tmp_path) is None


def test_cli_read_floor_keeps_command(tmp_path) -> None:
    store = WaveActiveFilesystemStore()
    store.arm(
        tmp_path,
        WaveActiveRecord(
            wave="design", provenance=WaveProvenance.COMMAND, armed_at=1.0
        ),
    )
    read = _read_active_floor(tmp_path)
    assert isinstance(read, WaveActiveRecord)
    assert read.provenance is WaveProvenance.COMMAND
