#!/usr/bin/env python3
"""Shared orchestrator-affordance reconciliation rule (R-8).

# des-hook:orchestrator-affordance-resolution

Extracted out of `orchestrator_affordance_refresh.py` so a SECOND producer --
`src/des/adapters/drivers/hooks/session_start_handler.py` -- can reach the
SAME decision instead of re-implementing it (RCA
`docs/feature/fix-affordance-resolver-prefers-stale-copy/rca.md`, Root Cause
E / R-8). Duplicating the rule across two modules would recreate the exact
"two rules, no shared SSOT" root cause one level up.

Candidate ENUMERATION (which roots to try, hopped off which `__file__`) and
the SELECTION wiring around them stay per-caller: the standalone hook has
three candidates including a dev checkout, the DES-side producer has two
install roots and no dev checkout, and the hop depth off `__file__` differs
between them. Only the DECISION between two INSTALL ROOTS OBLIGED TO AGREE
lives here.

Stdlib-only. Never statically imported across the `scripts/**` <->
`src/des/**` boundary in either direction: each side reaches it as a
same-directory SHIPPED FILE -- a sibling import for the standalone hook, an
`importlib.util.spec_from_file_location` load for `session_start_handler.py`.
Shipped to both runtime surfaces by the two already-existing installer lists
(`DES_HOOKS`, `_NWAVE_RUNTIME_HOOK_FILES` in
`scripts/install/plugins/des_plugin.py`).

Pure read-plus-hash functions over caller-supplied paths -- no writes, no
mutation, and never raising: an unreadable asset file is skipped, matching
the pre-extraction contract this module preserves exactly.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


DIVERGENCE_NOTICE_TEMPLATE = (
    "<DIVERGED-INSTALL-ROOTS>\n"
    "Two install outputs for the orchestrator-affordance assets disagree:\n"
    "  - {installed}\n"
    "  - {host_neutral}\n"
    "Served the fresher root by source mtime. Reinstall (targeting BOTH\n"
    "`claude_code` and a host-neutral platform) to reconcile this machine.\n"
    "</DIVERGED-INSTALL-ROOTS>\n\n"
)

INDETERMINATE_DIVERGENCE_NOTICE_TEMPLATE = (
    "<DIVERGED-INSTALL-ROOTS COULD-NOT-VERIFY-FRESHNESS>\n"
    "Two install outputs for the orchestrator-affordance assets disagree:\n"
    "  - {installed}\n"
    "  - {host_neutral}\n"
    "Freshness could not be determined (missing or identical source mtime),\n"
    "so neither root could be confidently picked as current -- served the\n"
    "Claude-scoped one. Reinstall to reconcile this machine.\n"
    "</DIVERGED-INSTALL-ROOTS>\n\n"
)


def directory_content_digest(directory: Path) -> str:
    """sha256 over every `*.md` file's bytes under `directory`, sorted by name.

    The PROPERTY this compares is content, not existence: two install roots
    that ship byte-identical assets are NOT a divergence, however far apart
    their mtimes sit (GDP-8 -- decide on the property, never a designation
    like "a tree is here").
    """
    hasher = hashlib.sha256()
    for path in sorted(directory.glob("*.md")):
        try:
            hasher.update(path.read_bytes())
        except OSError:
            continue
    return hasher.hexdigest()


def directory_freshness(directory: Path) -> float | None:
    """Newest `*.md` mtime under `directory`, or `None` if none is readable."""
    mtimes: list[float] = []
    for path in sorted(directory.glob("*.md")):
        try:
            mtimes.append(path.stat().st_mtime)
        except OSError:
            continue
    if not mtimes:
        return None
    return max(mtimes)


def reconcile_install_roots(
    installed: Path, host_neutral: Path
) -> tuple[Path, str | None]:
    """Reconcile TWO INSTALL OUTPUTS that are obliged to agree.

    Never call this for a dev-checkout candidate -- a dev checkout is
    deliberately at whatever revision the operator checked out, and
    reconciling it against a global install would reintroduce the exact
    shadowing bug the candidate order exists to prevent. Callers keep that
    protection in their own selection wiring.

    Reconciled first on CONTENT DIGEST (agreement is silent, however far
    apart the mtimes sit -- a fresh reinstall of identical content is not a
    divergence), then on SOURCE MTIME (the fresher root is served and the
    disagreement is announced IN-BAND, because Claude Code discards hook
    stderr). When digests differ and freshness cannot be confidently decided
    (a missing/unreadable mtime on either side, or an identical mtime), the
    caller gets an explicit COULD-NOT-VERIFY notice rather than a confident
    silent pick (GDP-6 / GDP-8 third-state corollary).
    """
    if directory_content_digest(installed) == directory_content_digest(host_neutral):
        return installed, None

    installed_mtime = directory_freshness(installed)
    host_neutral_mtime = directory_freshness(host_neutral)

    if (
        installed_mtime is None
        or host_neutral_mtime is None
        or installed_mtime == host_neutral_mtime
    ):
        return installed, INDETERMINATE_DIVERGENCE_NOTICE_TEMPLATE.format(
            installed=installed, host_neutral=host_neutral
        )

    winner = installed if installed_mtime > host_neutral_mtime else host_neutral
    return winner, DIVERGENCE_NOTICE_TEMPLATE.format(
        installed=installed, host_neutral=host_neutral
    )
