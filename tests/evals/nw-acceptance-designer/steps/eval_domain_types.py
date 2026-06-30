"""Typed vocabulary for the slice-08 consolidate-on-add EVAL ATs (Mandate-12).

slice-08 of sustainable-test-suite is the EVAL slice (DDD-7). It EXTENDS the
`nw-agent-evals` substrate with a NEW deterministic grader row: given an ATD/crafter
agent TRACE (trace-JSONL), the grader detects whether the run CONSOLIDATED-ON-ADD —
"steps reuse the ATD-authored shared vocabulary" (grader signal #2, DESIGN line 411,
C4 line 369). The grader is deterministic + git-free: trace-JSONL in, closed verdict out.

This module owns the TEST-SIDE typed verdict vocabulary the step bodies coerce Gherkin
literals into (no raw `str` where an enum exists). The SSOT for these tokens (DELIVER
lands them) is the new consolidate-on-add grader the substrate gains — the eval-substrate
grader module under `tests/evals/` (or `src/des/` if DELIVER homes the grader there); the
ATs assert against the grader's closed verdict.
"""

from __future__ import annotations

from enum import Enum


class ConsolidateOnAddEvalVerdict(str, Enum):
    """The closed deterministic verdict the consolidate-on-add grader emits over a trace.

    SSOT (DELIVER lands these): the new consolidate-on-add grader row added to the
    `nw-agent-evals` substrate (DDD-7 EXTEND, no new framework). The grader parses the
    captured trace-JSONL (the substrate already parses `tool_use` entries for tools / skills
    / artifacts) and classifies the run by signal #2 — does the authored step layer REUSE
    the ATD-authored shared vocabulary?

      * `consolidate-on-add` — the trace shows the authored step definitions REUSING the
                               shared vocabulary: the new step file imports from the shared
                               step/schema module AND binds a declarative step to an existing
                               shared step definition (no re-declaration), AND the run
                               declared a CONSOLIDATE/REUSE intent. Signal #2 DETECTED → PASS.
      * `add-only`           — the trace shows fresh per-feature step definitions: new step
                               files re-declare their own constants/steps with NO
                               import-from-shared and NO reuse of an existing shared step
                               definition, and NO CONSOLIDATE/REUSE intent declared. The
                               grader FLAGS the run as add-only (signal #2 absent).
      * `indeterminate`      — the trace cannot be parsed for the signal (empty / no
                               authoring tool_use entries / undecodable). Degrade-LOUD: the
                               grader NEVER fabricates a `consolidate-on-add` pass when the
                               evidence is unreadable (mirrors the slice-07 INDETERMINATE
                               denominator-absent discipline).
    """

    CONSOLIDATE_ON_ADD = "consolidate-on-add"
    ADD_ONLY = "add-only"
    INDETERMINATE = "indeterminate"


__all__ = ["ConsolidateOnAddEvalVerdict"]
