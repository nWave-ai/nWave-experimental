"""Derive the acceptance-oracle locator BY CONVENTION -- ``des compile-
contract`` decides where the oracle lives; ATD writes it there, it never
chooses the path (root has no way to obtain that judgment call from ATD
before ATD ever runs, since ATD holds no ``Bash`` and root's compile step
precedes ATD's own dispatch).

Convention: ``<test dir adjacent to the primary EXTEND target>/test_<slug>.py``
-- a Django-shaped project resolves to its app's own ``tests/`` package
(``hc/api/tests/test_maintenance_windows.py``); a flat pytest project falls
back to the repository's own top-level ``tests/`` directory
(``tests/test_<slug>.py``). Neither directory existing is a construction
refusal at the producer (``Blocked``), never a guessed/invented directory.
"""

from __future__ import annotations

from pathlib import Path


def resolve_oracle_test_dir(repo_root: Path, primary_target: str) -> str | None:
    """The POSIX repo-relative test directory this delivery's oracle
    belongs in: the primary EXTEND target's own sibling ``tests/`` when it
    already exists, else the repository's top-level ``tests/`` when THAT
    already exists, else ``None`` (no discoverable convention -- the
    workspace fragment must declare one)."""
    sibling = (Path(primary_target).parent / "tests").as_posix()
    if (repo_root / sibling).is_dir():
        return sibling
    if (repo_root / "tests").is_dir():
        return "tests"
    return None


def oracle_slug(delivery_id: str) -> str:
    """The schema-valid ``delivery-id`` (kebab-case) projected into a
    Python-module-safe slug (snake_case) -- the SAME deterministic
    projection for every caller, never a second ad-hoc naming rule."""
    return delivery_id.replace("-", "_")


def resolve_oracle_locator(
    repo_root: Path, primary_target: str, delivery_id: str
) -> str | None:
    """``<test_dir>/test_<slug>.py``, or ``None`` when no test directory
    convention is discoverable (see ``resolve_oracle_test_dir``)."""
    test_dir = resolve_oracle_test_dir(repo_root, primary_target)
    if test_dir is None:
        return None
    return f"{test_dir}/test_{oracle_slug(delivery_id)}.py"
