"""Meta test for the top-level test-module collection guard.

The guard lives in ``tests/conftest.py`` and refuses to collect test
modules placed at the top level of ``tests/`` (i.e. ``tests/test_*.py``).
The structural rule: top-level modules historically drifted out of sync
with their canonical siblings under ``tests/installer/``, ``tests/des/``,
etc. (e.g. a stale top-level attribution test lacked the isolation
fixture present in its canonical sibling). The 5-tier taxonomy is
enforced rather than merely descriptive.

This meta test exercises the guard by running a sub-pytest collection
against a fixture tests-tree that contains exactly one offending file.
We assert that pytest's exit code signals the failure AND that the error
message points the developer at the 5-tier layout.

It also enforces a complementary structural rule: no two test files
under ``tests/**`` may be byte-identical. The 9 byte-identical pairs
deleted in Track A.1 (commit 04e24f84) escaped the top-level guard
because each pair lived in a tier subdirectory; the duplicates accreted
silently. Detection is content-hash based (md5) and must run on every
``pytest`` invocation.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.xdist_group("collection_guard_meta")


CONFTEST_UNDER_TEST = Path(__file__).resolve().parents[1] / "conftest.py"

# Tests root for the byte-identical-duplicate guard. Resolved once at
# import time so the on-the-real-tree check uses the canonical path.
_TESTS_ROOT = Path(__file__).resolve().parents[1]


def _find_byte_identical_duplicates(tests_root: Path) -> dict[str, list[str]]:
    """Return ``{md5_hex: [rel_path, ...]}`` for groups of >=2 duplicate files.

    Pure function. Walks ``tests_root`` for every ``test_*.py`` (Python
    test module convention), excluding ``__pycache__/`` and dotfile
    directories (``.pytest_cache``, ``.hypothesis``, ``.mypy_cache``).
    Files are hashed with md5 over their raw bytes (cheapest-to-compute
    cryptographic hash; collision-resistance is not the threat model —
    we are detecting copy-paste, not adversarial inputs).

    Result contains ONLY hashes with two or more files. A single-entry
    hash is the normal case and is omitted to keep the result small for
    failure messages. Paths are returned relative to ``tests_root`` and
    sorted, so failure output is deterministic across runs.
    """
    by_hash: dict[str, list[str]] = {}
    for path in tests_root.rglob("test_*.py"):
        # Skip cache directories — they may legitimately contain
        # byte-identical compiled test cache that is not source code.
        if any(
            part in {"__pycache__", ".pytest_cache", ".hypothesis", ".mypy_cache"}
            for part in path.parts
        ):
            continue
        if not path.is_file():
            continue
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        rel = str(path.relative_to(tests_root)).replace("\\", "/")
        by_hash.setdefault(digest, []).append(rel)
    # Filter to groups with collisions and sort each group for stable output.
    return {
        digest: sorted(paths) for digest, paths in by_hash.items() if len(paths) > 1
    }


def _build_fixture_tree(root: Path, *, with_offender: bool) -> None:
    """Create a minimal tests/ tree with the real conftest copied in.

    When ``with_offender`` is True, a top-level ``test_offender.py`` is
    placed directly under ``root``; that's the violation the guard must
    reject. When False, the tree contains only a tier-subdir test, which
    must collect cleanly.
    """
    root.mkdir(parents=True, exist_ok=True)
    # Copy the real conftest verbatim so we exercise the SAME guard.
    (root / "conftest.py").write_text(
        CONFTEST_UNDER_TEST.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Tier-subdir test — must always be collectible.
    tier = root / "unit"
    tier.mkdir()
    (tier / "__init__.py").write_text("")
    (tier / "test_legitimate.py").write_text("def test_smoke():\n    assert True\n")
    if with_offender:
        (root / "test_offender.py").write_text(
            "def test_should_never_collect():\n    assert True\n"
        )


def _run_pytest_collect(rootdir: Path) -> subprocess.CompletedProcess[str]:
    """Run ``pytest --collect-only`` against ``rootdir``. No xdist."""
    # IMPORTANT: subprocess inherits PATH but we want a clean rootdir/ini.
    # We pass ``rootdir`` as the test directory and disable user/global
    # plugins via ``-p no:cacheprovider`` to avoid coupling.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:xdist",
            str(rootdir),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=rootdir,
    )


class TestTopLevelTestModuleGuard:
    """Contract: top-level ``tests/test_*.py`` must fail collection."""

    def test_offending_top_level_module_blocks_collection(self, tmp_path: Path) -> None:
        """A top-level ``test_*.py`` placed directly under the tests root
        must cause pytest collection to fail with a non-zero exit code
        AND a message pointing the developer at the 5-tier layout.
        """
        tests_root = tmp_path / "tests"
        _build_fixture_tree(tests_root, with_offender=True)

        result = _run_pytest_collect(tests_root)

        assert result.returncode != 0, (
            "Pytest collection MUST fail when a top-level test module is "
            f"present. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        combined = result.stdout + result.stderr
        assert "test_offender.py" in combined, (
            f"Guard error must name the offending file. Got: {combined!r}"
        )
        assert "tier subdirectory" in combined, (
            "Guard error must direct the developer to the 5-tier layout. "
            f"Got: {combined!r}"
        )

    def test_clean_tier_subdir_tests_collect(self, tmp_path: Path) -> None:
        """A tree without any top-level test module collects cleanly,
        proving the guard does not over-reach.
        """
        tests_root = tmp_path / "tests"
        _build_fixture_tree(tests_root, with_offender=False)

        result = _run_pytest_collect(tests_root)

        assert result.returncode == 0, (
            "Clean tree must collect successfully; guard must not over-fire. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "test_legitimate" in result.stdout, (
            f"Tier-subdir test must be collected. Got: {result.stdout!r}"
        )


class TestByteIdenticalDuplicateGuard:
    """Contract: no two ``test_*.py`` modules under tests/ may be byte-identical.

    Track A.1 (commit 04e24f84) deleted 9 byte-identical pairs that the
    top-level guard could not detect because they lived in tier
    subdirectories. This guard closes that gap: one md5-keyed pass over
    ``tests/**/test_*.py`` flags any new collisions before they ship.
    """

    def test_distinct_files_produce_no_duplicate_groups(self, tmp_path: Path) -> None:
        """Two files with different content must not be flagged as duplicates."""
        (tmp_path / "test_a.py").write_text("def test_a():\n    assert True\n")
        (tmp_path / "test_b.py").write_text("def test_b():\n    assert True\n")

        result = _find_byte_identical_duplicates(tmp_path)

        assert result == {}, (
            f"Distinct files must not be flagged as duplicates. Got: {result!r}"
        )

    def test_byte_identical_pair_is_detected_with_both_paths(
        self, tmp_path: Path
    ) -> None:
        """Two files with identical bytes must surface as one duplicate group
        listing both relative paths in the failure message.
        """
        sub = tmp_path / "subdir"
        sub.mkdir()
        identical_content = "def test_dup():\n    assert True\n"
        (tmp_path / "test_dup_one.py").write_text(identical_content)
        (sub / "test_dup_two.py").write_text(identical_content)

        result = _find_byte_identical_duplicates(tmp_path)

        assert len(result) == 1, (
            f"Expected exactly one duplicate group. Got: {result!r}"
        )
        (paths,) = result.values()
        assert paths == sorted(["test_dup_one.py", "subdir/test_dup_two.py"]), (
            f"Both offending paths must appear in the duplicate group. Got: {paths!r}"
        )

    def test_real_tests_tree_has_no_byte_identical_duplicates(self) -> None:
        """Regression net: the live ``tests/`` tree must contain no
        byte-identical ``test_*.py`` files.

        Failure means a new duplicate has been introduced — same fix as
        Track A.1: keep the canonical path, delete the duplicate, and
        reference the canonical-path commit in the deletion message.
        """
        duplicates = _find_byte_identical_duplicates(_TESTS_ROOT)

        assert duplicates == {}, (
            "Byte-identical test modules detected under tests/. "
            "Each group below must collapse to one canonical path:\n"
            + "\n".join(
                f"  md5={digest[:8]}: {paths}"
                for digest, paths in sorted(duplicates.items())
            )
        )
