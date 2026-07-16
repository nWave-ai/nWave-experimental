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
    return rendered
