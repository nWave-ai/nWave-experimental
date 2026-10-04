"""E2E: nWave installation coexists with a pre-existing pre-commit tool setup.

Migrated from: tests/e2e/Dockerfile.env-with-precommit
Layer 4 of platform-testing-strategy.md

Contract: nWave install must NOT:
  - delete an existing pre-commit hook script in .git/hooks/
  - set global core.hooksPath (coexistence fix)
  - install duplicate pre-commit hook files

And MUST:
  - install usable skills under ~/.claude/skills/nw-*/ for detected Claude Code

This test would have caught the attribution hook incident (2026-03): nWave
was setting global core.hooksPath, which shadowed any local .git/hooks/
pre-commit managed by the pre-commit tool.

Requires a Docker daemon.  Skips gracefully when Docker is unavailable.

Step-Id: 01-02
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e.conftest import exec_in_container, managed_container, require_docker


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_IMAGE = "python:3.12-slim"
_CONTAINER_SRC = "/src"


# ---------------------------------------------------------------------------
# Session-scoped fixture: bootstrap once, run all assertions
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def precommit_coexistence_container():
    """Start a container with pre-commit already installed, then run nwave-ai install.

    Mirrors the Dockerfile.env-with-precommit build sequence:
    1. Install pre-commit 3.6.0 (the real tool)
    2. git init a project and run pre-commit install (writes .git/hooks/pre-commit)
    3. Install nwave-ai from local source and run nwave-ai install

    Scoped to module so all assertion tests share one container.
    """
    from tests.e2e.conftest import _is_docker_available

    if not _is_docker_available():
        pytest.skip("Docker daemon not available")

    from testcontainers.core.container import (
        DockerContainer,  # type: ignore[import-untyped]
    )

    container = DockerContainer(image=_IMAGE)
    container.with_volume_mapping(str(_REPO_ROOT), _CONTAINER_SRC, "ro")
    container.with_env("HOME", "/root")
    container.with_env("DEBIAN_FRONTEND", "noninteractive")
    container._command = "tail -f /dev/null"

    with managed_container(container) as container:
        # Install system deps + pre-commit (the real tool)
        setup_script = (
            "set -e && "
            "apt-get update -qq && "
            "apt-get install -y --no-install-recommends git -qq && "
            "rm -rf /var/lib/apt/lists/* && "
            "pip install --quiet pre-commit==3.6.0"
        )
        code, out = exec_in_container(container, ["bash", "-c", setup_script])
        assert code == 0, f"System setup failed (exit {code}).\nOutput:\n{out}"

        # Declare Claude Code and a project with a real local pre-commit hook.
        project_setup = (
            "set -e && "
            "mkdir -p /root/.claude && "
            "git init /root/project && "
            "cd /root/project && "
            "git config user.email 'dev@test.com' && "
            "git config user.name 'Dev' && "
            "printf 'repos:\\n  - repo: local\\n    hooks:\\n"
            "      - id: trailing-ws\\n        name: trailing whitespace\\n"
            '        entry: "true"\\n        language: system\\n'
            "        types: [text]\\n' > .pre-commit-config.yaml && "
            "pre-commit install && "
            "echo '# Test project' > README.md && "
            "git add -A && "
            "git commit -m 'init' --no-verify"
        )
        code, out = exec_in_container(container, ["bash", "-c", project_setup])
        assert code == 0, f"Project setup failed (exit {code}).\nOutput:\n{out}"

        # Install nwave-ai from local source, then run nwave-ai install
        install_script = (
            "set -e && "
            "python -m venv /opt/nwave-venv && "
            "source /opt/nwave-venv/bin/activate && "
            "pip install --quiet "
            "rich typer pydantic 'pydantic-settings' httpx platformdirs "
            "pyyaml packaging jsonschema && "
            f"pip install --quiet --no-deps {_CONTAINER_SRC} && "
            f"export PYTHONPATH={_CONTAINER_SRC} && "
            "cd /root/project && "
            "echo y | python -m nwave_ai.cli install"
        )
        code, out = exec_in_container(container, ["bash", "-c", install_script])
        assert code == 0, f"nWave install failed (exit {code}).\nOutput:\n{out}"

        yield container


# ---------------------------------------------------------------------------
# Assertion tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@require_docker
class TestPreCommitCoexistence:
    """nWave install must coexist with a pre-existing pre-commit setup.

    Migrated from Dockerfile.env-with-precommit (4 assertions).
    """

    def test_precommit_hook_preserved_after_nwave_install(
        self, precommit_coexistence_container
    ) -> None:
        """The pre-commit hook script in .git/hooks/ must not be deleted by nWave install.

        nWave must chain onto the existing hook, not replace it.  Deletion of
        .git/hooks/pre-commit is the #1 symptom of the coexistence bug.
        """
        code, _ = exec_in_container(
            precommit_coexistence_container,
            ["test", "-f", "/root/project/.git/hooks/pre-commit"],
        )
        assert code == 0, (
            "nWave install deleted /root/project/.git/hooks/pre-commit.\n"
            "nWave must chain onto the existing hook, not replace or delete it."
        )

    def test_nwave_did_not_set_global_core_hooks_path(
        self, precommit_coexistence_container
    ) -> None:
        """nWave install must NOT set global core.hooksPath.

        Setting global core.hooksPath shadows any local .git/hooks/ directory,
        which breaks projects that rely on local hook scripts (including those
        managed by the pre-commit tool).  This was the root cause of the
        attribution hook incident (2026-03).
        """
        _code, global_hp = exec_in_container(
            precommit_coexistence_container,
            [
                "bash",
                "-c",
                "git config --global --get core.hooksPath 2>/dev/null || echo ''",
            ],
        )
        # strip whitespace/newlines from output
        value = global_hp.strip()
        assert value == "", (
            f"nWave install set global core.hooksPath to {value!r}.\n"
            "Global hooksPath must remain unset to avoid shadowing local .git/hooks/."
        )

    def test_no_duplicate_precommit_hooks(
        self, precommit_coexistence_container
    ) -> None:
        """No more than 2 pre-commit hook files in .git/hooks/ (original + nWave chain).

        nWave may install its own pre-commit hook entry, but must not create
        additional duplicates (e.g. pre-commit.1, pre-commit~, pre-commit.bak).
        """
        _code, count_out = exec_in_container(
            precommit_coexistence_container,
            [
                "bash",
                "-c",
                "find /root/project/.git/hooks -name 'pre-commit*'"
                " -not -name '*.sample' 2>/dev/null | wc -l",
            ],
        )
        try:
            count = int(count_out.strip())
        except ValueError:
            count = 0
        assert count <= 2, (
            f"Found {count} pre-commit hook files in .git/hooks/ after nWave install "
            "(expected <= 2).  nWave must not create duplicate hook files."
        )

    def test_nwave_skills_installed(self, precommit_coexistence_container) -> None:
        """Coexistence preserves deployment of usable Claude Code skills."""
        check_script = (
            "import json; from pathlib import Path; "
            "root = Path('/root/.claude/skills'); "
            "print(json.dumps({"
            "skill.name: bool((skill / 'SKILL.md').read_text().strip()) "
            "for skill in root.glob('nw-*') if skill.is_dir()"
            "}))"
        )
        code, out = exec_in_container(
            precommit_coexistence_container,
            ["python3", "-c", check_script],
        )
        assert code == 0, f"Cannot read deployed Claude Code skills:\n{out}"
        skills = json.loads(out)
        assert len(skills) > 50, (
            f"Only {len(skills)} skills installed with pre-commit present (expected > 50)."
        )
        assert all(skills.values()), (
            "Every deployed skill must provide a non-empty SKILL.md with pre-commit present."
        )
