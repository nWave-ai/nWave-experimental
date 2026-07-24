"""Fixer-agent prompt-template rendering -- the USER-EDITABLE task-text seam.

CREATE_NEW (des-refactor-fixer-swarm slice-01, Ale 2026-07-14 requirement): the
agent's task text is NEVER hardcoded in the harness. ``des refactor`` reads a
user-editable template file (default ``DEFAULT_TEMPLATE_PATH`` below, repo-root
relative), renders its per-item placeholders (``{item_id}``, ``{defect}``,
``{proposed_solution}``, ``{paradigm}``, ``{worktree}``), writes the rendered
text to a prompt FILE, and passes THAT file to ``agent_cmd`` -- so a
maintainer's own edit to the template file is what the agent actually receives,
never a string baked into this module.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.refactor.entry_gate import EntryGateVerdict


#: Default path (repo-root-relative) to the user-editable prompt template. The
#: harness bootstraps a default template here on first run (never overwriting
#: an existing, possibly user-edited, file).
DEFAULT_TEMPLATE_PATH = Path(".nwave/refactor-agent-prompt.md")

#: Fallback prompt text used when no template file exists yet at
#: ``DEFAULT_TEMPLATE_PATH`` (or the caller's override path) -- the harness
#: works out of the box with zero operator setup, while a maintainer's own
#: edit to the template file always wins once it exists.
DEFAULT_TEMPLATE_TEXT = (
    "Fix the following tech-debt item.\n\n"
    "Item: {item_id}\n"
    "Defect: {defect}\n"
    "Proposed solution: {proposed_solution}\n"
    "Paradigm: {paradigm}\n"
    "Worktree: {worktree}\n"
)

#: What each entry-gate verdict token MEANS -- offered to the fixer alongside
#: the token itself, so choosing one is a judgement about the item, not a
#: ritual incantation copied off a list. Read the token spellings from the
#: PRODUCTION enum (never re-typed here) so a token added to the closed set
#: is automatically in scope for this explanation, never silently exempt.
_VERDICT_EXPLANATIONS: dict[EntryGateVerdict, str] = {
    EntryGateVerdict.REFACTOR_SAFE: (
        "the change is behaviour-preserving and every test that covers it "
        "stayed green before and after"
    ),
    EntryGateVerdict.MECHANICAL_RENAME_EXEMPT: (
        "the change is a purely mechanical rename or move with no behaviour "
        "change to verify"
    ),
    EntryGateVerdict.CHARACTERIZE_FIRST: (
        "the code has no real test net yet and needs characterization tests "
        "written before it can be refactored safely"
    ),
    EntryGateVerdict.ABSTAINED: (
        "you could not reach a confident verdict on this item and are "
        "declining to certify it either way"
    ),
    EntryGateVerdict.MIKADO_ESCALATION: (
        "the change uncovers a larger dependency graph that needs Mikado "
        "Method planning before it can be attempted"
    ),
}

#: The harness-owned entry-gate verdict ask (fix-fixer-emits-entry-gate-
#: verdict). ``RefactorDrainService`` refuses to merge any item unless the
#: fixer's own stdout carries one of the five :class:`EntryGateVerdict`
#: tokens (``_entry_gate_refusal``) -- so this ask MUST reach the fixer on
#: every drain, regardless of whether the rendered text came from a
#: maintainer's own edited template or from ``DEFAULT_TEMPLATE_TEXT`` above.
#: Appended by :func:`render_prompt`, never baked into either template
#: source, so a maintainer's own template edit can never silently disarm it
#: (a user template that never mentions verdicts must still deliver this ask).
ENTRY_GATE_VERDICT_BLOCK = (
    "\n---\n"
    "ENTRY GATE VERDICT (required)\n"
    "When you are finished, self-report a verdict on your own change as the "
    "LAST line of your stdout output, printed bare with nothing else on that "
    "line. Choose exactly one of the following five tokens:\n"
    + "".join(
        f"- {verdict.value}: {explanation}\n"
        for verdict, explanation in _VERDICT_EXPLANATIONS.items()
    )
    + "Print only the bare token on its own final line -- this stdout output "
    "is the ONLY channel your verdict can reach the harness through.\n"
)


def load_prompt_template(template_path: Path) -> str:
    """Read the user-editable prompt-template file verbatim."""
    return template_path.read_text(encoding="utf-8")


def render_prompt(
    template_text: str,
    *,
    item_id: str,
    defect: str,
    proposed_solution: str,
    paradigm: str,
    worktree: Path,
) -> str:
    """Render ``template_text``'s placeholders for one pile item being drained.

    Substitutes ``{item_id}``/``{defect}``/``{proposed_solution}``/
    ``{paradigm}``/``{worktree}`` via literal replacement (never ``str.format``,
    which would raise on an unrelated brace a maintainer's own template text
    might contain) -- the rest of the text passes through unchanged.

    Appends :data:`ENTRY_GATE_VERDICT_BLOCK` after substitution, regardless of
    ``template_text``'s source (the default fallback or a maintainer's own
    edited file) -- the entry-gate ask is harness-owned, never a default a
    template edit can silently delete and thereby block every future drain.
    """
    rendered = template_text
    for placeholder, value in (
        ("{item_id}", item_id),
        ("{defect}", defect),
        ("{proposed_solution}", proposed_solution),
        ("{paradigm}", paradigm),
        ("{worktree}", str(worktree)),
    ):
        rendered = rendered.replace(placeholder, value)
    rendered += ENTRY_GATE_VERDICT_BLOCK
    return rendered
