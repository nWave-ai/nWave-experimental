"""Public oracle: no shipped asset instructs the LLM to write durable authority.

The binding constraint (`CLAUDE.md`, "Delegate the domain") is that a durable
document -- a brief or an ADR -- is constructed ONLY by the public producer
`des design --input -`; the LLM never authors that Markdown itself, in ANY
route, including the human-driven consultation branch. `nWave/tasks/nw/design.md`
line 42 named the last residual instance telling the LLM to "write the smallest
durable decision into that brief or the affected ADR" for that branch, which
contradicts `nWave/skills/nw-design/SKILL.md` ("DESIGN supplies semantic
decisions; it does not edit a durable brief or ADR and never authors Markdown
for a DESIGN document. ... DES is the sole writer").

This test scans every shipped task and skill file for the PROPERTY, not one
designation: any write-family verb (write/edit/author/draft/compose/update/
revise) taking a durable-authority document (a *named* brief or ADR -- "the
brief", "that ADR", never a bare English noun like a negotiation brief) as its
direct object, within one sentence. Three formulations that were never fed to
this regex while it was written are exercised below (see
`test_the_regex_discriminates_three_unseen_phrasings`) and each turns the scan
red, so the coverage claim is demonstrated, not asserted. Unrelated prose
("Pre-write labels ... negotiation brief" in nw-voss-negotiation) stays green
because its object is not "the/that/this brief" or an ADR. A prohibition
("does not edit a durable brief or ADR" in nw-design) stays green via a
negation lookbehind, and a fixture CSV row in nw-agent-evals stays green
because fenced code/data blocks are masked before the scan.

Scope, stated honestly: this catches an instruction to write/edit the document
ITSELF. It does not catch every possible circumlocution (e.g. "make the brief
say X") -- GDP-10 keeps the pattern to the verb family actually observed in
this codebase's vocabulary rather than chasing unbounded paraphrase.

nwave#36 dynamic-scan precedent: `tests/meta/test_source_banned_patterns.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).parents[4]

# The consultation route may name the destination (a brief or ADR) but must
# never tell the LLM to write/edit/author/draft/compose/revise/update it
# directly -- that authority is constructed only by the public producer
# (`des design --input -`). The object must be a NAMED durable document
# ("the"/"that"/"this" brief, or ADR/architecture decision record) so that an
# unrelated noun phrase like "negotiation brief" does not false-positive.
_DIRECT_AUTHORITY_WRITE = re.compile(
    r"\b(write|edit|author|draft|compose|update|revise)\b[^.\n]{0,60}"
    r"\b((the|that|this)\s+brief|ADR|architecture decision record)\b",
    re.IGNORECASE,
)

# A prohibition ("does not edit the ADR", "never author a brief") states the
# SAME constraint this gate enforces -- it is not an instruction to write.
# Exclude a match whose sentence opens with a negation before the verb.
_NEGATED = re.compile(
    r"\b(not|never|n't|cannot|can't)\s+\w*\s*$",
    re.IGNORECASE,
)


_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


def _mask_fenced_code_blocks(content: str) -> str:
    """Blank out fenced code/data blocks, keeping offsets stable.

    `nw-agent-evals/SKILL.md` ships a fixture CSV row ("write the ADR") as
    illustrative eval-dataset content, not resident prose the LLM follows as
    an operating instruction -- the same reason `_NEGATED` excludes a
    prohibition instead of the prose that states it. Masking (not stripping)
    preserves match.start() offsets for the negation lookbehind.
    """
    return _FENCED_CODE_BLOCK.sub(lambda m: " " * len(m.group(0)), content)


def _scan(files: list[Path]) -> list[tuple[str, str]]:
    """Return (relative_path, matched_snippet) for every non-negated hit
    found outside a fenced code/data block."""
    violations: list[tuple[str, str]] = []
    for path in files:
        content = _mask_fenced_code_blocks(path.read_text(encoding="utf-8"))
        for match in _DIRECT_AUTHORITY_WRITE.finditer(content):
            preceding = content[max(0, match.start() - 30) : match.start()]
            if _NEGATED.search(preceding):
                continue
            violations.append((str(path.relative_to(_REPO_ROOT)), match.group(0)))
    return violations


@pytest.mark.fast_gate
def test_no_task_instructs_writing_durable_authority_directly() -> None:
    """No `nWave/tasks/nw/*.md` file tells the LLM to write a brief/ADR itself.

    Uses Path.glob for dynamic discovery, so a future task file carrying the
    same legacy-route phrasing fails this gate without a test edit.
    """
    task_files = list((_REPO_ROOT / "nWave" / "tasks" / "nw").glob("*.md"))
    assert task_files, "No task files found -- check repo layout"

    violations = _scan(task_files)

    assert violations == [], (
        "Legacy direct-authority-write instruction found in task files:\n"
        + "\n".join(f"  - {p}: {s!r}" for p, s in violations)
        + "\n\nFix: route the human-driven consultation through the public "
        "producer (`des design --input -`), the same as the managed route."
    )


@pytest.mark.parametrize(
    "phrasing",
    [
        "please compose the brief yourself before moving on",
        "edit the ADR to record this decision",
        "update that brief with the new constraint",
    ],
    ids=["compose", "edit-adr", "update-that-brief"],
)
def test_the_regex_discriminates_three_unseen_phrasings(phrasing: str) -> None:
    """The property, not the designation: three phrasings distinct from the
    repaired line (`nWave/tasks/nw/design.md`, which said "write ... durable
    decision into that brief or the affected ADR") each still match, proving
    the gate generalises past the one sentence it was built to catch."""
    assert _DIRECT_AUTHORITY_WRITE.search(phrasing), phrasing


def test_the_regex_stays_green_on_unrelated_brief_prose() -> None:
    """`nw-voss-negotiation` says "Pre-write labels ... negotiation brief" --
    a bare noun phrase, not a named durable document -- and must not match."""
    assert not _DIRECT_AUTHORITY_WRITE.search(
        "Pre-write labels for likely tension moments in every negotiation brief"
    )


@pytest.mark.fast_gate
def test_no_skill_instructs_writing_durable_authority_directly() -> None:
    """No `nWave/skills/*/SKILL.md` file tells the LLM to write a brief/ADR itself."""
    skill_files = list((_REPO_ROOT / "nWave" / "skills").glob("*/SKILL.md"))
    assert skill_files, "No SKILL.md files found -- check repo layout"

    violations = _scan(skill_files)

    assert violations == [], (
        "Legacy direct-authority-write instruction found in skill files:\n"
        + "\n".join(f"  - {p}: {s!r}" for p, s in violations)
        + "\n\nFix: route the human-driven consultation through the public "
        "producer (`des design --input -`), the same as the managed route."
    )
