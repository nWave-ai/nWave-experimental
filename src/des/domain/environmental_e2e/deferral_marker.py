"""Environmental-e2e deferral marker -- the L1.7 / fail-mode-D writable side.

Fail-mode D (gate-family-implementation-2026-05-21.md line 899): when the gate
cannot provision a clean prefix to install into (no buildable artifact, no
hermetic install target), the gate writes a per-feature `environmental-e2e-
unverified` marker file and exits with the parse/IO code. The done-gate is
presence-of-proof (principle 13): a hand-`rm` of the marker satisfies "no
unverified block" but NOT "proof exists", so the done-gate still blocks until a
successful gate run lands an `EnvironmentalE2eVerified` ledger record.

Marker-write itself is fail-closed: a write failure surfaces as an exception
the CLI maps to exit 2 (parse/IO). This module provides:

  - `deferral_marker_path(repo_root, feature_id)` -- canonical on-disk path
  - `write_deferral_marker(path, reason)`         -- atomic write; raises on I/O fail

Stdlib-only, no domain dependencies.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


_DEFERRAL_MARKER_DIR = ".nwave/environmental-e2e"


def deferral_marker_path(repo_root: Path, feature_id: str) -> Path:
    """Canonical on-disk path of the deferral marker for ``feature_id``."""
    return repo_root / _DEFERRAL_MARKER_DIR / f"{feature_id}.unverified"


def write_deferral_marker(path: Path, reason: str) -> None:
    """Write the deferral marker atomically; raise on I/O failure (fail-closed).

    The marker carries a short diagnostic line naming why provisioning failed;
    the L1.7 layer treats the marker's presence (not its content) as the
    blocking signal, but the human reader benefits from the named cause.

    Atomic write: tmp file + ``os.replace`` so a crashed write never leaves a
    half-written marker the done-gate might race against. Any I/O failure
    propagates -- the CLI maps the exception to exit 2 (parse/IO).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
        handle.write(f"deferral: {reason}\n")
    Path(tmp_name).replace(path)


__all__ = ["deferral_marker_path", "write_deferral_marker"]
