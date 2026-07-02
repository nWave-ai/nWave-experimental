"""slice-07 acceptance: the DISTILL Final Wave Review Gate dispatch PROCEDURE
actually consults the review-step registry (JOB-002, wiring-completion slice,
Ale-ratified 2026-06-30 post feature-end deep-review gap).

Slices 01-06 proved ``DESConfig.resolve_review_steps()`` resolves correctly via
DIRECT in-process calls, but none of them wired the resolver into the actual
consumer: ``nw-distill/SKILL.md``'s Final Wave Review Gate dispatch prose,
which at HEAD unconditionally instructs "Dispatch four reviewers in
parallel" naming all four by name, regardless of any config. DESIGN's own
Reuse Analysis (``docs/feature/rigor-review-step-toggles/feature-delta.md``
~L217) already specified this EXTEND row; no prior slice executed it.

This is a methodology-SKILL.md (LLM-consumed prose) change, not testable
Python -- same artifact class as ``nw-rigor/SKILL.md`` (slice-05 precedent,
``test_slice_05_remove_dead_mutation_knob.py``). The pattern mirrors slice-05
exactly: a real file read of the shipped, REPO-TRACKED
``nWave/skills/nw-distill/SKILL.md`` (NOT the installed ``~/.claude/skills/``
copy).

Path-authority decision (repo-tracked vs installed): ``diff`` between
``nWave/skills/nw-distill/SKILL.md`` and ``~/.claude/skills/nw-distill/
SKILL.md`` is byte-empty at HEAD (2026-06-30), so the two are identical
today. ``nWave/skills/`` is nonetheless the CANONICAL SOURCE: confirmed via
``scripts/install/plugins/skills_plugin.py`` ``_resolve_source`` --
the OLD_HIERARCHICAL fallback resolves to ``project_root / "nWave" /
"skills"`` (the dev-mode install source), and the installed
``~/.claude/skills/`` copy is install-time-generated output, not tracked
in CI, not portable across machines/dev-containers. Testing the
installed copy would make this AT non-hermetic (depends on a personal
install state) and would not even collect on a clean CI checkout -- the
``tests/meta/test_acceptance_hermeticity.py`` guard's spirit (no
``~/.claude`` paths in step composition) extends to this choice even
though it targets a SKILL.md, not a hook path literal.

Driving surface (real, in-process, hermetic -- no interpreter fork, no
``~/.claude`` path): a REAL file read of the shipped
``nWave/skills/nw-distill/SKILL.md``, scoped to the "## Final Wave Review
Gate" section (bounded by the next "## " heading) -- the section the prompt
identifies (~L268-296 at HEAD).

Active-RED topology (nw-distill-red-scaffolding P1-P4):
  P1  module-top imports nothing not-yet-implemented (``re``, ``pathlib`` only)
      -> collection cannot ImportError -> RED, not BROKEN.
  P2  the ``Given`` reads a REAL shipped file at runtime; the file exists
      today (nothing absent at the file level -- only specific TOKENS within
      the dispatch-procedure section are absent).
  P3  the to-be-added tokens are checked at RUNTIME inside each ``Then``,
      never at collection.
  P4  each RED failure is a semantic ``AssertionError`` ("guide does not cite
      X", with DELIVER guidance naming the exact rewrite target) -- never an
      import/collection/file-not-found error.

RED strategy (explicit, per the slice-07 task; HARDENED post Sentinel NEEDS_REVISION
-- 3 BLOCKER findings, all "substring-presence-anywhere-in-section" is satisfiable by
a throwaway mention instead of a real procedural rewrite; see per-scenario notes):
  #1 RED because the numbered STEP-1 procedure (not the whole section --
     ``_extract_step1_procedure`` anchors on the ``"1. "`` list marker, bounded by
     the next ``"2. "`` item / the ``"| Step | Rule | Gate |"`` table header / the
     next ``"## "`` heading) says "Dispatch four reviewers in parallel" and lists
     all four by literal ``@nw-*-reviewer`` name -- the substring
     ``resolve_review_steps`` does not appear WITHIN that bounded step-1 text ->
     ``assert "resolve_review_steps" in step1`` fails. Anchoring to step 1
     specifically (not the section) closes the loophole where a crafter satisfies
     the AT by mentioning ``resolve_review_steps`` anywhere else in the section
     (e.g. a footnote) without touching the actual dispatch procedure.
  #2 RED because step-1 text never references ``.active()`` membership NOR
     contains dispatch-language within 120 chars of it -- the dispatch is narrated
     as unconditional ("Dispatch four reviewers") -> ``assert ".active()" in
     step1`` fails (and the proximity check ``_ACTIVE_NEAR_DISPATCH_RE`` would also
     fail independently once ``.active()`` exists, guarding against ``.active()``
     appearing only as disconnected background trivia rather than wired into the
     dispatch logic).
  #3 GREEN TODAY (regression-lock) because the existing background prose
     already states "Sentinel (`@nw-acceptance-designer-reviewer`) ALWAYS
     dispatches regardless of rigor cascade or scenario count fast-path"
     (slice-04-era language) -> ``assert "ALWAYS dispatches" in section``
     PASSES today; this is authored NOW so the slice-07 rewrite cannot
     silently regress the hard-pin guarantee. Unchanged by hardening (the
     finding targeted #1/#2/#4 only).
  #4 RED because the section's only cost/model line is the stale flat
     "**Cost**: 4 Haiku reviewers in parallel ~= $0.05-0.20 per feature" --
     neither ``model_for`` nor the phrase "per-step model" appears anywhere
     in the section -> the positive ``assert "model_for" in section or
     "per-step model" in section`` fails FIRST (pytest stops here today).
     Two additional assertions guard the post-GREEN state so a crafter cannot
     satisfy the AT by ADDING per-step-model language while leaving the old
     contradictory cost line untouched: a NEGATIVE
     ``assert not _STALE_COST_RE.search(section)`` (the literal "4 Haiku
     reviewers in parallel" phrase must be GONE) and a proximity check
     ``_COST_MODEL_RE`` requiring model-related text within 200 chars of the
     literal ``**Cost**:`` marker (the Cost line itself, not an unrelated
     paragraph, must describe per-step model resolution).

Resolution/observation is a pure read (shipped-file in -> token-presence
out, nothing mutated): @contract-shape:pure-function. No observable state
mutates -> Mandate-8 state-delta does not apply; example-based assertions
per Mandate-9 (layer-3 example-only).

The ``ctx`` fixture is the shared fixture in ``steps/conftest.py`` (reused
verbatim across all slices 01-07, per the feature-end consolidation note in
that module).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when


scenarios("../slice-07-wire-review-dispatch.feature")


def _nw_distill_skill_path() -> Path:
    # tests/des/acceptance/rigor_review_step_toggles/steps/this_file.py
    #   parents[0]=steps  [1]=rigor_review_step_toggles  [2]=acceptance
    #   [3]=des  [4]=tests  [5]=repo root
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "nWave" / "skills" / "nw-distill" / "SKILL.md"


_SECTION_HEADING = "## Final Wave Review Gate"
_NEXT_HEADING_RE = re.compile(r"\n## (?!Final Wave Review Gate)")


def _extract_final_wave_review_gate_section(full_text: str) -> str:
    """Return the "## Final Wave Review Gate" section, up to the next "## " heading."""
    start = full_text.index(_SECTION_HEADING)
    rest = full_text[start:]
    match = _NEXT_HEADING_RE.search(rest, len(_SECTION_HEADING))
    end = match.start() if match else len(rest)
    return rest[:end]


# ---------------------------------------------------------------------------
# Hardening helpers (post Sentinel NEEDS_REVISION, 3 BLOCKER findings): the
# whole-SECTION substring checks below are satisfiable by a throwaway mention
# anywhere in the section, not necessarily inside the numbered dispatch
# PROCEDURE. ``_extract_step1_procedure`` anchors scenarios #1/#2 to the
# bounded step-1 text only; ``_ACTIVE_NEAR_DISPATCH_RE`` proximity-guards
# scenario #2; ``_STALE_COST_RE``/``_COST_MODEL_RE`` add the negative +
# Cost-line-anchored checks scenario #4 was missing.
# ---------------------------------------------------------------------------

_STEP1_MARKER_RE = re.compile(r"^1\.\s", re.MULTILINE)
_STEP1_BOUNDARY_RE = re.compile(
    r"\n(?:2\.\s|\|\s*Step\s*\|\s*Rule\s*\|\s*Gate\s*\||## )"
)


def _extract_step1_procedure(section: str) -> str:
    """Return ONLY the numbered step-1 dispatch-decision text, not the whole section.

    Bounded between the "1. " list marker and whichever comes FIRST of: a
    "2. " next numbered item, the "| Step | Rule | Gate |" table header (the
    shipped table immediately follows step 1 today), or the next "## "
    heading. Markers are generic (not pinned to today's literal "Dispatch
    four reviewers" wording) so the boundary still resolves after DELIVER
    rewrites the step-1 prose.
    """
    marker = _STEP1_MARKER_RE.search(section)
    assert marker is not None, (
        "Final Wave Review Gate section has no numbered step-1 list item "
        "('1. ...') -- cannot anchor the dispatch-procedure assertions to a "
        "specific step"
    )
    start = marker.start()
    boundary = _STEP1_BOUNDARY_RE.search(section, start + 2)
    end = boundary.start() if boundary else len(section)
    return section[start:end]


_ACTIVE_NEAR_DISPATCH_RE = re.compile(
    r"(?:\.active\(\).{0,120}dispatch|dispatch.{0,120}\.active\(\))",
    re.IGNORECASE | re.DOTALL,
)
_STALE_COST_RE = re.compile(r"4 Haiku reviewers? in parallel", re.IGNORECASE)
_COST_MODEL_RE = re.compile(
    r"\*\*Cost\*\*:.{0,200}(?:model_for|per-step model)",
    re.IGNORECASE | re.DOTALL,
)


@given("the shipped nw-distill review-dispatch guide")
def given_review_dispatch_guide(ctx: dict[str, Any]) -> None:
    guide_path = _nw_distill_skill_path()
    assert guide_path.is_file(), f"shipped guide not found at {guide_path}"
    full_text = guide_path.read_text(encoding="utf-8")
    ctx["guide_path"] = guide_path
    ctx["gate_section"] = _extract_final_wave_review_gate_section(full_text)


# ---------------------------------------------------------------------------
# Scenario #1: resolver citation in the dispatch mechanism
# ---------------------------------------------------------------------------


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for its dispatch mechanism"
)
def when_inspect_dispatch_mechanism(ctx: dict[str, Any]) -> None:
    # Pure inspection -- no mutation of the shipped guide under test.
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure cites the review-step resolver as the mechanism deciding which reviewers run"
)
def then_cites_resolver(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    step1 = _extract_step1_procedure(section)
    assert "resolve_review_steps" in step1, (
        f"{ctx['guide_path']} Final Wave Review Gate numbered STEP 1 "
        f"('1. ...', extracted text: {step1!r}) does not cite "
        "`resolve_review_steps()` as the dispatch-decision mechanism -- the "
        "numbered step-1 procedure ('Dispatch four reviewers in parallel') "
        "must reference `DESConfig.resolve_review_steps()` (registry shipped "
        "by rigor-review-step-toggles slices 01-06, ADR-RST-001) WITHIN STEP "
        "1 ITSELF (not merely somewhere in the section) so the procedure "
        "ACTUALLY consults the resolved active-step set instead of "
        "unconditionally naming all four reviewers"
    )


# ---------------------------------------------------------------------------
# Scenario #2: conditional (not unconditional) dispatch language
# ---------------------------------------------------------------------------


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for conditional dispatch language"
)
def when_inspect_conditional_language(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure states reviewers are dispatched only when active, not unconditionally"
)
def then_conditional_dispatch(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    step1 = _extract_step1_procedure(section)
    assert ".active()" in step1, (
        f"{ctx['guide_path']} Final Wave Review Gate numbered STEP 1 "
        f"('1. ...', extracted text: {step1!r}) does not reference "
        "`.active()` membership -- the numbered dispatch procedure must "
        "make explicit, WITHIN STEP 1 ITSELF, that an inactive/disabled "
        "review step (per `ResolvedReviewStepSet.active()`) is NOT "
        "dispatched, not only as background narrative elsewhere in the "
        "section"
    )
    assert _ACTIVE_NEAR_DISPATCH_RE.search(step1), (
        f"{ctx['guide_path']} Final Wave Review Gate STEP 1 mentions "
        "`.active()` but not CONNECTED to the dispatch verb within ~120 "
        f"chars (extracted text: {step1!r}) -- `.active()` must be wired "
        "into the dispatch logic itself (e.g. 'dispatch each review step "
        "in `resolve_review_steps().active()`'), not a disconnected aside "
        "that happens to sit in step 1 without driving the dispatch "
        "decision"
    )


# ---------------------------------------------------------------------------
# Scenario #3: Sentinel hard-pin regression lock (GREEN today)
# ---------------------------------------------------------------------------


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for the Sentinel hard-pin guarantee"
)
def when_inspect_sentinel_hardpin(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then("the dispatch procedure still guarantees Sentinel always dispatches")
def then_sentinel_always(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert "ALWAYS dispatches" in section, (
        f"{ctx['guide_path']} Final Wave Review Gate section lost the "
        "Sentinel hard-pin guarantee ('Sentinel ... ALWAYS dispatches') -- "
        "the slice-07 resolve_review_steps() wiring MUST NOT regress the "
        "slice-04-era always-on hard-pin language; Sentinel "
        "(`@nw-acceptance-designer-reviewer`) must keep dispatching "
        "regardless of `is_always_on('sentinel')` / rigor cascade"
    )


# ---------------------------------------------------------------------------
# Scenario #4: per-step model resolution replaces the stale flat-cost line
# ---------------------------------------------------------------------------


@when(
    "the Final Wave Review Gate dispatch procedure is inspected for its cost-and-model description"
)
def when_inspect_cost_model(ctx: dict[str, Any]) -> None:
    ctx["gate_section"] = ctx["gate_section"]


@then(
    "the dispatch procedure describes per-step model resolution instead of a flat four-Haiku assumption"
)
def then_per_step_model(ctx: dict[str, Any]) -> None:
    section = ctx["gate_section"]
    assert "model_for" in section or "per-step model" in section, (
        f"{ctx['guide_path']} Final Wave Review Gate section still assumes "
        "'4 Haiku reviewers' uniformly (the stale **Cost** line) -- since "
        "slice-02 added per-step `model` resolution to the registry, the "
        "section must describe each active reviewer running on its "
        "resolved model (`model_for(step_id)`), not a flat all-Haiku "
        "cost line"
    )
    assert not _STALE_COST_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate section still contains "
        "the stale flat-cost phrase '4 Haiku reviewers in parallel' -- a "
        "crafter cannot pass this AT by ADDING per-step-model language "
        "while leaving the old, now-contradictory cost line untouched; the "
        "**Cost** line itself must be rewritten, not merely supplemented"
    )
    assert _COST_MODEL_RE.search(section), (
        f"{ctx['guide_path']} Final Wave Review Gate's `**Cost**:` line "
        "does not describe per-step model resolution within ~200 chars of "
        "the marker -- `model_for`/`per-step model` must appear in the "
        "Cost line ITSELF (the line a reader actually consults for cost), "
        "not in an unrelated paragraph elsewhere in the section"
    )
