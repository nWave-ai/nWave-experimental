#!/usr/bin/env python3
"""Fourth-carrier read side -- the MIKADO ledger, independently re-verified.

Design: docs/feature/f-mikado-node-closure-record/design/adrs/
adr-D70-mikado-node-closure-record.md (ADR-D70, D70-6). Feature-delta:
docs/feature/f-mikado-node-closure-record/feature-delta.md ([REF] Contract-
Tests row 2). DISTILL slice-02 of f-mikado-node-closure-record.

Promotes `docs/mikado/prototypes/d70_closure_record_probe.py`'s
`evaluate_node`/`independently_verify` into production, sourcing records
from `UnifiedEventStoreAdapter(project_root).read(LedgerFamily.MIKADO,
node_id)` in place of the prototype's in-memory `list[NodeClosureAttested]`,
and reusing the SAME two git ports `validate_mikado_tree_coherence.py`
already imports for its own SHA-vs-trunk / SHA-vs-content checks
(`git_commit_reachability.build_reachability`,
`git_commit_contents.build_contents`) -- no new git-access seam (Reuse
Analysis). A caller (the gate) constructs both ports ONCE and passes the
SAME instances into every call here, exactly as it already does for its own
three prose carriers.

Four states, never collapsed to three (prototype's own module docstring,
carried forward verbatim):

CLOSED               -- at least one closed-transition record exists whose
                         cited commit is independently confirmed reachable
                         from trunk AND to have rewritten the cited path.
OPEN                 -- at least one record exists for the node (the
                         mechanism has SEEN it) but no closed-transition
                         record independently verifies CLOSED.
REFUSED              -- a closed-transition record exists, none verifies
                         CLOSED, and at least one CONTRADICTS the claim (its
                         cited commit is not reachable, or is reachable but
                         did not rewrite the cited path). Worse than
                         absence -- an actively false claim -- so it is
                         never folded into COULD_NOT_DETERMINE.
COULD_NOT_DETERMINE  -- zero records exist for the node at all (absence is
                         NOT read as OPEN and NOT read as CLOSED); OR every
                         closed-transition record's own re-verification is
                         itself undecidable (e.g. an INDETERMINATE git read
                         during a repack race) and none verified CLOSED or
                         REFUSED.

Multi-claim rule (ADR-D70 D70-6 / feature-delta [REF] Failure Behaviour,
"the ledger is append-only... this supersedes the false claim for read
purposes... CLOSED wins if ANY claim verifies"): when a node carries more
than one closed-transition record, CLOSED wins over REFUSED if ANY record
independently verifies -- a later, correctly-citing record supersedes an
earlier REFUSED one for READ purposes, without ever editing history. Only
when NO record verifies CLOSED does a REFUSED record make the node REFUSED.

Two distinct REFUSED causes, distinguishable (never collapsed into one
undifferentiated message -- the gate's own `Finding.what` text must name
which applies, not merely "REFUSED"): a cited commit that is not reachable
from trunk at all (`RefusalCause.SHA_NOT_REACHABLE`), and a cited commit
that IS reachable but did not rewrite the cited path
(`RefusalCause.PATH_NOT_CARRIED`). `refusal_cause`/`node_refusal_cause` name
which applies; `NodeState` itself stays the closed four-member vocabulary
(zero new Finding/Severity vocabulary at the gate, per feature-delta Reuse
Analysis -- the distinction lives in the reason text, not in a new state).

Single-decision discipline (AT review, slice-02): `evaluate_node` and
`node_refusal_cause` NEVER re-derive the CLOSED/REFUSED verdict by calling
`reachability`/`contents` themselves -- every per-record verdict routes
through `independently_verify`, and every per-record cause routes through
`refusal_cause`. Two divergent copies of the same rule (one inline in the
node-level function, one in the per-record function) is the exact defect
this module exists to prevent.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any


sys.path.insert(0, str(Path(__file__).resolve().parent))

#: `des` is a `src/`-layout package. Under pytest, `pyproject.toml`'s
#: `pythonpath = ["src", "."]` already resolves it; under a standalone
#: invocation (the `mikado-tree-coherence` pre-commit hook,
#: `python3 scripts/validation/validate_mikado_tree_coherence.py`) it is not
#: on `sys.path` by default, so this mirrors the exact pattern
#: `git_commit_reachability.py`/`git_commit_contents.py` already use.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from git_commit_reachability import Reachability  # noqa: E402

from des.adapters.driven.logging.unified_event_store_adapter import (  # noqa: E402
    UnifiedEventStoreAdapter,
)
from des.domain.telemetry_paths import LedgerFamily  # noqa: E402


if TYPE_CHECKING:
    from git_commit_contents import CommitContentsPort
    from git_commit_reachability import CommitReachabilityPort


class NodeState(str, Enum):
    """The fourth carrier's four read-time states -- see module docstring."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    REFUSED = "REFUSED"
    COULD_NOT_DETERMINE = "COULD_NOT_DETERMINE"


class RefusalCause(str, Enum):
    """Which of the two distinct REFUSED causes applies to one record."""

    SHA_NOT_REACHABLE = "sha_not_reachable"
    PATH_NOT_CARRIED = "path_not_carried"


def independently_verify(
    record: dict[str, Any],
    *,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> NodeState:
    """Re-derive ONE closed-transition record's own claim -- never trust it.

    ``record`` is one flat row from ``ReadResult.records`` (the shape
    ``UnifiedEventStoreAdapter.append`` writes: ``record["transition"] ==
    "closed"``, ``record["cited_artifact"] == {"sha": ..., "path": ...}``).
    Returns exactly one of ``CLOSED`` / ``REFUSED`` / ``COULD_NOT_DETERMINE``
    -- never ``OPEN`` (that is a NODE-level absence-of-any-closure-claim
    verdict, not a per-record one; the caller filters non-``closed`` records
    before reaching here).

    ``reachability.reachable_from(sha, trunk_ref)`` first -- an
    ``INDETERMINATE`` outcome returns ``COULD_NOT_DETERMINE`` immediately
    (an environmental read failure is not evidence the claim is false, only
    that it could not be checked this run); a ``NOT_REACHABLE`` outcome
    returns ``REFUSED``. Only once the commit is confirmed ``REACHABLE`` does
    ``contents.changed_paths(...)`` run; an unavailable answer there also
    returns ``COULD_NOT_DETERMINE`` (never silently treated as REFUSED or
    CLOSED); the cited path absent from the changed set returns ``REFUSED``;
    present returns ``CLOSED``.
    """
    cited_artifact = record.get("cited_artifact") or {}
    cited_sha = cited_artifact.get("sha", "")
    cited_path = cited_artifact.get("path", "")

    answer = reachability.reachable_from(cited_sha, trunk_ref)
    if answer.outcome is Reachability.INDETERMINATE:
        return NodeState.COULD_NOT_DETERMINE
    if answer.outcome is Reachability.NOT_REACHABLE:
        return NodeState.REFUSED

    changed = contents.changed_paths(answer.resolved_sha or cited_sha)
    if not changed.is_available:
        return NodeState.COULD_NOT_DETERMINE
    if cited_path not in changed.paths:
        return NodeState.REFUSED
    return NodeState.CLOSED


def refusal_cause(
    record: dict[str, Any],
    *,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> RefusalCause | None:
    """Which distinct REFUSED cause applies to ``record``, or ``None``.

    ``None`` whenever ``independently_verify(record, ...)`` for the SAME
    record would not return ``REFUSED`` (i.e. it is CLOSED or
    COULD_NOT_DETERMINE) -- this function names WHY a REFUSED verdict holds,
    it never itself decides CLOSED/COULD_NOT_DETERMINE. The two causes are
    mutually exclusive by construction: a cited SHA is either not reachable
    at all (``SHA_NOT_REACHABLE``), or it IS reachable and simply did not
    rewrite the cited path (``PATH_NOT_CARRIED``) -- never both, because a
    SHA that is not reachable is never asked what it changed.
    """
    verdict = independently_verify(
        record, reachability=reachability, contents=contents, trunk_ref=trunk_ref
    )
    if verdict is not NodeState.REFUSED:
        return None

    cited_artifact = record.get("cited_artifact") or {}
    cited_sha = cited_artifact.get("sha", "")
    answer = reachability.reachable_from(cited_sha, trunk_ref)
    if answer.outcome is Reachability.NOT_REACHABLE:
        return RefusalCause.SHA_NOT_REACHABLE
    return RefusalCause.PATH_NOT_CARRIED


def _closed_records_for(node_id: str, *, project_root: Path) -> list[dict[str, Any]]:
    """This node's own records, filtered to closed-transition ones.

    Shared by ``evaluate_node`` and ``node_refusal_cause`` so the two never
    diverge on what "this node's closed records" means.
    """
    adapter = UnifiedEventStoreAdapter(project_root=project_root)
    result = adapter.read(LedgerFamily.MIKADO, node_id)
    node_records = [r for r in result.records if r.get("node_id") == node_id]
    return [r for r in node_records if r.get("transition") == "closed"]


def evaluate_node(
    node_id: str,
    *,
    project_root: Path,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> NodeState:
    """The node-level four-state verdict (ADR-D70 D70-6).

    Reads the node's own MIKADO partition via
    ``UnifiedEventStoreAdapter(project_root).read(LedgerFamily.MIKADO,
    node_id)``. Zero records -> ``COULD_NOT_DETERMINE``. Records present but
    none is a ``transition == "closed"`` record -> ``OPEN``. One or more
    closed-transition records -> apply the multi-claim rule (module
    docstring): ``CLOSED`` if ANY record's ``independently_verify`` returns
    ``CLOSED``; else ``REFUSED`` if ANY returns ``REFUSED``; else
    ``COULD_NOT_DETERMINE``. Never re-derives the per-record verdict itself
    -- every record's verdict comes from ``independently_verify``.
    """
    adapter = UnifiedEventStoreAdapter(project_root=project_root)
    result = adapter.read(LedgerFamily.MIKADO, node_id)
    node_records = [r for r in result.records if r.get("node_id") == node_id]
    if not node_records:
        return NodeState.COULD_NOT_DETERMINE

    closed_records = [r for r in node_records if r.get("transition") == "closed"]
    if not closed_records:
        return NodeState.OPEN

    any_refused = False
    for record in closed_records:
        verdict = independently_verify(
            record, reachability=reachability, contents=contents, trunk_ref=trunk_ref
        )
        if verdict is NodeState.CLOSED:
            return NodeState.CLOSED
        if verdict is NodeState.REFUSED:
            any_refused = True
    return NodeState.REFUSED if any_refused else NodeState.COULD_NOT_DETERMINE


def node_refusal_cause(
    node_id: str,
    *,
    project_root: Path,
    reachability: CommitReachabilityPort,
    contents: CommitContentsPort,
    trunk_ref: str,
) -> RefusalCause | None:
    """Which distinct REFUSED cause applies to ``node_id``, or ``None``.

    ``None`` whenever ``evaluate_node(node_id, ...)`` for the SAME
    arguments is not ``REFUSED``. When it IS ``REFUSED``, names the cause of
    the FIRST closed-transition record (ledger order) whose
    ``independently_verify`` returned ``REFUSED`` -- the gate's own
    ``Finding.what`` text uses this to distinguish "cited commit is not
    reachable from trunk" from "cited commit is reachable but does not
    carry the cited path" (never a single undifferentiated REFUSED message
    for both causes). Never re-derives the cause itself -- every record's
    cause comes from ``refusal_cause``.
    """
    node_state = evaluate_node(
        node_id,
        project_root=project_root,
        reachability=reachability,
        contents=contents,
        trunk_ref=trunk_ref,
    )
    if node_state is not NodeState.REFUSED:
        return None

    for record in _closed_records_for(node_id, project_root=project_root):
        cause = refusal_cause(
            record, reachability=reachability, contents=contents, trunk_ref=trunk_ref
        )
        if cause is not None:
            return cause
    return None


__all__ = [
    "NodeState",
    "RefusalCause",
    "evaluate_node",
    "independently_verify",
    "node_refusal_cause",
    "refusal_cause",
]
