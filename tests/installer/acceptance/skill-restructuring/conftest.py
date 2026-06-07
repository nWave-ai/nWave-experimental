"""
Pytest-BDD configuration for skill-restructuring acceptance tests.

This conftest sits at the test file level and imports step definitions
from the steps/ package. Fixtures are also defined here so pytest-bdd
can discover them alongside the step definitions.

Note: The directory name "skill-restructuring" contains a hyphen, which
prevents standard Python relative imports. We use importlib with explicit
file paths to load step definition modules.
"""

import importlib.util
import logging
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Step definition registration
# ---------------------------------------------------------------------------
# The "skill-restructuring" directory name contains a hyphen, making it an
# invalid Python package name. Relative imports (from .steps import ...) fail
# under pytest's --import-mode=importlib. We load step modules by file path
# and inject their public names into this conftest's namespace so pytest-bdd
# can discover @given/@when/@then step definitions.

_steps_dir = Path(__file__).parent / "steps"

for _step_module_name in [
    "agent_builder_steps",
    "agent_path_steps",
    "audit_steps",
    "ci_validation_steps",
    "distribution_steps",
    "filtering_steps",
    "install_steps",
    "naming_steps",
]:
    _step_file = _steps_dir / f"{_step_module_name}.py"
    if _step_file.exists():
        _spec = importlib.util.spec_from_file_location(
            f"skill_restructuring_steps.{_step_module_name}",
            str(_step_file),
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        # Inject step functions into conftest namespace for pytest-bdd discovery
        for _attr_name in dir(_mod):
            if not _attr_name.startswith("_"):
                globals()[f"_step_{_step_module_name}_{_attr_name}"] = getattr(
                    _mod, _attr_name
                )


# ---------------------------------------------------------------------------
# Fixtures: Test Environment
# ---------------------------------------------------------------------------


@pytest.fixture
def project_root() -> Path:
    """Return the nWave project root directory."""
    return Path(__file__).resolve().parents[4]


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

    # Create minimal framework-catalog.yaml in the temp project root
    # so load_public_agents(strict=True) does not raise CatalogNotFoundError.
    temp_project_root = skills_source_dir.parent.parent
    nwave_dir = temp_project_root / "nWave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = nwave_dir / "framework-catalog.yaml"
    if not catalog_path.exists():
        catalog_path.write_text(
            "agents: {}\n",
            encoding="utf-8",
        )

    return InstallContext(
        claude_dir=clean_claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=temp_project_root,
        framework_source=skills_source_dir.parent,
        dry_run=False,
    )


@pytest.fixture
def skills_plugin():
    """Create a SkillsPlugin instance -- the driving port for installation."""
    from scripts.install.plugins.skills_plugin import SkillsPlugin

    return SkillsPlugin()


# ---------------------------------------------------------------------------
# Fixtures: Framework Catalog and Ownership
# ---------------------------------------------------------------------------


@pytest.fixture
def framework_catalog(project_root):
    """Create minimal framework-catalog.yaml for filtering tests.

    Includes public and private agents so filtering tests can validate
    that skills owned by private agents are excluded from public
    distributions.
    """
    catalog_content = textwrap.dedent("""\
        agents:
          troubleshooter:
            wave: CROSS_WAVE
            priority: 2
            role: debugging
            public: true
          software-crafter:
            wave: DELIVER
            priority: 1
            role: implementation
            public: true
          business-osint:
            wave: CROSS_WAVE
            priority: 2
            role: business_intelligence
            public: false
    """)
    nwave_dir = project_root / "nWave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = nwave_dir / "framework-catalog.yaml"
    catalog_path.write_text(catalog_content, encoding="utf-8")
    return catalog_path


@pytest.fixture
def ownership_map():
    """Skill-to-agent ownership mapping for filtering tests.

    Maps flat nw-prefixed skill directory names to their owning agent.
    Used by is_public_skill() to determine whether a skill should be
    included in public distributions.
    """
    return {
        "nw-five-whys-methodology": "troubleshooter",
        "nw-investigation-techniques": "troubleshooter",
        "nw-post-mortem-framework": "troubleshooter",
        "nw-tdd-methodology": "software-crafter",
        "nw-private-skill": "business-osint",
    }


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
