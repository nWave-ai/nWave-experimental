"""Regression: mutation-testing policy must be coherent across guidance files.

Owner decision (2026-08-10): this repo opts into `nightly-delta` — the
checked-in `.github/workflows/mutation-nightly.yml` is its project-level
authority. Mutation testing is NOT a per-feature DELIVER gate and NOT a
rigor-profile knob. For other installed projects, an unspecified project
strategy remains fail-safe `disabled`; `/nw-mutation-test` stays usable as an
explicit, on-demand command regardless of strategy. PBT is active and
independent, and must not carry mutation-policy prose.

Supersedes test_nw_deliver_skill_mutation_default_matches_fr1.py and
test_mutation_test_task_body_matches_its_own_banner.py, which pinned the
stale FR-1 "mutation is fully deprecated / disabled everywhere" policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "mutation-nightly.yml"
_PBT_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-property-based-testing" / "SKILL.md"
_MUTATION_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-mutation-test" / "SKILL.md"
_MUTATION_TASK = _REPO_ROOT / "nWave" / "tasks" / "nw" / "mutation-test.md"
_RIGOR_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-rigor" / "SKILL.md"
_DELIVER_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"
_FRAMEWORK_CATALOG = _REPO_ROOT / "nWave" / "framework-catalog.yaml"


def test_repo_declares_nightly_delta_and_workflow_exists() -> None:
    claude_md = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "Mutation Testing Strategy: nightly-delta" in claude_md
    assert _WORKFLOW.is_file()


@pytest.mark.parametrize("path", [_MUTATION_SKILL, _MUTATION_TASK])
def test_generic_mutation_docs_default_to_disabled_unless_explicit(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert "default" in text and "disabled" in text
    assert "on-demand" in text or "opt-in" in text or "explicit" in text


def test_pbt_skill_has_no_mutation_policy_prose() -> None:
    text = _PBT_SKILL.read_text(encoding="utf-8").lower()
    assert "mutation" not in text


@pytest.mark.parametrize("path", [_DELIVER_SKILL, _RIGOR_SKILL])
def test_deliver_and_rigor_have_no_mutation_enabled_or_per_feature_gate(
    path: Path,
) -> None:
    text = path.read_text(encoding="utf-8")
    assert "mutation_enabled" not in text
    assert "Phase 5" not in text


def test_rigor_skill_states_mutation_is_project_level_not_a_rigor_axis() -> None:
    text = _RIGOR_SKILL.read_text(encoding="utf-8").lower()
    assert "not a rigor axis" in text
    assert "no longer a rigor axis" not in text
    assert "deprecated" not in text.split("mutation testing")[1][:200]


def test_deliver_skill_has_no_per_feature_mutation_route() -> None:
    text = _DELIVER_SKILL.read_text(encoding="utf-8")
    assert "mutation-testing-report" not in text


@pytest.mark.parametrize("path", [_MUTATION_SKILL, _MUTATION_TASK])
def test_mutation_docs_never_restore_the_users_worktree(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "git checkout -- src/ tests/" not in text
    assert "git checkout --" not in text
    assert "git reset" not in text or "FORBIDDEN" in text
    lowered = text.lower()
    assert "python projects require mutation" not in lowered
    assert "disposable worktree" in lowered or "disposable copy" in lowered
    assert "phase 8" not in lowered
    assert (
        "phase 8 - finalize (orchestrator continues develop.md workflow)" not in lowered
    )
    assert "standalone" in lowered


def test_framework_catalog_mutation_test_description_coherence() -> None:
    """Verify mutation_test description in framework catalog is coherent."""
    catalog_text = _FRAMEWORK_CATALOG.read_text(encoding="utf-8")
    catalog = yaml.safe_load(catalog_text)

    mutation_desc = catalog["commands"]["mutation_test"]["description"]
    mutation_desc_lower = mutation_desc.lower()

    # Must NOT be deprecated
    assert "deprecated" not in mutation_desc_lower

    # Must mention explicit invocation
    assert "explicit" in mutation_desc_lower or "on-demand" in mutation_desc_lower

    # Must state disabled default
    assert (
        "disabled" in mutation_desc_lower
        or "default is disabled" in mutation_desc_lower
    )
