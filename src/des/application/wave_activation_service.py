"""WaveActivationService -- application-side holder of Reader+Writer at the
PreToolUse seam (slice-07c, nwave-flow-v2-enforcement).

SHAPE per DESIGN feature-delta § slice-07c code-design (F3 NORMATIVO): the hook
adapter peeks the anchor-owned ``entry_pending`` flag (the deterministic
wave-entering signal -- never prompt wording) through this collaborator and
clears it ONLY after the gate allows the entering dispatch (clear-on-allow
NORMATIVE). The slice-04 design reserved the floor writer for "the submission
adapter + the PreToolUse fallback" -- this is that collaborator, named.

Asymmetric authority preserved (§22.0): ``PreToolUseService`` itself stays
writer-free; only this service (held by the ADAPTER, never the veto path)
writes. slice-07d EXTENDS it with ``arm_inferred``.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING

from des.domain.wave_active import (
    WAVE_VOCABULARY,
    NoWaveActive,
    WaveActiveRecord,
    WaveProvenance,
    is_inferred_floor_expired,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.ports.driven_ports.wave_active_store import (
        WaveActiveReader,
        WaveActiveWriter,
    )


class ClearFloorOutcome(Enum):
    """The observable outcome of a sanctioned ``clear_floor`` over the floor state.

    The closed set the operator-facing ``des wave-clear`` CLI maps to exit codes:
      * ``CLEARED`` -- a record was present and removed (loud + audited).
      * ``NOOP_SUCCESS`` -- the floor was absent; an idempotent no-op (audited).
      * ``INDETERMINATE`` -- the floor was corrupt/unreadable; the clear refuses
        rather than fabricate success (degrade-LOUD, never silent-pass).
    """

    CLEARED = "CLEARED"
    NOOP_SUCCESS = "NOOP_SUCCESS"
    INDETERMINATE = "INDETERMINATE"


class WaveActivationService:
    """Peeks + clears the anchor-owned wave-entry flag over the wave-active floor."""

    def __init__(
        self,
        reader: WaveActiveReader,
        writer: WaveActiveWriter,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._reader = reader
        self._writer = writer
        # RC3: the time source for the INFERRED-floor TTL (default: wall clock;
        # tests inject a fake). Wall-clock seconds, never git/external tooling.
        self._clock = clock

    def peek_entry(self, project_root: Path) -> bool | Indeterminate:
        """True iff an armed wave's entry is still pending (floor v1.1, F3).

        ``NoWaveActive`` -> False (no entry to gate). ``Indeterminate`` ->
        propagated (degrade-LOUD, §17 -- a corrupt floor is never coerced to a
        bool).
        """
        state = self._reader.read(project_root)
        if isinstance(state, WaveActiveRecord):
            return state.entry_pending
        if isinstance(state, Indeterminate):
            return state
        return False

    def clear_entry(self, project_root: Path) -> None:
        """Clear the entry flag (clear-on-allow; bounded change, idempotent)."""
        self._writer.clear_entry(project_root)

    def clear_floor(self, project_root: Path) -> ClearFloorOutcome:
        """Clear the whole wave-active floor (the sanctioned operator clear).

        Reuses the shipped ``WaveActiveWriter.clear`` -- the CLI is its first
        consumer (D11 dormant-seam). Classifies the floor first so the operator
        sees a TRUTHFUL outcome:

          * a record present -> ``WaveActiveWriter.clear`` removes it ->
            ``CLEARED``.
          * ``NoWaveActive`` -> nothing to remove -> idempotent ``NOOP_SUCCESS``.
          * ``Indeterminate`` (corrupt/unreadable floor) -> ``INDETERMINATE``;
            the corrupt floor is NOT removed (degrade-LOUD, §17 -- never coerce a
            read failure into a fabricated success).
        """
        state = self._reader.read(project_root)
        if isinstance(state, Indeterminate):
            return ClearFloorOutcome.INDETERMINATE
        if isinstance(state, NoWaveActive):
            return ClearFloorOutcome.NOOP_SUCCESS
        self._writer.clear(project_root)
        return ClearFloorOutcome.CLEARED

    def arm_inferred(
        self, project_root: Path, declared_wave: str
    ) -> bool | Indeterminate:
        """Arm the declared wave with INFERRED provenance (slice-07d, F4).

        The fallback strand: a wave-DECLARING dispatch on an empty floor arms
        enforcement by itself (the submission anchor never fired -- S2
        cross-runtime closure). Vocabulary validation happens HERE (the USE
        site): an out-of-vocabulary declaration is treated as absent -> no
        arm, no garbage record (K2/S1).

          * reader ``NoWaveActive`` + declared_wave in ``WAVE_VOCABULARY`` ->
            write ``WaveActiveRecord(declared_wave, INFERRED,
            entry_pending=False)`` -> True. ``entry_pending`` stays False:
            arm and gate-IN coincide in the SAME PreToolUse pass (self-entry
            NORMATIVE) -- no cross-event channel, no stale pending state.
          * a record already armed -> no-op False (I3: INFERRED never
            clobbers COMMAND; the filesystem store enforces it again,
            defence-in-depth).
          * reader ``Indeterminate`` -> propagated (degrade-LOUD, S17 --
            never arm over a corrupt floor).
        """
        if declared_wave not in WAVE_VOCABULARY:
            return False
        state = self._reader.read(project_root)
        if isinstance(state, Indeterminate):
            return state
        # A live record blocks re-arm (I3: INFERRED never clobbers COMMAND). RC3:
        # an EXPIRED inferred floor is a stale guess -> treated as absent, so the
        # fallback re-arms fresh (self-heal). A COMMAND floor never expires.
        if isinstance(state, WaveActiveRecord) and not is_inferred_floor_expired(
            state, self._clock()
        ):
            return False
        self._writer.arm(
            project_root,
            WaveActiveRecord(
                wave=declared_wave,
                provenance=WaveProvenance.INFERRED,
                entry_pending=False,
                armed_at=self._clock(),
            ),
        )
        return True
