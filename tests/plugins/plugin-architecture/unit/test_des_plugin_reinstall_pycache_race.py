"""Regression tests for reinstall-over-an-active-runtime ENOTEMPTY race (#43).

Reinstalling nWave over a live runtime fails with
``OSError: [Errno 39] Directory not empty: '.../__pycache__'`` and leaves a
PARTIAL DES plugin install. ``shutil.rmtree`` raises ``ENOTEMPTY`` only when a
directory is concurrently modified during its removal walk: a live Python
process importing the INSTALLED ``des`` module writes fresh bytecode into a
``__pycache__`` subdir WHILE the installer's ``rmtree`` is removing the old
module tree, so the walk hits a directory that just gained a new entry.

Two racing loci in ``scripts/install/plugins/des_plugin.py``:

- ``_install_des_module`` (module replace, ~L496): ``shutil.rmtree(target_dir)``
  removes the old module tree before ``copytree`` lands the new one.
- ``_clear_bytecode_cache`` (~L713-715): removes each ``__pycache__`` found
  under the freshly-copied module; a concurrent writer racing the SAME
  directory hits the identical error shape.

The race is simulated deterministically -- no real concurrency -- by
monkeypatching ``shutil.rmtree`` (as seen from ``des_plugin``) to raise
``ENOTEMPTY`` on the first call against the racing path, then behave
normally afterward (a retry, or a call against a different/renamed path,
succeeds). This pins the exact ``OSError`` shape a concurrent writer produces
without depending on timing.
"""

import errno
import logging
import shutil
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.des_plugin_reinstall_pycache_race")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def plugin() -> DESPlugin:
    """Provide a fresh DESPlugin instance."""
    return DESPlugin()


@pytest.fixture
def isolated_project_root(tmp_path: Path, shared_des_source: Path) -> Path:
    """Isolated project root exposing only ``src/des`` (symlink to the shared copy).

    ``_install_des_module`` / ``_clear_bytecode_cache`` are driven directly, so
    only the module source needs to be present -- no scripts/templates.
    """
    root = tmp_path / "isolated_project"
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "des").symlink_to(shared_des_source)
    return root


@pytest.fixture
def install_context(
    tmp_path: Path, isolated_project_root: Path, test_logger: logging.Logger
) -> InstallContext:
    """Create InstallContext with a temporary claude_dir and isolated project."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=isolated_project_root / "scripts" / "install",
        templates_dir=isolated_project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=isolated_project_root,
        framework_source=None,
        dry_run=False,
    )


@pytest.fixture
def install_context_with_existing_module(
    install_context: InstallContext,
) -> InstallContext:
    """InstallContext where lib/python/des already holds a stale __pycache__.

    Simulates a reinstall-over-an-active-runtime: a previous install left a
    module tree on disk, including bytecode caches, before the new install
    starts (mirrors L495: ``if target_dir.exists(): shutil.rmtree(target_dir)``).
    """
    target_dir = install_context.claude_dir / "lib" / "python" / "des"
    stale_cache = target_dir / "domain" / "__pycache__"
    stale_cache.mkdir(parents=True, exist_ok=True)
    (stale_cache / "phase_event.cpython-312.pyc").write_bytes(b"stale-bytecode")
    (target_dir / "__init__.py").write_text("# stale previous install\n")
    return install_context


def _racing_rmtree(racing_path: Path, real_rmtree=shutil.rmtree):
    """Build a ``shutil.rmtree`` stand-in raising ENOTEMPTY once for ``racing_path``.

    First call against ``racing_path`` raises ``OSError(ENOTEMPTY, ...)`` --
    the shape a concurrent writer produces. Every other call (a retry against
    the same path, a call against a different/renamed path, or any other
    directory) delegates to the real ``shutil.rmtree``.
    """
    raised_for: list[Path] = []

    def fake_rmtree(path, *args, **kwargs):
        candidate = Path(path)
        if candidate == racing_path and candidate not in raised_for:
            raised_for.append(candidate)
            raise OSError(errno.ENOTEMPTY, "Directory not empty", str(candidate))
        return real_rmtree(path, *args, **kwargs)

    return fake_rmtree


# -----------------------------------------------------------------------------
# Locus 1 -- _install_des_module (L496 module replace)
# -----------------------------------------------------------------------------


class TestInstallDesModuleSurvivesRacingPycache:
    """The module-copy step must be resilient to a racing __pycache__ ENOTEMPTY."""

    def test_install_des_module_survives_enotempty_from_racing_pycache(
        self,
        plugin: DESPlugin,
        install_context_with_existing_module: InstallContext,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A concurrent-writer race on the old module's __pycache__ must not
        abort the module replace (issue #43).

        RED at HEAD: the raw ENOTEMPTY from L496's ``shutil.rmtree(target_dir)``
        propagates uncaught out of the rmtree call, is caught by
        ``_install_des_module``'s own try/except, and surfaces as
        ``result.success is False`` -- the copy never happens, leaving a
        partial install.
        """
        target_dir = (
            install_context_with_existing_module.claude_dir / "lib" / "python" / "des"
        )
        assert target_dir.exists(), "fixture must pre-seed a stale module tree"

        monkeypatch.setattr(
            "scripts.install.plugins.des_plugin.shutil.rmtree",
            _racing_rmtree(target_dir),
        )

        result = plugin._install_des_module(install_context_with_existing_module)

        assert result.success, (
            "Module copy must survive a racing ENOTEMPTY on the old module's "
            f"__pycache__ (issue #43), got: {result.message}"
        )
        assert (target_dir / "__init__.py").exists(), "new module tree must land"
        assert (target_dir / "application").exists(), (
            "new module tree must fully replace the stale one"
        )

    def test_install_des_module_copies_cleanly_without_race(
        self,
        plugin: DESPlugin,
        install_context_with_existing_module: InstallContext,
    ):
        """Guard: a normal (non-racing) reinstall still replaces the module tree."""
        target_dir = (
            install_context_with_existing_module.claude_dir / "lib" / "python" / "des"
        )

        result = plugin._install_des_module(install_context_with_existing_module)

        assert result.success, result.message
        assert (target_dir / "__init__.py").exists()
        assert (target_dir / "application").exists()


# -----------------------------------------------------------------------------
# Locus 2 -- _clear_bytecode_cache (L713-715)
# -----------------------------------------------------------------------------


class TestClearBytecodeCacheSurvivesRacingPycache:
    """Bytecode-cache clearing must not propagate a racing __pycache__ ENOTEMPTY."""

    def test_clear_bytecode_cache_does_not_propagate_enotempty_from_a_racing_pycache(
        self,
        plugin: DESPlugin,
        install_context: InstallContext,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A concurrent writer racing one __pycache__ must not abort clearing
        the others (issue #43).

        The goal of ``_clear_bytecode_cache`` is only to force a recompile --
        a racing ``__pycache__`` left behind (its stale .pyc gets naturally
        recompiled on next import) is harmless; the raw exception propagating
        and aborting the whole install is not.

        RED at HEAD: the raw ``shutil.rmtree(cache_dir)`` at L715 propagates
        uncaught -- there is no try/except around the loop.
        """
        target_dir = tmp_path / "des_module"
        racing_cache = target_dir / "domain" / "__pycache__"
        clean_cache = target_dir / "application" / "__pycache__"
        racing_cache.mkdir(parents=True, exist_ok=True)
        clean_cache.mkdir(parents=True, exist_ok=True)
        (racing_cache / "phase_event.cpython-312.pyc").write_bytes(b"stale")
        (clean_cache / "orchestrator.cpython-312.pyc").write_bytes(b"stale")

        monkeypatch.setattr(
            "scripts.install.plugins.des_plugin.shutil.rmtree",
            _racing_rmtree(racing_cache),
        )

        plugin._clear_bytecode_cache(target_dir, install_context)  # must not raise

        assert not clean_cache.exists(), (
            "the non-racing __pycache__ must still be cleared"
        )

    def test_clear_bytecode_cache_removes_all_pycache_dirs_without_race(
        self, plugin: DESPlugin, install_context: InstallContext, tmp_path: Path
    ):
        """Guard: a normal (non-racing) clear still removes every __pycache__."""
        target_dir = tmp_path / "des_module"
        cache_a = target_dir / "domain" / "__pycache__"
        cache_b = target_dir / "application" / "__pycache__"
        cache_a.mkdir(parents=True, exist_ok=True)
        cache_b.mkdir(parents=True, exist_ok=True)
        (cache_a / "phase_event.cpython-312.pyc").write_bytes(b"stale")
        (cache_b / "orchestrator.cpython-312.pyc").write_bytes(b"stale")

        plugin._clear_bytecode_cache(target_dir, install_context)

        assert not cache_a.exists()
        assert not cache_b.exists()
