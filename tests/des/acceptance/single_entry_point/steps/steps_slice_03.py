"""Step methods for slice-03 — every repo-internal caller uses `des <sub>`.

Mandate-12 criterion 3: every step body has ≤ 2 statements, the last is a
delegation to `composition.<method>(...)`, no control flow in bodies. All
business logic lives in `composition.py`.

Pillar 1: step names speak the domain (migration scan, runtime-authoring
trees, legacy module-form, legacy console-script names, package contract,
shipped entries). NO technical jargon (no "regex", "grep", "AST", "rglob",
"pyproject"). Technical detail lives behind the composition methods.

Pillar 2: chained narrative — every scenario reuses the Background's
Given_the_nwave_runtime_is_installed from steps_slice_01. The When/Then
chain reads as a sequential migration-audit story per AT.

Mandate 9 + 11: layer 3 filesystem scan + TOML parse — example-only, NO
PBT machinery. AT-07/AT-08 are class-level set-difference assertions
(zero hits across the runtime-authoring trees); AT-09 is a bounded-change
contract over the packaged console-script surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import then, when


if TYPE_CHECKING:
    from .composition import DesCliComposition


# Feature binding lives in `../test_slice_03_call_site_migration.py` — that
# binder calls `scenarios(...)` after the pytest config stack is active.


# ---- When ---------------------------------------------------------------


@when(
    "the migration scan inspects the runtime-authoring trees for module-form references",
    target_fixture="module_form_hits",
)
def when_the_migration_scan_inspects_for_module_form_references(
    installed_runtime: DesCliComposition,
) -> tuple[tuple[str, int, str], ...]:
    return installed_runtime.scan_runtime_authoring_trees_for_module_form()


@when(
    "the migration scan inspects the runtime-authoring trees for the five legacy "
    "console-script names",
    target_fixture="des_prefixed_hits",
)
def when_the_migration_scan_inspects_for_des_prefixed_references(
    installed_runtime: DesCliComposition,
) -> tuple[tuple[str, int, str], ...]:
    return installed_runtime.scan_runtime_authoring_trees_for_des_prefixed_shims()


@when(
    "the package contract test inspects the shipped console-script entries",
    target_fixture="shipped_console_entries",
)
def when_the_package_contract_inspects_shipped_entries(
    installed_runtime: DesCliComposition,
) -> tuple[str, ...]:
    return installed_runtime.read_packaged_console_script_entries()


# ---- Then ---------------------------------------------------------------


@then("the migration scan finds zero occurrences of the legacy module-form invocation")
def then_migration_scan_finds_zero_module_form_hits(
    module_form_hits: tuple[tuple[str, int, str], ...],
) -> None:
    assert module_form_hits == (), (
        "AT-07: legacy module-form invocation `python -m des.cli.X` still "
        "present in the runtime-authoring trees. Every callsite MUST migrate "
        "to `des <subcommand>`. Hits:\n"
        + "\n".join(
            f"  {relpath}:{lineno}: {line}"
            for relpath, lineno, line in module_form_hits
        )
    )


@then("the migration scan finds zero occurrences of the legacy console-script names")
def then_migration_scan_finds_zero_des_prefixed_hits(
    des_prefixed_hits: tuple[tuple[str, int, str], ...],
) -> None:
    assert des_prefixed_hits == (), (
        "AT-08: legacy `des-{log-phase|init-log|verify-integrity|roadmap|"
        "health-check}` console-script names still present in the runtime-"
        "authoring trees. Every callsite MUST migrate to `des <subcommand>`. "
        "Hits:\n"
        + "\n".join(
            f"  {relpath}:{lineno}: {line}"
            for relpath, lineno, line in des_prefixed_hits
        )
    )


@then("the migration scan excludes its own pattern declaration")
def then_migration_scan_excludes_its_own_pattern_declaration(
    installed_runtime: DesCliComposition,
) -> None:
    exclusions = installed_runtime.regression_test_self_exclusion_paths()
    assert "tests/regression/test_no_module_form_in_runtime_emit.py" in exclusions, (
        "OQ-3 self-exclusion contract: the regression test file MUST be in "
        f"the scanner's exclusion list (it holds the patterns AS pattern "
        f"declarations). Current exclusions: {exclusions}"
    )


@then("the shipped entries include the installer entry and the des dispatcher entry")
def then_shipped_entries_include_installer_and_dispatcher(
    shipped_console_entries: tuple[str, ...],
) -> None:
    missing = {"nwave-ai", "des"} - set(shipped_console_entries)
    assert not missing, (
        f"AT-09: [project.scripts] missing required entries: {sorted(missing)}. "
        f"Shipped entries: {shipped_console_entries}. The installer entry "
        f"`nwave-ai` and the dispatcher entry `des` MUST both be declared."
    )


@then("no des-prefixed legacy entry remains in the package surface")
def then_no_des_prefixed_legacy_entry_remains(
    shipped_console_entries: tuple[str, ...],
) -> None:
    legacy_survivors = [
        entry
        for entry in shipped_console_entries
        if entry
        in {
            "des-log-phase",
            "des-init-log",
            "des-verify-integrity",
            "des-roadmap",
            "des-health-check",
        }
    ]
    assert not legacy_survivors, (
        f"AT-09: legacy `des-*` console-script entries still in [project.scripts]: "
        f"{legacy_survivors}. Slice-01 collapsed them into the `des` dispatcher; "
        f"any survivor here defeats DDD-8."
    )
