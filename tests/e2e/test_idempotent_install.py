"""E2E: nWave installation is idempotent (second install produces no meaningful changes).

Migrated from: tests/e2e/Dockerfile.env-idempotent
Layer 4 of platform-testing-strategy.md

Contract: running nwave-ai install TWICE must:
  - succeed both times (exit 0)
  - produce identical content snapshots (files + hashes + hook counts)
  - result in zero duplicate hook commands in settings.json
  - result in zero duplicate skill directories

Note: TestFreshInstallIdempotent in test_fresh_install.py covers the basic
second-install-exits-zero and no-duplicate-shims contract.  This class covers
the SNAPSHOT-level idempotence: content hash comparison across installs, which
is a distinct and complementary assertion.

Requires a Docker daemon.  Skips gracefully when Docker is unavailable.

Step-Id: 01-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.conftest import exec_in_container, managed_container, require_docker


_REPO_ROOT = Path(__file__).parent.parent.parent
_IMAGE = "python:3.12-slim"
_CONTAINER_SRC = "/src"

# Snapshot script: captures file list + content hashes + hook counts.
# Mirrors the snapshot() shell function in Dockerfile.env-idempotent.
_SNAPSHOT_SCRIPT = """
import hashlib, json, pathlib, sys

home = pathlib.Path("/root")
claude = home / ".claude"
lines = []

# File listing (sorted)
lines.append("=== FILES ===")
for root_dir in [claude / "skills", claude / "agents", home / ".nwave"]:
    if root_dir.exists():
        for p in sorted(root_dir.rglob("*")):
            if p.is_file():
                lines.append(str(p))

# Content hashes of skill files
lines.append("=== CONTENT HASHES ===")
skills = claude / "skills"
if skills.exists():
    for p in sorted(skills.rglob("SKILL.md")):
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  {p}")

settings = claude / "settings.json"
if settings.exists():
    digest = hashlib.md5(settings.read_bytes()).hexdigest()
    lines.append(f"{digest}  {settings}")

# Hook counts
lines.append("=== HOOK COUNT ===")
if settings.exists():
    d = json.loads(settings.read_text())
    for event, entries in sorted(d.get("hooks", {}).items()):
        count = len(entries) if isinstance(entries, list) else 1
        lines.append(f"{event}: {count}")

print("\\n".join(lines))
"""

_INSTALL_SCRIPT = (
    f"export PYTHONPATH={_CONTAINER_SRC} && "
    "echo y | /opt/nwave-venv/bin/python -m nwave_ai.cli install --platform claude-code 2>&1"
)


@pytest.fixture(scope="module")
def idempotent_install_container():
    """Container that runs nwave-ai install twice and captures both snapshots.

    Yields the container plus (snapshot1_lines, snapshot2_lines) for comparison.
    Mirrors Dockerfile.env-idempotent build + test sequence.
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
        # Bootstrap venv + first install
        bootstrap_script = (
            "set -e && "
            "apt-get update -qq && "
            "apt-get install -y --no-install-recommends git -qq && "
            "rm -rf /var/lib/apt/lists/* && "
            "python -m venv /opt/nwave-venv && "
            "source /opt/nwave-venv/bin/activate && "
            "pip install --quiet "
            "rich typer pydantic 'pydantic-settings' httpx platformdirs pyyaml packaging && "
            f"pip install --quiet --no-deps {_CONTAINER_SRC} && "
            f"export PYTHONPATH={_CONTAINER_SRC} && "
            "echo y | python -m nwave_ai.cli install --platform claude-code"
        )
        code, out = exec_in_container(container, ["bash", "-c", bootstrap_script])
        assert code == 0, f"First install failed (exit {code}).\nOutput:\n{out}"

        # Capture snapshot after first install
        code, snap1 = exec_in_container(container, ["python3", "-c", _SNAPSHOT_SCRIPT])
        assert code == 0, f"Snapshot 1 failed (exit {code}).\nOutput:\n{snap1}"

        # Second install
        second_code, second_output = exec_in_container(
            container, ["bash", "-c", _INSTALL_SCRIPT]
        )

        # Capture snapshot after second install
        code, snap2 = exec_in_container(container, ["python3", "-c", _SNAPSHOT_SCRIPT])
        assert code == 0, f"Snapshot 2 failed (exit {code}).\nOutput:\n{snap2}"

        yield container, snap1, snap2, second_code, second_output


@pytest.mark.e2e
@require_docker
class TestIdempotentInstall:
    """Second nwave-ai install must produce no meaningful changes to installed artifacts.

    Migrated from Dockerfile.env-idempotent (5 assertions).
    Complements TestFreshInstallIdempotent (which covers shim-level idempotence).
    """

    def test_both_installs_succeed(self, idempotent_install_container) -> None:
        """The two observed installs, not an unrelated third run, must exit 0."""
        _, _, _, second_code, second_output = idempotent_install_container
        assert second_code == 0, (
            f"Second nwave-ai install exited {second_code}.\nOutput:\n{second_output}"
        )

    def test_content_snapshots_identical(self, idempotent_install_container) -> None:
        """Content hashes of skill files must be identical after two install runs.

        A non-idempotent installer may regenerate files with different content
        (e.g. timestamps embedded in files, rewritten hooks with different UUIDs).
        """
        _, snap1, snap2, _, _ = idempotent_install_container

        snap1_hash_lines = [
            l
            for l in snap1.splitlines()  # noqa: E741
            if l.startswith("=== CONTENT") or ("SKILL.md" in l or "settings.json" in l)
        ]
        snap2_hash_lines = [
            l
            for l in snap2.splitlines()  # noqa: E741
            if l.startswith("=== CONTENT") or ("SKILL.md" in l or "settings.json" in l)
        ]

        # Extract just hash lines (lines starting with hex digest)
        def hash_lines(lines: list[str]) -> list[str]:
            return [l for l in lines if l[:2].isalnum() and "  " in l]  # noqa: E741

        h1 = hash_lines(snap1_hash_lines)
        h2 = hash_lines(snap2_hash_lines)

        diff = set(h1) ^ set(h2)
        assert not diff, (
            "Content hashes differ between first and second install runs — "
            "installer is not content-idempotent.\n"
            "Changed entries:\n" + "\n".join(f"  {d}" for d in sorted(diff))
        )

    def test_no_duplicate_hook_commands_in_settings(
        self, idempotent_install_container
    ) -> None:
        """settings.json must not repeat a command for the same event and matcher.

        Different tools may intentionally dispatch the same hook action. Repeated
        registrations for one matcher, not commands shared by distinct matchers,
        indicate that reinstall appended rather than deduplicated hooks.
        """
        container, _, _, _, _ = idempotent_install_container

        dedup_script = """
import json, pathlib

settings = json.loads(pathlib.Path('/root/.claude/settings.json').read_text())
assert settings.get('hooks'), "Installed hook registrations are missing"
duplicates = 0
for event, entries in settings['hooks'].items():
    assert isinstance(entries, list), f"Invalid hook entries for {event}"
    registrations = []
    for entry in entries:
        matcher = entry.get('matcher', '')
        hooks = entry.get('hooks', [entry])
        for hook in hooks:
            if hook.get('command'):
                registrations.append((matcher, hook['command']))
    duplicates += len(registrations) - len(set(registrations))
print(duplicates)
"""
        code, count_out = exec_in_container(container, ["python3", "-c", dedup_script])
        assert code == 0, f"Cannot inspect installed hook registrations.\n{count_out}"
        duplicates = int(count_out.strip())
        assert duplicates == 0, (
            f"Found {duplicates} duplicate event/matcher hook registration(s) after "
            "two install runs. Installer must deduplicate hook registrations."
        )

    def test_no_duplicate_skill_directories(self, idempotent_install_container) -> None:
        """Skill directory names must be unique after two install runs.

        Detects backup copies (nw-tdd-methodology, nw-tdd-methodology.bak) created
        by a non-idempotent installer.
        """
        container, _, _, _, _ = idempotent_install_container

        _code, listing = exec_in_container(
            container,
            [
                "bash",
                "-c",
                "ls -d /root/.claude/skills/nw-* 2>/dev/null | sort",
            ],
        )
        dirs = [l.strip() for l in listing.splitlines() if l.strip()]  # noqa: E741
        unique_dirs = sorted(set(dirs))
        assert len(dirs) == len(unique_dirs), (
            f"Duplicate skill directory names found after two install runs "
            f"({len(dirs)} total, {len(unique_dirs)} unique).\n"
            "Non-unique entries: " + str([d for d in dirs if dirs.count(d) > 1])
        )

    def test_file_listing_stable_between_installs(
        self, idempotent_install_container
    ) -> None:
        """The set of installed files must be the same after both install runs.

        New files appearing after the second install (e.g. .bak, .orig, copies)
        indicate the installer is not cleaning up temporary artifacts.
        """
        _, snap1, snap2, _, _ = idempotent_install_container

        def file_lines(snap: str) -> set[str]:
            in_files = False
            result = set()
            for line in snap.splitlines():
                if line.startswith("=== FILES ==="):
                    in_files = True
                    continue
                if line.startswith("==="):
                    in_files = False
                if in_files and line.strip():
                    result.add(line.strip())
            return result

        files1 = file_lines(snap1)
        files2 = file_lines(snap2)

        new_files = files2 - files1
        removed_files = files1 - files2

        problems: list[str] = []
        if new_files:
            problems.append(
                "New files after second install:\n"
                + "\n".join(f"  + {f}" for f in sorted(new_files))
            )
        if removed_files:
            problems.append(
                "Files removed by second install:\n"
                + "\n".join(f"  - {f}" for f in sorted(removed_files))
            )

        assert not problems, (
            "Installed file set changed between first and second install runs.\n"
            + "\n".join(problems)
        )
