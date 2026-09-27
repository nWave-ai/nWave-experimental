"""The published nw-auto skill, as an agent reads it after a real install.

This module holds NO observation and NO expected result. It models the
PUBLISHED artefact as an object and offers pure predicates over text, so the
oracle can ask its questions both of real published bytes and of synthetic
phrasings that were never written against those predicates.

Two boundary facts are load-bearing and are not re-implemented here:

* the installer refuses under a non-virtualenv interpreter, and every ambient
  location it may touch (``HOME``, ``CLAUDE_CONFIG_DIR``, ``CODEX_HOME``,
  ``NWAVE_AGENTS_HOME``) must be pinned inside a throwaway sandbox -- both are
  already encoded once, in
  ``tests/installer/acceptance/session_start_notice/session_journey.py``, and
  are reused rather than forked;
* the child also needs a throwaway CWD: running the installer with the
  repository root as cwd rewrites the repository's own CLAUDE.md and AGENTS.md.

Nothing here imports a production symbol, reads a template, or touches the
source skill. Skills are data the installer publishes.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tests.installer.acceptance.session_start_notice.session_journey import (
    environment_for,
    run_cli,
)


# The exact published path nWave/agents/nw-nwave-buddy.md:50 tells an agent to
# read. Anything else would observe a different artefact.
PUBLISHED_SKILL_RELATIVE = Path(".claude/skills/nw-auto/SKILL.md")
PUBLISHED_SKILLS_DIR_RELATIVE = Path(".claude/skills")

INSTALL_ARGUMENTS = ("install", "--yes", "--platform", "claude-code")

SECTION_THREE_HEADING = "## 3."
NEXT_SECTION = re.compile(r"^## ", re.MULTILINE)
PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

# Anchors that identify section 3 as the place where the orchestrator is
# already holding a refusal. Measured present today.
REFUSAL_OUTCOME_ROW = "| `Refusal` |"
FINDING_INVOCATION = "--finding -"
EXPECTED_FINDING_INVOCATIONS = 3

# Guidance, never a promised runner behaviour: a closed forbidden set, measured
# absent today, so the correction cannot silently become a gate the installed
# DES does not provide.
FORBIDDEN_PROMISES = (
    "des forwards",
    "automatically forwards",
    "the runner forwards",
)


class PublishedSkillMissing(Exception):
    """The install published no nw-auto SKILL.md at all."""


class SectionThreeMissing(Exception):
    """Section 3 is absent, or no longer the place that holds a refusal."""


class InstallerDidNotComplete(Exception):
    """The public installer port did not establish anything to observe."""


@dataclass(frozen=True)
class InstalledSkill:
    """The bytes of the published nw-auto skill.

    Constructed only by running the real public installer process, so every
    question asked of it is answered about published bytes.
    """

    published_text: str

    @classmethod
    def published_by_real_install(cls, sandbox: Path) -> InstalledSkill:
        system_home = sandbox / "home"
        agents_home = sandbox / "agents"
        workdir = sandbox / "cwd"
        for directory in (system_home, agents_home, workdir):
            directory.mkdir(parents=True, exist_ok=True)

        environment = environment_for(system_home=system_home, agents_home=agents_home)
        process = run_cli(environment, workdir, *INSTALL_ARGUMENTS)
        if process.returncode != 0:
            raise InstallerDidNotComplete(
                "the public installer port established nothing to observe: "
                f"`nwave-ai {' '.join(INSTALL_ARGUMENTS)}` exited "
                f"{process.returncode}\nstderr:\n{process.stderr}"
            )

        skill_path = system_home / PUBLISHED_SKILL_RELATIVE
        if not skill_path.is_file():
            raise PublishedSkillMissing(
                f"the install exited 0 but published no {PUBLISHED_SKILL_RELATIVE}; "
                f"published skills: {cls._published_skills(system_home)}"
            )
        return cls(skill_path.read_text(encoding="utf-8"))

    @staticmethod
    def _published_skills(system_home: Path) -> list[str]:
        skills_dir = system_home / PUBLISHED_SKILLS_DIR_RELATIVE
        if not skills_dir.is_dir():
            return []
        return sorted(entry.name for entry in skills_dir.iterdir())

    def section_three(self) -> str:
        """Section 3 extracted structurally: its heading up to the next ``## ``.

        Structural, never by designation, so an assertion can never read green
        on prose that lives in another section.
        """
        start = self.published_text.find(SECTION_THREE_HEADING)
        if start == -1:
            raise SectionThreeMissing(
                f"the published skill carries no '{SECTION_THREE_HEADING}' heading"
            )
        rest = self.published_text[start + len(SECTION_THREE_HEADING) :]
        following = NEXT_SECTION.search(rest)
        end = len(rest) if following is None else following.start()
        return SECTION_THREE_HEADING + rest[:end]

    def section_three_holds_a_refusal(self) -> None:
        """Section 3 is still the place the orchestrator holds a refusal.

        A section 3 that has lost the ``Refusal`` outcome row or either
        ``--finding -`` invocation is a Refusal naming what it actually
        carried; it never reads as the observation met.
        """
        section = self.section_three()
        findings = section.count(FINDING_INVOCATION)
        if REFUSAL_OUTCOME_ROW not in section or findings != (
            EXPECTED_FINDING_INVOCATIONS
        ):
            raise SectionThreeMissing(
                "section 3 is no longer the place that holds a refusal: it "
                f"carries the Refusal outcome row = "
                f"{REFUSAL_OUTCOME_ROW in section}, and "
                f"{findings} `{FINDING_INVOCATION}` invocations (expected "
                f"{EXPECTED_FINDING_INVOCATIONS}).\nsection 3 as published:\n"
                f"{section}"
            )

    def sections_other_than_three(self) -> str:
        section = self.section_three()
        return self.published_text.replace(section, "\n")

    def forbidden_promises_present(self) -> tuple[str, ...]:
        body = self.published_text.lower()
        return tuple(phrase for phrase in FORBIDDEN_PROMISES if phrase in body)


def paragraphs_of(text: str) -> tuple[str, ...]:
    """Text cut into paragraphs, as a reader meets them.

    Paragraph-level co-occurrence is what makes the claims readable rather than
    satisfiable by words scattered across a section.
    """
    return tuple(
        block.strip() for block in PARAGRAPH_SPLIT.split(text) if block.strip()
    )


# ---------------------------------------------------------------------------
# Pure predicates over one paragraph. Each names ONE claim.
# ---------------------------------------------------------------------------

_TRAVELS_UNCHANGED = re.compile(
    r"travels?\s+(?:\w+\s+){0,3}?(?:unchanged|whole|verbatim|intact)",
    re.IGNORECASE,
)
_IS_DATA = re.compile(r"\bis\s+(?:the\s+)?DATA\b|\bis\s+data\b")
_DESTINATION = re.compile(r"the step that answers", re.IGNORECASE)
_CARRIERS = ("WHAT", "WHY", "HOW", "DIAGNOSTIC")


def states_the_text_travels_unchanged(paragraph: str) -> bool:
    """A refusal's own text is DATA that travels unchanged to its answerer.

    All four named carriers -- WHAT, WHY, HOW and a role's DIAGNOSTIC -- and the
    destination must stand in the SAME paragraph as the unchanged-travel claim.
    """
    if not _TRAVELS_UNCHANGED.search(paragraph):
        return False
    if not _IS_DATA.search(paragraph):
        return False
    if not _DESTINATION.search(paragraph):
        return False
    return all(
        re.search(rf"\b{carrier}\b", paragraph) is not None for carrier in _CARRIERS
    )


_PARAPHRASE = re.compile(r"\bparaphrase\b", re.IGNORECASE)
_SUMMARY = re.compile(r"\bsummar(?:y|ise|ize|ised|ized)\b", re.IGNORECASE)
_NEW_CLAIM = re.compile(r"\ba new claim\b", re.IGNORECASE)
_AUTHORED_BY_ANOTHER = re.compile(
    r"(?:authored|written|made)\s+by\s+(?:someone|a role|an author)[^.]*"
    r"who did not (?:make|author|write) it",
    re.IGNORECASE,
)
_NARROWS = re.compile(
    r"(?:silently\s+)?narrows?\s+what[^.]*(?:can see|sees)", re.IGNORECASE
)


def states_a_paraphrase_is_a_new_claim(paragraph: str) -> bool:
    """A paraphrase or a summary is a NEW claim that silently narrows the view."""
    if not (_PARAPHRASE.search(paragraph) and _SUMMARY.search(paragraph)):
        return False
    if not _NEW_CLAIM.search(paragraph):
        return False
    if not _AUTHORED_BY_ANOTHER.search(paragraph):
        return False
    return _NARROWS.search(paragraph) is not None


_THE_LLM = re.compile(r"\bLLM\b")
_CHOOSES_ANSWERER = re.compile(
    r"chooses which step (?:answers|responds)", re.IGNORECASE
)
_MAY_ADD = re.compile(r"may add[^.]*context", re.IGNORECASE)
_ALONGSIDE = re.compile(r"\balongside\b", re.IGNORECASE)
_NEVER_INSTEAD = re.compile(r"never in place of", re.IGNORECASE)


def states_the_llm_adds_alongside(paragraph: str) -> bool:
    """The LLM still chooses the answerer and adds context ALONGSIDE, never instead."""
    if not (_THE_LLM.search(paragraph) and _CHOOSES_ANSWERER.search(paragraph)):
        return False
    if not _MAY_ADD.search(paragraph):
        return False
    return bool(_ALONGSIDE.search(paragraph)) and bool(_NEVER_INSTEAD.search(paragraph))


def any_paragraph_states(predicate, text: str) -> bool:
    return any(predicate(paragraph) for paragraph in paragraphs_of(text))


def diagnostic_for(text: str) -> str:
    """The paragraphs actually read, so a failure names what was there."""
    found = paragraphs_of(text)
    return "\n---\n".join(found) if found else "<no paragraphs>"


def installer_argv() -> str:
    return " ".join(("nwave-ai", *INSTALL_ARGUMENTS))


def sandbox_diagnostic(process: subprocess.CompletedProcess[str]) -> str:
    return (
        f"exit={process.returncode}\nstdout:\n{process.stdout}\n"
        f"stderr:\n{process.stderr}"
    )
