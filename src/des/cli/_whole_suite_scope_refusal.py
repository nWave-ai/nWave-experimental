"""Shared verification-scope whole-suite-coverage refusal (K4 Run 12).

Mirrors `_verification_command_refusal.py`'s shape: `des dispatch` and
`des validate-delivery-contract` both call this, one WHAT/WHY/HOW message,
no drifting second copy across the two point-of-use verification call
sites (ADR-SSOT-002 Section 4a item 9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.workspace_test_command_resolver import (
    contract_covers_whole_suite,
    declared_whole_suite_command,
)


if TYPE_CHECKING:
    from pathlib import Path


def missing_whole_suite_scope_finding(
    repo_root: Path, contract: dict
) -> tuple[str, str, str] | None:
    """One `(what, why, how)` defect when the workspace's own root
    `CLAUDE.md` declares a whole-suite test command that `verification-
    scope.commands` never carries -- `None` when it declares none, or when
    one command already carries that exact scope."""
    if contract_covers_whole_suite(repo_root, contract):
        return None
    declared = declared_whole_suite_command(repo_root)
    command_text = " ".join(declared or [])
    return (
        f"verification-scope.commands never carries the whole-suite scope "
        f"this workspace's own root CLAUDE.md declares ({command_text!r})",
        "an oracle-only verification scope is blind to regressions outside "
        "the new oracle (K4 Run 12: an N+1 query, two stale pinned "
        "assertions and a crash on unsaved instances surfaced only through "
        "3 reviewer rounds instead of the crafter's own BASELINE/GREEN)",
        "add one more `verification-scope.commands` entry carrying the "
        "exact whole-suite command CLAUDE.md states, alongside the oracle "
        "command(s) already there -- the crafter's BASELINE already runs "
        "every listed command, so this is the one place the fix belongs",
    )
