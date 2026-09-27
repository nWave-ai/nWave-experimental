"""A backgrounded step is recovered by reading the Request's state.

Observation
-----------
An agent reading the published nw-auto skill is told, at the exact point where
it learns a step must be invoked in the foreground and never backgrounded, what
to do when the environment backgrounds it anyway: the turn is recorded by DES,
so the agent reads the Request's state to learn whether the turn landed and what
is owed next, and waiting for a notification is named as the move that cannot
work. It stays guidance the agent reasons with, not a new rule.

Stimulus
--------
Run the REAL public installer process, ``nwave-ai install --yes --platform
claude-code``, inside a throwaway sandbox whose ``HOME``, ``NWAVE_AGENTS_HOME``,
``CLAUDE_CONFIG_DIR`` and ``CODEX_HOME`` are pinned, then read the bytes it
published at ``<system_home>/.claude/skills/nw-auto/SKILL.md`` and extract
section 8 structurally -- its ``## 8.`` heading up to the next ``## ``.

Expected
--------
Exactly one bullet of section 8 carries, together: the backgrounding hazard, the
recorded turn, the ``des state`` reading that tells whether the turn landed and
what is owed next, and the naming of waiting-for-a-notification as the move that
cannot work. No phrase of the closed forbidden set turns that recovery bullet
into a promised runner behaviour or gate.

Falsifier
---------
Section 8 as published today ends the backgrounding bullet at "you would wait on
a turn that has already ended" and offers no move: ``des state`` and the word
"recorded" do not occur inside section 8 at all, so the predicate is unsatisfied
and the agent that is backgrounded is left with nothing to read.

The expected text is derived from sources OUTSIDE the target file: ADR-DES-003
L2 ("a turn is bought before its record is written"), ADR-DES-003 O2 (``des
state`` prints the owned per-value state and names the canonical ``NEXT``), and
``src/des/cli/step_terminal.py`` ("never backgrounded, because no notification
reaches a step invocation"). Nothing here imports a production symbol, reads a
template, or reads the source skill: skills are data the installer publishes.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.installer.acceptance.session_start_notice.session_journey import (
    environment_for,
    run_cli,
)


# The published location, measured: HOME-rooted under the pinned sandbox HOME,
# never project-rooted. An oracle pointed at the project root would observe an
# absent file and could pass vacuously.
PUBLISHED_SKILL_RELATIVE = Path(".claude/skills/nw-auto/SKILL.md")
PUBLISHED_SKILLS_DIR_RELATIVE = Path(".claude/skills")

INSTALL_ARGUMENTS = ("install", "--yes", "--platform", "claude-code")

SECTION_EIGHT_HEADING = "## 8."
NEXT_SECTION = re.compile(r"^## ", re.MULTILINE)
BULLET_START = re.compile(r"^-\s+", re.MULTILINE)

# Guidance, never a gate: guard section 8's backgrounding bullets rather than
# unrelated instructions in the published skill. "never" is deliberately NOT
# guarded -- section 8 is already an imperative checklist.
FORBIDDEN_PROMISES = (
    "you must",
    "mandatory",
    "is required",
    "never wait",
    "des notifies",
    "notifies you",
    "des resumes",
    "automatically",
    "will tell you",
    "before proceeding",
    "you may not",
)


class InstallerDidNotComplete(Exception):
    """The public installer port established nothing to observe."""


class PublishedSkillMissing(Exception):
    """The install published no nw-auto SKILL.md at all."""


class SectionEightMissing(Exception):
    """The published skill has no section 8."""


@dataclass(frozen=True)
class InstalledAutoSkill:
    """The bytes of the published nw-auto skill, as an agent reads them."""

    published_text: str

    @classmethod
    def published_by_real_install(cls, sandbox: Path) -> InstalledAutoSkill:
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
                f"`{installer_argv()}` exited {process.returncode}\n"
                f"stderr:\n{process.stderr}"
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

    def section_eight(self) -> str:
        """Section 8 extracted structurally, never by designation.

        Scoping is load-bearing: ``des state`` and "recorded" both occur
        elsewhere in the skill, so an unscoped scan would read green on section
        7 without the change ever being made.
        """
        start = self.published_text.find(SECTION_EIGHT_HEADING)
        if start == -1:
            raise SectionEightMissing(
                f"the published skill carries no '{SECTION_EIGHT_HEADING}' heading"
            )
        rest = self.published_text[start + len(SECTION_EIGHT_HEADING) :]
        following = NEXT_SECTION.search(rest)
        end = len(rest) if following is None else following.start()
        return SECTION_EIGHT_HEADING + rest[:end]

    def forbidden_recovery_promises_present(self) -> tuple[str, ...]:
        recovery = "\n".join(
            bullet.lower()
            for bullet in bullets_of(self.section_eight())
            if _BACKGROUNDED.search(bullet)
        )
        return tuple(phrase for phrase in FORBIDDEN_PROMISES if phrase in recovery)


def bullets_of(text: str) -> tuple[str, ...]:
    """Text cut into bullets, as a reader meets them.

    Bullet-level co-occurrence is what makes the hazard and its recovery stand
    together, rather than being satisfiable by words scattered across a section.
    """
    pieces = BULLET_START.split(text)
    return tuple(piece.strip() for piece in pieces[1:] if piece.strip())


# ---------------------------------------------------------------------------
# Pure, total predicates over ONE bullet. Each names one claim.
# ---------------------------------------------------------------------------

_BACKGROUNDED = re.compile(r"background(?:ed|s|ing)?", re.IGNORECASE)
_NOTIFICATION = re.compile(r"notification", re.IGNORECASE)
_RECORDED = re.compile(r"\brecord(?:s|ed|ing)?\b", re.IGNORECASE)
_DES_STATE = re.compile(r"`?des state`?")
_REQUESTS_STATE = re.compile(r"\b(?:request|state)\b", re.IGNORECASE)
_WHAT_IS_OWED_NEXT = re.compile(r"\b(?:next|owe[ds]?|owing)\b", re.IGNORECASE)
_INEFFECTIVE_WAIT = re.compile(
    r"\bwait(?:ing)?\b[^.?!]*\bnotification\b[^.?!]*"
    r"(?:cannot work|does not work|doesn't work|won't work|will not work|ineffective|fails?)\b",
    re.IGNORECASE,
)


def states_the_turn_is_recorded(bullet: str) -> bool:
    """The turn DES bought is recorded, so the work is not lost."""
    return _RECORDED.search(bullet) is not None


def states_the_state_is_read(bullet: str) -> bool:
    """The agent reads the Request's state, and the reading move is named."""
    return bool(_DES_STATE.search(bullet)) and bool(_REQUESTS_STATE.search(bullet))


def states_what_is_owed_next(bullet: str) -> bool:
    """The reading tells whether the turn landed and what is owed next."""
    return _WHAT_IS_OWED_NEXT.search(bullet) is not None


def names_waiting_as_the_move_that_fails(bullet: str) -> bool:
    """Waiting for a notification is expressly named as ineffective."""
    return bool(_BACKGROUNDED.search(bullet)) and bool(_INEFFECTIVE_WAIT.search(bullet))


def states_the_backgrounded_recovery(bullet: str) -> bool:
    """All four claims stand in the SAME bullet.

    The hazard and its recovery must be readable together: an agent that meets
    the failing move without the working one is left with nothing to do.
    """
    return (
        names_waiting_as_the_move_that_fails(bullet)
        and states_the_turn_is_recorded(bullet)
        and states_the_state_is_read(bullet)
        and states_what_is_owed_next(bullet)
    )


def any_bullet_states(predicate, text: str) -> bool:
    return any(predicate(bullet) for bullet in bullets_of(text))


def diagnostic_for(text: str) -> str:
    """The bullets actually read, so a failure names what was there."""
    found = bullets_of(text)
    return "\n---\n".join(found) if found else "<no bullets>"


def installer_argv() -> str:
    return " ".join(("nwave-ai", *INSTALL_ARGUMENTS))


# ---------------------------------------------------------------------------
# The observation.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def published_skill(tmp_path_factory: pytest.TempPathFactory) -> InstalledAutoSkill:
    """One real install, whose published bytes every question is asked of."""
    sandbox = tmp_path_factory.mktemp("backgrounded-step-recovery")
    return InstalledAutoSkill.published_by_real_install(sandbox)


def test_a_backgrounded_step_is_recovered_by_reading_the_requests_state(
    published_skill: InstalledAutoSkill,
) -> None:
    section = published_skill.section_eight()
    assert any_bullet_states(states_the_backgrounded_recovery, section), (
        "no single bullet of section 8 tells an agent whose step was "
        "backgrounded what to do: the turn is recorded, so read the Request's "
        "state with `des state` to learn whether the turn landed and what is "
        "owed next, and waiting for a notification cannot work.\n"
        f"section 8 bullets as published:\n{diagnostic_for(section)}"
    )


def test_the_recovery_stays_guidance_and_never_becomes_a_gate(
    published_skill: InstalledAutoSkill,
) -> None:
    present = published_skill.forbidden_recovery_promises_present()
    assert present == (), (
        "the published backgrounding recovery carries phrases that turn "
        "guidance into a rule or promise runner behaviour DES does not provide: "
        f"{list(present)}"
    )


if __name__ == "__main__":
    # The declared invocation is `uv run python <this file>`. Running the module
    # must EXECUTE the observation, not merely define it, so the exit status
    # carries the verdict.
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
