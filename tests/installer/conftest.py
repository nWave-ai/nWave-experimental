"""Installer-suite fixtures.

Holds the ``~/.nwave/hooks/`` restore guard. Kept in THIS conftest (not the
repo-root ``tests/conftest.py``) on purpose: the pre-commit test-selector
treats ``tests/conftest.py`` as a full-suite trigger, whereas a change here
maps only to ``tests/installer/`` — and every test that wipes the hook lives
under this tree anyway.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _snapshot_nwave_hooks(hooks_dir: Path) -> dict[str, bytes]:
    """filename -> bytes for every file in hooks_dir ({} when absent). Pure."""
    if not hooks_dir.is_dir():
        return {}
    return {
        entry.name: entry.read_bytes()
        for entry in sorted(hooks_dir.iterdir())
        if entry.is_file()
    }


@pytest.fixture(scope="session", autouse=True)
def guard_nwave_attribution_hook():
    """Session guard that RESTORES the developer's ~/.nwave/hooks/ after the run.

    Installer/uninstaller acceptance tests invoke ``install_nwave.main()`` (and
    uninstall), whose attribution plugin runs ``migrate_legacy_hook`` — which
    deletes ``~/.nwave/hooks/nwave_attribution_hook.py`` via ``Path.home()``
    whenever a test lacks HOME isolation. That file backs the real
    prepare-commit-msg attribution hook, so losing it blocks the NEXT
    ``git commit`` (prepare-commit-msg can no longer find the script) — the
    recurring "commits break after a test run" trap.

    Many installer tests touch this path (``test_install_no_package_manager``,
    the uninstaller fixtures, ...), so per-fixture HOME redirects alone are
    whack-a-mole. Mirroring ``guard_git_hooks`` in the root conftest: snapshot
    before, RESTORE after, warn rather than fail (the restore is the safety net
    and we want commits left unblocked).

    The dir is resolved ONCE at setup under the real HOME and the snapshot is
    captured there, so a test leaking a patched ``$HOME`` cannot redirect the
    restore target. No-op on machines without a pre-existing hook (e.g. CI), so
    the guard never fabricates state it does not own. Additive-only on restore
    (never deletes), which keeps it safe across xdist workers.
    """
    hooks_dir = Path.home() / ".nwave" / "hooks"
    before = _snapshot_nwave_hooks(hooks_dir)

    yield

    if not before:
        return  # Nothing pre-existing to protect — do not fabricate state.

    after = _snapshot_nwave_hooks(hooks_dir)
    if before == after:
        return

    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name, content in before.items():
        path = hooks_dir / name
        path.write_bytes(content)
        path.chmod(0o755)

    import sys

    sys.stderr.write(
        "\nNWAVE-HOOK-GUARD: a test mutated ~/.nwave/hooks/ — "
        f"RESTORED {sorted(before)} to {hooks_dir}\n"
    )


@pytest.fixture(scope="session", autouse=True)
def isolate_install_lock_destination(tmp_path_factory):
    """Give this pytest worker its own install and project destinations.

    ``install_nwave.main()`` takes an exclusive per-destination lock before any
    write (``scripts/install/install_lock.py``), keyed to ``NWAVE_AGENTS_HOME``
    / ``HOME``. Around twenty tests in this tree drive ``main()`` in process
    against monkeypatched config dirs, so under ``-n auto`` two workers can run
    two of them at the same instant, against the SAME real destination -- and
    the second is then correctly refused, failing a test that has nothing to do
    with concurrency. Measured 2026-08-22: an intermittent
    ``test_installation_verifier`` failure under ``-n 4`` that reproduced on
    neither file alone.

    The escape hatch used here is the one the refusal message itself
    prescribes -- an isolated destination, per worker -- NOT a switch that
    disarms the lock (a gate that can be turned off is not a floor, GDP-7).
    The lock still binds inside each worker, so a test that genuinely nests two
    installs still sees the refusal.

    The project root is equally an effect destination after the unified-config
    cutover: ``DESPlugin`` bootstraps and migrates
    ``<NWAVE_PROJECT_ROOT>/.nwave/config.json``. Without this companion
    override an in-process installer test inherits the checkout cwd and can
    retire the lane's tracked legacy marker during migration.

    Bonus, and the reason this is scoped to the whole installer tree rather
    than the ``main()`` call sites alone: ``NWAVE_AGENTS_HOME`` also redirects
    ``create_backup``, ``record_install_metadata`` and the retention config
    read away from the developer's real ``~/.nwave`` -- the mutation the
    session hook guard above exists to repair after the fact.
    """
    destination = tmp_path_factory.mktemp("nwave_agents_home")
    project = tmp_path_factory.mktemp("nwave_project_root")
    patch = pytest.MonkeyPatch()
    patch.setenv("NWAVE_AGENTS_HOME", str(destination))
    patch.setenv("NWAVE_PROJECT_ROOT", str(project))
    yield destination
    patch.undo()
