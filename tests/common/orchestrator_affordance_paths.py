"""Rename-proof resolver for shipped ``nWave/data/orchestrator-affordance/*.md``
assets.

Commit 5b3878878 renamed all three shipped assets to encode injection order
(the loader is ``sorted(assets_dir.glob("*.md"))``):

    spine-discipline.md    -> 00-spine-discipline.md
    des-command-catalog.md -> 10-des-command-catalog.md
    00-standing-loops.md   -> 50-standing-loops.md

The numeric prefix is EXPECTED to change again as injection order is
retuned -- a test that hardcodes today's prefix (e.g. ``50-standing-loops.md``)
is the same dangling-citation defect with a new date. Resolve a single named
asset by globbing on its ROLE-BEARING STEM instead (e.g. ``"spine-discipline"``,
``"des-command-catalog"``, ``"standing-loops"``).

Shared by ``tests/bugs/des`` and ``tests/des/acceptance`` -- both already
import from ``tests.common`` (see ``tests/common/in_process_cli.py``,
``tests/common/state_delta.py``), so this lives alongside them rather than
duplicated per tree.
"""

from __future__ import annotations

from pathlib import Path


_ASSET_DIR_PARTS = ("nWave", "data", "orchestrator-affordance")


def affordance_assets_dir(repo_root: Path) -> Path:
    """The shipped orchestrator-affordance directory under ``repo_root``."""
    return repo_root.joinpath(*_ASSET_DIR_PARTS)


def resolve_affordance_asset(repo_root: Path, stem: str) -> Path:
    """Resolve a shipped orchestrator-affordance asset by ROLE STEM, never a
    hardcoded numeric-prefixed basename.

    WHAT: globs ``*<stem>.md`` inside ``nWave/data/orchestrator-affordance/``.
    WHY: the numeric prefix encodes injection order and churns by design
    (mikado D50 rename) -- pinning today's prefix in a citation is exactly
    the dangling-citation defect this resolver exists to prevent.
    HOW on failure: refuses LOUD (never ``IndexError``/``StopIteration``/a
    silent skip) naming the directory searched, the pattern used, and what
    was actually found there.
    """
    directory = affordance_assets_dir(repo_root)
    pattern = f"*{stem}.md"
    matches = sorted(directory.glob(pattern))
    if len(matches) == 1:
        return matches[0]
    all_present = sorted(p.name for p in directory.glob("*.md"))
    raise AssertionError(
        f"WHAT: expected exactly ONE file matching {pattern!r} in "
        f"{directory}, found {len(matches)} ({[m.name for m in matches]!r}). "
        "WHY: orchestrator-affordance asset basenames carry a numeric "
        "injection-order prefix (mikado D50) that is EXPECTED to change -- "
        f"a caller must resolve by role stem, not a literal basename. "
        f"Directory currently contains: {all_present!r}. "
        f"HOW: confirm the asset ships with a unique role-bearing stem "
        f"{stem!r} inside {directory}; if its role name changed, update the "
        "caller's stem argument to match."
    )


def affordance_asset_names(repo_root: Path) -> set[str]:
    """Independent filesystem read of the real shipped basenames -- the
    other side of a genuine two-source comparison (vs. an emitted ledger /
    ``docgen.scan`` output), never a literal name list that would go stale
    the next time the injection-order prefix churns.
    """
    return {p.name for p in affordance_assets_dir(repo_root).glob("*.md")}
