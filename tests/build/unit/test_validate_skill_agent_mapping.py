"""Tests for skill-agent mapping validation/census script.

Validates that validate_skill_agent_mapping.py correctly detects:
- Broken references (agent references non-existent skill directory) -- REAL
  validation, exit 1.
- Naming convention violations (missing nw- prefix) -- REAL validation,
  exit 1.
- Clean pass when all mappings are consistent.

And CENSUSES, never as a verdict (2026-08-24,
docs/analysis/2026-08-24-decisione-gate-skill-orfane.md):
- Orphan skill directories (not referenced by any agent's frontmatter) --
  exit 0 always, split into PUBLIC_SHARED_SKILLS-explained and
  unexplained, reported in a `MEASURED:` line that never says PASSED/OK.

Driving port: validate() function for the two real checks; main()'s
stdout for the census framing (`TestCensusIsNeverAVerdict` below).
Test Budget: 5 behaviors x 2 = 10 max unit tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.validation import validate_skill_agent_mapping


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
            ["nw-tdd-methodology", "nw-code-design-oo"],
        )
        _make_skill_dir(tmp_path, "nw-tdd-methodology")
        _make_skill_dir(tmp_path, "nw-code-design-oo")

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


# ---------------------------------------------------------------------------
# Behavior 5: orphan reporting is a CENSUS, never a verdict (2026-08-24)
# ---------------------------------------------------------------------------


class TestCensusIsNeverAVerdict:
    """`F-SKILL-MAPPING-GATE-WARNS-NEVER-FAILS`
    (docs/analysis/2026-08-24-decisione-gate-skill-orfane.md): the orphan
    count is real and reported, but exit 0 on it alone is a DELIBERATE
    choice, not an oversight -- so the wording must never read as a
    passed check."""

    def test_real_project_output_never_contains_the_word_passed(self):
        """FALSIFIER for the semantic change: not 'does it exit 0' (it
        already did) but 'can the text be misread as a verdict'."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert "PASSED" not in result.stdout
        assert "MEASURED:" in result.stdout

    def test_measured_line_reports_total_orphan_and_split_counts(
        self, monkeypatch, tmp_path, capsys
    ):
        """Two orphans, one explained by the allow-list, one not -- the
        printed line must carry all four counts (total skills, total
        orphans, explained, unexplained), never just the raw orphan
        count PUBLIC_SHARED_SKILLS was built to explain away."""
        _ensure_dirs(tmp_path)
        _make_agent(tmp_path, "nw-test-agent", ["nw-referenced-skill"])
        _make_skill_dir(tmp_path, "nw-referenced-skill")
        _make_skill_dir(tmp_path, "nw-explained-orphan")
        _make_skill_dir(tmp_path, "nw-unexplained-orphan")
        monkeypatch.setattr(
            "scripts.validation.validate_skill_agent_mapping.PUBLIC_SHARED_SKILLS",
            frozenset({"nw-explained-orphan"}),
        )

        exit_code = validate_skill_agent_mapping.main(["--project-root", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 0
        assert "PASSED" not in out
        assert "3 skill(s)" in out
        assert "2 without a resolvable owner" in out
        assert "1 explained by PUBLIC_SHARED_SKILLS" in out
        assert "1 unexplained" in out

    def test_a_real_error_still_reads_as_a_verdict(self, tmp_path, capsys):
        """CONTROPROVA: the census framing must not soften the two REAL
        checks -- a broken reference still prints FAILED and exits 1."""
        _ensure_dirs(tmp_path)
        _make_agent(tmp_path, "nw-test-agent", ["nw-missing-skill"])

        exit_code = validate_skill_agent_mapping.main(["--project-root", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 1
        assert "FAILED: 1 error(s) found" in out
        assert "MEASURED:" not in out
