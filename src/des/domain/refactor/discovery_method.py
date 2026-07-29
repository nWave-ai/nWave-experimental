"""Discovery-method domain -- the CHANNEL a pile item was found through.

CREATE_NEW (Mikado D01). ``defects.md``/``done.md`` record WHAT was found and
never HOW, so the yield of a verification method has no denominator and every
per-method value question answers NO_EVIDENCE. ``discovered_by=`` is that
denominator, declared per row.

Shape deliberately MIRRORS the already-ratified ``paradigm_select`` precedent
in this same package -- a closed ``str`` enum plus a selection dataclass whose
negative path carries a WHAT/WHY/HOW reason instead of a bare bool. Two fields
with the same job (a small closed vocabulary declared on a pile row, refused
when unrecognised) get the same shape; inventing a second idiom for the second
field is how a codebase acquires two of everything.

The closed set is DERIVED, not invented: each member is a channel actually
attested in the prose of the two real pile files as of 2026-07-28 (row counts
are occurrences across ``defects.md`` + ``done.md``). ``measurement``
(``MISURATO``/``MEASURED``, by far the most frequent phrase at 185) is
deliberately NOT a member -- it names how a claim was VERIFIED, not how the
defect was FOUND, and admitting it would repeat the very GDP-8 error the
``RITRATTATO-shipped-assets-hardcode-vendor-paths`` row documents: classifying
on the DESIGNATION (the word present in the text) rather than the PROPERTY
(the channel that surfaced the defect).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecognizedDiscoveryMethod(str, Enum):
    """The closed set of channels a pile item may declare it was found through.

    ``UNATTRIBUTED`` is a first-class member, not a hole: "I looked and cannot
    say" is a real, DECLARABLE answer, and it is also what a row written before
    this field existed resolves to on parse. Keeping it inside the set is what
    lets a consumer sum coverage over the whole pile instead of over the subset
    that happens to carry a token.
    """

    #: Found while delivering a slice -- the defect surfaced in the work itself.
    SLICE_EXECUTION = "slice-execution"
    #: Reported by a dispatched lane/shard agent working its own assignment.
    LANE_REPORT = "lane-report"
    #: Found by a deliberate sweep/census whose purpose was to find defects.
    SYSTEMATIC_AUDIT = "systematic-audit"
    #: Found by searching the tree (grep/AST scan) for a suspected shape.
    CODE_SEARCH = "code-search"
    #: Found because something broke in operation -- a crash, a lost worktree.
    OPERATIONAL_INCIDENT = "operational-incident"
    #: Found by a review that set out to FALSIFY an existing claim.
    ADVERSARIAL_REVIEW = "adversarial-review"
    #: Found because a gate refused and the refusal was correct.
    GATE_REFUSAL = "gate-refusal"
    #: Declared unknown -- and the value a pre-field row parses as.
    UNATTRIBUTED = "unattributed"


@dataclass(frozen=True)
class DiscoveryMethodSelection:
    """The outcome of selecting a declared discovery channel -- a WHAT/WHY/HOW
    refusal on the negative path, never a bare bool (the standing error-surface
    mandate; same shape as ``ParadigmSelection``)."""

    accepted: bool
    method: str | None
    reason: str | None = None


def select_discovery_method(declared: str) -> DiscoveryMethodSelection:
    """Select the discovery channel for a pile item's declared field.

    Single-source read of the item's OWN declared token: there is no second
    channel to compare against, so "unrecognised", "near-miss abbreviation"
    and "absent" collapse into ONE refusal condition -- the token is not a
    member of ``RecognizedDiscoveryMethod``.

    An empty string refuses rather than resolving to ``UNATTRIBUTED``. The two
    are different facts -- "nobody declared anything" versus "the author
    declared they could not tell" -- and collapsing them here would re-create,
    inside the fix, the exact loss of information the field exists to undo.
    """
    try:
        RecognizedDiscoveryMethod(declared)
    except ValueError:
        return DiscoveryMethodSelection(
            accepted=False, method=None, reason=_refusal_message(declared)
        )
    return DiscoveryMethodSelection(accepted=True, method=declared)


def _refusal_message(declared: str) -> str:
    """WHAT/WHY/HOW: names the offending token verbatim AND the full accepted
    set, because the realistic error is a near-miss (``audit`` for
    ``systematic-audit``) where knowing only that you are wrong does not tell
    you what to write instead."""
    recognized = ", ".join(member.value for member in RecognizedDiscoveryMethod)
    return (
        f"unrecognized declared discovery method {declared!r} -- the "
        "discovered_by= field takes a closed vocabulary, not free text, "
        "because a channel nobody can group by is not a denominator. Fix: set "
        "this pile row's discovered_by= field to one of the recognized values: "
        f"{recognized}."
    )
