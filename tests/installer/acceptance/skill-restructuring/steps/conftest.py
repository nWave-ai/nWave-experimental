"""
Pytest-BDD fixtures for skill-restructuring acceptance tests.

Provides shared fixtures for test setup, installation context,
and filesystem simulation. All tests invoke through driving ports
(SkillsPlugin.install, .verify, .uninstall) -- never internal components.
"""

import logging
from pathlib import Path

import pytest

# Register step definitions with pytest-bdd
from . import (  # noqa: F401
    agent_path_steps,
    audit_steps,
    ci_validation_steps,
    distribution_steps,
    filtering_steps,
    install_steps,
    naming_steps,
)


# ---------------------------------------------------------------------------
# Fixtures: Test Environment
# ---------------------------------------------------------------------------


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for test execution."""
    logger = logging.getLogger("test.skill-restructuring")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger


@pytest.fixture
def clean_claude_dir(tmp_path: Path) -> Path:
    """Simulate a clean ~/.claude directory for testing.

    Returns a temporary directory that acts as the Claude config root.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir


@pytest.fixture
def skills_target_dir(clean_claude_dir: Path) -> Path:
    """The skills installation target directory."""
    skills_dir = clean_claude_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


@pytest.fixture
def skills_source_dir(tmp_path: Path) -> Path:
    """A temporary source directory simulating nWave/skills/ with nw-prefixed layout."""
    source = tmp_path / "nWave" / "skills"
    source.mkdir(parents=True, exist_ok=True)
    return source


@pytest.fixture
def populate_troubleshooter_skills(skills_source_dir: Path) -> list[str]:
    """Create 3 troubleshooter skill directories in nw-prefixed format.

    Returns the list of skill directory names created.
    """
    skill_names = [
        "nw-five-whys-methodology",
        "nw-investigation-techniques",
        "nw-post-mortem-framework",
    ]
    for name in skill_names:
        skill_dir = skills_source_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name.removeprefix('nw-')}\n"
            f"description: Test skill for {name}\n---\n\n"
            f"# {name.removeprefix('nw-').replace('-', ' ').title()}\n\n"
            f"Content for {name}.\n",
            encoding="utf-8",
        )
    return skill_names


@pytest.fixture
def old_namespace_dir(skills_target_dir: Path) -> Path:
    """Create an old-style nw/ namespace directory with legacy skill files."""
    old_nw = skills_target_dir / "nw"
    old_nw.mkdir(parents=True, exist_ok=True)

    # Create a legacy skill file
    crafter_dir = old_nw / "software-crafter"
    crafter_dir.mkdir(parents=True, exist_ok=True)
    (crafter_dir / "tdd-methodology.md").write_text(
        "# TDD Methodology\n\nLegacy content.\n",
        encoding="utf-8",
    )
    return old_nw


@pytest.fixture
def custom_user_skill(skills_target_dir: Path) -> Path:
    """Create a user-owned custom skill directory (not nWave-managed)."""
    custom_dir = skills_target_dir / "my-prompt-patterns"
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "SKILL.md").write_text(
        "# My Custom Prompts\n\nUser content.\n",
        encoding="utf-8",
    )
    return custom_dir


@pytest.fixture
def install_context(
    clean_claude_dir: Path,
    project_root: Path,
    skills_source_dir: Path,
    test_logger: logging.Logger,
):
    """Create an InstallContext configured for skill-restructuring tests.

    Uses the real InstallContext with test-controlled paths.
    """
    from scripts.install.plugins.base import InstallContext

    return InstallContext(
        claude_dir=clean_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=skills_source_dir.parent.parent,
        framework_source=skills_source_dir.parent,
        dry_run=False,
    )


@pytest.fixture
def skills_plugin():
    """Create a SkillsPlugin instance -- the driving port for installation."""
    from scripts.install.plugins.skills_plugin import SkillsPlugin

    return SkillsPlugin()


# ---------------------------------------------------------------------------
# Pytest-BDD error reporting
# ---------------------------------------------------------------------------


def pytest_bdd_step_error(
    request, feature, scenario, step, step_func, step_func_args, exception
):
    """Log step errors for debugging."""
    logging.error(f"Step failed: {step.name}")
    logging.error(f"Feature: {feature.name}")
    logging.error(f"Scenario: {scenario.name}")
    logging.error(f"Exception: {exception}")
