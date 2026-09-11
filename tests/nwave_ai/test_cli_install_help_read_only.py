"""Regression coverage for the read-only ``nwave-ai install --help`` surface."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _persistent_state(root: Path) -> dict[Path, bytes | None]:
    """Return every persistent path below one isolated HOME and file bytes."""
    return {
        path.relative_to(root): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def test_install_help_exits_cleanly_without_changing_conflicting_config(
    tmp_path: Path,
) -> None:
    """Help delegates to the installer help surface before any write preflight."""
    home = tmp_path / "persistent-home"
    config_dir = home / ".nwave"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        '{"attribution": {"enabled": true}}\n', encoding="utf-8"
    )
    (config_dir / "global-config.json").write_text(
        '{"attribution": {"enabled": false}}\n', encoding="utf-8"
    )
    project = tmp_path / "caller-project"
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    before_home = _persistent_state(home)
    before_project = _persistent_state(project)

    env = os.environ | {
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "PYTHONPATH": f"{REPO_ROOT / 'src'}:{REPO_ROOT}",
    }
    for install_args in (
        ["--help"],
        ["--yes", "--density-only", "--help"],
        ["--target", str(home), "-h"],
    ):
        result = subprocess.run(
            [sys.executable, "-m", "nwave_ai.cli", "install", *install_args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, result.stderr
        assert "USAGE:" in result.stdout
        assert result.stderr == ""
        assert _persistent_state(home) == before_home
        assert _persistent_state(project) == before_project
