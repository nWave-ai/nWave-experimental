"""A refusal's own text travels whole to the step that answers it.

Authority: docs/product/architecture/brief.md#A Refusal's Own Text Travels Whole
to the Step That Answers It

The observation: reading section 3 of the PUBLISHED nw-auto skill -- the section
that already carries the ``Refusal`` outcome row and the three ``--finding -``
invocations, so it is read at the moment the orchestrator is holding a refusal --
shows three things stated there, each as its own paragraph:

1. a refusal's own text (its WHAT, WHY and HOW lines and a role's DIAGNOSTIC) is
   DATA that travels unchanged to the step that answers it;
2. a paraphrase or a summary is a new claim about the refusal, authored by
   someone who did not make it, that silently narrows what the answering role
   can see;
3. the LLM still chooses which step answers and may add its own context
   alongside the forwarded text, never in place of it.

Every question is asked of bytes a real ``nwave-ai install`` published into a
throwaway sandbox, at the exact path an agent is told to read, and every
assertion is SCOPED to section 3: the file's only pre-existing "unchanged" and
"whole" live in sections 7 and 6, so an unscoped scan would read green on prose
that has nothing to do with a refusal.

Run it:

    .venv/bin/python -m pytest \
        tests/installer/acceptance/refusal_travels_whole/test_refusal_text_travels_whole.py
    .venv/bin/python \
        tests/installer/acceptance/refusal_travels_whole/test_refusal_text_travels_whole.py

``.venv/bin/python`` is named explicitly because the installer refuses under a
non-virtualenv interpreter.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import pytest
from tests.installer.acceptance.refusal_travels_whole.installed_skill import (
    InstalledSkill,
    any_paragraph_states,
    diagnostic_for,
    installer_argv,
    states_a_paraphrase_is_a_new_claim,
    states_the_llm_adds_alongside,
    states_the_text_travels_unchanged,
)


@pytest.fixture(scope="module")
def published_skill(tmp_path_factory: pytest.TempPathFactory) -> InstalledSkill:
    return InstalledSkill.published_by_real_install(
        tmp_path_factory.mktemp("published-nwave")
    )


def test_section_three_states_that_a_refusals_own_text_travels_whole(
    published_skill: InstalledSkill,
) -> None:
    published_skill.section_three_holds_a_refusal()
    section = published_skill.section_three()
    read = diagnostic_for(section)

    assert any_paragraph_states(states_the_text_travels_unchanged, section), (
        "section 3 of the published nw-auto skill does not state, in one "
        "paragraph, that a refusal's own text -- its WHAT, WHY and HOW lines and "
        "a role's DIAGNOSTIC -- is DATA that travels unchanged to the step that "
        f"answers it.\nsection 3 paragraphs as published ({installer_argv()}):\n"
        f"{read}"
    )

    assert any_paragraph_states(states_a_paraphrase_is_a_new_claim, section), (
        "section 3 does not state that a paraphrase or a summary is a new claim "
        "about the refusal, authored by someone who did not make it, that "
        "silently narrows what the answering role can see.\nsection 3 "
        f"paragraphs as published:\n{read}"
    )

    assert any_paragraph_states(states_the_llm_adds_alongside, section), (
        "section 3 does not state that the LLM still chooses which step answers "
        "and may add its own context alongside the forwarded text, never in "
        f"place of it.\nsection 3 paragraphs as published:\n{read}"
    )


def test_the_discipline_stays_guidance_and_promises_no_forwarding(
    published_skill: InstalledSkill,
) -> None:
    """It never claims that DES, a step or a runner forwards on your behalf."""
    promised = published_skill.forbidden_promises_present()
    assert promised == (), (
        "the published nw-auto skill turns the discipline into a runner "
        "behaviour the installed DES does not provide; forbidden phrases "
        f"present: {promised}"
    )


def test_the_claims_are_scoped_to_section_three(
    published_skill: InstalledSkill,
) -> None:
    """The pre-existing "unchanged"/"whole" prose elsewhere cannot satisfy them."""
    elsewhere = published_skill.sections_other_than_three()
    for predicate in (
        states_the_text_travels_unchanged,
        states_a_paraphrase_is_a_new_claim,
        states_the_llm_adds_alongside,
    ):
        assert not any_paragraph_states(predicate, elsewhere), (
            f"{predicate.__name__} is satisfied by prose OUTSIDE section 3, so "
            "the observation could read green on text that has nothing to do "
            "with a refusal"
        )


# ---------------------------------------------------------------------------
# Discrimination: three weakened phrasings the predicates were never written
# against. Each stays RED on exactly the claim it weakens, and green on the
# others, so the discrimination is demonstrated rather than asserted.
# ---------------------------------------------------------------------------

_FULL_TRAVEL = (
    "A refusal's own text is data. Its WHAT, WHY and HOW lines, and a role's "
    "DIAGNOSTIC, travel unchanged to the step that answers it."
)
_FULL_PARAPHRASE = (
    "A paraphrase or a summary is a new claim about the refusal, authored by "
    "someone who did not make it, and it silently narrows what the answering "
    "role can see."
)
_FULL_LLM = (
    "The LLM still chooses which step answers, and may add its own context "
    "alongside the forwarded text, never in place of it."
)

WEAKENED_TRAVEL = (
    "A refusal's own text is data. Its WHAT, WHY and HOW lines travel unchanged "
    "to the step that answers it."
)
WEAKENED_PARAPHRASE = (
    "Keep the gist of the refusal when you hand it on, and do not lose a "
    "paraphrase or a summary of what it said."
)
WEAKENED_LLM = (
    "The LLM still chooses which step answers, and may add its own context in "
    "place of the forwarded text."
)


@pytest.mark.parametrize(
    ("weakened", "weakened_predicate"),
    [
        (
            (WEAKENED_TRAVEL, _FULL_PARAPHRASE, _FULL_LLM),
            states_the_text_travels_unchanged,
        ),
        (
            (_FULL_TRAVEL, WEAKENED_PARAPHRASE, _FULL_LLM),
            states_a_paraphrase_is_a_new_claim,
        ),
        (
            (_FULL_TRAVEL, _FULL_PARAPHRASE, WEAKENED_LLM),
            states_the_llm_adds_alongside,
        ),
    ],
    ids=["drops-DIAGNOSTIC", "gist-instead-of-new-claim", "in-place-of-alongside"],
)
def test_a_weakened_phrasing_stays_red_on_exactly_the_claim_it_weakens(
    weakened: tuple[str, ...], weakened_predicate
) -> None:
    text = "\n\n".join(weakened)
    assert not any_paragraph_states(weakened_predicate, text), (
        f"{weakened_predicate.__name__} accepts a phrasing that weakens the very "
        f"claim it questions:\n{text}"
    )
    for predicate in (
        states_the_text_travels_unchanged,
        states_a_paraphrase_is_a_new_claim,
        states_the_llm_adds_alongside,
    ):
        if predicate is weakened_predicate:
            continue
        assert any_paragraph_states(predicate, text), (
            f"{predicate.__name__} is not discriminating: it went red on a "
            f"phrasing that weakens only {weakened_predicate.__name__}"
        )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as sandbox:
        skill = InstalledSkill.published_by_real_install(Path(sandbox))
        test_section_three_states_that_a_refusals_own_text_travels_whole(skill)
        test_the_discipline_stays_guidance_and_promises_no_forwarding(skill)
        test_the_claims_are_scoped_to_section_three(skill)
    print("observation met")
