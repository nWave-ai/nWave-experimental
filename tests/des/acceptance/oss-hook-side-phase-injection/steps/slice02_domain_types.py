"""Domain types for slice-02 -- DISTILL dispatch marker enforcement +
DELIVER-exit symmetry.

slice-02 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).
Every domain noun in the slice-02 Gherkin is expressed once here as a typed
enum or NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- domain types module exists with typed
enums for every domain noun used in Gherkin).

slice-02 covers two driving surfaces:

  G-DISTILL-PRE (PreToolUse) -- a ``D_DISTILL`` acceptance-designer dispatch is
  validated for its marker set BEFORE it runs. A dispatch carrying
  ``DES-MODE:atdd_pure`` + ``DES-PHASE:D_DISTILL`` + ``DES-SLICE:feature-end`` +
  ``DES-PROJECT-ID`` classifies ``'valid'`` (the closed-world XOR holds:
  D_DISTILL is a feature-end phase, scope is the feature-end literal) and is
  ALLOWED. A dispatch missing ``DES-PROJECT-ID``, or carrying a ``slice-N``
  per-slice scope instead of ``feature-end``, is BLOCKED
  ``DistillDispatchMarkerSetIncomplete`` (the DISTILL-specific mirror of the U1
  ``AtddPureMarkerSetIncomplete`` block).

  G-DELIVER-EXIT (SubagentStop) -- a ``G_COMMIT`` crafter return that verifies
  its slice commit now ALSO leaves a ``WorkflowPhaseCompletedGCommit`` ledger
  record (``slice_id=N``) alongside the existing ``SliceCommitVerified`` -- the
  DELIVER-exit half of the SF ADR-016 success-terminal symmetry (the DISTILL-exit
  half shipped in slice-01 as ``WorkflowPhaseCompletedDistill``).

HARD INVARIANT (hook-can't-spawn-agent): both gates only ALLOW / BLOCK / EMIT --
they never dispatch an agent. The observable surface is the block decision, the
exit code, and the ledger record -- never "the hook dispatched an agent".
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "atdd-pure-demo").
FeatureId = NewType("FeatureId", str)


# A carpaccio slice identifier (e.g. "slice-01").
class DispatchVerdict(str, Enum):
    """The user-observable verdict of the G-DISTILL-PRE PreToolUse gate.

    ALLOWED -- the ``D_DISTILL`` dispatch carries a complete, coherent marker
               set; the gate permits the dispatch to run.
    BLOCKED -- the ``D_DISTILL`` dispatch is missing ``DES-PROJECT-ID`` or
               carries an incoherent (phase, scope) pair; the gate refuses it
               via a ``{"decision": "block"}`` JSON body.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class DistillDispatchShape(str, Enum):
    """The shape of the ``D_DISTILL`` acceptance-designer dispatch marker set.

    COMPLETE        -- ``DES-MODE:atdd_pure`` + ``DES-PHASE:D_DISTILL`` +
                       ``DES-SLICE:feature-end`` + ``DES-PROJECT-ID`` all
                       present and coherent; classifies ``'valid'`` via the
                       closed-world XOR; the gate ALLOWS.
    PROJECT_ID_MISSING
                    -- every marker present EXCEPT ``DES-PROJECT-ID``; the gate
                       BLOCKS ``DistillDispatchMarkerSetIncomplete`` (the
                       feature id is the substrate key the DISTILL-exit gate
                       later needs).
    SLICE_SCOPED    -- ``DES-PHASE:D_DISTILL`` paired with a ``slice-N``
                       per-slice scope instead of the ``feature-end`` literal;
                       the closed-world XOR fails (a feature-end phase with a
                       per-slice scope is incoherent), so the gate BLOCKS
                       ``DistillDispatchMarkerSetIncomplete``.
    """

    COMPLETE = "complete"
    PROJECT_ID_MISSING = "project-id-missing"
    SLICE_SCOPED = "slice-scoped"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies -- each body is a single typed lookup + composition call).

# The block event name expected per Gherkin phrase for the G-DISTILL-PRE gate.
# ``allows the dispatch`` carries no block event.
DISTILL_DISPATCH_BLOCK_EVENT_BY_PHRASE: dict[str, str | None] = {
    "allows the dispatch": None,
    "an incomplete DISTILL dispatch marker set": "DistillDispatchMarkerSetIncomplete",
}

# The defective-dispatch shape per Gherkin phrase (AT-2 enumerates the two
# materially-distinct ways a D_DISTILL dispatch is marker-incomplete: C5/C6).
DEFECTIVE_DISPATCH_SHAPE_BY_PHRASE: dict[str, DistillDispatchShape] = {
    "is missing its project identifier": DistillDispatchShape.PROJECT_ID_MISSING,
    "is scoped to a single slice instead of the whole feature": (
        DistillDispatchShape.SLICE_SCOPED
    ),
}
