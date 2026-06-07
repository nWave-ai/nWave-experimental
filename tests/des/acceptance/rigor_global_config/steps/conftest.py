"""
Shared fixtures for rigor global config acceptance tests.

Provides temporary filesystem fixtures that simulate project and global
configuration directories for testing the DESConfig cascade, rigor scope
persistence, and uninstall lifecycle.

All fixtures use pytest tmp_path for test isolation -- no real filesystem
state leaks between tests.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """
    Temporary project directory with .nwave/ config structure.

    Creates the .nwave/ directory and an empty des-config.json
    (the minimal project config that DESConfig expects).

    Returns:
        Path to the project root (parent of .nwave/)
    """
    project_root = tmp_path / "project"
    nwave_dir = project_root / ".nwave"
    nwave_dir.mkdir(parents=True)
    config_file = nwave_dir / "des-config.json"
    config_file.write_text(json.dumps({}), encoding="utf-8")
    return project_root


@pytest.fixture
def global_config_dir(tmp_path: Path) -> Path:
    """
    Temporary global configuration directory (~/.nwave/ equivalent).

    Creates the directory but does NOT create global-config.json --
    individual tests control whether the file exists and its contents.

    Returns:
        Path to the global config directory
    """
    global_dir = tmp_path / "home" / ".nwave"
    global_dir.mkdir(parents=True)
    return global_dir


@pytest.fixture
def project_config_path(project_dir: Path) -> Path:
    """Path to the project-level des-config.json."""
    return project_dir / ".nwave" / "des-config.json"


@pytest.fixture
def global_config_path(global_config_dir: Path) -> Path:
    """Path to the global-level global-config.json."""
    return global_config_dir / "global-config.json"
