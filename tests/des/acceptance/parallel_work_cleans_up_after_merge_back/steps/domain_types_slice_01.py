"""DISTILL-interim wire contract for `des verify-worktree-cleanup` (slice-01).

No production code exists yet (`src/des/cli/verify_worktree_cleanup.py` is a
RED scaffold; `verify-worktree-cleanup` is not yet a registered `des`
subcommand). Per feature-delta `Wave: DESIGN / [REF] Driving Ports`, the CLI
emits a `nwave.worktree_cleanup.v1`-shaped JSON report naming every worktree's
path/branch/verdict/removed, exit 0 iff no `CLEANUP_DUE` entry remains
unresolved, exit 1 otherwise with WHAT/WHY/HOW (GDP-3). The exact envelope
shape is DISTILL-pinned HERE, concretely, as the acceptance criteria DELIVER
must satisfy -- mirrors the sibling `autonomous-consolidation-and-bugfix-loops`
slice-01 precedent (a DISTILL-interim wire contract named where DESIGN left
the concrete field names open).

    {"event": "WorktreeCleanupReport",
     "schema": "nwave.worktree_cleanup.v1",
     "entries": [{"path": <str>, "branch": <str>,
                  "verdict": "CLEAN"|"CLEANUP_DUE"|"NOT_YET_MERGEABLE",
                  "removed": <bool>}, ...],
     # present ONLY when exit_code == 1 (GDP-3 self-explaining refusal):
     "what": <str>, "why": <str>, "how": <str>}

`CleanupSweepOutcome` is the PORT-EXPOSED observable this slice's step bodies
assert on (Mandate 8 Universe) -- independently re-derived from REAL git state
(`git worktree list --porcelain`) wherever possible, not solely from the
not-yet-existing payload, so the RED reason is genuine business behaviour
missing, never a parsing artifact of an absent module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorktreeVerdictPhrase(Enum):
    """The 3 fixture states `Given` steps select between (typed-parameter
    lookup, Mandate-12 criterion 2 -- never a raw string dispatch)."""

    CONFIRMED_MERGED_STILL_REGISTERED = (
        "confirmed merged into the target branch and still registered"
    )
    NOT_YET_MERGED = "not yet merged into the target branch"
    NO_LINKED_WORKTREES = "has no linked worktrees registered at all"


PHRASE_BY_TEXT: dict[str, WorktreeVerdictPhrase] = {
    phrase.value: phrase for phrase in WorktreeVerdictPhrase
}


@dataclass(frozen=True)
class CleanupSweepOutcome:
    """Port-exposed observable outcome of one `verify-worktree-cleanup` sweep.

    Every field is re-derivable from a REAL git/ledger read, independent of
    whether the not-yet-existing CLI ever produces a parseable payload --
    the RED reason stays "wrong behaviour", never "no JSON to parse".
    """

    exit_code: int
    event: str | None
    entry_count: int
    worktree_removed: bool
    still_registered: bool
    has_what_why_how: bool
    new_feature_end_pending_count: int
