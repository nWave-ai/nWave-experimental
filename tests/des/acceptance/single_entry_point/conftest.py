"""Top-level conftest for the single-entry-point acceptance suite.

Per-feature acceptance fixtures live here when needed. Step modules in
`steps/` are imported by the slice binder test modules at the feature
directory level (e.g. `test_slice_01.py`), NOT here — pytest-bdd's
`scenarios(...)` call must execute under an active pytest config stack.

Parallel-load pinning: this suite drives real-repo-tree rglob scans /
``cwd=<real repo>`` subprocesses over the ``AtCompletionLedger`` substrate.
Under the contract gate's ``-n auto --dist loadgroup`` those scans race
across workers non-deterministically. The collection hook pins every item
here to the ``real_repo_scan`` xdist_group so they run on ONE worker
(``run_contract_gate``'s prescribed design at ``_parallel_pytest_args``).
"""

from __future__ import annotations

from pathlib import Path

import pytest


_SUITE_DIR = Path(__file__).parent


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Pin every item in this suite to the ``real_repo_scan`` xdist worker group.

    Prevents spurious cross-worker races on the shared real-repo-tree
    substrate under ``--dist loadgroup``. NOT masking -- the tests run
    honestly, just serialized within one worker.

    Scoped to this suite via ``_belongs_to_this_suite``: a non-root
    ``pytest_collection_modifyitems`` receives EVERY session item, not only
    those under this directory. Without the guard this hook pinned the whole
    suite onto one worker (a latent over-serialization). The root conftest's
    generic detector handles every other cwd=<real repo> suite.
    """
    group = pytest.mark.xdist_group("real_repo_scan")
    for item in items:
        if _belongs_to_this_suite(item):
            item.add_marker(group)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
