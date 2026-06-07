"""Unit tests for nwave_attribution_hook.py (prepare-commit-msg hook).

Tests validate trailer injection through the hook's main() driving port
and assert at the commit message file boundary.

Test Budget: 8 behaviors x 2 = 16 max. Using 8 tests (1 per behavior).

Behaviors tested:
1. Trailer appended when attribution enabled
2. No trailer when attribution disabled
3. No trailer when config missing (graceful exit)
4. No duplication on amend (trailer already present)
5. Corrupt config exits cleanly
6. Project override disables global enabled
7. Custom trailer value from config
8. Merge commit handled (trailer added)
"""

import json
from pathlib import Path

import pytest

from scripts.hooks.nwave_attribution_hook import process_commit_message


# Serialize tests touching .git/hooks/ to avoid xdist races on shared state.
pytestmark = pytest.mark.xdist_group("git_hooks")


def _write_global_config(
    config_dir: Path,
    *,
    enabled: bool = True,
    trailer: str = "Co-Authored-By: nWave <nwave@nwave.ai>",
) -> None:
    """Write a global-config.json with attribution settings."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "global-config.json"
    config_file.write_text(
        json.dumps({"attribution": {"enabled": enabled, "trailer": trailer}}),
        encoding="utf-8",
    )


def _write_project_config(
    project_dir: Path,
    *,
    enabled: bool,
) -> None:
    """Write a .nwave/des-config.json with attribution override."""
    nwave_dir = project_dir / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    config_file = nwave_dir / "des-config.json"
    config_file.write_text(
        json.dumps({"attribution": {"enabled": enabled}}),
        encoding="utf-8",
    )


class TestAttributionHook:
    """Tests for hook trailer injection via process_commit_message()."""

    def test_trailer_appended_when_enabled(self, tmp_path: Path) -> None:
        """Config enabled -> trailer appended after blank line."""
        global_dir = tmp_path / ".nwave"
        _write_global_config(global_dir)

        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat(api): add rate limiting", encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        content = msg_file.read_text(encoding="utf-8")
        assert "feat(api): add rate limiting" in content
        assert "\n\nCo-Authored-By: nWave <nwave@nwave.ai>" in content

    def test_no_trailer_when_disabled(self, tmp_path: Path) -> None:
        """Config disabled -> no change to commit message."""
        global_dir = tmp_path / ".nwave"
        _write_global_config(global_dir, enabled=False)

        msg_file = tmp_path / "COMMIT_EDITMSG"
        original = "feat(ui): add dark mode"
        msg_file.write_text(original, encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        assert msg_file.read_text(encoding="utf-8") == original

    def test_no_trailer_when_config_missing(self, tmp_path: Path) -> None:
        """No config file -> no trailer, exit 0."""
        global_dir = tmp_path / ".nwave-missing"

        msg_file = tmp_path / "COMMIT_EDITMSG"
        original = "chore: cleanup"
        msg_file.write_text(original, encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        assert msg_file.read_text(encoding="utf-8") == original

    def test_no_duplication_on_amend(self, tmp_path: Path) -> None:
        """Trailer already present -> no second copy added."""
        global_dir = tmp_path / ".nwave"
        _write_global_config(global_dir)

        msg_file = tmp_path / "COMMIT_EDITMSG"
        already_has = (
            "feat(api): add rate limiting\n\nCo-Authored-By: nWave <nwave@nwave.ai>"
        )
        msg_file.write_text(already_has, encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        content = msg_file.read_text(encoding="utf-8")
        assert content.count("Co-Authored-By: nWave") == 1

    def test_corrupt_config_exits_cleanly(self, tmp_path: Path) -> None:
        """Bad JSON in config -> no trailer, exit 0."""
        global_dir = tmp_path / ".nwave"
        global_dir.mkdir(parents=True)
        config_file = global_dir / "global-config.json"
        config_file.write_text("{invalid json!!!", encoding="utf-8")

        msg_file = tmp_path / "COMMIT_EDITMSG"
        original = "fix: something"
        msg_file.write_text(original, encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        assert msg_file.read_text(encoding="utf-8") == original

    def test_project_override_disables(self, tmp_path: Path) -> None:
        """Global enabled + project disabled -> no trailer."""
        global_dir = tmp_path / ".nwave"
        _write_global_config(global_dir, enabled=True)

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        _write_project_config(project_dir, enabled=False)

        msg_file = project_dir / "COMMIT_EDITMSG"
        original = "feat: project commit"
        msg_file.write_text(original, encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
            project_config_dir=project_dir / ".nwave",
        )

        assert result == 0
        assert msg_file.read_text(encoding="utf-8") == original

    def test_custom_trailer_from_config(self, tmp_path: Path) -> None:
        """Custom trailer value from config used instead of default."""
        global_dir = tmp_path / ".nwave"
        custom = "Co-Authored-By: MyOrg <dev@myorg.com>"
        _write_global_config(global_dir, trailer=custom)

        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: custom trailer", encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            global_config_dir=global_dir,
        )

        assert result == 0
        content = msg_file.read_text(encoding="utf-8")
        assert custom in content
        assert "nWave <nwave@nwave.ai>" not in content

    def test_merge_commit_handled(self, tmp_path: Path) -> None:
        """Merge commit source -> trailer still added."""
        global_dir = tmp_path / ".nwave"
        _write_global_config(global_dir)

        msg_file = tmp_path / "MERGE_MSG"
        msg_file.write_text("Merge branch 'feature' into main", encoding="utf-8")

        result = process_commit_message(
            commit_msg_path=str(msg_file),
            merge_source="merge",
            global_config_dir=global_dir,
        )

        assert result == 0
        content = msg_file.read_text(encoding="utf-8")
        assert "Co-Authored-By: nWave <nwave@nwave.ai>" in content


@pytest.mark.parametrize(
    "operation_type",
    ["commit", "amend", "merge", "squash"],
    ids=["commit", "amend", "merge", "squash"],
)
def test_no_duplication_across_operations(tmp_path: Path, operation_type: str) -> None:
    """Credit line never duplicated regardless of operation type."""
    global_dir = tmp_path / ".nwave"
    _write_global_config(global_dir)

    msg_file = tmp_path / "COMMIT_EDITMSG"
    trailer = "Co-Authored-By: nWave <nwave@nwave.ai>"
    msg_file.write_text(f"feat: {operation_type}\n\n{trailer}", encoding="utf-8")

    merge_source = operation_type if operation_type != "commit" else None

    result = process_commit_message(
        commit_msg_path=str(msg_file),
        merge_source=merge_source,
        global_config_dir=global_dir,
    )

    assert result == 0
    content = msg_file.read_text(encoding="utf-8")
    assert content.count("Co-Authored-By: nWave") == 1
