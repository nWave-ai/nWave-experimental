"""BDD fixtures for the saturated scheduler acceptance slice."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.e2e.conftest import pypi_shape_wheel  # noqa: F401

from .steps.composition import SaturatedSchedulerComposition
from .steps.installed_candidate import InstalledCandidateComposition


@pytest.fixture
def composition(tmp_path: Path) -> SaturatedSchedulerComposition:
    """A real, isolated feature-plan/evidence workspace for the CLI driving port."""
    return SaturatedSchedulerComposition(tmp_path)


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


@pytest.fixture(scope="session")
def installed_public_candidate(
    pypi_shape_wheel: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Install the exact release-shaped candidate once into a clean environment."""
    venv = tmp_path_factory.mktemp("installed_public_scheduler")
    create = subprocess.run(
        ["uv", "venv", str(venv)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert create.returncode == 0, (
        f"candidate environment creation failed: {create.stderr}"
    )
    python = venv / (
        "Scripts/python.exe" if __import__("os").name == "nt" else "bin/python"
    )
    install = subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(pypi_shape_wheel)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert install.returncode == 0, f"candidate installation failed: {install.stderr}"
    return venv


@pytest.fixture
def installed_composition(
    tmp_path: Path, installed_public_candidate: Path
) -> InstalledCandidateComposition:
    return InstalledCandidateComposition(tmp_path, installed_public_candidate)
