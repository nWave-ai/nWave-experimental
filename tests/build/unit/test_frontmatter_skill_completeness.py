"""Unit test for the frontmatter-completeness check (WS-11 D1 prevention).

`check_frontmatter_completeness` flags an agent that LOADS a skill via a
`skills/nw-X/SKILL.md` body reference but does not OWN `nw-X` via either
channel — its frontmatter `skills:` list OR the role-skill-loading.yaml
registry (folded in by `build_ownership_map`) — the drift the union-based
`check_references` misses.
"""

from pathlib import Path

from scripts.validation.validate_skill_references import (
    check_frontmatter_completeness,
)


def _make_repo(tmp_path: Path, frontmatter_skills: list[str]) -> Path:
    """Build a minimal nWave tree: skill nw-foo + an agent that loads it.

    CONTRACT_SHAPE: bounded-change.
    """
    (tmp_path / "skills" / "nw-foo").mkdir(parents=True)
    (tmp_path / "skills" / "nw-foo" / "SKILL.md").write_text("placeholder")
    (tmp_path / "agents").mkdir()
    declared = "".join(f"  - {s}\n" for s in frontmatter_skills)
    (tmp_path / "agents" / "nw-bar.md").write_text(
        f"---\nname: nw-bar\nskills:\n{declared}---\n"
        "Load `~/.claude/skills/nw-foo/SKILL.md` now.\n"
    )
    return tmp_path


def test_loaded_but_undeclared_skill_is_flagged_as_drift(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: an agent loading nw-foo without
    declaring it in frontmatter is reported."""
    repo = _make_repo(tmp_path, frontmatter_skills=["nw-other"])
    drift = check_frontmatter_completeness(repo)
    assert any("nw-foo" in entry and "nw-bar.md" in entry for entry in drift), drift


def test_no_drift_once_the_loaded_skill_is_declared(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: declaring the loaded skill in
    frontmatter clears the drift."""
    repo = _make_repo(tmp_path, frontmatter_skills=["nw-other", "nw-foo"])
    assert check_frontmatter_completeness(repo) == []


def test_no_drift_when_the_loaded_skill_is_registry_owned(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: a skill owned only through
    role-skill-loading.yaml's phase field also clears the drift."""
    repo = _make_repo(tmp_path, frontmatter_skills=["nw-other"])
    (repo / "data").mkdir()
    (repo / "data" / "role-skill-loading.yaml").write_text(
        "version: 1\nroles:\n  nw-bar:\n    phase:\n      nw-foo: some phase\n"
    )
    assert check_frontmatter_completeness(repo) == []


def test_real_nwave_tree_has_zero_frontmatter_completeness_drift():
    """CONTRACT_SHAPE: unbounded-preservation. Outcome: the shipped nWave/ tree
    owns every loaded skill (regression guard for WS-11 D1)."""
    nwave_dir = Path(__file__).resolve().parents[3] / "nWave"
    assert check_frontmatter_completeness(nwave_dir) == []
