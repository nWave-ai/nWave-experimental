"""Where one completed turn's durable fact is found again, and by what name.

A turn commit is an ordinary Git object -- `base` as its only parent, OUT of the
final candidate's parent chain (ADR-SSOT-002 Section 4a) -- and this namespace
is the only thing that keeps it findable by the NEXT process.

The grammar lives here rather than inside the runner because it now has two
readers: the runner, which WRITES a record at the end of a turn, and the
read-only state projection, which reads the same names to answer "what does this
value already carry".  Two hand-written copies of a ref grammar are two
contracts, and a drifted copy would make the projection report a turn absent
while the record sits on disk under the name the runner used.
"""

from __future__ import annotations

import hashlib


#: Nothing else reads or writes here, and a delivery ref never enters it.
TURN_REF_ROOT = "refs/nwave/turns"

#: The two facts a resume consumes.  `ORACLE_TURN` is recorded only once the
#: aggregate review has APPROVED the set, so one record answers both "was the
#: oracle authored" and "was it approved"; recording it at authoring time would
#: let a resume skip a review that had vetoed.
ORACLE_TURN = "oracle"
CRAFT_TURN = "craft"

#: The third record, added by ADR-DES-003 §5. It is keyed on the REQUEST rather
#: than on a value, because the candidate is whole-Request: `turn_ref(request,
#: request, VERIFY_TURN)`. Two things need it and neither had a substrate. `des
#: verify` must be free on a second call (L1), and `des integrate` must refuse a
#: candidate no verification covers -- a decision the orchestrator holds and the
#: carrier could not hold the fact for. It is also the durable home ADR-SSOT-002
#: Window 1a's anchor `Y` already needs: that anchor points at the diagnostic
#: turn log today, which the same subsection forbids any step to read.
VERIFY_TURN = "verify"

#: Where a rewritten Request's previous graph is kept (ADR-DES-003 §7). An
#: ordinary Git commit, like a turn commit: a measurement surface no step reads
#: to decide, and no new file store. It exists because the repair for a changed
#: mind used to be deleting the handover by hand -- six times in two days -- and
#: a deletion leaves nothing to read afterwards.
ARCHIVE_REF_ROOT = "refs/nwave/archive"


def archive_ref(stamp: str, request: str) -> str:
    """Where one rewritten Request's previous graph is archived."""
    return f"{ARCHIVE_REF_ROOT}/{stamp}-{digest(request)}"


def digest(text: str) -> str:
    """The fixed-length key one string contributes to a ref path.

    Fixed length at every level, so no two keys can collide as a Git directory
    and a file, and a leftover record from a different Request can never be read
    as this one's.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def turn_ref(request: str, observation: str, role: str) -> str:
    """One completed turn's ref, keyed by Request, value and role.

    KEYED BY THE REQUEST, which is why a rewrite must re-key: §7's kept values
    keep records that would otherwise be orphaned under the old digest.
    """
    return f"{TURN_REF_ROOT}/{digest(request)}/{digest(observation)}/{role}"


#: The verify record's SECOND half, keyed exactly like the first. `VERIFY_TURN`
#: keeps its predicate -- the ref names the candidate -- and this one names the
#: judgement over it, as a commit whose subject carries the closed word and
#: whose body carries the judge's own diagnostic. Two refs and not one because
#: a ref points at an object and the outcome is text: the same reason a turn
#: record is a commit here rather than a file.
VERIFY_OUTCOME_TURN = "verify-outcome"

#: Where an integration the ORCHESTRATOR decided is written down. Outside the
#: turn namespace because integration releases the turn records, and a decision
#: whose evidence disappears with the graph it decided about is no evidence.
DECISION_REF_ROOT = "refs/nwave/decisions"


def decision_ref(request: str, candidate: str) -> str:
    """Where one orchestrator integration decision is found again."""
    return f"{DECISION_REF_ROOT}/{digest(request)}/{candidate}"
