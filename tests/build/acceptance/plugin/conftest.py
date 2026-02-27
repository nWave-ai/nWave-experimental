"""
Pytest-BDD Configuration for Plugin Build Acceptance Tests.

Provides fixtures for the plugin build pipeline acceptance tests.
All fixtures use real filesystem operations for the build pipeline
and produce temporary directories for plugin output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixtures: Source Tree
# ---------------------------------------------------------------------------


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    current = Path(__file__).resolve()
    # Navigate from tests/build/acceptance/plugin/conftest.py to project root
    return current.parents[4]


@pytest.fixture
def nwave_source_tree(project_root: Path) -> Path:
    """Return the nWave framework source directory."""
    source = project_root / "nWave"
    assert source.exists(), f"nWave source tree not found: {source}"
    return source


@pytest.fixture
def des_source_tree(project_root: Path) -> Path:
    """Return the DES source directory."""
    source = project_root / "src" / "des"
    assert source.exists(), f"DES source tree not found: {source}"
    return source


@pytest.fixture
def pyproject_path(project_root: Path) -> Path:
    """Return the path to pyproject.toml."""
    path = project_root / "pyproject.toml"
    assert path.exists(), f"pyproject.toml not found: {path}"
    return path


# ---------------------------------------------------------------------------
# Fixtures: Build Output
# ---------------------------------------------------------------------------


@pytest.fixture
def plugin_output_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for plugin build output."""
    output = tmp_path / "plugin"
    output.mkdir(parents=True, exist_ok=True)
    return output


# ---------------------------------------------------------------------------
# Fixtures: Build Configuration (will be replaced by real BuildConfig)
# ---------------------------------------------------------------------------


@pytest.fixture
def build_config(
    nwave_source_tree: Path,
    des_source_tree: Path,
    pyproject_path: Path,
    plugin_output_dir: Path,
) -> dict[str, Any]:
    """
    Provide a default build configuration for the plugin assembler.

    This is a placeholder that will be replaced by the real BuildConfig
    dataclass once implemented by the software crafter.
    """
    return {
        "source_root": nwave_source_tree.parent,
        "nwave_dir": nwave_source_tree,
        "des_dir": des_source_tree,
        "pyproject_path": pyproject_path,
        "output_dir": plugin_output_dir,
        "plugin_name": "nw",
    }


# ---------------------------------------------------------------------------
# Fixtures: Build Results (populated by When steps)
# ---------------------------------------------------------------------------


@pytest.fixture
def build_result() -> dict[str, Any]:
    """
    Mutable container for build pipeline results.

    When steps populate this dict; Then steps read from it.
    Avoids storing state on pytest module.
    """
    return {
        "plugin_dir": None,
        "success": None,
        "error": None,
        "validation_result": None,
    }


# ---------------------------------------------------------------------------
# Fixtures: Minimal Source Trees (for edge case testing)
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_source_tree(tmp_path: Path) -> Path:
    """
    Create a minimal source tree with exactly 1 agent, 1 skill, 1 command.

    Used for minimum viable build tests.
    """
    root = tmp_path / "minimal_source"
    root.mkdir()

    # Minimal pyproject.toml
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "nwave"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )

    # 1 agent
    agents_dir = root / "nWave" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "nw-test-agent.md").write_text(
        "---\nname: nw-test-agent\n---\n# Test Agent\n",
        encoding="utf-8",
    )

    # 1 skill
    skills_dir = root / "nWave" / "skills" / "test-agent"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill.md").write_text(
        "---\nname: test-skill\n---\n# Test Skill\n",
        encoding="utf-8",
    )

    # 1 command
    commands_dir = root / "nWave" / "tasks" / "nw"
    commands_dir.mkdir(parents=True)
    (commands_dir / "test-command.md").write_text(
        "---\nname: test-command\n---\n# Test Command\n",
        encoding="utf-8",
    )

    # Minimal DES source
    des_dir = root / "src" / "des"
    des_dir.mkdir(parents=True)
    (des_dir / "__init__.py").write_text("", encoding="utf-8")

    return root
