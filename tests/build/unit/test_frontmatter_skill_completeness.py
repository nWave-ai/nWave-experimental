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
    check_references,
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


def test_no_drift_when_the_loaded_skill_is_catalog_only_owned(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: a skill owned only through
    role-skill-loading.yaml's catalog_only field also clears the drift."""
    repo = _make_repo(tmp_path, frontmatter_skills=["nw-other"])
    (repo / "data").mkdir()
    (repo / "data" / "role-skill-loading.yaml").write_text(
        "version: 1\nroles:\n  nw-bar:\n    catalog_only:\n      - nw-foo\n"
    )
    assert check_frontmatter_completeness(repo) == []


def test_removing_catalog_only_entry_reintroduces_drift(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: once the catalog_only entry
    that owned a loaded skill is removed, the skill reverts to unowned and
    the drift check flags it again."""
    repo = _make_repo(tmp_path, frontmatter_skills=["nw-other"])
    (repo / "data").mkdir()
    (repo / "data" / "role-skill-loading.yaml").write_text(
        "version: 1\nroles:\n  nw-bar:\n    catalog_only:\n      - nw-unrelated\n"
    )
    drift = check_frontmatter_completeness(repo)
    assert any("nw-foo" in entry and "nw-bar.md" in entry for entry in drift), drift


def test_real_nwave_tree_has_zero_frontmatter_completeness_drift():
    """CONTRACT_SHAPE: unbounded-preservation. Outcome: the shipped nWave/ tree
    owns every loaded skill (regression guard for WS-11 D1)."""
    nwave_dir = Path(__file__).resolve().parents[3] / "nWave"
    assert check_frontmatter_completeness(nwave_dir) == []


def test_real_nwave_tree_has_no_false_skill_loading_doctrine():
    """CONTRACT_SHAPE: unbounded-preservation. Outcome: no shipped public
    agent/skill/template source claims frontmatter `skills:` is decorative,
    declarative-only, or does not auto-load, and none claims subagents
    cannot use the Skill tool -- both are false: `skills:` eagerly preloads
    full content into custom subagents, and Skill invocation is available
    to Task-dispatched sub-agents (only slash commands are not)."""
    nwave_dir = Path(__file__).resolve().parents[3] / "nWave"
    banned_patterns = [
        "skills frontmatter is decorative",
        "declarative-only",
        "does not auto-load",
        "does not auto load",
        "subagents cannot use skill",
        "sub-agents cannot use skill",
        "cannot use the skill tool",
    ]
    offenders = []
    for path in (nwave_dir / "agents").glob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        for pattern in banned_patterns:
            if pattern in text:
                offenders.append(f"{path}: {pattern!r}")
    for path in (nwave_dir / "skills").rglob("SKILL.md"):
        text = path.read_text(encoding="utf-8").lower()
        for pattern in banned_patterns:
            if pattern in text:
                offenders.append(f"{path}: {pattern!r}")
    for path in (nwave_dir / "templates").glob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        for pattern in banned_patterns:
            if pattern in text:
                offenders.append(f"{path}: {pattern!r}")
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# check_references: native `Invoke Skill(nw-*)` channel (channel 3)
# ---------------------------------------------------------------------------


def _make_referrer_repo(tmp_path: Path, body: str) -> Path:
    """Build a minimal nWave tree with a single public agent whose body is
    *body*. Unlike `_make_repo`, this includes a framework-catalog.yaml
    because `check_references` (unlike `check_frontmatter_completeness`)
    loads it with `strict=True`.
    """
    (tmp_path / "agents").mkdir(parents=True)
    (tmp_path / "agents" / "nw-bar.md").write_text(f"---\nname: nw-bar\n---\n{body}\n")
    (tmp_path / "framework-catalog.yaml").write_text(
        "agents:\n  bar:\n    wave: DELIVER\n    public: true\n    description: Bar\n"
    )
    return tmp_path


def test_native_invoke_skill_reference_is_recognized_when_skill_missing(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: a native `Invoke Skill(nw-foo)`
    call is recognized as a reference (channel 3) and flagged as dangling
    when `nw-foo` does not exist on disk at all."""
    repo = _make_referrer_repo(tmp_path, "Invoke Skill(nw-foo)")
    dangling = check_references(repo)
    assert any("nw-foo" in entry and "nw-bar.md" in entry for entry in dangling), (
        dangling
    )


def test_native_invoke_skill_placeholder_is_ignored(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: the template placeholder
    `Invoke Skill(nw-{skill-name})` is not an executable reference and must
    not be flagged, even though no real skill exists in the repo."""
    repo = _make_referrer_repo(tmp_path, "Invoke Skill(nw-{skill-name})")
    assert check_references(repo) == []


def test_native_invoke_skill_reference_to_strippable_skill_fails(tmp_path):
    """CONTRACT_SHAPE: bounded-change. Outcome: a native `Invoke Skill(nw-foo)`
    call is flagged as dangling when `nw-foo` exists on disk but is not
    owned by any public agent (so the release strip removes it)."""
    repo = _make_referrer_repo(tmp_path, "Invoke Skill(nw-foo)")
    (repo / "skills" / "nw-foo").mkdir(parents=True)
    (repo / "skills" / "nw-foo" / "SKILL.md").write_text("# foo\n")
    dangling = check_references(repo)
    assert any(
        "nw-foo" in entry and "release strip removes" in entry for entry in dangling
    ), dangling
