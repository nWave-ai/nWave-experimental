"""Regression test: nw-user-examiner must open the workspace's own
environment file BEFORE trying to start anything itself, and must never
fall back to the project's own test suite when a service will not start.

Run 9 (K4 matrix): the examiner never opened `.k4-user-environment.md`
(present the whole time) and instead hand-derived a start sequence from
README/CLAUDE.md/api.md; her server died between separate Bash tool calls
(a bare `cmd &` only backgrounds for that ONE call), and she burned ~25
calls restarting it before falling back to `manage.py test` -- forbidden.
This locks GDP-9-form self-check language and the tightened
start-block-plus-bound / never-run-tests rules into the public agent spec's
START step, without weakening the source-blind epistemology or the terminal
PASS/FAIL/INDETERMINATE verdict contract.
"""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENT_PATH = PROJECT_ROOT / "nWave" / "agents" / "nw-user-examiner.md"


def _agent_text() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def _start_step(text: str) -> str:
    """Extract the numbered START workflow step, bounded to the next
    numbered step so assertions stay scoped to this rule. Whitespace is
    collapsed so a markdown line-wrap can never split a phrase this
    module asserts on."""
    match = re.search(r"3\. \*\*START\*\*.*?(?=\n4\. \*\*|\Z)", text, re.DOTALL)
    assert match, "START workflow step not found in nw-user-examiner.md"
    return " ".join(match.group(0).split())


def test_environment_file_is_named_first_in_gdp9_form():
    """Interrogative self-check naming the lazy alternative (GDP-9), THEN
    the imperative for the honest-no branch -- neither half alone is
    sufficient."""
    step = _start_step(_agent_text())
    lowered = step.lower()

    assert "did you open the environment file" in lowered, (
        "the interrogative GDP-9 form must ask whether the environment "
        "file was opened before starting anything"
    )
    assert "before trying to start anything yourself" in lowered
    assert "open it now" in lowered, (
        "the imperative for the honest-no branch must be present, not just the question"
    )


def test_environment_file_name_examples_are_generic_not_k4_hardcoded():
    """The agent spec is a general nWave asset, not K4-harness-specific:
    it must name recognizable EXAMPLE filenames (K4's own
    `.k4-user-environment.md` among them) rather than hard-depend on one
    harness's private convention, plus a discovery fallback."""
    step = _start_step(_agent_text())

    assert ".k4-user-environment.md" in step
    assert "directory listing" in step.lower()


def test_environment_file_outranks_charter_recipe_for_concrete_facts():
    """A charter's PublicStartRecipe names only the public shape; the
    environment file, when present, carries the concrete per-run facts
    (host/port, credential) that shape needs."""
    step = _start_step(_agent_text())
    lowered = step.lower()

    assert "publicstartrecipe" in lowered
    assert "shape" in lowered
    assert "host/port" in lowered or "host" in lowered


def test_start_bound_is_documented_block_plus_three_more_calls():
    step = _start_step(_agent_text())

    assert "documented start block plus" in step.lower()
    assert "3 more calls" in step or "≤3 more calls" in step
    assert "8 tool calls total spent on start" in step.lower()


def test_never_falls_back_to_the_projects_own_test_suite():
    step = _start_step(_agent_text())
    lowered = step.lower()

    assert "test suite" in lowered
    assert "never" in lowered
    assert "implementation-adjacent evidence" in lowered


def test_source_blindness_and_verdict_contract_preserved():
    """The fix must not weaken source-blindness or the terminal
    PASS/FAIL/INDETERMINATE verdict contract."""
    text = _agent_text()

    assert "Source blind" in text
    assert "PASS | FAIL | INDETERMINATE" in text

    step = _start_step(text)
    for forbidden_term in ("controller", "ledger", "hook", "registry"):
        assert forbidden_term not in step.lower(), (
            f"'{forbidden_term}' must not appear in the START step"
        )
