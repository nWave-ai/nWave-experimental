"""Wave-active store driven ports (slice-04, nwave-flow-v2-enforcement).

READ/WRITE SPLIT (principle 12: a reader must not expose writes). Two ABCs over
one filesystem floor (git-free, Python-only). SHAPE per DESIGN feature-delta
§ slice-04 code-design.

Asymmetric authority (§22.0): ``PreToolUseService`` consumes ONLY
``WaveActiveReader`` -- the type system forbids it from arming/clearing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.wave_active import NoWaveActive, WaveActiveRecord
    from des.ports.driven_ports.committed_scope_port import Indeterminate


class WaveActiveReader(ABC):
    """Driven, read-only port over the wave-active floor (pure-function shape)."""

    @abstractmethod
    def read(
        self, project_root: Path
    ) -> WaveActiveRecord | NoWaveActive | Indeterminate:
        """Return the armed record, ``NoWaveActive`` (absent), or ``Indeterminate``.

        Absent state -> ``NoWaveActive`` (NOT raise -- S1 is normal). Unreadable /
        corrupt floor -> degrade-LOUD ``Indeterminate`` (NEVER fabricate
        ``NoWaveActive`` masking a read failure).
        """
        ...


class WaveActiveWriter(ABC):
    """Driven, write port over the wave-active floor (bounded-change shape)."""

    @abstractmethod
    def arm(self, project_root: Path, record: WaveActiveRecord) -> None:
        """Write the single wave-active floor record (bounded-change).

        I3 dominance: an INFERRED arm is a no-op when a COMMAND record already
        exists. A write outside the floor path raises (fail-closed).
        """
        ...

    @abstractmethod
    def clear(self, project_root: Path) -> None:
        """Clear the floor record. Idempotent; absent floor = success."""
        ...

    @abstractmethod
    def clear_entry(self, project_root: Path) -> None:
        """Clear ONLY the ``entry_pending`` flag (slice-07c, floor v1.1).

        Bounded change: the wave record itself stays armed on the same single
        floor file -- only the flag clears (clear-on-allow NORMATIVE).
        Idempotent: already-cleared / absent floor = success.
        """
        ...
