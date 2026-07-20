"""Shared git-repo-template provisioning for the ``commit-slice`` test family.

Per ``nw-distill-port-treatment-policy`` §"Shared-provisioning default for
``@real-io``": the real adapter's provisioning (here: ``git init`` + the base
walking-skeleton commit, six real ``git`` subprocess spawns) happens ONCE per
test process, never once per test. Per-test independence is a separate, cheap
concern layered on top: every caller gets its own filesystem copy of the
already-committed template, so no test's mutations (further commits, staged
files, installed hooks, ledger writes under ``.nwave/``) can leak into another
test's repo -- they are different directories on disk from the moment the
test starts touching them.

Motivating evidence (measured 2026-07-19/20, this codebase): the
``test_commit_slice_*`` family re-ran ``git init`` + 3x ``git config`` +
``git add`` + ``git commit`` (six subprocess spawns) inside every single test
function. Building that identical base repo once and handing out
``shutil.copytree`` copies replaces five of those six subprocess spawns per
test with one filesystem copy of a handful of small files.

Safety: the template directory itself is NEVER handed to a test or mutated
after construction -- ``provision_commit_slice_repo`` always copies OUT of it
into the caller-supplied destination. The template's committer identity
(``t@t`` / ``t``) is a fixed constant; no test in this family asserts on
committer name/email, only on commit MESSAGE trailers and file content, so
unifying every call site onto one shared identity is behavior-preserving.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import tempfile
from pathlib import Path


_TEMPLATE_DIR: Path | None = None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _build_template() -> Path:
    """Build the canonical base repo ONCE: git init + one committed file tree.

    Byte-shape mirrors the ``_init_repo`` helper duplicated (verbatim, per
    each file's own docstring) across the ``test_commit_slice_*`` family:
    a git work-tree with ``tests/unit/test_base.py``, a ``conftest.py`` that
    auto-marks collected items ``unit``, and a ``pytest.ini`` declaring the
    three DES markers -- committed as ``"base: walking skeleton"``.
    """
    root = Path(tempfile.mkdtemp(prefix="commit_slice_git_template_"))
    atexit.register(shutil.rmtree, root, True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into hook-count tests.
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")
    return root


def provision_commit_slice_repo(dest: Path) -> None:
    """Materialize an independent copy of the shared base repo at ``dest``.

    The base repo (six real ``git`` subprocess spawns) is built lazily, once
    per process, and cached. Every call after the first replaces those six
    spawns with a single ``shutil.copytree`` -- a plain filesystem copy of a
    handful of small files, including ``.git``. ``dest`` must not already
    exist (mirrors ``shutil.copytree`` default semantics, and matches every
    call site's actual usage: a fresh ``tmp_path / "repo"`` per test).
    """
    global _TEMPLATE_DIR
    if _TEMPLATE_DIR is None:
        _TEMPLATE_DIR = _build_template()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_TEMPLATE_DIR, dest)
