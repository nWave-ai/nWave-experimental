"""E2E: nWave attribution hook fires during a real git commit (CRITICAL behavioral test).

Migrated from: tests/e2e/Dockerfile.env-behavioral-smoke
Layer 4 of platform-testing-strategy.md

THE CRITICAL TEST. Validates that nWave's attribution hook actually executes
during a real ``git commit`` in an environment where pre-commit is also installed.

This test would have caught the attribution hook bug (2026-03): the hook was
installed in ~/.nwave/hooks/ but pre-commit's local core.hooksPath shadowed
the global hooksPath, so git never executed nWave's hook.

Contract:
  1. pre-commit hook script exists in .git/hooks/ before nWave install
  2. git commit succeeds after nWave install
  3. commit message contains nWave attribution trailer (Co-Authored-By / nwave)
  4. commit with real file also succeeds (pre-commit + nWave coexistence)
  5. pre-commit hooks actually execute (not silently skipped by hooksPath override)

Requires a Docker daemon.  Skips gracefully when Docker is unavailable.

Step-Id: 01-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.conftest import exec_in_container, managed_container, require_docker


pytestmark = pytest.mark.e2e_smoke

_REPO_ROOT = Path(__file__).parent.parent.parent
_IMAGE = "python:3.12-slim"
_CONTAINER_SRC = "/src"


@pytest.fixture(scope="module")
def behavioral_smoke_container():
    """Container with pre-commit + nwave installed, configured for attribution.

    Mirrors Dockerfile.env-behavioral-smoke build sequence:
    1. Install pre-commit 3.6.0
    2. Create project with pre-commit installed (sets local core.hooksPath)
    3. Enable attribution and activate the disposable project in unified config
    4. Install nwave-ai from local source and run nwave-ai install
    5. Make a real git commit to verify attribution hook fires
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
        # System deps + pre-commit
        setup_script = (
            "set -e && "
            "sed -i 's@http://deb.debian.org@https://deb.debian.org@g' "
            "/etc/apt/sources.list.d/debian.sources && "
            "apt-get update -qq && "
            "apt-get install -y --no-install-recommends git -qq && "
            "rm -rf /var/lib/apt/lists/* && "
            "pip install --quiet pre-commit==3.6.0"
        )
        code, out = exec_in_container(container, ["bash", "-c", setup_script])
        assert code == 0, f"System setup failed (exit {code}).\nOutput:\n{out}"

        # Create project with pre-commit installed (installs hook, may set core.hooksPath)
        project_setup = (
            "set -e && "
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
            "git commit -m 'test: initialize attribution fixture'"
        )
        code, out = exec_in_container(container, ["bash", "-c", project_setup])
        assert code == 0, f"Project setup failed (exit {code}).\nOutput:\n{out}"

        # Configure attribution before install (mirrors Dockerfile ENV setup)
        # Use a simpler write to avoid shell quoting complexity
        write_config = """python3 -c "
import json, pathlib
pathlib.Path('/root/.nwave').mkdir(exist_ok=True)
pathlib.Path('/root/.nwave/config.json').write_text(
    json.dumps({'attribution': {'enabled': True, 'trailer': 'Co-Authored-By: nWave <nwave@nwave.ai>'}})
)
pathlib.Path('/root/project/.nwave').mkdir(exist_ok=True)
pathlib.Path('/root/project/.nwave/config.json').write_text(
    json.dumps({'enabled': True})
)
print('config written')
" """
        code, out = exec_in_container(container, ["bash", "-c", write_config])
        assert code == 0, (
            f"Attribution config write failed (exit {code}).\nOutput:\n{out}"
        )

        # Bootstrap minimal Claude settings
        settings_setup = (
            "mkdir -p /root/.claude && "
            'printf \'{"permissions": {}, "hooks": {}}\' > /root/.claude/settings.json'
        )
        code, out = exec_in_container(container, ["bash", "-c", settings_setup])
        assert code == 0, f"Settings setup failed (exit {code}).\nOutput:\n{out}"

        # Install nwave-ai from local source
        install_script = (
            "set -e && "
            "python -m venv /opt/nwave-venv && "
            "source /opt/nwave-venv/bin/activate && "
            "pip install --quiet "
            "rich typer pydantic 'pydantic-settings' httpx platformdirs pyyaml packaging jsonschema && "
            f"pip install --quiet --no-deps {_CONTAINER_SRC} && "
            f"export PYTHONPATH={_CONTAINER_SRC} && "
            "cd /root/project && "
            "python -m nwave_ai.cli install --platform claude-code --yes"
        )
        code, out = exec_in_container(container, ["bash", "-c", install_script])
        assert code == 0, f"nWave installation failed (exit {code}).\n{out}"

        yield container


@pytest.mark.e2e
@require_docker
class TestBehavioralSmoke:
    """Attribution hook must fire during a real git commit with pre-commit installed.

    Migrated from Dockerfile.env-behavioral-smoke (5 assertions).
    This is the CRITICAL test that catches the attribution hook / hooksPath bug.
    """

    def test_precommit_hook_exists_before_nwave_install(
        self, behavioral_smoke_container
    ) -> None:
        """The pre-commit hook script must exist in .git/hooks/ (pre-state verification).

        Confirms the test environment is set up correctly: pre-commit has
        installed its hook, establishing the hooksPath context that nWave
        must coexist with.
        """
        code, _ = exec_in_container(
            behavioral_smoke_container,
            ["test", "-f", "/root/project/.git/hooks/pre-commit"],
        )
        assert code == 0, (
            "Pre-state check failed: /root/project/.git/hooks/pre-commit not found.\n"
            "Test environment is not set up correctly — pre-commit must have installed "
            "its hook before nWave install runs."
        )

    def test_git_commit_succeeds_after_nwave_install(
        self, behavioral_smoke_container
    ) -> None:
        """A real git commit must succeed after nWave install.

        Uses --allow-empty to avoid needing real file changes.  A non-zero exit
        means nWave's hook installation broke the git commit workflow.
        """
        commit_script = (
            "cd /root/project && "
            "git commit --allow-empty -m 'test: behavioral smoke commit' 2>&1; "
            "echo EXIT:$?"
        )
        _code, out = exec_in_container(
            behavioral_smoke_container, ["bash", "-c", commit_script]
        )
        exit_line = next(
            (l for l in out.splitlines() if l.startswith("EXIT:")),  # noqa: E741
            "EXIT:1",
        )
        exit_code = exit_line.split(":")[1].strip()
        assert exit_code == "0", (
            f"git commit failed (exit {exit_code}) after nWave install.\n"
            "nWave's hook installation must not break the git commit workflow.\n"
            f"Output:\n{out}"
        )

    def test_commit_message_contains_nwave_attribution(
        self, behavioral_smoke_container
    ) -> None:
        """The installed host hook must attribute a real commit with pre-commit active."""
        script = r"""
import json
from pathlib import Path
import re
import subprocess

repo = "/root/project"
settings = json.loads(Path("/root/.claude/settings.json").read_text())
commands = [
    hook["command"]
    for entry in settings["hooks"]["PreToolUse"]
    if re.search(entry.get("matcher", ""), "Bash")
    for hook in entry.get("hooks", [])
    if "claude_code_hook_adapter" in hook.get("command", "")
]
assert len(commands) == 1, commands
original = "git commit --allow-empty -m 'test: attribution check'"
payload = {
    "tool_name": "Bash",
    "agent_id": "e2e-precommit-coexistence",
    "cwd": repo,
    "tool_input": {"command": original},
}
hook = subprocess.run(
    commands[0], shell=True, input=json.dumps(payload), text=True,
    capture_output=True, cwd=repo, timeout=60,
)
assert hook.returncode == 0, (hook.stdout, hook.stderr)
response = json.loads(hook.stdout)
rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]
assert rewritten != original, response
commit = subprocess.run(
    ["bash", "-c", rewritten], cwd=repo, text=True,
    capture_output=True, timeout=60,
)
assert commit.returncode == 0, (commit.stdout, commit.stderr)
message = subprocess.check_output(
    ["git", "log", "-1", "--format=%B"], cwd=repo, text=True,
)
assert "Co-Authored-By: nWave <nwave@nwave.ai>" in message, message
print(message)
"""
        code, out = exec_in_container(
            behavioral_smoke_container, ["/opt/nwave-venv/bin/python", "-c", script]
        )
        assert code == 0, f"Installed attribution hook failed.\n{out}"

    def test_commit_with_real_file_succeeds(self, behavioral_smoke_container) -> None:
        """A commit adding a real file must succeed (pre-commit + nWave coexistence).

        Exercises the full hook chain: pre-commit runs its hooks, then nWave
        adds the attribution trailer.  A failure here indicates hook chaining
        is broken.
        """
        commit_script = (
            "cd /root/project && "
            "echo 'smoke test content' > smoke-file.txt && "
            "git add smoke-file.txt && "
            "git commit -m 'test: pre-commit coexistence' 2>&1; "
            "echo EXIT:$?"
        )
        _code, out = exec_in_container(
            behavioral_smoke_container, ["bash", "-c", commit_script]
        )
        exit_line = next(
            (l for l in out.splitlines() if l.startswith("EXIT:")),  # noqa: E741
            "EXIT:1",
        )
        exit_code = exit_line.split(":")[1].strip()
        assert exit_code == "0", (
            f"Real-file commit failed (exit {exit_code}) — hook chain is broken.\n"
            f"Output:\n{out}"
        )

    def test_precommit_hooks_actually_executed(
        self, behavioral_smoke_container
    ) -> None:
        """pre-commit hooks must actually run (not be silently skipped).

        If nWave's install overrides core.hooksPath globally, pre-commit's
        hooks directory is bypassed and the pre-commit tool's hooks never
        execute.  The commit output must contain evidence of hook execution
        (hook name or Passed/Failed status line).
        """
        commit_script = (
            "cd /root/project && "
            "echo 'coexistence check' > coexistence-check.txt && "
            "git add coexistence-check.txt && "
            "git commit -m 'test: verify pre-commit ran' 2>&1"
        )
        code, out = exec_in_container(
            behavioral_smoke_container, ["bash", "-c", commit_script]
        )
        hook_ran = any(
            kw in out.lower()
            for kw in ("trailing whitespace", "passed", "failed", "running hooks")
        )
        assert code == 0, f"Commit failed (exit {code}).\n{out}"
        assert hook_ran, f"pre-commit hook did not execute.\n{out}"
