"""Tests for skill-agent mapping validation script.

Validates that validate_skill_agent_mapping.py correctly detects:
- Broken references (agent references non-existent skill directory)
- Orphan skill directories (not referenced by any agent)
- Naming convention violations (missing nw- prefix)
- Clean pass when all mappings are consistent

Driving port: validate() function -- the public API.
Test Budget: 4 behaviors x 2 = 8 max unit tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT_PATH = (
    PROJECT_ROOT / "scripts" / "validation" / "validate_skill_agent_mapping.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(tmp_path: Path, name: str, skills: list[str]) -> None:
    """Create an agent .md file with given skill references."""
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(
        {"name": name, "description": "Test", "model": "inherit", "skills": skills},
        default_flow_style=False,
    )
    (agents_dir / f"{name}.md").write_text(f"---\n{fm}---\n\n# {name}\n")


def _make_skill_dir(tmp_path: Path, dir_name: str) -> None:
    """Create a skill directory with SKILL.md."""
    skills_dir = tmp_path / "nWave" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = skills_dir / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {dir_name}\n---\n\n# Skill\n")


def _ensure_dirs(tmp_path: Path) -> None:
    """Ensure both agents and skills directories exist."""
    (tmp_path / "nWave" / "agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "nWave" / "skills").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Unit tests: validate() function -- the driving port
# ---------------------------------------------------------------------------


class TestValidateSkillAgentMapping:
    """Behavior 1: Broken reference detection (agent -> missing dir)."""

    def test_broken_reference_fails_with_agent_and_skill_named(self, tmp_path):
        """Agent referencing non-existent skill directory causes failure."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_agent(tmp_path, "nw-test-agent", ["nw-nonexistent-skill"])

        result = validate(tmp_path)

        assert result.exit_code == 1
        assert len(result.errors) > 0
        error_text = " ".join(result.errors)
        assert "nw-test-agent" in error_text
        assert "nw-nonexistent-skill" in error_text

    def test_multiple_broken_refs_all_reported(self, tmp_path):
        """Multiple broken references from different agents all reported."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_agent(tmp_path, "nw-agent-a", ["nw-missing-one"])
        _make_agent(tmp_path, "nw-agent-b", ["nw-missing-two"])

        result = validate(tmp_path)

        assert result.exit_code == 1
        assert len(result.errors) == 2


class TestOrphanDetection:
    """Behavior 2: Orphan directory detection (dir not referenced)."""

    def test_orphan_directory_produces_warning_not_error(self, tmp_path):
        """Unreferenced skill directory produces warning, not failure."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_skill_dir(tmp_path, "nw-orphan-skill")
        _make_agent(tmp_path, "nw-test-agent", ["nw-other-skill"])
        _make_skill_dir(tmp_path, "nw-other-skill")

        result = validate(tmp_path)

        assert result.exit_code == 0
        assert len(result.warnings) > 0
        warning_text = " ".join(result.warnings)
        assert "nw-orphan-skill" in warning_text


class TestNamingConvention:
    """Behavior 3: nw-prefix enforcement on skill directories."""

    def test_non_prefixed_directory_fails(self, tmp_path):
        """Skill directory without nw- prefix causes failure."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_skill_dir(tmp_path, "bad-skill-name")

        result = validate(tmp_path)

        assert result.exit_code == 1
        error_text = " ".join(result.errors)
        assert "bad-skill-name" in error_text

    @pytest.mark.parametrize(
        "bad_name",
        ["legacy-skill", "my-custom-thing", "NW-uppercase"],
    )
    def test_various_non_prefixed_names_fail(self, tmp_path, bad_name):
        """Various naming violations all produce errors."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_skill_dir(tmp_path, bad_name)

        result = validate(tmp_path)

        assert result.exit_code == 1
        assert any(bad_name in e for e in result.errors)


class TestCleanPass:
    """Behavior 4: All mappings correct produces clean pass."""

    def test_consistent_mapping_passes_clean(self, tmp_path):
        """All refs match dirs and all dirs referenced produces clean pass."""
        from scripts.validation.validate_skill_agent_mapping import validate

        _ensure_dirs(tmp_path)
        _make_agent(
            tmp_path,
            "nw-test-crafter",
            ["nw-tdd-methodology", "nw-quality-framework"],
        )
        _make_skill_dir(tmp_path, "nw-tdd-methodology")
        _make_skill_dir(tmp_path, "nw-quality-framework")

        result = validate(tmp_path)

        assert result.exit_code == 0
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# Integration: script runs against real nWave directory
# ---------------------------------------------------------------------------


class TestScriptIntegration:
    """Integration: script validates real project files."""

    def test_script_validates_real_project(self):
        """Running the script against the real repo must exit 0."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            f"Script exited with {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
