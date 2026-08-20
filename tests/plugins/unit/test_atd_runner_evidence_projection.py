"""Tool surface, sealed readiness, and dispatch-boundary projection (2026-08-16).

Dense semantic projections, resilient to Markdown heading/prose refactors:

1. ATD's tool surface is exactly Read/Write/Edit — no Bash, no Skill — so it
   can compile a contract but never execute, install or discover anything.
2. Dependency readiness (owner/version, declared=yes, present=yes) is sealed
   compiler input from the architecture authority; any undeclared or absent
   dependency is `EVIDENCE_GAP` before any write, and ATD never edits a
   manifest/lock file or installs, repairs, executes or validates a
   dependency.
3. Root's single `des dispatch` call is the only bridge from CONTRACT_READY
   to a crafter, and RED/BROKEN classification belongs to the crafter's own
   BASELINE step, never to ATD.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"

ACCEPTANCE_DESIGNER = (NWAVE_DIR / "agents" / "nw-acceptance-designer.md").read_text(
    encoding="utf-8"
)
AUTO_SKILL = (NWAVE_DIR / "skills" / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_atd_tool_surface_is_read_write_edit_bash_only() -> None:
    """Ale's construction-over-file correction (2026-08-20) added `Bash`,
    locked to `des fill-contract` by an installed PreToolUse hook (see
    `test_atd_fill_contract_bash_lockdown.py`) -- `Skill` is still absent."""
    header = _norm(ACCEPTANCE_DESIGNER[:400])
    assert "tools: Read, Write, Edit, Bash" in header
    body = _norm(ACCEPTANCE_DESIGNER)
    assert "This role holds no `Skill` tool" in body


def test_atd_serializes_exact_schema_shapes_and_never_embeds_forbidden_dependency_metadata() -> (
    None
):
    body = _norm(ACCEPTANCE_DESIGNER)
    assert (
        "Serialize every field in the exact shape and enum the read "
        "`CONTRACT-SCHEMA` requires" in body
    )
    assert "`schema-version`, `repository.worktree`, `targetPlan`, `paradigm`" in body
    assert "each `verification-scope` command object" in body
    assert "add no property the schema's `additionalProperties` forbids" in body
    assert (
        "dependency metadata is never embedded unless the schema names that "
        "property" in body
    )


def test_atd_never_performs_dependency_mutation() -> None:
    body = _norm(ACCEPTANCE_DESIGNER)
    assert (
        "for each dependency (including any `BROAD_INPUT_DOMAIN` language PBT "
        "adapter) its final owner/version plus declared=yes, present=yes "
        "readiness facts" in body
    )
    assert (
        "Any dependency recorded as undeclared or absent returns `EVIDENCE_GAP` "
        "immediately, before any example read or artifact write" in body
    )
    assert (
        "It never edits a manifest/lock file and never installs, repairs, "
        "executes or validates a dependency" in body
    )


def test_root_single_dispatch_and_classification_belongs_to_crafter_baseline() -> None:
    body = _norm(ACCEPTANCE_DESIGNER)
    assert (
        "this role never returns a thin header, a digest or a RED/GREEN/BROKEN "
        "classification" in body
    )
    auto = _norm(AUTO_SKILL)
    assert "Root never calls `des dispatch` a second time" in auto
    assert "des dispatch --repo-root ROOT --delivery-contract PATH" in auto
