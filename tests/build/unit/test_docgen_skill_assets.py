"""Regression guard for packaged skill support material."""

from pathlib import Path

from scripts.docgen import scan


def test_scan_catalogues_only_the_flat_skill_entry_point(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    skill = root / "nWave" / "skills" / "nw-example"
    references = skill / "references"
    references.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    (references / "detail.md").write_text("# Detail\n", encoding="utf-8")
    (root / "nWave" / "agents").mkdir(parents=True)
    (root / "nWave" / "tasks" / "nw").mkdir(parents=True)
    (root / "nWave" / "templates").mkdir(parents=True)

    paths = scan(root)

    assert paths["skills"] == [skill / "SKILL.md"]


def test_scan_preserves_direct_legacy_skill_discovery(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    legacy = root / "nWave" / "skills" / "legacy-owner"
    legacy.mkdir(parents=True)
    (legacy / "method.md").write_text("# Method\n", encoding="utf-8")
    (root / "nWave" / "agents").mkdir(parents=True)
    (root / "nWave" / "tasks" / "nw").mkdir(parents=True)
    (root / "nWave" / "templates").mkdir(parents=True)

    paths = scan(root)

    assert paths["skills"] == [legacy / "method.md"]


def test_generated_loading_uses_receiving_roles_tools(tmp_path: Path) -> None:
    from scripts.docgen import _role_skill_loading_body

    root = tmp_path
    agents = root / "nWave/agents"
    agents.mkdir(parents=True)
    spec = agents / "nw-example.md"
    spec.write_text("---\nname: nw-example\ntools: Read, Edit\n---\n")
    data = root / "nWave/data"
    data.mkdir()
    (data / "role-skill-loading.yaml").write_text(
        "version: 1\nroles:\n  nw-example:\n    on_demand:\n      nw-knowledge: a domain law is present\n"
    )
    skill = root / "nWave/skills/nw-knowledge"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: nw-knowledge\n---\nContent.")
    result = _role_skill_loading_body("nw-example", root)
    assert "Read `~/.claude/skills/nw-knowledge/SKILL.md`" in result
    assert "a domain law is present" in result
    assert "Invoke Skill" not in result
    spec.write_text("---\nname: nw-example\ntools: Read, Skill\n---\n")
    assert "Invoke Skill(nw-knowledge)" in _role_skill_loading_body("nw-example", root)


def test_generated_loading_includes_the_global_semantic_lens(tmp_path: Path) -> None:
    from scripts.docgen import _role_skill_loading_body

    root = tmp_path
    agents = root / "nWave/agents"
    agents.mkdir(parents=True)
    (agents / "nw-example.md").write_text(
        "---\nname: nw-example\ntools: Read, Skill\n---\n", encoding="utf-8"
    )
    data = root / "nWave/data"
    data.mkdir()
    (data / "role-skill-loading.yaml").write_text(
        "version: 1\n"
        "global_on_demand:\n"
        "  nw-typesafe-system-one: every bounded semantic judgment\n"
        "roles:\n"
        "  nw-example:\n"
        "    catalog_only:\n"
        "      - nw-knowledge\n",
        encoding="utf-8",
    )
    skill = root / "nWave/skills/nw-typesafe-system-one"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: nw-typesafe-system-one\n---\nContent.", encoding="utf-8"
    )

    rendered = _role_skill_loading_body("nw-example", root)

    assert "Invoke Skill(nw-typesafe-system-one)" in rendered
    assert "every bounded semantic judgment" in rendered
