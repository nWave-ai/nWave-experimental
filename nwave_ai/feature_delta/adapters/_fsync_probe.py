"""Shared fsync-and-readback probe for filesystem-writing adapters.

DD-A5 (overlayfs/network-fs lie probe): a filesystem that silently discards
writes must be detected at startup, not at first real write. This helper
encapsulates the canonical sequence used by both RealFileSystemWriter and
MigrationDriver: write a known payload, fsync, read back, assert byte-equal.

Extracted 2026-05-03 to eliminate duplicated probe() bodies between
adapters/filesystem.py and adapters/migration.py (RPP L3).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def fsync_probe(probe_content: bytes, suffix: str = ".probe") -> None:
    """Write `probe_content` to a tempfile, fsync, read back, assert byte-equal.

    Args:
        probe_content: The bytes payload to round-trip through the filesystem.
        suffix: Extension for the temp file (purely cosmetic — visible in
            error logs of monitoring tools that scan tmpdir).

    Raises:
        RuntimeError: if the read-back content differs from `probe_content`,
            indicating overlayfs / network-fs / dirty-cache silent corruption.
        OSError: if the temp directory is unwritable (filesystem unhealthy).
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(probe_content)
        tmp.flush()
        os.fsync(tmp.fileno())

    try:
        read_back = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    if read_back != probe_content:
        raise RuntimeError(
            f"Filesystem probe failed: wrote {len(probe_content)} bytes, "
            f"read back {len(read_back)} bytes. "
            "Possible overlayfs or network filesystem inconsistency."
        )
