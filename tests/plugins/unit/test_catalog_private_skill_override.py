"""Unit tests for the catalog-declared private-skill override.

A skill's visibility used to be DERIVED only: public when at least one
owning agent is public. There was no way to express "private skill owned
by a public agent". These tests pin the declarative override in
``framework-catalog.yaml`` (``skills: {<dir>: {public: false}}``) and the
falsifier that undeclared skills keep the derived behaviour.
"""

from pathlib import Path

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    is_public_skill,
    load_private_skills,
    load_public_agents,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"


def _write_tree(
    root: Path, catalog_skills: str, *, command_skill: bool = False
) -> Path:
    """Build a minimal nWave tree: one public agent owning two skills."""
    nwave = root / "nWave"
    (nwave / "agents").mkdir(parents=True)
    (nwave / "skills" / "nw-secret-lens").mkdir(parents=True)
    (nwave / "skills" / "nw-open-lens").mkdir(parents=True)

    (nwave / "agents" / "nw-widget-maker.md").write_text(
        "---\n"
        "name: nw-widget-maker\n"
        "skills:\n"
        "  - nw-secret-lens\n"
        "  - nw-open-lens\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    frontmatter = (
        "---\nname: nw-secret-lens\nuser-invocable: true\n---\n"
        if command_skill
        else "---\nname: nw-secret-lens\nuser-invocable: false\ndisable-model-invocation: true\n---\n"
    )
    (nwave / "skills" / "nw-secret-lens" / "SKILL.md").write_text(
        frontmatter, encoding="utf-8"
    )
    (nwave / "skills" / "nw-open-lens" / "SKILL.md").write_text(
        "---\nname: nw-open-lens\nuser-invocable: false\ndisable-model-invocation: true\n---\n",
        encoding="utf-8",
    )

    (nwave / "framework-catalog.yaml").write_text(
        "name: test\nagents:\n  widget-maker:\n    public: true\n" + catalog_skills,
        encoding="utf-8",
    )
    return nwave


def _verdicts(nwave: Path) -> dict[str, bool]:
    public_agents = load_public_agents(nwave)
    ownership = build_ownership_map(nwave / "agents")
    command_skills = detect_command_skills(nwave / "skills")
    private_skills = load_private_skills(nwave)
    return {
        name: is_public_skill(
            name, public_agents, ownership, command_skills, private_skills
        )
        for name in ("nw-secret-lens", "nw-open-lens")
    }


class TestCatalogPrivateSkillOverride:
    def test_declared_private_skill_owned_by_public_agent_is_not_public(self, tmp_path):
        nwave = _write_tree(
            tmp_path,
            "skills:\n  nw-secret-lens:\n    public: false\n",
        )
        assert _verdicts(nwave)["nw-secret-lens"] is False

    def test_undeclared_skill_owned_by_public_agent_stays_public(self, tmp_path):
        """Falsifier: the derived behaviour is unchanged for every other skill."""
        nwave = _write_tree(
            tmp_path,
            "skills:\n  nw-secret-lens:\n    public: false\n",
        )
        assert _verdicts(nwave)["nw-open-lens"] is True

    def test_no_skills_section_leaves_every_skill_public(self, tmp_path):
        """Falsifier: absent declaration section changes nothing at all."""
        nwave = _write_tree(tmp_path, "")
        assert _verdicts(nwave) == {"nw-secret-lens": True, "nw-open-lens": True}

    def test_declaration_beats_the_command_skill_public_override(self, tmp_path):
        """Fail-closed: no public path may resurrect a declared-private skill."""
        nwave = _write_tree(
            tmp_path,
            "skills:\n  nw-secret-lens:\n    public: false\n",
            command_skill=True,
        )
        assert detect_command_skills(nwave / "skills") == {"nw-secret-lens"}
        assert _verdicts(nwave)["nw-secret-lens"] is False

    def test_public_true_declaration_is_not_a_private_declaration(self, tmp_path):
        nwave = _write_tree(
            tmp_path,
            "skills:\n  nw-secret-lens:\n    public: true\n",
        )
        assert _verdicts(nwave)["nw-secret-lens"] is True


class TestRealCatalog:
    """The real tree must keep working while no skill is declared private.

    The mechanism is deliberately dormant here: the declaration for
    nw-cross-cutting-invariants arrives with the skill split, not with this
    slice. Nothing above depends on the real catalog, so these stay true
    whether or not a declaration is later added.
    """

    def test_the_declaration_section_is_readable(self):
        """load_private_skills tolerates an empty or absent section."""
        assert isinstance(load_private_skills(NWAVE_DIR), set)

    def test_no_skill_is_declared_private_yet(self):
        assert load_private_skills(NWAVE_DIR) == set()

    def test_a_real_agent_skill_remains_public(self):
        """Falsifier on the real tree: nothing became private by accident."""
        public_agents = load_public_agents(NWAVE_DIR)
        ownership = build_ownership_map(NWAVE_DIR / "agents")
        command_skills = detect_command_skills(NWAVE_DIR / "skills")
        private_skills = load_private_skills(NWAVE_DIR)
        for skill in ("nw-code-design-oo", "nw-cross-cutting-invariants"):
            assert is_public_skill(
                skill, public_agents, ownership, command_skills, private_skills
            ), f"{skill} lost public status without a declaration"
