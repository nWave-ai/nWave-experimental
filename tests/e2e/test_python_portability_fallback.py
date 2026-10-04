"""E2E: DES CLI portable-Python resolution works across environments.

Migrated from: tests/e2e/Dockerfile.verify-python-portability
Layer 4 of platform-testing-strategy.md

Validates the portable interpreter fallback against the installed DES dispatcher:

    $(command -v python3 || command -v python) ~/.claude/bin/des health-check --help

Simulates three operating-system setups inside a single Linux container
(the only controllable environment) and a fourth static-content scan:

  1. macOS-like      — only ``python3`` on PATH
  2. Windows-like    — only ``python`` on PATH
  3. Linux-standard  — both available
  4. Template scan   — no bare ``python/python3 -m des.cli`` in live task commands

Assertions count: 4 (one per scenario). Each alias scenario has its own PATH
directory and invokes the real installed runtime without modifying global
interpreter symlinks or replacing DES with a stub.

Requires a Docker daemon.  Skips gracefully when Docker is unavailable.

Step-Id: 01-03
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.conftest import exec_in_container, managed_container, require_docker


_REPO_ROOT = Path(__file__).parent.parent.parent
_IMAGE = "python:3.12-slim"


@pytest.fixture(scope="module")
def portability_container():
    """Install the Claude Code runtime before exercising isolated Python aliases."""
    from tests.e2e.conftest import _is_docker_available

    if not _is_docker_available():
        pytest.skip("Docker daemon not available")

    from testcontainers.core.container import (
        DockerContainer,  # type: ignore[import-untyped]
    )

    container = DockerContainer(image=_IMAGE)
    container.with_volume_mapping(str(_REPO_ROOT), "/src", "ro")
    container.with_env("HOME", "/root")
    container.with_env("DEBIAN_FRONTEND", "noninteractive")
    container._command = "tail -f /dev/null"

    with managed_container(container) as container:
        setup = (
            "set -e && "
            "python -m venv /opt/nwave-venv && "
            "/opt/nwave-venv/bin/pip install --quiet "
            "rich typer pydantic pydantic-settings httpx platformdirs pyyaml packaging && "
            "/opt/nwave-venv/bin/pip install --quiet --no-deps /src && "
            "PYTHONPATH=/src /opt/nwave-venv/bin/python -m nwave_ai.cli "
            "install --platform claude-code --yes && "
            "mkdir -p /workspace/python3-only /workspace/python-only /workspace/both && "
            "ln -s /opt/nwave-venv/bin/python /workspace/python3-only/python3 && "
            "ln -s /opt/nwave-venv/bin/python /workspace/python-only/python && "
            "ln -s /opt/nwave-venv/bin/python /workspace/both/python3 && "
            "ln -s /opt/nwave-venv/bin/python /workspace/both/python"
        )
        code, out = exec_in_container(container, ["bash", "-c", setup])
        assert code == 0, f"Runtime installation failed (exit {code}).\n{out}"
        yield container


def _assert_portable_dispatch(container, path: str, expected_alias: str) -> None:
    """Resolve only the scenario's aliases and execute the installed dispatcher."""
    script = (
        f"export PATH={path} && "
        "resolved=$(command -v python3 || command -v python) && "
        'printf "RESOLVED=%s\\n" "$resolved" && '
        '"$resolved" /root/.claude/bin/des health-check --help'
    )
    code, out = exec_in_container(container, ["/bin/bash", "-c", script])
    assert code == 0, f"Installed DES invocation failed (exit {code}).\n{out}"
    assert f"RESOLVED={path}/{expected_alias}\n" in out, (
        f"Expected {expected_alias} in isolated PATH {path}.\n{out}"
    )
    assert "usage:" in out and "--json" in out, (
        f"Installed health-check did not produce its public help.\n{out}"
    )


@pytest.mark.e2e
@require_docker
class TestPythonPortabilityFallback:
    """Portable Python resolution: macOS/Windows-like/Linux + template scan.

    Migrated from Dockerfile.verify-python-portability (4 scenarios).
    """

    def test_macos_homebrew_python3_only(self, portability_container) -> None:
        """macOS Homebrew: only ``python3`` exists; ``command -v python3`` wins."""
        _assert_portable_dispatch(
            portability_container, "/workspace/python3-only", "python3"
        )

    def test_windows_like_python_only(self, portability_container) -> None:
        """Windows-like: only ``python`` exists; ``command -v python`` is the fallback."""
        _assert_portable_dispatch(
            portability_container, "/workspace/python-only", "python"
        )

    def test_linux_standard_both_available(self, portability_container) -> None:
        """Linux: python3 AND python available; command -v python3 wins first."""
        _assert_portable_dispatch(portability_container, "/workspace/both", "python3")

    def test_templates_use_portable_pattern(self, portability_container) -> None:
        """Every live task template must use a portable interpreter or DES shim."""
        script = r"""
from pathlib import Path
import re

templates = sorted(Path("/src/nWave/tasks/nw").glob("*.md"))
assert templates, "No live task templates were scanned"
bare_python = re.compile(
    r"(?<!\$\(command -v )(?<!\|\| command -v )\bpython3?\s+-m\s+des\.cli\b"
)
violations = [
    f"{template}:{number}:{line}"
    for template in templates
    for number, line in enumerate(template.read_text().splitlines(), 1)
    if bare_python.search(line)
]
assert not violations, "\n".join(violations)
"""
        code, out = exec_in_container(portability_container, ["python3", "-c", script])
        assert code == 0, f"Task-template portability scan failed.\n{out}"
