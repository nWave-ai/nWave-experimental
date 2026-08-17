"""K4 crafter first-mutation budget (2026-08-16, compact Core Principles).

Confirmed defect (43-call pre-edit failure): the crafter re-researched
declared DeliveryContract facts before its first production Edit. The
compact Core Principles section is the current carrier for the fix; this
module no longer freezes the deleted large Dispatch/Workflow section.

Parameterized across both nw-software-crafter.md (OO) and
nw-functional-software-crafter.md (FP).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "nWave" / "agents"
CRAFTERS = {
    "oo": AGENTS_DIR / "nw-software-crafter.md",
    "fp": AGENTS_DIR / "nw-functional-software-crafter.md",
}


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _principles(body: str) -> str:
    start = body.index("## Core Principles")
    end = body.index("## Skill Loading")
    return " ".join(body[start:end].split())


@pytest.mark.parametrize("path", CRAFTERS.values(), ids=CRAFTERS.keys())
def test_max_turns_45_no_retry_controller_or_new_ledger_language(path):
    body = _body(path)
    match = re.search(r"^maxTurns:\s*(\d+)\s*$", body, flags=re.MULTILINE)
    assert match is not None and match.group(1) == "45"
    lowered = body.lower()
    for forbidden in (
        "retry budget",
        "retry controller",
        "new ledger",
        "receipt artifact",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize("path", CRAFTERS.values(), ids=CRAFTERS.keys())
def test_first_mutation_bound_15_from_task_entry_with_skills_and_budget_reserved(path):
    principles = _principles(_body(path)).lower()
    assert "tool-call 15" in principles
    assert "counted from task entry" in principles
    assert "skill invocations counting" in principles
    assert "reserve remaining budget for" in principles
    assert (
        "declared targets, literal verification commands and the terminal result"
        in principles
    )


@pytest.mark.parametrize("path", CRAFTERS.values(), ids=CRAFTERS.keys())
def test_named_target_facts_closed_authoritative_no_rediscovery(path):
    principles = _principles(_body(path))
    for field in (
        "targets[].overlap",
        ".justification",
        ".declared-imports",
        ".boundary",
    ):
        assert field in principles
    assert "closed and authoritative" in principles
    lowered = principles.lower()
    assert "never re-derive them" in lowered
    assert "clarification_needed" in lowered
    assert "indeterminate" in lowered
    assert "never a research detour" in lowered


@pytest.mark.parametrize("path", CRAFTERS.values(), ids=CRAFTERS.keys())
def test_oracle_tests_immutable_and_terminal_result_fields_survive(path):
    body = _body(path)
    principles = _principles(body)
    assert "do not author, edit, regenerate or weaken tests" in principles.lower()
    assert "terminality is explicit" in principles.lower()
    assert "never `pass`" in principles.lower()
