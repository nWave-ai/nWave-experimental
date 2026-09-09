"""Per-test `.nwave` ROOT resolver (DDD-14, slice-05 of sustainable-test-suite).

PARALLELISM RESTORATION. The full suite was forced SERIAL (`-n0`) because tests
share `.nwave/` state via `Path.cwd()` when cwd=repo: a stale wave floor in
`.nwave/wave-active/active.json` (and other per-test `.nwave` writes) read off
`Path.cwd()` by production `WaveActiveReader`/`pre_tool_use_handler` contaminate
cross-test under `-n auto` (xdist workers share the repo cwd). The cure is per-test
`.nwave` ROOT isolation: each test resolves its OWN `.nwave` root under a per-test
tmp dir (via an explicit `DES_PROJECT_DIR` override the autouse fixture in
`tests/conftest.py` sets), so NO shared `Path.cwd()/.nwave` is touched and `-n auto`
passes GREEN where serial was masking the interference.

Boundary (DDD-14, 2026-06-22): a PURE domain function — reads `DES_PROJECT_DIR`
(process-memory) then falls back to `Path.cwd()` (`getcwd(2)`) and returns a `Path`;
zero writes/mutation/external-system, so NO driven port (the port pattern is for I/O
boundaries). Mirrors the proven pure-domain sibling
`src/des/domain/repo_path_resolver.py::resolve_repo_root`.
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_nwave_root() -> Path:
    """Return the active `.nwave` root for the current process.

    Prefer the ``DES_PROJECT_DIR`` env override (the per-test tmp dir the isolation
    fixture sets) over the shared repo ``Path.cwd()``, so each test resolves a
    per-test isolated `.nwave` root. With no override the shared repo cwd is the
    layout-independent fallback (the un-isolated status).
    """
    override = os.environ.get("DES_PROJECT_DIR")
    if override:
        return Path(override)
    return Path.cwd()
