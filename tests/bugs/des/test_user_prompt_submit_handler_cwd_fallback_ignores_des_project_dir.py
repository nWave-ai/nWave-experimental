"""Regression AT -- `handle_user_prompt_submit`'s `Path.cwd()` fallback
ignores the per-test `.nwave` ROOT isolation override (`DES_PROJECT_DIR` /
`resolve_nwave_root()`, `src/des/domain/nwave_root.py`).

Site under test (`src/des/adapters/drivers/hooks/user_prompt_submit_handler.py:140`,
inside `handle_user_prompt_submit`):

    project_root = Path(payload.get("cwd") or Path.cwd())

Reached when the submitted-prompt stdin JSON carries no (or an empty)
`"cwd"` key. `project_root` is then threaded into
`CommandLiteralWaveActiveAnchor.on_prompt_submitted`, which ARMS the
wave-active floor (`.nwave/wave-active/active.json`) at that root whenever
the prompt opens with a literal `/nw-<wave>` command. A wrong root here means
the floor is armed at the WRONG project -- exactly the cross-test /
cross-worker `.nwave` bleed `resolve_nwave_root()` was built to prevent
(DDD-14/15).

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the
two reads apart): a `/nw-discuss` prompt submitted with `DES_PROJECT_DIR` set
to `isolated_root` while the process is `chdir`'d to `shared_cwd_root`. Only
ONE of the two roots ends up with an armed floor; which one directly proves
which resolver the handler used.

RED before the fix: the floor is armed at `shared_cwd_root` (bare
`Path.cwd()`). GREEN after: it is armed at `isolated_root`
(`resolve_nwave_root()`).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.user_prompt_submit_handler import (
    handle_user_prompt_submit,
)


def _floor_path(root: Path) -> Path:
    return root / ".nwave" / "wave-active" / "active.json"


def _run_handler_no_cwd_in_stdin(monkeypatch: pytest.MonkeyPatch, prompt: str) -> int:
    """Submit `prompt` via stdin with NO `"cwd"` key, so the `Path.cwd()`
    fallback under test fires."""
    stdin_text = json.dumps({"prompt": prompt})
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    return handle_user_prompt_submit()


@pytest.mark.negative_at
def test_handle_user_prompt_submit_cwd_fallback_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    exit_code = _run_handler_no_cwd_in_stdin(monkeypatch, "/nw-discuss let's start")
    assert exit_code == 0, f"expected exit 0, got {exit_code}"

    isolated_floor = _floor_path(isolated_root)
    shared_floor = _floor_path(shared_cwd_root)
    assert isolated_floor.exists() and not shared_floor.exists(), (
        "handle_user_prompt_submit's Path.cwd() fallback "
        "(user_prompt_submit_handler.py:140, `project_root = "
        "Path(payload.get('cwd') or Path.cwd())`) must honour DES_PROJECT_DIR "
        "via resolve_nwave_root() when the submitted stdin carries no 'cwd'. "
        f"Observed: isolated root floor exists={isolated_floor.exists()}, shared "
        f"cwd root floor exists={shared_floor.exists()} -- the '/nw-discuss' "
        "command literal armed the SHARED cwd root instead of the isolated "
        "DES_PROJECT_DIR root."
    )


def test_handle_user_prompt_submit_cwd_fallback_arms_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "unset_cwd_project"
    project_root.mkdir()

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(project_root)

    exit_code = _run_handler_no_cwd_in_stdin(monkeypatch, "/nw-design let's start")
    assert exit_code == 0, f"expected exit 0, got {exit_code}"

    assert _floor_path(project_root).exists(), (
        "with DES_PROJECT_DIR unset, the '/nw-design' command literal must "
        "still arm Path.cwd()'s floor; no floor was written there."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
