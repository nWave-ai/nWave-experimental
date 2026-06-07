"""Step definitions -- slice-04: spine-ledger installer wiring + aggregator subcommand.

F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2 slice-04 (FINAL slice). Layer 3
(subprocess + FS acceptance + in-process import for the HOOK_EVENTS pin):
the production driving ports are:

  - `python -m nwave_ai.cli install --target <claude-home>` and
    `python -m nwave_ai.cli uninstall --target <claude-home>` subprocesses
    against an isolated tmp_path target (AT-1 walking skeleton),
  - `python -m des verify-slice-ledger-evidence --report --since=<date>`
    subprocess against a tmp_path target seeded with a synthetic audit log
    (AT-2 aggregator subcommand),
  - in-process import of `scripts.shared.hook_definitions.HOOK_EVENTS` for
    the pin-and-marker-prefix assertion (AT-3 HOOK_EVENTS pin).

The only driven ports are:
  - the real filesystem (tmp_path target carries `claude-home/settings.json`,
    `claude-home/scripts/`, `.nwave/des/logs/audit-{date}.log`),
  - the real subprocess (real `nwave_ai.cli` + `des` CLIs),
  - the real Python import system (`importlib.reload(hook_definitions)` for
    pin assertion freshness).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly).
Three ATs cover the slice-04 contract: walking-skeleton install/uninstall
round-trip + aggregator subcommand structured-JSON emission + HOOK_EVENTS
pin + marker prefix verification. PBT precluded by OR-reduction
(Mandate 9 v2: real I/O on subprocess + real filesystem + real installer
plugin chain).

Step bodies delegate to `InstallWiringFixture` (Mandate-12 criterion 3:
<=2 statements per body, final statement is a composition method call,
zero control flow in step bodies).

RED-for-the-right-reason: the slice-04 production wiring does NOT EXIST
YET. The crafter lands in DELIVER:

  1. `DES_HOOKS` list in `scripts/install/plugins/des_plugin.py` (mirrors
     `DES_SCRIPTS`) propagating the 3 spine-ledger hook scripts to
     `~/.claude/scripts/` at install time + removing them at uninstall.
  2. Two new `HOOK_EVENTS` entries in `scripts/shared/hook_definitions.py`:
     one PreToolUse/Bash entry registering the slice-02 spine-ledger
     pre-commit hook via the installer-templated Python form (alongside the
     existing shell-form `_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK` entry, OR
     replacing it — crafter chooses per shipped-hook contract), and one
     SubagentStop entry registering the slice-03 spine-ledger detector.
     Both new entries carry the `# des-hook:` marker prefix.
  3. `src/des/cli/verify_slice_ledger_evidence.py` subcommand module with
     a `main(argv)` entry that supports `--report --since=<YYYY-MM-DD>` and
     emits a single-line JSON report to stdout naming the cumulative event
     counts (`slice_commits_verified`, `carpaccio_gates_cleared`,
     `bypasses_detected`, `bypasses_used`) since the given date.
  4. Registration of the new subcommand in the `_REGISTRY` tuple in
     `src/des/cli/__main__.py`.

When the composition fixture invokes the slice-04 surfaces via subprocess
/ in-process import:
  - `nwave-ai install` succeeds but does NOT propagate the spine-ledger
    hook scripts (no `DES_HOOKS` list) → AT-1 fires AssertionError on
    `assert_target_scripts_contain_spine_ledger_hooks` with the missing
    file names enumerated.
  - `des verify-slice-ledger-evidence` exits non-zero with stderr naming
    the missing subcommand → AT-2 fires AssertionError on
    `assert_aggregator_exits_ok`.
  - `len(HOOK_EVENTS) == 10` not 12 → AT-3 fires AssertionError on
    `assert_post_slice_04_hook_events_count`.

That is the correct RED: each `Then` step fires AssertionError on a
post-condition observation reflecting the missing functionality. ZERO
`IMPORT_ERROR` / `FIXTURE_BROKEN` / `SETUP_FAILURE` classifications.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via:
  - AT-1: `python -m nwave_ai.cli install/uninstall` subprocess (real
    composition root via `nwave_ai.cli` entry point → `install_nwave.py`
    orchestrator → plugin registry → `DESPlugin.install/uninstall`).
  - AT-2: `python -m des verify-slice-ledger-evidence` subprocess (real
    `__main__.py` dispatcher → subcommand module).
  - AT-3: `importlib.reload(scripts.shared.hook_definitions)` in-process
    import of the SHARED SUBSTRATE CONFIG module. This is NOT a Mandate-13
    violation: `hook_definitions.py` is shared installer + plugin builder
    substrate config (not domain code, not adapter code); it is part of
    the installer's driving composition (the installer reads `HOOK_EVENTS`
    to emit settings.json). The forbidden-path rule
    (`tests/des/unit/(?:domain|cli)/*`) does NOT apply — this test ships
    under `tests/installer/acceptance/...`. The HOOK_EVENTS pin verifies
    the installer's input contract (the tuple of hook event registrations
    is the installer's domain input, not arbitrary business logic).

Skip marker: per ADR-028 + friction #26 lesson (slice-02 missed this and
was orchestrator-patched), the whole module is marked `pytest.mark.skip`
AT FILE HEAD until the crafter lands the slice-04 production wiring. The
crafter unskips on A_GREEN_ATS. This is the RED scaffold contract: the
ATs exist, classify as RED-for-the-right-reason in reviewer logs, but
do NOT execute against the missing production wiring on every CI run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import (
    AggregatorInvocation,
    HookEventsSnapshot,
    InstallerInvocation,
    InstallWiringFixture,
)


scenarios("../slice-04-installer-wiring.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> InstallWiringFixture:
    """Per-test install-wiring fixture rooted at an isolated tmp target."""
    return InstallWiringFixture(target_root=tmp_path / "target")


@pytest.fixture
def installer_box() -> dict[str, object]:
    """Carrier for captured InstallerInvocation across When/Then steps."""
    return {}


@pytest.fixture
def aggregator_box() -> dict[str, object]:
    """Carrier for captured AggregatorInvocation across When/Then steps."""
    return {}


@pytest.fixture
def snapshot_box() -> dict[str, object]:
    """Carrier for HookEventsSnapshot across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given("the operator runs `nwave-ai install` against an isolated installation target")
def given_operator_runs_nwave_ai_install(fixture: InstallWiringFixture) -> None:
    # Background framing step (Pillar 1): documents the installer entry
    # point. The composition fixture knows the install target path; no
    # business logic in step body.
    fixture.ensure_no_disabled_gates_file()


@given(
    "the installation target's `settings.json` carries the slice-00 / "
    "slice-02 / slice-03 spine-ledger hook entries with `# des-hook:` "
    "marker prefixes"
)
def given_settings_json_carries_spine_ledger_entries(
    fixture: InstallWiringFixture,
) -> None:
    # Background framing step: documents the installer's output contract
    # (post-install state). Actual assertion of marker prefixes lives in
    # AT-1 / AT-3 Then steps.
    fixture.ensure_no_disabled_gates_file()


@given(
    "the installation target's `~/.claude/scripts/` directory carries the "
    "3 spine-ledger hook scripts"
)
def given_scripts_dir_carries_hook_scripts(fixture: InstallWiringFixture) -> None:
    # Background framing step: documents the `DES_HOOKS` list contract.
    fixture.ensure_no_disabled_gates_file()


@given(
    "the `des` dispatcher registry advertises the `verify-slice-ledger-evidence` subcommand"
)
def given_des_dispatcher_advertises_aggregator(fixture: InstallWiringFixture) -> None:
    # Background framing step: documents the dispatcher registry contract.
    fixture.ensure_no_disabled_gates_file()


# --- AT-1 (install/uninstall round-trip) preconditions ---------------------


@given("a clean target machine with no prior `~/.claude/` tree")
def given_clean_target_machine(fixture: InstallWiringFixture) -> None:
    fixture.prepare_clean_install_target()


# --- AT-2 (aggregator subcommand) preconditions ---------------------------


@given(
    parsers.parse(
        'a target machine with an audit log carrying {count:d} "{event_name}" '
        'events on "{date}"'
    )
)
def given_target_with_audit_log_events(
    fixture: InstallWiringFixture, count: int, event_name: str, date: str
) -> None:
    fixture.seed_synthetic_audit_log_for_aggregator(event_name, count, date)


@given(
    parsers.parse(
        'the audit log also carries {count:d} "{event_name}" events on "{date}"'
    )
)
def given_audit_log_also_carries_events(
    fixture: InstallWiringFixture, count: int, event_name: str, date: str
) -> None:
    fixture.seed_synthetic_audit_log_for_aggregator(event_name, count, date)


@given(
    parsers.parse(
        'the audit log already carries {count:d} "{event_name}" events on "{date}"'
    )
)
def given_audit_log_already_carries_events(
    fixture: InstallWiringFixture, count: int, event_name: str, date: str
) -> None:
    fixture.seed_synthetic_audit_log_for_aggregator(event_name, count, date)


# --- AT-3 (HOOK_EVENTS pin) preconditions ---------------------------------


@given(
    parsers.parse(
        "the pre-slice-04 `HOOK_EVENTS` tuple in `scripts.shared.hook_definitions` "
        "carries exactly {expected:d} entries"
    )
)
def given_pre_slice_04_hook_events_baseline_count(
    fixture: InstallWiringFixture, expected: int
) -> None:
    _ = expected  # baseline check is informational; AT-3 verifies post-state
    fixture.note_pre_slice_04_hook_events_count()


@given(
    parsers.parse(
        "the pre-slice-04 `HOOK_EVENTS` tuple carries exactly {expected:d} "
        '"{event_kind}" entries'
    )
)
def given_pre_slice_04_event_kind_baseline_count(
    fixture: InstallWiringFixture, expected: int, event_kind: str
) -> None:
    _ = expected, event_kind  # baseline framing; AT-3 verifies post-state
    fixture.note_pre_slice_04_hook_events_count()


# --- Actions ---------------------------------------------------------------


@when("the operator runs `nwave-ai install` against the clean target")
def when_operator_runs_install(
    fixture: InstallWiringFixture, installer_box: dict[str, object]
) -> None:
    installer_box["invocation"] = fixture.run_nwave_ai_install()


@when("the operator runs `nwave-ai uninstall` against the installed target")
def when_operator_runs_uninstall(
    fixture: InstallWiringFixture, installer_box: dict[str, object]
) -> None:
    installer_box["invocation"] = fixture.run_nwave_ai_uninstall()


@when(
    parsers.parse(
        "the operator runs `des verify-slice-ledger-evidence --report --since={since}`"
    )
)
def when_operator_runs_aggregator(
    fixture: InstallWiringFixture, aggregator_box: dict[str, object], since: str
) -> None:
    aggregator_box["invocation"] = fixture.run_aggregator_subcommand(since)


@when(
    "the operator imports `scripts.shared.hook_definitions` after the slice-04 wiring lands"
)
def when_operator_imports_hook_definitions(
    fixture: InstallWiringFixture, snapshot_box: dict[str, object]
) -> None:
    snapshot_box["snapshot"] = fixture.snapshot_hook_events()


# --- AT-1 observations -----------------------------------------------------


@then(
    parsers.parse(
        "the target machine's `~/.claude/scripts/` directory contains "
        '"{script_a}" and "{script_b}" and "{script_c}"'
    )
)
def then_target_scripts_contain_three_hooks(
    fixture: InstallWiringFixture,
    installer_box: dict[str, object],
    script_a: str,
    script_b: str,
    script_c: str,
) -> None:
    _ = script_a, script_b, script_c  # canonical list lives in composition
    fixture.assert_target_scripts_contain_spine_ledger_hooks(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        "the target machine's `settings.json` carries exactly one new "
        '"{event_kind}" entry whose command names "{module_marker}"'
    )
)
def then_settings_carries_one_new_entry(
    fixture: InstallWiringFixture,
    installer_box: dict[str, object],
    event_kind: str,
    module_marker: str,
) -> None:
    _ = event_kind, module_marker  # parsed contract; composition asserts both
    fixture.assert_settings_json_carries_new_spine_ledger_entries(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


@then('the new spine-ledger hook entries carry "# des-hook:" marker prefixes')
def then_new_entries_carry_des_hook_marker(
    fixture: InstallWiringFixture, installer_box: dict[str, object]
) -> None:
    fixture.assert_new_spine_ledger_entries_carry_des_hook_marker(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        'the target machine\'s `settings.json` carries zero "{event_kind}" '
        'entries whose command names "{module_marker}"'
    )
)
def then_settings_carries_zero_spine_ledger_entries(
    fixture: InstallWiringFixture,
    installer_box: dict[str, object],
    event_kind: str,
    module_marker: str,
) -> None:
    _ = event_kind, module_marker  # composition asserts across both event kinds
    fixture.assert_settings_json_has_no_spine_ledger_entries(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    "the target machine's `~/.claude/scripts/` directory contains zero "
    "spine-ledger hook scripts"
)
def then_scripts_dir_contains_zero_spine_ledger(
    fixture: InstallWiringFixture, installer_box: dict[str, object]
) -> None:
    fixture.assert_target_scripts_contain_zero_spine_ledger_hooks(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    "the target machine's pre-existing settings entries outside the "
    "spine-ledger hook scope are unchanged"
)
def then_sentinel_entry_preserved(
    fixture: InstallWiringFixture, installer_box: dict[str, object]
) -> None:
    fixture.assert_settings_sentinel_entry_preserved(
        installer_box["invocation"]  # type: ignore[arg-type]
    )


# --- AT-2 observations -----------------------------------------------------


@then(parsers.parse("the subcommand exits with status {expected_exit:d}"))
def then_subcommand_exits_with_status(
    fixture: InstallWiringFixture,
    aggregator_box: dict[str, object],
    expected_exit: int,
) -> None:
    _ = expected_exit  # composition asserts == 0 (the only happy path)
    fixture.assert_aggregator_exits_ok(
        aggregator_box["invocation"]  # type: ignore[arg-type]
    )


@then("the subcommand emits structured JSON to stdout")
def then_subcommand_emits_structured_json(
    fixture: InstallWiringFixture, aggregator_box: dict[str, object]
) -> None:
    fixture.assert_aggregator_stdout_is_json(
        aggregator_box["invocation"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        'the structured JSON names the field "{field_name}" with value "{value}"'
    )
)
def then_json_field_equals_string(
    fixture: InstallWiringFixture,
    aggregator_box: dict[str, object],
    field_name: str,
    value: str,
) -> None:
    fixture.assert_aggregator_stdout_field_equals_string(
        aggregator_box["invocation"],  # type: ignore[arg-type]
        field_name,
        value,
    )


@then(
    parsers.parse(
        'the structured JSON names the field "{field_name}" with value {value:d}'
    )
)
def then_json_field_equals_int(
    fixture: InstallWiringFixture,
    aggregator_box: dict[str, object],
    field_name: str,
    value: int,
) -> None:
    fixture.assert_aggregator_stdout_field_equals_int(
        aggregator_box["invocation"],  # type: ignore[arg-type]
        field_name,
        value,
    )


@then("the target machine filesystem is unchanged outside transient stdout emission")
def then_filesystem_unchanged_outside_stdout(
    fixture: InstallWiringFixture, aggregator_box: dict[str, object]
) -> None:
    fixture.assert_aggregator_filesystem_unchanged(
        aggregator_box["invocation"]  # type: ignore[arg-type]
    )


# --- AT-3 observations -----------------------------------------------------


@then(
    parsers.parse(
        "the post-slice-04 `HOOK_EVENTS` tuple carries exactly {expected:d} entries"
    )
)
def then_post_slice_04_total_count(
    fixture: InstallWiringFixture,
    snapshot_box: dict[str, object],
    expected: int,
) -> None:
    _ = expected  # canonical post-count == 13 enforced in composition
    fixture.assert_post_slice_04_hook_events_count(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        "the post-slice-04 `HOOK_EVENTS` tuple carries exactly {expected:d} "
        '"PreToolUse" entries'
    )
)
def then_post_slice_04_pre_tool_use_count(
    fixture: InstallWiringFixture,
    snapshot_box: dict[str, object],
    expected: int,
) -> None:
    _ = expected  # canonical post-count == 6 enforced in composition
    fixture.assert_post_slice_04_pre_tool_use_count(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


@then(
    parsers.parse(
        "the post-slice-04 `HOOK_EVENTS` tuple carries exactly {expected:d} "
        '"SubagentStop" entries'
    )
)
def then_post_slice_04_subagent_stop_count(
    fixture: InstallWiringFixture,
    snapshot_box: dict[str, object],
    expected: int,
) -> None:
    _ = expected  # canonical post-count == 3 enforced in composition
    fixture.assert_post_slice_04_subagent_stop_count(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


@then(
    'every "PreToolUse" entry whose command names "spine_ledger" carries the '
    '"# des-hook:" marker prefix'
)
def then_every_pre_tool_use_spine_ledger_carries_marker(
    fixture: InstallWiringFixture, snapshot_box: dict[str, object]
) -> None:
    fixture.assert_every_spine_ledger_pre_tool_use_entry_carries_des_hook_marker(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


@then(
    'every "SubagentStop" entry whose command names "spine_ledger" carries the '
    '"# des-hook:" marker prefix'
)
def then_every_subagent_stop_spine_ledger_carries_marker(
    fixture: InstallWiringFixture, snapshot_box: dict[str, object]
) -> None:
    fixture.assert_every_spine_ledger_subagent_stop_entry_carries_des_hook_marker(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


@then(
    "the shared `_is_des_command` predicate returns true for every "
    "spine-ledger entry's command string"
)
def then_is_des_command_matches_every_spine_ledger(
    fixture: InstallWiringFixture, snapshot_box: dict[str, object]
) -> None:
    fixture.assert_is_des_command_matches_every_spine_ledger_entry(
        snapshot_box["snapshot"]  # type: ignore[arg-type]
    )


# --- Unused-imports guard (ruff F401) --------------------------------------

# Re-exports for downstream slice authors and for ruff F401 quiet:
_TYPE_REEXPORTS = (
    InstallerInvocation,
    AggregatorInvocation,
    HookEventsSnapshot,
)
