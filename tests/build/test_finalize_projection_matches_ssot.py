"""Projection law for ADR-SSOT-002 Section 8 whole-delivery finalize.

Static projection checks over the internal nw-finalize Skill and its callers.
This is a projection-conformance test, never an installed ABCDEF proof.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "nWave/skills/nw-finalize/SKILL.md"
TASK = ROOT / "nWave/tasks/nw/finalize.md"
BUGFIX = ROOT / "nWave/skills/nw-bugfix/SKILL.md"
CATALOG = ROOT / "nWave/skills/nw-buddy-command-catalog/SKILL.md"
CLI_REGISTRY = ROOT / "src/des/cli/__main__.py"
RETIRED_RUNTIME = (
    ROOT / "src/des/cli/finalize_workspace.py",
    ROOT / "src/des/application/finalize_workspace.py",
)


@pytest.mark.parametrize("path", [SKILL, BUGFIX])
def test_finalize_projection_retires_temporary_workspace_ceremony(path: Path) -> None:
    text = path.read_text(encoding="utf-8").casefold()

    for retired in (
        "des finalize-workspace",
        "promotion completeness",
        "completion ledger",
        "at-completion ledger",
        "living history",
        "feature workspace preserved",
    ):
        assert retired not in text


def test_finalize_skill_is_internal_without_default_agent_ceremony() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "user-invocable: false" in text
    assert "argument-hint" not in text
    assert "by default" not in text
    assert "called by `/nw-deliver`" in text


def test_finalize_skill_projects_authorized_delivery_paths_union() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "`AuthorizedDeliveryPaths`" in text
    assert "Finalize authors no paths." in text
    assert "`Diff(B,K)`" in text
    assert "never persisted or supplied by a" in text


def test_finalize_skill_projects_exact_scope_and_closure_laws() -> None:
    text = SKILL.read_text(encoding="utf-8")

    required = (
        "complete pending Git path set",
        "including formerly-untracked paths",
        "Stage exactly the verified path set",
        "normal commit hooks exactly once",
        "single whole-delivery commit",
        "fresh clean checkout of F",
        "exact\n   B-derived `PreservationVector`",
        "contains the authorized verification argv",
        "Caller-supplied vectors or metadata are non-authoritative.",
        "canonical deterministic final metadata",
        "<admitted-predecessor>",
        "admitted predecessor is B or K",
        "Clean-checkout: true",
        "`PASS`, `FAIL` or `INDETERMINATE`",
    )
    for law in required:
        assert law in text
    assert "both\nvectors" not in text
    assert "contract verification vectors" not in text
    expected = text[text.index("## Expected result") :]
    assert "FINALIZE-RESULT" not in expected
    assert (
        expected.index("Commit: git-<algorithm>:<F>")
        < expected.index("Clean-checkout: true")
        < expected.index("Verdict: PASS | FAIL | INDETERMINATE")
    )


def test_finalize_skill_projects_positive_ownership_and_idempotence_laws() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "byte-for-byte unchanged, in `C`'s base revision is preexisting" in text
    assert "never a finalize input, defect classification target" in text
    assert "## Idempotence law" in text
    assert "rerun may return `PASS` only for the exact F" in text
    assert "no second commit or state-changing" in text
    assert "atomic same-object no-op" in text
    assert "foreign, stale or mismatched F" in text
    assert "merely clean tree" in text


def test_finalize_task_is_deleted_not_a_sentinel() -> None:
    assert not TASK.exists()


def test_finalize_runtime_is_deleted_instead_of_replaced() -> None:
    registry = CLI_REGISTRY.read_text(encoding="utf-8")

    assert "finalize-workspace" not in registry
    assert "des.cli.finalize_workspace" not in registry
    assert all(not path.exists() for path in RETIRED_RUNTIME)


def test_buddy_catalog_drops_the_public_finalize_row() -> None:
    text = CATALOG.read_text(encoding="utf-8")

    assert "/nw-finalize" not in text


def test_bugfix_consumes_delivers_finalize_instead_of_invoking_it_again() -> None:
    text = BUGFIX.read_text(encoding="utf-8")

    assert "/nw-finalize" not in text
    assert "`nw-finalize` Skill a second time" in text
    assert "already calls" in text
    assert "already returned" in text
