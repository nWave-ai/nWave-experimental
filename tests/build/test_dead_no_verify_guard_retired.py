"""Regression -- the superseded `git_no_verify_guard.py` stays retired.

Hook-audit fix 2026-07-29 (Difetto D). `git_no_verify_guard.py` (234 lines, a
well-designed audited-kill-switch guard) self-declared itself superseded by
`no_verify_reminder.py` in the successor's own docstring ("Supersedes the
heavier git_no_verify_guard.py thread per the lean direction: Ale 2026-06-26").
Verified: only `no_verify_reminder.py` was ever referenced by the canonical
install-wiring SSOT (`scripts/shared/hook_definitions.py` +
`scripts/install/plugins/des_plugin.py`); `git_no_verify_guard.py` appeared
nowhere in that wiring, in any test, or in scripts/README.md -- only in its own
file and two historical/analysis docs (a 2026-06-25 session handoff describing
a since-superseded manual `~/.claude/settings.json` edit on one machine, never
part of the shipped install pipeline). Same risk class as Difetto A/B: code
that reads as protective but never fires is worse than no code at all --
someone debugging "why didn't --no-verify get caught" would read it and
wrongly conclude it was live.

Retired (deleted) rather than re-wired: the lean successor already covers the
same STANDING (a bypass needs explicit human authorization) with less surface,
and re-wiring the heavier guard would just resurrect the duplication Ale
explicitly moved away from on 2026-06-26.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_RETIRED_SCRIPT = "scripts/hooks/git_no_verify_guard.py"

_CANONICAL_WIRING_FILES = (
    "scripts/shared/hook_definitions.py",
    "scripts/install/plugins/des_plugin.py",
)


def test_retired_script_is_absent_from_disk() -> None:
    """`git_no_verify_guard.py` must not be resurrected."""
    assert not (PROJECT_ROOT / _RETIRED_SCRIPT).exists(), (
        "WHAT: the retired git_no_verify_guard.py is back on disk.\n"
        "WHY: it was superseded by the leaner no_verify_reminder.py "
        "(Ale 2026-06-26) and was never wired into the install pipeline "
        "afterward -- resurrecting it re-opens the same-standing duplication "
        "the successor exists to avoid.\n"
        "HOW: extend no_verify_reminder.py instead of reviving this file."
    )


def test_canonical_install_wiring_never_references_the_retired_guard() -> None:
    """The install-wiring SSOT must not re-wire the retired guard."""
    offenders = [
        rel
        for rel in _CANONICAL_WIRING_FILES
        if "git_no_verify_guard" in (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "WHAT: a canonical install-wiring file references the retired "
        "git_no_verify_guard.py.\n"
        "WHY/HOW: see test_retired_script_is_absent_from_disk.\n"
        f"    {offenders}"
    )


def test_successor_guard_is_the_one_actually_wired() -> None:
    """Positive control: `no_verify_reminder.py` -- not nothing -- fills the gap.

    Guards against a retirement that silently drops the STANDING enforcement
    entirely rather than replacing it with the leaner successor.
    """
    present = [
        rel
        for rel in _CANONICAL_WIRING_FILES
        if "no_verify_reminder" in (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    ]
    assert present == list(_CANONICAL_WIRING_FILES), (
        "WHAT: the successor no_verify_reminder.py is missing from the "
        "canonical install-wiring SSOT.\n"
        "WHY: retiring the old guard without the successor actually wired "
        "would silently drop --no-verify enforcement entirely.\n"
        f"    present in: {present}"
    )
