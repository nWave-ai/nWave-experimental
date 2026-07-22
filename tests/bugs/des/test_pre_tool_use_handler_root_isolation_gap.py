"""Regression AT -- four bare `Path.cwd()` call sites in
`src/des/adapters/drivers/hooks/pre_tool_use_handler.py` ignore the per-test
`.nwave` ROOT isolation override (`DES_PROJECT_DIR` / `resolve_nwave_root()`,
`src/des/domain/nwave_root.py`).

Unlike the sibling `PreToolUseService._read_active_wave()` /
`._discuss_gate_in_invoker()` call sites (already wired through
`resolve_nwave_root()`), this ADAPTER file still reads bare `Path.cwd()` at
FOUR sites -- every one of them is exercised here, each with its own
discriminating assertion:

  2a. `_peek_wave_entering` (line ~218): `activation.peek_entry(Path.cwd())`
      -- the STRUCTURAL wave-entering read (F3 NORMATIVO).
  2b. `_arm_inferred_fallback` (line ~257): `activation.arm_inferred(Path.cwd(),
      declared_wave)` -- the INFERRED-floor self-entry fallback (F4).
  2c. `handle_pre_tool_use()`'s clear-on-allow branch (line ~519):
      `activation.clear_entry(Path.cwd())` -- the clear-on-allow write that
      closes the wave-entering lifecycle peek_entry opened.
  2d. `_evaluate_u1_intercept`'s DEFAULT `project_root` (line ~180):
      `project_root = Path.cwd()`, used when the dispatch carries no
      `DES-PROJECT-ROOT` marker override (the override logic itself is
      untouched and out of scope here).

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the
two reads apart), shared across 2a/2b/2c: two real tmp roots --
`shared_cwd_root` (the process `chdir` target, standing in for the real repo
checkout a shared xdist worker would see) and `isolated_root`
(`DES_PROJECT_DIR`, the per-test isolation target). 2d uses a monkeypatched
`intercept_atdd_pure_dispatch` stub to directly OBSERVE the `project_root`
argument the real production function constructs and passes downward --
driving `_evaluate_u1_intercept` itself (the real code under test), with only
its own deep dependency (the carpaccio CLI subprocess machinery, far too
heavy to stand up for this narrow question) stubbed to capture what it
received.

Each site's `(a)` test asserts isolation-when-set (RED against current code);
each site's `(b)` test asserts unset-unchanged (PASSES today and must keep
passing -- `monkeypatch.delenv("DES_PROJECT_DIR", raising=False)` defeats the
autouse `_isolate_nwave_root` fixture in `tests/conftest.py` so the true
unset path is actually exercised, not masked by it).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.drivers.hooks import pre_tool_use_handler
from des.adapters.drivers.hooks.carpaccio_intercept import InterceptDecision
from des.adapters.drivers.hooks.pre_tool_use_handler import (
    _arm_inferred_fallback,
    _evaluate_u1_intercept,
    _peek_wave_entering,
    handle_pre_tool_use,
)
from des.application.wave_activation_service import WaveActivationService
from des.domain.wave_active import WaveActiveRecord, WaveProvenance


def _armed_store(root: Path, *, wave: str, entry_pending: bool) -> None:
    WaveActiveFilesystemStore().arm(
        root,
        WaveActiveRecord(
            wave=wave, provenance=WaveProvenance.COMMAND, entry_pending=entry_pending
        ),
    )


def _floor_path(root: Path) -> Path:
    return root / ".nwave" / "wave-active" / "active.json"


# ---------------------------------------------------------------------------
# 2a -- `_peek_wave_entering` (line ~218)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_peek_wave_entering_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    # Only the isolated root's floor is armed with a pending entry;
    # shared_cwd_root is left unarmed (NoWaveActive -> entry not pending).
    _armed_store(isolated_root, wave="discuss", entry_pending=True)

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    store = WaveActiveFilesystemStore()
    activation = WaveActivationService(reader=store, writer=store)
    wave_entering, block = _peek_wave_entering({"tool_name": "Agent"}, activation)

    assert block is None, f"unexpected block: {block!r}"
    assert wave_entering is True, (
        "_peek_wave_entering (pre_tool_use_handler.py:218) must honour "
        "DES_PROJECT_DIR via resolve_nwave_root() -- the isolated root's "
        "floor carries entry_pending=True. Observed wave_entering=False: the "
        "call reads bare Path.cwd() (the shared, unarmed root) instead."
    )


def test_peek_wave_entering_reads_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unset_cwd_project"
    root.mkdir()
    _armed_store(root, wave="discuss", entry_pending=True)

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    store = WaveActiveFilesystemStore()
    activation = WaveActivationService(reader=store, writer=store)
    wave_entering, block = _peek_wave_entering({"tool_name": "Agent"}, activation)

    assert block is None, f"unexpected block: {block!r}"
    assert wave_entering is True, (
        "with DES_PROJECT_DIR unset, _peek_wave_entering must still read "
        f"Path.cwd(); observed wave_entering={wave_entering!r}, expected True."
    )


# ---------------------------------------------------------------------------
# 2b -- `_arm_inferred_fallback` (line ~257)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_arm_inferred_fallback_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()
    # Both floors start unarmed (NoWaveActive) -- arm_inferred only writes
    # when the floor is empty.

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    store = WaveActiveFilesystemStore()
    activation = WaveActivationService(reader=store, writer=store)
    prompt = "<!-- DES-WAVE: discuss -->\nsome work"
    wave_entering, block = _arm_inferred_fallback(
        {"tool_name": "Agent"}, prompt, activation
    )

    assert block is None, f"unexpected block: {block!r}"
    assert wave_entering is True, f"expected the fallback to arm, got {wave_entering!r}"

    isolated_floor = _floor_path(isolated_root)
    shared_floor = _floor_path(shared_cwd_root)
    assert isolated_floor.exists() and not shared_floor.exists(), (
        "_arm_inferred_fallback (pre_tool_use_handler.py:257) must arm the "
        "isolated DES_PROJECT_DIR root (resolve_nwave_root()), not bare "
        f"Path.cwd(). Observed: isolated floor exists={isolated_floor.exists()}, "
        f"shared cwd floor exists={shared_floor.exists()} -- the fallback armed "
        "the shared cwd root instead of the isolated one."
    )


def test_arm_inferred_fallback_arms_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unset_cwd_project"
    root.mkdir()

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    store = WaveActiveFilesystemStore()
    activation = WaveActivationService(reader=store, writer=store)
    prompt = "<!-- DES-WAVE: discuss -->\nsome work"
    wave_entering, block = _arm_inferred_fallback(
        {"tool_name": "Agent"}, prompt, activation
    )

    assert block is None, f"unexpected block: {block!r}"
    assert wave_entering is True, f"expected the fallback to arm, got {wave_entering!r}"
    assert _floor_path(root).exists(), (
        "with DES_PROJECT_DIR unset, _arm_inferred_fallback must still arm "
        "Path.cwd()'s floor; no floor was written there."
    )


# ---------------------------------------------------------------------------
# 2c -- clear-on-allow inside `handle_pre_tool_use()` (line ~519)
# ---------------------------------------------------------------------------


def _run_handler_with_stdin(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return handle_pre_tool_use()


def _markerless_agent_payload(prompt: str) -> dict[str, object]:
    return {
        "tool_name": "Agent",
        "tool_input": {"prompt": prompt, "subagent_type": "child"},
    }


@pytest.mark.negative_at
def test_clear_on_allow_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clear-on-allow write must clear the ISOLATED root's entry flag,
    not the shared process cwd's.

    Both roots are armed IDENTICALLY (entry_pending=True, wave="design" --
    deliberately not "discuss", to stay clear of the DISCUSS gate-IN branch)
    so `wave_entering` resolves True via EITHER the buggy Path.cwd() read or
    the fixed resolve_nwave_root() read -- decoupling this assertion from
    site 2a's fix status. The dispatch is markerless (no DES-* markers at
    all), which is unconditionally ALLOWED by PreToolUseService (S1,
    non_des_task) regardless of which wave is active, so the clear-on-allow
    branch always fires.
    """
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    _armed_store(shared_cwd_root, wave="design", entry_pending=True)
    _armed_store(isolated_root, wave="design", entry_pending=True)

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    exit_code = _run_handler_with_stdin(
        monkeypatch, _markerless_agent_payload("do something ordinary")
    )
    assert exit_code == 0, (
        f"expected the markerless dispatch to be allowed, got {exit_code}"
    )

    store = WaveActiveFilesystemStore()
    isolated_state = store.read(isolated_root)
    assert isinstance(isolated_state, WaveActiveRecord), (
        f"isolated root floor unexpectedly missing/corrupt: {isolated_state!r}"
    )
    assert isolated_state.entry_pending is False, (
        "handle_pre_tool_use()'s clear-on-allow branch (pre_tool_use_handler.py:519, "
        "`activation.clear_entry(Path.cwd())`) must clear the isolated "
        "DES_PROJECT_DIR root's entry flag (resolve_nwave_root()), not the "
        f"shared cwd's. Observed isolated_root entry_pending="
        f"{isolated_state.entry_pending!r} (still True -- untouched): the clear "
        "landed on Path.cwd() (the shared root) instead."
    )


def test_clear_on_allow_clears_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unset_cwd_project"
    root.mkdir()
    _armed_store(root, wave="design", entry_pending=True)

    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    exit_code = _run_handler_with_stdin(
        monkeypatch, _markerless_agent_payload("do something ordinary")
    )
    assert exit_code == 0, (
        f"expected the markerless dispatch to be allowed, got {exit_code}"
    )

    store = WaveActiveFilesystemStore()
    state = store.read(root)
    assert isinstance(state, WaveActiveRecord), f"floor unexpectedly missing: {state!r}"
    assert state.entry_pending is False, (
        "with DES_PROJECT_DIR unset, the clear-on-allow branch must still "
        f"clear Path.cwd()'s entry flag; observed entry_pending="
        f"{state.entry_pending!r}, expected False."
    )


# ---------------------------------------------------------------------------
# 2d -- `_evaluate_u1_intercept`'s default `project_root` (line ~180)
# ---------------------------------------------------------------------------


def _atdd_pure_prompt() -> str:
    return (
        "<!-- DES-MODE: atdd_pure -->\n"
        "<!-- DES-PROJECT-ID: demo-feature -->\n"
        "do some atdd_pure work"
    )


@pytest.mark.negative_at
def test_u1_intercept_default_project_root_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    captured: dict[str, Path] = {}

    def _capture_intercept(
        *, prompt: str, feature_id: str, project_root: Path, subagent_type: str
    ) -> InterceptDecision:
        captured["project_root"] = project_root
        return InterceptDecision.allow()

    monkeypatch.setattr(
        pre_tool_use_handler, "intercept_atdd_pure_dispatch", _capture_intercept
    )
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    result = _evaluate_u1_intercept(_atdd_pure_prompt(), "child")

    assert result is None, f"unexpected block payload: {result!r}"
    assert captured.get("project_root") == isolated_root, (
        "_evaluate_u1_intercept's default project_root "
        "(pre_tool_use_handler.py:180, `project_root = Path.cwd()`) must "
        "honour DES_PROJECT_DIR via resolve_nwave_root() when no "
        "DES-PROJECT-ROOT marker overrides it. Observed project_root="
        f"{captured.get('project_root')!r} (== Path.cwd(), the shared root) "
        "instead of the isolated DES_PROJECT_DIR root."
    )


def test_u1_intercept_default_project_root_reads_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "unset_cwd_project"
    root.mkdir()

    captured: dict[str, Path] = {}

    def _capture_intercept(
        *, prompt: str, feature_id: str, project_root: Path, subagent_type: str
    ) -> InterceptDecision:
        captured["project_root"] = project_root
        return InterceptDecision.allow()

    monkeypatch.setattr(
        pre_tool_use_handler, "intercept_atdd_pure_dispatch", _capture_intercept
    )
    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)

    result = _evaluate_u1_intercept(_atdd_pure_prompt(), "child")

    assert result is None, f"unexpected block payload: {result!r}"
    assert captured.get("project_root") == root, (
        "with DES_PROJECT_DIR unset, _evaluate_u1_intercept's default "
        f"project_root must still be Path.cwd(); observed "
        f"{captured.get('project_root')!r}, expected {root!r}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
