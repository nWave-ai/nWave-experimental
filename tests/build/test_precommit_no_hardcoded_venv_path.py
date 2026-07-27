"""Regression pin: no pre-commit hook `entry` hardcodes a `.venv/` path.

Bug class (prepush-hook-hardcodes-venv-python-breaking-agnosticism): a hook
entry like ``.venv/bin/python -m ...`` is a literal path relative to the repo
root. It breaks in any worktree/clone whose venv is not at that exact
location, violating this repo's target-machine-agnosticism mandate (CLAUDE.md:
hook commands must use `$HOME`/`uv run`/bare interpreters, never a hardcoded
`.venv/` path). Every sibling hook in this file uses `uv run` or `python3`.
"""

from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"


def test_no_hook_entry_hardcodes_venv_path():
    """No hook's `entry:` string contains a literal `.venv/` path."""
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    offenders = []
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            entry = hook.get("entry", "")
            if ".venv/" in entry:
                offenders.append(f"{hook.get('id', '<unknown>')}: {entry!r}")

    assert not offenders, (
        "hook entry(ies) hardcode a `.venv/`-relative interpreter path -- "
        "breaks any worktree/clone without a venv at that exact location; "
        "use `uv run ...` or a bare `python3` instead:\n  " + "\n  ".join(offenders)
    )
