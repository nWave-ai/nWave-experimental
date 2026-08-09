"""K3-A availability checks: the mode-select skill and its reuse contract.

K3-A (docs/analysis/2026-08-06-kernel-acceleration-mission.md, "K3-A Activation
+ Mode UX") is hook-only: one small skill + reuse of the EXISTING SubagentStart
additionalContext hook. These checks are targeted (not the full install
matrix): they demonstrate (a) the skill is present and discoverable in the
same flat layout every other nw-* skill uses, (b) its instructions are
operational directives an LLM can execute (not prose-only), and (c) the reused
hook still exists unmodified and stays fail-open/non-blocking.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO / "nWave/skills/nw-mode-select/SKILL.md"
HOOK_PATH = REPO / "src/des/adapters/drivers/hooks/subagent_start_handler.py"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_skill_file_exists_in_the_flat_nw_skills_layout() -> None:
    assert SKILL_PATH.is_file(), (
        f"K3-A skill missing at {SKILL_PATH} — must sit under nWave/skills/nw-<name>/SKILL.md "
        "like every other nw-* skill (subagent_start_handler.py's reminder assumes this layout)."
    )


def test_skill_frontmatter_declares_name_description_and_user_invocable() -> None:
    text = _skill_text()
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    frontmatter = text.split("---\n", 2)[1]
    assert "name: nw-mode-select" in frontmatter
    assert "description:" in frontmatter
    assert "user-invocable: true" in frontmatter


def test_skill_description_names_the_load_trigger_not_just_the_topic() -> None:
    """A description with no trigger is inert prose the LLM never reaches for."""
    frontmatter = _skill_text().split("---\n", 2)[1]
    description_line = next(
        line for line in frontmatter.splitlines() if line.startswith("description:")
    )
    assert "Load" in description_line, (
        "Description must name WHEN to load the skill (operational trigger), "
        f"got: {description_line!r}"
    )


def test_skill_carries_operative_human_auto_decision_procedure() -> None:
    """human/auto must be a decision procedure, not a description of one."""
    text = _skill_text()
    for marker in (
        "## Step 1",
        "## Step 2",
        "## Step 3",
        "S (small)",
        "M (medium)",
        "L (large)",
        "human-on-the-loop",
        "auto",
        "Direct mode",
    ):
        assert marker in text, f"missing operative marker: {marker!r}"


def test_skill_forbids_ledger_sequencer_and_new_hook_scope_creep() -> None:
    """K3-A's binding fence: no sequencer/engine/DSL/ledger, no new hook code."""
    text = _skill_text()
    assert "Not a sequencer" in text
    assert "Not a ledger" in text
    assert "adds no hook code of its own" in text


def test_skill_names_the_reused_html_projection_mechanism_not_a_new_one() -> None:
    text = _skill_text()
    assert "scripts/gen_status_dashboard.py" in text
    assert "do not build a template engine" in text


def test_skill_line_count_is_compressed_by_at_least_30_percent() -> None:
    """Deletion-first contract correction: SKILL.md must shrink from its
    prior 104 lines by >=30% (<=73) while preserving the decision table."""
    assert len(_skill_text().splitlines()) <= 73


def test_skill_self_contained_s_invokes_selector_then_never_nw_auto() -> None:
    """Corrected contract: S no longer skips this skill -- it invokes
    nw-mode-select once, classifies S, then exits directly without ever
    delegating to nw-auto (delegation is Auto M/L only)."""
    text = _skill_text()
    assert "only a self-contained S skips this skill entirely" not in text
    assert "S never delegates to `nw-auto`" in text


def test_skill_hook_statement_matches_runtime_blocking_truth() -> None:
    """The reused hook may block the first mutation until mode/size
    selection is observed once; it is not unconditionally non-blocking."""
    text = _skill_text()
    assert "is non-blocking and reused as-is" not in text
    assert "may block the first mutation until this one selection is observed" in text


def test_subagent_start_hook_reused_unmodified_and_still_fail_open() -> None:
    """The reused hook must still exist and its non-blocking contract must hold."""
    assert HOOK_PATH.is_file(), f"K3-A relies on the existing hook at {HOOK_PATH}"
    tree = ast.parse(HOOK_PATH.read_text(encoding="utf-8"))
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "handle_subagent_start"
    )
    source = ast.get_source_segment(HOOK_PATH.read_text(encoding="utf-8"), func)
    assert source is not None
    assert "except Exception" in source and "return 0" in source, (
        "handle_subagent_start must stay fail-open (except Exception -> return 0); "
        "K3-A must never turn this into a blocking gate."
    )


def test_skill_is_reachable_from_the_reminder_message_naming_convention() -> None:
    """The reused hook tells agents to load skills by NAME via the Skill tool
    (D3-analog fix: a hardcoded ~/.claude-relative path is invalid under an
    isolated CLAUDE_CONFIG_DIR) — confirm nw-mode-select fits the addressable
    flat nw-<name>/SKILL.md layout the Skill tool's own resolver expects."""
    hook_source = HOOK_PATH.read_text(encoding="utf-8")
    assert "~/.claude" not in hook_source
    assert "Skill tool" in hook_source
    assert SKILL_PATH.parent.name == "nw-mode-select"
    assert SKILL_PATH.name == "SKILL.md"
