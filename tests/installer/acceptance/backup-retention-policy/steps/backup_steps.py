"""Step definitions for backup-retention-policy acceptance tests.

Driving port: BackupManager.apply_retention(max_count) — invoked exactly as
install_nwave.py will invoke it during the install backup phase. Restore is
exercised through the existing restore_backup driving port in
install_nwave.py:225-271.

Strategy C (Real local): real filesystem on tmp_path, real BackupManager,
real glob/sort semantics. No mocks of filesystem, time, or subprocess.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, parsers, then, when

from scripts.install.install_utils import BackupManager, Logger


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers (test infrastructure only — NOT business logic)
# ---------------------------------------------------------------------------


def _make_backup_dir(claude_config_home: Path, name: str) -> Path:
    """Create a fixture backup directory with realistic-looking contents.

    Each fake backup contains agents/ and commands/ subdirs with one
    marker file so restore round-trip tests can assert the right backup
    was selected.
    """
    backup = claude_config_home / "backups" / name
    backup.mkdir(parents=True)
    (backup / "agents").mkdir()
    (backup / "commands").mkdir()
    (backup / "agents" / "marker.md").write_text(f"agent-from-{name}\n")
    (backup / "commands" / "marker.md").write_text(f"command-from-{name}\n")
    (backup / "backup-manifest.txt").write_text(f"backup: {name}\n")
    return backup


def _list_nwave_backups(claude_config_home: Path) -> list[str]:
    """Return sorted list of nwave-* backup directory names."""
    backups_dir = claude_config_home / "backups"
    if not backups_dir.exists():
        return []
    return sorted(p.name for p in backups_dir.glob("nwave-*"))


def _list_all_backups(claude_config_home: Path) -> list[str]:
    """Return all entries in the backups dir (including foreign dirs)."""
    backups_dir = claude_config_home / "backups"
    if not backups_dir.exists():
        return []
    return sorted(p.name for p in backups_dir.iterdir())


def _build_backup_manager(backup_type: str = "install") -> BackupManager:
    """Build a real BackupManager wired to the isolated CLAUDE_CONFIG_DIR.

    Logger is silent so test output stays clean. CLAUDE_CONFIG_DIR is set
    by the claude_config_home fixture before this is called.
    """
    return BackupManager(Logger(silent=True), backup_type)


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("Marco has a clean Claude config home at the test sandbox")
def given_clean_claude_config_home(claude_config_home, scenario_state):
    """Background: ensure the sandbox is in a known clean state.

    The claude_config_home fixture already creates a clean config dir with
    an empty backups/ subdir; this step exists so the Gherkin reads
    naturally and so future setup can hook in here.
    """
    assert claude_config_home.exists()
    assert (claude_config_home / "backups").exists()
    assert _list_all_backups(claude_config_home) == []


# ---------------------------------------------------------------------------
# Given — preconditions about prior backups
# ---------------------------------------------------------------------------


@given("Marco has no prior nWave install in his Claude config home")
def given_no_prior_install(claude_config_home):
    agents = claude_config_home / "agents"
    commands = claude_config_home / "commands"
    assert not agents.exists()
    assert not commands.exists()


@given(parsers.parse('Marco has exactly 1 prior backup named "{name}"'))
def given_one_prior_backup(claude_config_home, name):
    _make_backup_dir(claude_config_home, name)


@given("Marco has 10 backup directories from prior installs:")
def given_ten_prior_backups_table(claude_config_home, datatable):
    # datatable is a list of rows; first row is header per pytest-bdd default,
    # but here we have a single-column list — accept either shape.
    for row in datatable:
        name = row[0] if isinstance(row, (list, tuple)) else row
        if name and name != "name":
            _make_backup_dir(claude_config_home, name)


@given(
    parsers.parse(
        "Marco has 11 backup directories from prior installs spanning several days"
    )
)
def given_eleven_prior_backups(claude_config_home):
    for day in range(1, 12):
        name = f"nwave-install-202601{day:02d}-100000"
        _make_backup_dir(claude_config_home, name)


@given(parsers.parse("Marco has 11 successful prior installs spanning several days"))
def given_eleven_successful_installs(claude_config_home):
    for day in range(1, 12):
        name = f"nwave-install-202601{day:02d}-100000"
        _make_backup_dir(claude_config_home, name)


@given(parsers.parse('Marco has 8 backup directories named "{first}" through "{last}"'))
def given_eight_install_backups(claude_config_home, first, last):
    # Hard-coded for the S6 fixture range to keep parsing simple and explicit.
    for day in range(1, 9):
        name = f"nwave-install-202601{day:02d}-100000"
        _make_backup_dir(claude_config_home, name)


@given(parsers.parse('Marco has 2 backup directories named "{first}" and "{second}"'))
def given_two_uninstall_backups(claude_config_home, first, second):
    _make_backup_dir(claude_config_home, first)
    _make_backup_dir(claude_config_home, second)


@given(parsers.parse("Marco has {n:d} backup directories from prior installs:"))
def given_n_prior_backups_table(claude_config_home, n, datatable):
    for row in datatable:
        name = row[0] if isinstance(row, (list, tuple)) else row
        if name and name != "name":
            _make_backup_dir(claude_config_home, name)


@given(parsers.parse('Marco has a personal directory "{name}" alongside his backups'))
def given_foreign_directory(claude_config_home, scenario_state, name):
    foreign = claude_config_home / "backups" / name
    foreign.mkdir()
    (foreign / "marco-notes.txt").write_text("personal\n")
    scenario_state["foreign_dirs"].append(name)


# ---------------------------------------------------------------------------
# Given — config preconditions
# ---------------------------------------------------------------------------


@given("no override exists for the maximum backup count")
def given_no_config_override(nwave_config_home):
    config_file = nwave_config_home / "global-config.json"
    assert not config_file.exists()


@given(parsers.parse("the maximum backup count is the default of {n:d}"))
def given_default_cap(nwave_config_home, n):
    # D4 (scope.md): default cap is 10, no override file present
    config_file = nwave_config_home / "global-config.json"
    assert not config_file.exists()


@given(
    parsers.parse(
        "Marco has set the maximum backup count to {value:d} in his nWave global config"
    )
)
def given_integer_cap_override(nwave_config_home, value):
    nwave_config_home.mkdir(parents=True, exist_ok=True)
    config_file = nwave_config_home / "global-config.json"
    config_file.write_text(json.dumps({"backups": {"max_count": value}}) + "\n")


@given(
    parsers.parse(
        'Marco has set the maximum backup count to "{value}" in his nWave global config'
    )
)
def given_string_cap_override(nwave_config_home, value):
    nwave_config_home.mkdir(parents=True, exist_ok=True)
    config_file = nwave_config_home / "global-config.json"
    config_file.write_text(json.dumps({"backups": {"max_count": value}}) + "\n")


@given("Marco has a nWave global config with no maximum backup count set")
def given_config_without_cap_key(nwave_config_home):
    nwave_config_home.mkdir(parents=True, exist_ok=True)
    config_file = nwave_config_home / "global-config.json"
    config_file.write_text(json.dumps({"attribution": {"enabled": False}}) + "\n")


# ---------------------------------------------------------------------------
# Given — "new backup just created" preconditions
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'a new backup directory "{name}" has just been created by the install'
    )
)
def given_new_backup_created(claude_config_home, scenario_state, name):
    _make_backup_dir(claude_config_home, name)
    scenario_state["new_backup_name"] = name


@given("Marco has 10 prior install backups spanning the first ten days of January 2026")
def given_ten_prior_january_backups(claude_config_home):
    for day in range(1, 11):
        name = f"nwave-install-202601{day:02d}-100000"
        _make_backup_dir(claude_config_home, name)


@given("Marco has an existing nWave install with agents and commands on disk")
def given_existing_install(claude_config_home):
    """Drop minimal agents/ and commands/ so BackupManager.create_backup
    has something to back up — without this it short-circuits at line 370
    of install_utils.py and no new backup is created (and retention has
    nothing to prune past the cap).
    """
    agents_dir = claude_config_home / "agents"
    commands_dir = claude_config_home / "commands"
    agents_dir.mkdir()
    commands_dir.mkdir()
    (agents_dir / "marco-agent.md").write_text("agent body\n")
    (commands_dir / "marco-command.md").write_text("command body\n")


@given("the install has just applied retention, removing the oldest backup")
def given_retention_already_applied(claude_config_home, scenario_state):
    """Convenience setup for restore-after-retention scenarios.

    Drives the same apply_retention path the install would, so the restore
    scenarios start from a realistic post-retention state.
    """
    manager = _build_backup_manager()
    result = manager.apply_retention()
    scenario_state["retention_result"] = result


# ---------------------------------------------------------------------------
# When — driving port invocations
# ---------------------------------------------------------------------------


@when("Marco runs the install backup phase")
def when_runs_install_backup_phase(claude_config_home, scenario_state):
    """Drive BackupManager.create_backup() — same call install_nwave.py makes."""
    manager = _build_backup_manager()
    backup_path = manager.create_backup(dry_run=False)
    scenario_state["create_backup_returned"] = backup_path


@when("Marco lets the install apply its retention policy")
def when_apply_retention(claude_config_home, scenario_state):
    """Drive BackupManager.apply_retention() — the new driving port.

    Captures any raised error so Then steps can assert validation behavior
    without aborting the test prematurely. Also snapshots the pre-call count
    of nwave-* backups so ``then_no_prior_removed`` can assert strict
    equality (post-DELIVER review D3 — the previous ``len >= 1`` assertion
    was near-tautological and would have passed even if retention partially
    pruned).
    """
    scenario_state["pre_apply_count"] = len(_list_nwave_backups(claude_config_home))
    manager = _build_backup_manager()
    try:
        result = manager.apply_retention()
        scenario_state["retention_result"] = result
    except Exception as err:
        scenario_state["raised_error"] = err


@when(
    "Marco runs the installer's create-backup phase through the installer entry point"
)
def when_marco_runs_installer_create_backup(claude_config_home, scenario_state):
    """Drive ``NWaveInstaller.create_backup()`` — the outer seam ``main()``
    invokes (install_nwave.py:886). Proves retention is wired into the wrapper,
    not just into ``BackupManager.apply_retention`` directly. See DWD-10.

    Snapshots the set of backup directory names BEFORE invocation so Then steps
    can identify which directory is the new one without re-deriving it from
    the timestamp.
    """
    from scripts.install.install_nwave import NWaveInstaller

    pre_call_backups = set(_list_nwave_backups(claude_config_home))
    scenario_state["pre_call_backups"] = pre_call_backups

    installer = NWaveInstaller()
    try:
        installer.create_backup()
    except Exception as err:
        scenario_state["raised_error"] = err
        return

    post_call_backups = set(_list_nwave_backups(claude_config_home))
    scenario_state["post_call_backups"] = post_call_backups
    new_names = post_call_backups - pre_call_backups
    # Exactly one new backup is expected (the one BackupManager just created).
    scenario_state["new_backup_name"] = next(iter(new_names), None)


@when("Marco asks the installer to restore from the most recent backup")
def when_marco_restores(claude_config_home, scenario_state):
    """Drive restore_backup() — existing driving port in install_nwave.py.

    Imports lazily so module collection does not pull the full installer
    surface for non-restore scenarios.

    Captures the selected backup path from the production-side observability
    contract ``installer.last_restored_from`` (Option B per DWD-09). The
    test must NOT recompute the selection via its own glob/sort — that
    would assert the test against itself instead of against production.
    """
    from scripts.install.install_nwave import NWaveInstaller

    installer = NWaveInstaller()
    ok = installer.restore_backup()
    scenario_state["restore_result"] = ok
    picked_path = installer.last_restored_from
    scenario_state["restore_picked"] = picked_path.name if picked_path else None


# ---------------------------------------------------------------------------
# Then — observable outcomes
# ---------------------------------------------------------------------------


@then(parsers.parse('the oldest backup "{name}" is removed from disk'))
def then_oldest_removed(claude_config_home, name):
    survivors = _list_nwave_backups(claude_config_home)
    assert name not in survivors, (
        f"Expected {name!r} to be pruned but it is still on disk: {survivors}"
    )


@then(parsers.parse("exactly {n:d} backup directories remain on disk"))
def then_n_backups_remain(claude_config_home, n):
    survivors = _list_nwave_backups(claude_config_home)
    assert len(survivors) == n, (
        f"Expected exactly {n} nwave-* dirs, found {len(survivors)}: {survivors}"
    )


@then(parsers.parse("exactly {n:d} backup directory remains on disk"))
def then_one_backup_remains(claude_config_home, n):
    survivors = _list_nwave_backups(claude_config_home)
    assert len(survivors) == n


@then(
    parsers.parse('exactly {n:d} backup directories matching "nwave-*" remain on disk')
)
def then_n_nwave_backups_remain(claude_config_home, n):
    survivors = _list_nwave_backups(claude_config_home)
    assert len(survivors) == n


@then("the surviving backups are the 10 most recent ones")
def then_surviving_are_most_recent(claude_config_home):
    survivors = _list_nwave_backups(claude_config_home)
    expected = [f"nwave-install-202601{day:02d}-100000" for day in range(2, 12)]
    assert survivors == expected, f"Expected {expected}, got {survivors}"


@then(parsers.parse('the surviving backups are "{first}" through "{last}"'))
def then_surviving_range(claude_config_home, first, last):
    survivors = _list_nwave_backups(claude_config_home)
    assert survivors[0] == first
    assert survivors[-1] == last


@then(parsers.parse('the surviving backup is "{name}"'))
def then_only_survivor_is(claude_config_home, name):
    survivors = _list_nwave_backups(claude_config_home)
    assert survivors == [name], f"Expected only {name!r} to survive, got {survivors}"


@then(parsers.parse('no backup directory matching "nwave-*" remains on disk'))
def then_no_nwave_backups_remain(claude_config_home):
    survivors = _list_nwave_backups(claude_config_home)
    assert survivors == [], f"Expected zero nwave-* dirs, got {survivors}"


@then(
    parsers.parse('no backup directory matching "nwave-*" exists in his backups area')
)
def then_no_nwave_dir_exists(claude_config_home):
    survivors = _list_nwave_backups(claude_config_home)
    assert survivors == []


@then("no backup directory was removed")
def then_no_backup_removed(scenario_state):
    result = scenario_state.get("retention_result")
    assert result is not None, "apply_retention did not return a result"
    assert result.pruned == [], f"Expected no pruning, got {result.pruned}"


@then("both prior and new backups are still present")
def then_both_present(claude_config_home):
    survivors = _list_nwave_backups(claude_config_home)
    assert len(survivors) >= 2


@then(parsers.parse('Marco\'s "{name}" directory is still present and untouched'))
def then_foreign_dir_untouched(claude_config_home, name):
    foreign = claude_config_home / "backups" / name
    assert foreign.exists(), f"Foreign dir {name!r} was removed"
    assert (foreign / "marco-notes.txt").read_text() == "personal\n"


@then('the lex-smallest of the 10 prior "nwave-*" directories is removed')
def then_lex_smallest_removed(claude_config_home):
    survivors = _list_nwave_backups(claude_config_home)
    assert "nwave-install-20260101-100000" not in survivors


@then(parsers.parse('the pruned directory is "{name}"'))
def then_pruned_is(scenario_state, name):
    result = scenario_state.get("retention_result")
    assert result is not None
    assert name in result.pruned, (
        f"Expected {name!r} in pruned list, got {result.pruned}"
    )


@then("the install backup phase reports nothing was backed up")
def then_nothing_backed_up(scenario_state):
    # create_backup returns None when there is no prior install (D-existing
    # behavior, install_utils.py:367-372)
    assert scenario_state.get("create_backup_returned") is None


@then(
    parsers.parse(
        'the install reports a clear error mentioning "max_count" and the value "{value}"'
    )
)
def then_validation_error(scenario_state, value):
    err = scenario_state.get("raised_error")
    assert err is not None, "Expected an error but apply_retention succeeded"
    msg = str(err)
    assert "max_count" in msg, f"Error message missing 'max_count': {msg!r}"
    assert value in msg, f"Error message missing value {value!r}: {msg!r}"


@then("the new backup directory is still present on disk")
def then_new_backup_present(claude_config_home, scenario_state):
    name = scenario_state.get("new_backup_name")
    assert name is not None
    assert (claude_config_home / "backups" / name).exists()


@then("no prior backup directory was removed")
def then_no_prior_removed(claude_config_home, scenario_state):
    """Strict equality on pre-/post- counts (post-DELIVER review D3).

    The previous ``len(survivors) >= 1`` assertion was near-tautological —
    it would have passed even if retention had partially pruned (e.g.
    pruned all but the newest). Strict equality against ``pre_apply_count``
    captured before the When step proves NO pruning ran at all.

    Used by S9 negative-cap scenario (milestone-2) where invalid config
    must abort retention before any disk write. Other S9 scenarios
    (non-int cap, missing key) do NOT use this step:
    - Non-int cap raises before any pruning, but the scenario does not
      bind this step (it only asserts ``new backup directory is still
      present on disk``).
    - Missing-key falls back to default cap=10 and pruning may legitimately
      run, so this step is correctly absent from that scenario.
    """
    pre_count = scenario_state.get("pre_apply_count")
    assert pre_count is not None, (
        "pre_apply_count not captured; ensure the When step runs before this Then"
    )
    survivors = _list_nwave_backups(claude_config_home)
    assert len(survivors) == pre_count, (
        f"Expected exactly {pre_count} nwave-* dirs (no pruning when validation "
        f"fails), found {len(survivors)}: {survivors}"
    )


@then("no error or warning about the maximum backup count is reported")
def then_no_warning(scenario_state):
    assert scenario_state.get("raised_error") is None


@then("the new install backup created by the installer is still on disk")
def then_new_installer_backup_present(claude_config_home, scenario_state):
    """Outer-seam wiring assertion (DWD-10).

    The installer's own ``create_backup`` produced a fresh backup directory
    (snapshotted via ``post_call_backups - pre_call_backups`` in the When
    step). That fresh backup MUST survive the retention pass — pruning is
    expected to remove the oldest, not the newest.
    """
    new_name = scenario_state.get("new_backup_name")
    assert new_name is not None, (
        "NWaveInstaller.create_backup did not produce a new nwave-* directory"
    )
    assert (claude_config_home / "backups" / new_name).exists(), (
        f"New backup {new_name!r} was unexpectedly pruned by retention"
    )


# ---------------------------------------------------------------------------
# Then — restore semantics
# ---------------------------------------------------------------------------


@then("the restore picks the most recent surviving backup")
def then_restore_picks_most_recent(claude_config_home, scenario_state):
    """Assert the path captured from production (``last_restored_from``).

    The captured value comes from production-side selection, not from a
    test-side recomputation. This is the assertion the reviewer's Nit 1
    flagged: previously the step re-ran glob/sort and compared against
    itself, which would false-pass if production's selection logic changed.

    Crafter-reviewer FLAG 8 follow-up: assert the captured value also
    matches the lex-largest surviving backup (the contract D2 promises),
    not just that it is non-None. Without this, production could pick the
    second-most-recent and the test would silently pass.
    """
    picked = scenario_state.get("restore_picked")
    assert picked is not None, (
        "restore_backup did not expose a selected path on last_restored_from"
    )
    assert scenario_state.get("restore_result") is True, (
        "restore_backup returned False — cannot assert selection on failure"
    )
    expected = sorted(_list_nwave_backups(claude_config_home))[-1]
    assert picked == expected, (
        f"restore_backup picked {picked!r}; expected lex-largest survivor "
        f"{expected!r} per D2 lex-sort contract"
    )


@then("the restored agents and commands match the contents of that backup")
def then_restore_round_trip(claude_config_home, scenario_state):
    picked = scenario_state.get("restore_picked")
    assert picked is not None
    agents_marker = (claude_config_home / "agents" / "marker.md").read_text()
    commands_marker = (claude_config_home / "commands" / "marker.md").read_text()
    assert agents_marker == f"agent-from-{picked}\n"
    assert commands_marker == f"command-from-{picked}\n"


@then("Marco's agents directory contains the contents of that backup")
def then_marco_agents_match(claude_config_home, scenario_state):
    picked = scenario_state.get("restore_picked")
    assert picked is not None
    text = (claude_config_home / "agents" / "marker.md").read_text()
    assert text == f"agent-from-{picked}\n"


@then("Marco's commands directory contains the contents of that backup")
def then_marco_commands_match(claude_config_home, scenario_state):
    picked = scenario_state.get("restore_picked")
    assert picked is not None
    text = (claude_config_home / "commands" / "marker.md").read_text()
    assert text == f"command-from-{picked}\n"


@then("the restore reports success")
def then_restore_reports_success(scenario_state):
    assert scenario_state.get("restore_result") is True


# ---------------------------------------------------------------------------
# pytest-bdd scenario binding
# ---------------------------------------------------------------------------
# Test files (test_walking_skeleton.py etc.) bind individual scenarios via
# @scenario decorators. This module owns the step definitions only.

_ = pytest  # silence "imported but unused" — pytest is used by fixtures
