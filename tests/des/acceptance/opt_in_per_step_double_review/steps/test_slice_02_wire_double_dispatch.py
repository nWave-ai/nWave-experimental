"""slice-02 acceptance: the DISTILL Final Wave Review Gate dispatch PROCEDURE
actually consults ``requires_agreement(step_id)`` (slice-01, shipped) and applies
the DD-3 agreement predicate + escalation rules (ADR-RST-002 decision 4).

slice-01 proved ``ResolvedReviewStepSet.requires_agreement(step_id)`` resolves
correctly via DIRECT ``DESConfig`` calls, but none of that wired the resolved
decision into the actual consumer: ``nw-distill/SKILL.md``'s Final Wave Review
Gate dispatch prose, which at HEAD dispatches each active step exactly once
(the sibling ``rigor-review-step-toggles`` feature's own slice-07 wiring) and
says nothing about ``requires_agreement``, double-dispatch, or the DD-3
outcome-class predicate. ``docs/feature/opt-in-per-step-double-review/
design/adrs/ADR-RST-002-per-step-review-agreement.md`` decision 4 is the
wiring specification this slice scaffolds against.

This is a methodology-SKILL.md (LLM-consumed prose) change, not testable
Python -- same artifact class as the sibling's own slice-07
(``test_slice_07_wire_review_dispatch.py``). The pattern mirrors slice-07
exactly (mirrored, not cross-imported -- this feature's own established
per-feature self-containment convention, see slice-01's ``conftest.py``
docstring): a real file read of the shipped, REPO-TRACKED
``nWave/skills/nw-distill/SKILL.md`` (NOT the installed ``~/.claude/skills/``
copy -- same path-authority rationale slice-07 already documented: the
installed copy is install-time-generated output, not portable/hermetic).

Driving surface (real, in-process, hermetic -- no interpreter fork, no
``~/.claude`` path): a REAL file read of the shipped
``nWave/skills/nw-distill/SKILL.md``, scoped to the "## Final Wave Review
Gate" section (bounded by the next "## " heading) -- the section
ADR-RST-002 decision 4 names as the EXTEND target.

Active-RED topology (nw-distill-red-scaffolding P1-P4, mirrors slice-07
exactly):
  P1  module-top imports nothing not-yet-implemented (``re``, ``pathlib``
      only) -> collection cannot ImportError -> RED, not BROKEN.
  P2  the ``Given`` reads a REAL shipped file at runtime; the file exists
      today (nothing absent at the file level -- only specific TOKENS within
      the dispatch-procedure section are absent).
  P3  the to-be-added tokens are checked at RUNTIME inside each ``Then``,
      never at collection.
  P4  each RED failure is a semantic ``AssertionError`` ("guide does not cite
      X", with DELIVER guidance naming the exact rewrite target) -- never an
      import/collection/file-not-found error.

RED strategy (explicit, per scenario):
  #1 RED because the section's numbered dispatch procedure names each active
     step dispatched exactly once (slice-07 wiring); neither
     ``requires_agreement`` nor a "twice"/"two dispatches" instruction appears
     anywhere in the section today.
  #2 RED because neither "pass-class"/"pass class" nor "fail-class"/
     "fail class" (the DD-3 vocabulary) appears anywhere in the section --
     only the bare ``approval_status`` enum (Step 2's table row) exists today,
     with no classification into pass/fail buckets.
  #3 RED because no "disagree"/"side by side"/human-resolution escalation
     language exists anywhere in the section today.
  #4 RED because no "UNRESOLVED"/timeout/dispatch-failure escalation language
     exists anywhere in the section today.
  #5 GREEN TODAY (regression-lock) because the existing background prose
     already states "Sentinel (`@nw-acceptance-designer-reviewer`) ALWAYS
     dispatches regardless of rigor cascade or scenario count fast-path"
     (slice-04-era language, carried through slice-07's rewrite) ->
     ``assert "ALWAYS dispatches" in section`` PASSES today; authored NOW so
     the slice-02 double-dispatch rewrite cannot silently regress the
     hard-pin guarantee (DD-5 orthogonality: `always_on` and
     `require_agreement` are independent axes -- Sentinel keeps its hard pin
     even when opted into agreement).

Resolution/observation is a pure read (shipped-file in -> token-presence out,
nothing mutated): @contract-shape:pure-function. No observable state mutates
-> Mandate-8 state-delta does not apply; example-based assertions per
Mandate-9 (layer-3+ example-only) -- scenario #2 is the example-only analogue
of a property test, proving the DD-3 predicate's FULL 4-value vocabulary
(not just the 2 example rows already covered by Domain Examples 1/2) is
encoded, per the Contract-shape induction row of the 3-source induction map.

The ``ctx`` fixture is the shared fixture in ``steps/conftest.py`` (reused
verbatim across slice-01 and slice-02, per that module's docstring).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when


scenarios("../slice-02-wire-double-dispatch.feature")


def _nw_distill_skill_path() -> Path:
    # tests/des/acceptance/opt_in_per_step_double_review/steps/this_file.py
    #   parents[0]=steps  [1]=opt_in_per_step_double_review  [2]=acceptance
    #   [3]=des  [4]=tests  [5]=repo root
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "nWave" / "skills" / "nw-distill" / "SKILL.md"


_SECTION_HEADING = "## Final Wave Review Gate"
_NEXT_HEADING_RE = re.compile(r"\n## (?!Final Wave Review Gate)")


def _extract_final_wave_review_gate_section(full_text: str) -> str:
    """Return the "## Final Wave Review Gate" section, up to the next "## " heading.

    Mirrors ``rigor_review_step_toggles/steps/test_slice_07_wire_review_dispatch
    .py``'s identically-named helper BY SHAPE (per-feature self-containment
    convention, not cross-imported).
    """
    start = full_text.index(_SECTION_HEADING)
    rest = full_text[start:]
    match = _NEXT_HEADING_RE.search(rest, len(_SECTION_HEADING))
    end = match.start() if match else len(rest)
    return rest[:end]


@given("the shipped nw-distill review-dispatch guide")
def given_review_dispatch_guide(ctx: dict[str, Any]) -> None:
    guide_path = _nw_distill_skill_path()
    assert guide_path.is_file(), f"shipped guide not found at {guide_path}"
    full_text = guide_path.read_text(encoding="utf-8")
    ctx["guide_path"] = guide_path
    ctx["gate_section"] = _extract_final_wave_review_gate_section(full_text)


# ---------------------------------------------------------------------------
# Scenario #1: double-dispatch conditioned on requires_agreement(step_id)
# ---------------------------------------------------------------------------

_RA_NEAR_TWICE_RE = re.compile(
    r"(?:requires_agreement.{0,250}(?:twice|two dispatches|two separate dispatches)"
    r"|(?:twice|two dispatches|two separate dispatches).{0,250}requires_agreement)",
    re.IGNORECASE | re.DOTALL,
)
_IDENTICAL_SCOPE_RE = re.compile(r"(?:identical|same).{0,40}scope", re.IGNORECASE)


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for double-dispatch conditioning"
)
def when_inspect_double_dispatch_conditioning(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure dispatches an opted-in step's reviewer twice on the identical scope, conditioned on requires_agreement"
)
def then_double_dispatch_conditioned(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert "requires_agreement" in section, (
        f"{ctx['guide_path']} Final Wave Review Gate section does not cite "
        "`requires_agreement` -- the dispatch procedure must consult "
        "`resolve_review_steps().requires_agreement(step_id)` (shipped by "
        "opt-in-per-step-double-review slice-01, ADR-RST-002) to decide "
        "whether a step is dispatched once or twice"
    )
    assert _RA_NEAR_TWICE_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section mentions "
        "`requires_agreement` but not CONNECTED to a 'twice'/'two dispatches' "
        "instruction within ~250 chars -- the procedure must wire "
        "`requires_agreement(step_id)` into the dispatch count itself (e.g. "
        "'for each active step where requires_agreement(step_id) is True: "
        "dispatch that step's agent TWICE'), not a disconnected aside"
    )
    assert _IDENTICAL_SCOPE_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not state "
        "the two dispatches run on the IDENTICAL/SAME review scope -- "
        "ADR-RST-002 decision 4(a) requires both dispatches to review the "
        "identical scope, not two different slices of the review"
    )


# ---------------------------------------------------------------------------
# Scenario #2: full pass-class/fail-class vocabulary (contract-shape induction)
# ---------------------------------------------------------------------------

_PASS_CLASS_RE = re.compile(r"pass[- ]class", re.IGNORECASE)
_FAIL_CLASS_RE = re.compile(r"fail[- ]class", re.IGNORECASE)
_PASS_CLASS_VALUES_RE = re.compile(
    r"pass[- ]class.{0,120}approved.{0,60}conditionally_approved"
    r"|pass[- ]class.{0,120}conditionally_approved.{0,60}approved",
    re.IGNORECASE | re.DOTALL,
)
_FAIL_CLASS_VALUES_RE = re.compile(
    r"fail[- ]class.{0,120}needs_revision.{0,60}rejected"
    r"|fail[- ]class.{0,120}rejected.{0,60}needs_revision",
    re.IGNORECASE | re.DOTALL,
)


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for the agreement predicate"
)
def when_inspect_agreement_predicate(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure classifies every approval_status value into the correct pass-class or fail-class"
)
def then_full_outcome_class_vocabulary(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert _PASS_CLASS_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not name "
        "a 'pass-class' outcome bucket -- DD-3 (ADR-RST-002 decision 4b) "
        "requires the procedure to classify approval_status values into a "
        "named pass-class vs fail-class before comparing two dispatches"
    )
    assert _FAIL_CLASS_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not name "
        "a 'fail-class' outcome bucket -- see DD-3 (ADR-RST-002 decision 4b)"
    )
    assert _PASS_CLASS_VALUES_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section's pass-class "
        "does not enumerate BOTH `approved` and `conditionally_approved` "
        "within ~120 chars of the 'pass-class' marker -- the full DD-3 "
        "vocabulary (not just one example value) must be classified so "
        "any of the 4 approval_status values is unambiguously bucketed"
    )
    assert _FAIL_CLASS_VALUES_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section's fail-class "
        "does not enumerate BOTH `needs_revision` and `rejected` within "
        "~120 chars of the 'fail-class' marker -- see DD-3 (ADR-RST-002 "
        "decision 4b)"
    )


# ---------------------------------------------------------------------------
# Scenario #3: disagreement escalates, blocks pass-and-move-on
# ---------------------------------------------------------------------------

_DISAGREE_BLOCK_RE = re.compile(
    r"(?:disagree.{0,200}(?:block|blocks|blocking)"
    r"|(?:block|blocks|blocking).{0,200}disagree)",
    re.IGNORECASE | re.DOTALL,
)
_SIDE_BY_SIDE_RE = re.compile(r"side[- ]by[- ]side|side by side", re.IGNORECASE)


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for disagreement handling"
)
def when_inspect_disagreement_handling(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure surfaces both verdicts side by side and blocks the gate until a human resolves the disagreement"
)
def then_disagreement_escalates(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert re.search(r"disagree", section, re.IGNORECASE), (
        f"{ctx['guide_path']} Final Wave Review Gate section has no "
        "'disagree'-rooted language -- DD-3 requires an explicit disagreement "
        "escalation when the two dispatches' outcome classes differ "
        "(ADR-RST-002 decision 4b)"
    )
    assert _SIDE_BY_SIDE_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not state "
        "both verdicts are shown 'side by side' -- Domain Example 2 requires "
        "both dispatches' verdicts surfaced together, never silently picking "
        "one"
    )
    assert _DISAGREE_BLOCK_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section mentions "
        "disagreement but not CONNECTED to a 'block'/'blocks'/'blocking' "
        "instruction within ~200 chars -- a disagreement must BLOCK the "
        "gate's existing pass-and-move-on path (Rule/Step 5), not merely be "
        "narrated"
    )
    assert re.search(r"human", section, re.IGNORECASE), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not "
        "mention a human resolving the disagreement -- DD-3 requires the "
        "block to persist 'until a human resolves it', never an automatic "
        "pick"
    )


# ---------------------------------------------------------------------------
# Scenario #4: dispatch failure -- distinct UNRESOLVED escalation class
# ---------------------------------------------------------------------------

_FAILURE_TOKEN_RE = re.compile(
    r"timeout|unavailable|fails? to return|no verdict", re.IGNORECASE
)
_UNRESOLVED_NEAR_FAILURE_RE = re.compile(
    r"(?:UNRESOLVED.{0,250}(?:timeout|unavailable|fails? to return|no verdict)"
    r"|(?:timeout|unavailable|fails? to return|no verdict).{0,250}UNRESOLVED)",
    re.IGNORECASE | re.DOTALL,
)
_BOTH_COMPLETED_RE = re.compile(
    r"both.{0,60}(?:dispatches|verdicts).{0,60}complet", re.IGNORECASE | re.DOTALL
)


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for dispatch-failure handling"
)
def when_inspect_dispatch_failure_handling(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure surfaces a missing or failed dispatch as an unresolved escalation distinct from a disagreement"
)
def then_dispatch_failure_escalates(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert "UNRESOLVED" in section, (
        f"{ctx['guide_path']} Final Wave Review Gate section has no "
        "'UNRESOLVED' marker -- Domain Example 4 / the Non-Functional "
        "Requirements 'both-verdicts-required policy' require a distinct "
        "escalation label for a missing/failed dispatch, separate from the "
        "DD-3 disagreement escalation"
    )
    assert _FAILURE_TOKEN_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not name "
        "a dispatch-failure cause (timeout / reviewer unavailable / fails to "
        "return / no verdict) -- Domain Example 4's failure mode must be "
        "named, not only the generic word 'UNRESOLVED'"
    )
    assert _UNRESOLVED_NEAR_FAILURE_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section mentions "
        "'UNRESOLVED' and a failure cause but they are not CONNECTED within "
        "~250 chars -- the UNRESOLVED label must be wired to the actual "
        "dispatch-failure narration"
    )
    assert _BOTH_COMPLETED_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section does not state "
        "the step resolves PASS/FAIL only when BOTH dispatches return a "
        "COMPLETED verdict -- the Non-Functional Requirements' "
        "'both-verdicts-required policy' must be encoded so a single "
        "completed dispatch is never treated as sufficient, even when the "
        "other times out"
    )


# ---------------------------------------------------------------------------
# Scenario #5: Sentinel always-dispatches guarantee (regression lock, GREEN today)
# ---------------------------------------------------------------------------


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for the Sentinel hard-pin guarantee"
)
def when_inspect_sentinel_hardpin(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure still guarantees Sentinel always dispatches regardless of any per-step agreement opt-in"
)
def then_sentinel_always_survives_rewrite(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert "ALWAYS dispatches" in section, (
        f"{ctx['guide_path']} Final Wave Review Gate section lost the "
        "Sentinel hard-pin guarantee ('Sentinel ... ALWAYS dispatches') -- "
        "the slice-02 requires_agreement/double-dispatch wiring MUST NOT "
        "regress the slice-04/slice-07-era always-on hard-pin language; "
        "Sentinel (`@nw-acceptance-designer-reviewer`) keeps dispatching "
        "regardless of `is_always_on('sentinel')` AND regardless of whether "
        "it is also opted into `require_agreement` (DD-5 orthogonality)"
    )
