"""Regression AT -- `activation_gate.apply_gate`'s `Path.cwd()` fallback
ignores the per-test `.nwave` ROOT isolation override (`DES_PROJECT_DIR` /
`resolve_nwave_root()`, `src/des/domain/nwave_root.py`).

Site under test (`src/des/adapters/drivers/hooks/activation_gate.py:117`,
inside `apply_gate`):

    project_root = _parse_cwd(stdin_text) or Path.cwd()

Reached when the hook envelope's stdin JSON carries no (or an empty) `"cwd"`
key -- `_parse_cwd` returns `None` and the bare `Path.cwd()` fallback resolves
the activation decision's project root instead of an isolation-aware
resolver. `apply_gate` is the SINGLE hook dispatch point (ADR-AG-001): a
wrong project root here means the gate resolves activation against the wrong
project entirely -- dispatching (or silencing) the wrong repo's hooks.

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the
two reads apart): two real tmp roots, each carrying its OWN
`.nwave/local-config.json` `enabled_for_repo` marker with an OPPOSITE value
(`isolated_root` -> `True` / ACTIVE, `shared_cwd_root` -> `False` / INACTIVE).
`resolve_activation` short-circuits on a present marker
(`src/des/domain/activation_policy.py`), so this discriminates independently
of the real machine's `~/.nwave/global-config.json` state.

RED before the fix: `apply_gate` reads the shared cwd's INACTIVE marker via
bare `Path.cwd()` -> `sys.exit(0)` (silenced, never dispatched). GREEN after:
it reads the isolated root's ACTIVE marker via `resolve_nwave_root()` ->
returns the stdin text for dispatch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.activation_gate import apply_gate


# A command literal outside every special-cased set (`_ACTIVATION_EXEMPT_COMMANDS`
# = session-start only; `_PRE_TASK_COMMANDS` = pre-task/pre-tool-use;
# `_USER_PROMPT_SUBMIT` = user-prompt-submit) so `apply_gate`'s activation
# resolution is the ONLY thing deciding dispatch-vs-silence for this call.
_NEUTRAL_COMMAND = "post-tool-use"


def _write_local_config(root: Path, *, enabled_for_repo: bool) -> None:
    config_dir = root / ".nwave"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": enabled_for_repo}), encoding="utf-8"
    )


def _apply_gate_no_cwd_in_stdin() -> str | None:
    """Call `apply_gate` with a stdin payload carrying NO `"cwd"` key, so
    `_parse_cwd` returns None and the `Path.cwd()` fallback under test fires.
    Returns the outcome as either the dispatched stdin text, or `"__EXIT__"`
    if `apply_gate` called `sys.exit(0)` (silenced)."""
    stdin_text = json.dumps({"subagent_type": None})
    try:
        return apply_gate(_NEUTRAL_COMMAND, stdin_text)
    except SystemExit:
        return "__EXIT__"


@pytest.mark.negative_at
def test_apply_gate_cwd_fallback_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    _write_local_config(isolated_root, enabled_for_repo=True)
    _write_local_config(shared_cwd_root, enabled_for_repo=False)

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    outcome = _apply_gate_no_cwd_in_stdin()

    assert outcome != "__EXIT__", (
        "activation_gate.apply_gate's Path.cwd() fallback "
        "(activation_gate.py:117, `project_root = _parse_cwd(stdin_text) or "
        "Path.cwd()`) must honour DES_PROJECT_DIR via resolve_nwave_root() "
        "when the stdin envelope carries no 'cwd' -- the isolated root's "
        "local-config.json declares enabled_for_repo=True (active). Observed "
        "sys.exit(0) (silenced): the gate read the SHARED cwd's INACTIVE "
        "marker via bare Path.cwd() instead of the isolated DES_PROJECT_DIR "
        "root."
    )


def test_apply_gate_cwd_fallback_reads_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "unset_cwd_project"
    project_root.mkdir()
    _write_local_config(project_root, enabled_for_repo=True)

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(project_root)

    outcome = _apply_gate_no_cwd_in_stdin()

    assert outcome != "__EXIT__", (
        "with DES_PROJECT_DIR unset, apply_gate's fallback must still read "
        "Path.cwd() -- the cwd project's local-config.json declares "
        "enabled_for_repo=True (active); observed sys.exit(0) (silenced) "
        "instead of a dispatch."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
