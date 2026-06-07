"""Pytest-BDD configuration for backup-retention-policy acceptance tests.

This conftest sits at the test directory level. Because the directory name
"backup-retention-policy" contains hyphens (so relative imports do not
work under --import-mode=importlib), step modules are loaded by file path
and their public names are injected into this conftest's namespace so
pytest-bdd can discover @given/@when/@then step definitions.

Strategy: C (Real local). All adapters use real filesystem on tmp_path with
HOME and CLAUDE_CONFIG_DIR isolated via monkeypatch. No InMemory adapter
appears in any walking skeleton or focused scenario.
"""

import importlib.util
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Step definition registration (by file path, due to hyphenated dir name)
# ---------------------------------------------------------------------------

_steps_dir = Path(__file__).parent / "steps"

for _step_module_name in [
    "backup_steps",
]:
    _step_file = _steps_dir / f"{_step_module_name}.py"
    if _step_file.exists():
        _spec = importlib.util.spec_from_file_location(
            f"backup_retention_policy_steps.{_step_module_name}",
            str(_step_file),
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr_name in dir(_mod):
            if not _attr_name.startswith("_"):
                globals()[f"_step_{_step_module_name}_{_attr_name}"] = getattr(
                    _mod, _attr_name
                )


# ---------------------------------------------------------------------------
# Fixtures: Test environment (Strategy C — Real local)
# ---------------------------------------------------------------------------


@pytest.fixture
def claude_config_home(tmp_path, monkeypatch):
    """Real, isolated Claude config home rooted in tmp_path.

    Sets CLAUDE_CONFIG_DIR so that PathUtils.get_claude_config_dir() resolves
    to this directory. The backups subdirectory is created eagerly so that
    Given steps can drop in fixture backup directories.
    """
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    backups_dir = config_dir / "backups"
    backups_dir.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    return config_dir


@pytest.fixture
def nwave_config_home(tmp_path, monkeypatch):
    """Real, isolated ~/.nwave/ home rooted in tmp_path.

    Sets HOME so that Path.home() / '.nwave' / 'global-config.json' resolves
    inside the sandbox. The directory is NOT created eagerly — Given steps
    that write a config will create it; absence-of-config scenarios rely on
    it staying absent.
    """
    home_dir = tmp_path / "marco-home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir / ".nwave"


@pytest.fixture
def scenario_state():
    """Mutable state passed between Given/When/Then steps.

    Holds: the new backup just created (str name), the retention result
    object returned by apply_retention, captured exceptions, restore result,
    and the foreign directory name(s).
    """
    return {
        "new_backup_name": None,
        "retention_result": None,
        "raised_error": None,
        "restore_result": None,
        "restore_picked": None,
        "foreign_dirs": [],
    }
