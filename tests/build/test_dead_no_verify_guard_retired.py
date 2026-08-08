"""Regression -- retired --no-verify guard scripts stay retired.

Hook-audit fix 2026-07-29 (Difetto D). `git_no_verify_guard.py` (234 lines, a
well-designed audited-kill-switch guard) self-declared itself superseded by
`no_verify_reminder.py` in the successor's own docstring ("Supersedes the
heavier git_no_verify_guard.py thread per the lean direction: Ale 2026-06-26").
`git_no_verify_guard.py` appeared nowhere in the successor's wiring, in any
test, or in scripts/README.md -- only in its own file and two
historical/analysis docs (a 2026-06-25 session handoff describing a
since-superseded manual `~/.claude/settings.json` edit on one machine, never
part of the shipped install pipeline).

Deletion-first cleanup 2026-08-08 (base 580804264): `no_verify_reminder.py`
itself was in turn found inert -- never registered in the
`hook_definitions.HOOK_EVENTS` SSOT, so generated Claude settings never
invoked it. It was only copied into fresh installs via `des_plugin.DES_HOOKS`
as dead packaging weight. Same risk class as Difetto A/B: code that reads as
protective but never fires is worse than no code at all -- someone debugging
"why didn't --no-verify get caught" would read it and wrongly conclude it was
live.

The exact historical hook-command string it once emitted remains in
`des_plugin._RETIRED_HOOK_COMMANDS` ON PURPOSE -- old installations still
carry that string in their `settings.json` and need it stripped on upgrade --
so this file does not assert the string is absent from `des_plugin.py`
entirely, only that the packaging roster (`DES_HOOKS`) and the generated
hook config no longer re-wire it live.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_RETIRED_SCRIPTS = (
    "scripts/hooks/git_no_verify_guard.py",
    "scripts/hooks/no_verify_reminder.py",
)


def test_retired_scripts_are_absent_from_disk() -> None:
    """Neither retired --no-verify guard script may be resurrected."""
    present = [rel for rel in _RETIRED_SCRIPTS if (PROJECT_ROOT / rel).exists()]
    assert not present, (
        "WHAT: a retired --no-verify guard script is back on disk.\n"
        "WHY: git_no_verify_guard.py was superseded 2026-06-26; its successor "
        "no_verify_reminder.py was itself retired 2026-08-08 as dead-but-shipped "
        "packaging weight that generated settings never invoked.\n"
        "HOW: extend the live --no-verify guard in hook_definitions.py instead "
        "of reviving a retired script.\n"
        f"    {present}"
    )


def test_canonical_install_wiring_never_references_git_no_verify_guard() -> None:
    """The install-wiring SSOT must not re-wire the original retired guard."""
    wiring_files = (
        "scripts/shared/hook_definitions.py",
        "scripts/install/plugins/des_plugin.py",
    )
    offenders = [
        rel
        for rel in wiring_files
        if "git_no_verify_guard" in (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "WHAT: a canonical install-wiring file references the retired "
        "git_no_verify_guard.py.\n"
        "WHY/HOW: see test_retired_scripts_are_absent_from_disk.\n"
        f"    {offenders}"
    )


def test_hook_definitions_never_references_no_verify_reminder() -> None:
    """Generated Claude settings must never re-wire the retired module path."""
    from scripts.shared.hook_definitions import generate_hook_config

    config = generate_hook_config(lambda action: f"python3 -m des.hook {action}")
    commands = [
        hook["command"]
        for entries in config.values()
        for entry in entries
        for hook in entry["hooks"]
    ]
    assert all("no_verify_reminder" not in cmd for cmd in commands)


def test_des_hooks_packaging_roster_no_longer_ships_no_verify_reminder() -> None:
    """Fresh installs must stop copying the retired inert script.

    The exact historical hook-command string remains in
    `des_plugin._RETIRED_HOOK_COMMANDS` on purpose (see module docstring) --
    this check is scoped to the packaging list, not to every string in the
    file.
    """
    from scripts.install.plugins.des_plugin import DESPlugin

    assert "no_verify_reminder.py" not in DESPlugin.DES_HOOKS
