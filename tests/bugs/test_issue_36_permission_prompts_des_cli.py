"""Regression properties for permission-free public DES invocation."""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BANNED_PATTERNS = (
    re.compile(r"PYTHONPATH=\$HOME/\.claude/lib/python.*-m\s+des\.cli\.", re.DOTALL),
    re.compile(r"PYTHONPATH=~/\.claude/lib/python.*-m\s+des\.cli\.", re.DOTALL),
)


def _public_instruction_files() -> list[Path]:
    return sorted((_REPO_ROOT / "nWave" / "skills").glob("nw-*/SKILL.md")) + sorted(
        (_REPO_ROOT / "nWave" / "tasks" / "nw").glob("*.md")
    )


def test_no_pythonpath_pattern_in_public_skills_and_tasks() -> None:
    """Every current public instruction uses the installed ``des`` entry point."""
    violations = []
    for path in _public_instruction_files():
        content = path.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in _BANNED_PATTERNS):
            violations.append(str(path.relative_to(_REPO_ROOT)))

    assert violations == []


@pytest.mark.parametrize(
    "invocation",
    [
        "PYTHONPATH=$HOME/.claude/lib/python python3 -m des.cli.log_phase",
        "PYTHONPATH=~/.claude/lib/python python3 -m des.cli.log_phase",
    ],
)
def test_banned_pattern_detection_is_sensitive(invocation: str) -> None:
    assert any(pattern.search(invocation) for pattern in _BANNED_PATTERNS)


def test_consolidated_des_shim_is_resolvable_on_a_staged_path(tmp_path: Path) -> None:
    """PATH resolution is proven without reading the user's installed profile."""
    fake_bin = tmp_path / ".claude" / "bin"
    fake_bin.mkdir(parents=True)
    shim = fake_bin / "des"
    shim.write_text("#!/usr/bin/env python3\nprint('stub')\n", encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    resolved = shutil.which("des", path=str(fake_bin))

    assert os.access(shim, os.X_OK)
    assert resolved is not None
    assert Path(resolved).resolve() == shim.resolve()
