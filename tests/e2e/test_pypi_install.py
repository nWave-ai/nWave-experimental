"""E2E tests for wheel install verification via testcontainers.

Migrates assertions from ``tests/e2e/Dockerfile.verify-install`` into a
pytest-discoverable testcontainers test class.

The Dockerfile.verify-install script tested the published PyPI package
(``nwave-ai``).  This testcontainers version uses the **local wheel** so that
CI can verify the code in the current repo — not just the last published release.

**Local-wheel vs PyPI-package mapping**

The published PyPI package is ``nwave-ai``.  The local wheel built from
``pyproject.toml`` is named ``nwave`` (the dev package name).  The table below
maps each Dockerfile assertion to its testcontainers equivalent:

| Dockerfile check | TestPyPIInstall equivalent |
|-----------------|---------------------------|
| ``pipx install nwave-ai`` succeeds | ``pipx install nwave-*.whl`` + ``package nwave`` in ``pipx list`` |
| Installed package version matches source | ``pipx list`` contains version from ``pyproject.toml`` |
| No stale global ``nwave`` package | No ``nwave`` package in the system interpreter |
| ``hook_definitions.py`` in wheel | Isolated pipx Python imports it and DES from its own venv |
| Source installer exits 0 | ``python -m nwave_ai.cli install`` via ``PYTHONPATH=/src`` exits 0 |

The development wheel ships ``nwave_ai``, ``des``, and ``scripts/shared``.
Import checks use its isolated pipx interpreter without the source checkout on
``sys.path``. The installer still uses the mounted source tree for framework
assets; the source-free distribution install is covered by the PyPI-shape suite.

Uses shared helpers from ``tests/e2e/conftest.py``.

Requires a Docker daemon.  Skips gracefully when docker is unavailable.

Step-Id: 01-01
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # Python 3.10 fallback

from tests.e2e.conftest import (
    _DOCKER_AVAILABLE,
    exec_in_container,
    managed_container,
    require_docker,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_CONTAINER_SRC = "/src"
_IMAGE = "python:3.12-slim"
_PIPX_HOME = "/opt/pipx"
_PIPX_PYTHON = f"{_PIPX_HOME}/venvs/nwave/bin/python"


def _expected_version() -> str:
    """Read the project version from pyproject.toml."""
    toml_path = _REPO_ROOT / "pyproject.toml"
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    return data["project"]["version"]


# ---------------------------------------------------------------------------
# Module-scoped container fixture — local wheel install
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pypi_install_container():
    """Start a container, install nwave from the local wheel via pipx, yield it.

    Build flow (mirrors Dockerfile.verify-install but uses local source):
    1. Build a wheel from ``/src`` (the mounted repo root) → ``/tmp/dist/nwave-*.whl``
    2. Install the wheel via pipx (matches end-user ``pipx install nwave-ai`` flow)
    3. Create a minimal ``~/.claude/settings.json`` for the installer preflight
    4. Run ``python -m nwave_ai.cli install`` with ``PYTHONPATH=/src`` (the dev CLI)
    """
    if not _DOCKER_AVAILABLE:
        pytest.skip("Docker daemon not available")

    from testcontainers.core.container import (  # type: ignore[import-untyped]
        DockerContainer,
    )

    container = DockerContainer(image=_IMAGE)
    container.with_volume_mapping(str(_REPO_ROOT), _CONTAINER_SRC, "ro")
    container.with_env("HOME", "/root")
    container.with_env("DEBIAN_FRONTEND", "noninteractive")
    container.with_env("PIPX_HOME", _PIPX_HOME)
    # Keep container alive while tests run
    container._command = "tail -f /dev/null"

    with managed_container(container) as container:
        # Bootstrap follows the same pattern as fresh_install_container in
        # test_fresh_install.py:
        #   1. Create a venv (satisfies installer "running in venv" preflight)
        #   2. Install runtime deps + the local wheel into the venv
        #   3. Install pipx for the pipx-level assertions (pipx list, pipx venv)
        #   4. Build a wheel and install it via pipx (mirrors end-user flow)
        #   5. Create minimal ~/.claude/settings.json
        #   6. Run the installer via the dev CLI with PYTHONPATH=/src
        bootstrap_script = (
            "set -e && "
            # 1. Venv (required by installer preflight)
            "python -m venv /opt/nwave-venv && "
            "source /opt/nwave-venv/bin/activate && "
            # 2. Runtime deps + local wheel
            "pip install --quiet "
            "rich typer pydantic 'pydantic-settings' httpx platformdirs "
            "pyyaml packaging jsonschema && "
            f"pip install --quiet --no-deps {_CONTAINER_SRC} && "
            # 3+4. pipx (system-level) + build wheel + pipx install
            # pipx must be installed at system level so it can isolate the venv
            "deactivate && "
            "pip install --quiet pipx build && "
            "pipx ensurepath && "
            f"python -m build --wheel {_CONTAINER_SRC} --outdir /tmp/dist && "
            "pipx install /tmp/dist/nwave-*.whl && "
            # 5. Minimal settings.json
            "mkdir -p /root/.claude && "
            'echo \'{"permissions": {}, "hooks": {}}\' > /root/.claude/settings.json && '
            # 6. Run the source installer inside the venv. The dev wheel ships
            # the CLI, but this fixture uses the checkout's framework assets;
            # the PyPI-shape suite owns the source-free distribution install.
            "source /opt/nwave-venv/bin/activate && "
            f"export PYTHONPATH={_CONTAINER_SRC} && "
            "echo y | python -m nwave_ai.cli install"
        )
        code, out = exec_in_container(container, ["bash", "-c", bootstrap_script])
        assert code == 0, f"Container bootstrap failed (exit {code}).\nOutput:\n{out}"

        yield container


# ---------------------------------------------------------------------------
# Assertions — all share the same running container
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@require_docker
class TestPyPIInstall:
    """Wheel installation, isolated imports, and source-install deployment.

    Extends the checks migrated from Dockerfile.verify-install.
    """

    def test_pipx_install_succeeds(self, pypi_install_container) -> None:
        """pipx install must succeed and register the ``nwave`` package.

        Mirrors Dockerfile.verify-install section [1/5]: the pipx package
        version check confirms the wheel installed without error.

        The local development wheel is named ``nwave``; the published
        distribution is ``nwave-ai`` and has a separate curated asset layout.
        """
        code, out = exec_in_container(
            pypi_install_container,
            ["bash", "-c", "pipx list 2>&1"],
        )
        assert code == 0, f"pipx list failed (exit {code}).\n{out}"
        assert "package nwave" in out, (
            "nwave package not found in pipx list output — install did not register.\n"
            f"pipx list output:\n{out}"
        )

    def test_version_consistency(self, pypi_install_container) -> None:
        """pipx list must report the version matching ``pyproject.toml``.

        Mirrors Dockerfile.verify-install sections [2/5] and [5/5]: CLI version
        matches the published pipx package version.

        For the local wheel the version is read directly from ``pyproject.toml``
        (the single source of truth) and compared with the pipx registration.
        """
        expected = _expected_version()
        code, out = exec_in_container(
            pypi_install_container,
            ["bash", "-c", "pipx list 2>&1"],
        )
        assert code == 0, f"pipx list failed (exit {code}).\n{out}"
        assert re.search(re.escape(expected), out), (
            f"Expected version {expected!r} not found in pipx list output.\n"
            f"Output:\n{out}"
        )

    def test_no_duplicate_nwave_package(self, pypi_install_container) -> None:
        """Only one ``nwave`` / ``nwave-ai`` distribution must be installed.

        Mirrors Dockerfile.verify-install section [3/5]: checks for stale
        package contamination.

        In the local-wheel scenario the ``nwave`` package installed by pipx IS
        the authoritative distribution.  This test verifies that no second copy
        is present outside the pipx venv (e.g. a system-wide ``nwave`` pip
        install that could shadow the pipx shims).

        ``pip list`` scoped to the pipx venv should show exactly one ``nwave``
        entry; a second entry in the global site-packages would indicate
        contamination.
        """
        # Check that the global pip environment does NOT have nwave installed
        # (it should only exist inside the pipx isolated venv)
        check_script = (
            'python3 -c "'
            "from importlib.metadata import packages_distributions; "
            "pkgs = packages_distributions(); "
            "nwave_pkgs = [k for k in pkgs if k.lower().startswith('nwave')]; "
            "print('global nwave packages:', nwave_pkgs); "
            "exit(0)"
            '"'
        )
        code, out = exec_in_container(
            pypi_install_container,
            ["bash", "-c", check_script],
        )
        assert code == 0, f"Package check failed (exit {code}).\n{out}"
        # The global Python should have no nwave* packages
        # (the pipx venv is isolated; packages_distributions() on the system
        #  interpreter should return empty for nwave)
        assert "global nwave packages: []" in out, (
            "Unexpected nwave* package found in global Python environment.\n"
            "Only the pipx-isolated venv should contain nwave.\n"
            f"Output:\n{out}"
        )

    def test_hook_definitions_importable_from_installed_wheel(
        self, pypi_install_container
    ) -> None:
        """The pipx wheel supplies hook definitions and their DES dependency.

        Isolated Python ignores PYTHONPATH and the working directory. An
        import from /src cannot stand in for a missing installed module.
        """
        check_script = (
            "import json; from pathlib import Path; "
            "import des; import scripts.shared.hook_definitions as hd; "
            "print(json.dumps({"
            "'hook_definitions': str(Path(hd.__file__).resolve()), "
            "'des': str(Path(des.__file__).resolve())"
            "}))"
        )
        code, out = exec_in_container(
            pypi_install_container,
            [_PIPX_PYTHON, "-I", "-c", check_script],
        )
        assert code == 0, (
            f"The installed wheel cannot import hook definitions and DES:\n{out}"
        )
        origins = json.loads(out)
        venv = Path(_PIPX_PYTHON).parent.parent
        for module, origin in origins.items():
            assert Path(origin).is_relative_to(venv), (
                f"{module} resolved outside the installed pipx environment: {origin}"
            )

    def test_state_delta_assert_state_delta_importable(
        self, pypi_install_container
    ) -> None:
        """The installed wheel exports assert_state_delta without source fallback."""
        check_script = (
            "from nwave_ai.state_delta import assert_state_delta; "
            "assert callable(assert_state_delta)"
        )
        code, out = exec_in_container(
            pypi_install_container,
            [_PIPX_PYTHON, "-I", "-c", check_script],
        )
        assert code == 0, (
            "The installed wheel cannot import nwave_ai.state_delta.assert_state_delta.\n"
            f"Output:\n{out}"
        )

    def test_state_delta_path_strategy_importable(self, pypi_install_container) -> None:
        """strategies subpackage must be importable even without hypothesis.

        Importing the installed strategies module must not require hypothesis
        (a dev-dependency); only calling path_strategy() would require it.
        """
        check_script = (
            "from importlib.util import find_spec; "
            "assert find_spec('hypothesis') is None; "
            "from nwave_ai.state_delta.strategies import path_strategy; "
            "assert callable(path_strategy)"
        )
        code, out = exec_in_container(
            pypi_install_container,
            [_PIPX_PYTHON, "-I", "-c", check_script],
        )
        assert code == 0, (
            "The installed wheel cannot import path_strategy without hypothesis.\n"
            f"Output:\n{out}"
        )

    def test_nwave_ai_install_succeeds(self, pypi_install_container) -> None:
        """``nwave-ai install`` (via dev CLI) must exit 0 and deploy assets.

        Mirrors Dockerfile.verify-install: the final end-user action after
        ``pipx install nwave-ai`` is running ``nwave-ai install``.

        This fixture invokes the source CLI with ``PYTHONPATH=/src`` so it can
        install the checkout's framework assets. The PyPI-shape suite covers
        invoking the wheel's entry point without the source tree.

        Assertion: at least one DES shim is present in ``~/.claude/bin/`` after
        the install, which confirms the installer ran to completion.
        """
        code, out = exec_in_container(
            pypi_install_container,
            ["test", "-d", "/root/.claude/bin"],
        )
        assert code == 0, (
            "~/.claude/bin/ not present after nwave-ai install — "
            "installer did not deploy shims.\n"
            "nwave-ai install output captured during fixture setup."
        )
        # At least one shim must be deployed
        code, out = exec_in_container(
            pypi_install_container,
            ["bash", "-c", "ls /root/.claude/bin/ | head -5"],
        )
        assert out.strip(), (
            "~/.claude/bin/ is empty after nwave-ai install — no shims deployed."
        )
