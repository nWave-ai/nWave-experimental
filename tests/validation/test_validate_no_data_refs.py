"""Tests for validate_no_data_refs.py validation script.

Validates that:
- Script exits 0 when no nWave/data/ references found
- Script exits 1 and reports file:line details when violations found
- Clean files without any bad patterns exit 0
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validation" / "validate_no_data_refs.py"


class TestCurrentCodebaseIsClean:
    """Script exits 0 on the current (clean) codebase."""

    def test_exits_0_on_current_codebase(self):
        """No nWave/data/ references should remain in agents/skills/tasks."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            f"Script found violations in clean codebase:\n{result.stdout}"
        )


class TestDetectsViolations:
    """Script detects nWave/data/ references and reports them."""

    def test_flags_nwave_data_reference(self, tmp_path):
        """nWave/data/ pattern must be flagged."""
        _create_scan_dirs(tmp_path)
        bad_file = tmp_path / "nWave" / "agents" / "bad-agent.md"
        bad_file.write_text("Load config from nWave/data/config.yaml\n")

        result = _run_script(tmp_path)
        assert result.returncode == 1
        assert "bad-agent.md:1" in result.stdout
        assert "nWave/data/" in result.stdout

    def test_flags_data_config_reference(self, tmp_path):
        """data/config/ pattern must be flagged."""
        _create_scan_dirs(tmp_path)
        bad_file = tmp_path / "nWave" / "skills" / "some-skill.md"
        bad_file.write_text("See data/config/settings.yaml for details\n")

        result = _run_script(tmp_path)
        assert result.returncode == 1
        assert "some-skill.md:1" in result.stdout
        assert "data/config/" in result.stdout

    def test_flags_data_methodologies_reference(self, tmp_path):
        """data/methodologies/ pattern must be flagged."""
        _create_scan_dirs(tmp_path)
        bad_file = tmp_path / "nWave" / "tasks" / "nw" / "bad-task.md"
        bad_file.write_text("Load from data/methodologies/tdd.yaml\n")

        result = _run_script(tmp_path)
        assert result.returncode == 1
        assert "bad-task.md:1" in result.stdout
        assert "data/methodologies/" in result.stdout

    def test_reports_multiple_violations(self, tmp_path):
        """Multiple violations across files are all reported."""
        _create_scan_dirs(tmp_path)
        (tmp_path / "nWave" / "agents" / "a.md").write_text("ref nWave/data/foo\n")
        (tmp_path / "nWave" / "skills" / "b.md").write_text("ref data/config/bar\n")

        result = _run_script(tmp_path)
        assert result.returncode == 1
        assert "a.md:1" in result.stdout
        assert "b.md:1" in result.stdout


class TestCleanFiles:
    """Files without bad patterns exit 0."""

    def test_docs_research_output_not_flagged(self, tmp_path):
        """docs/research/ used as output path is not a bad pattern."""
        _create_scan_dirs(tmp_path)
        ok_file = tmp_path / "nWave" / "agents" / "researcher.md"
        ok_file.write_text("Write research document to docs/research/topic.md\n")

        result = _run_script(tmp_path)
        assert result.returncode == 0, (
            f"False positive on docs/research/ output path:\n{result.stdout}"
        )

    def test_clean_files_exit_0(self, tmp_path):
        """Files without any data references exit 0."""
        _create_scan_dirs(tmp_path)
        clean_file = tmp_path / "nWave" / "agents" / "clean.md"
        clean_file.write_text("This agent uses nWave/skills/common/rules.md\n")

        result = _run_script(tmp_path)
        assert result.returncode == 0

    def test_empty_scan_dirs_exit_0(self, tmp_path):
        """Empty scan directories exit 0."""
        _create_scan_dirs(tmp_path)

        result = _run_script(tmp_path)
        assert result.returncode == 0


# --- Helpers ---


def _create_scan_dirs(root: Path) -> None:
    """Create the directory structure the script expects to scan."""
    (root / "nWave" / "agents").mkdir(parents=True)
    (root / "nWave" / "skills").mkdir(parents=True)
    (root / "nWave" / "tasks" / "nw").mkdir(parents=True)


def _run_script(root: Path) -> subprocess.CompletedProcess:
    """Run the validation script against the given root directory."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
    )
