"""Acceptance tests: hourly affordance refresh at the ROUTER surface
(EXAMINE-FAIL reloop, `orchestrator-affordance-hourly-refresh`).

Vera drove the REAL edge exactly as Claude Code does:
  ``uv run python -m des.adapters.drivers.hooks.hook_router user-prompt-submit``
with minimal JSON stdin (``{}`` / ``{"cwd": <throwaway-with-.nwave>}``), from a
directory WITHOUT wave-active/DES-active state. Every probe returned exit 0,
ZERO bytes of stdout, no sentinel written, no ``additionalContext`` -- the
hourly refresh never fires from the real entry point.

Meanwhile ``test_orchestrator_affordance_hourly_refresh_acceptance.py`` (the
existing sibling suite) is GREEN because it drives
``handle_user_prompt_submit`` directly, in-process -- it bypasses
``hook_router.main()`` entirely, and therefore bypasses whatever swallows the
flow before the handler ever runs. This file closes that gap: it drives the
ROUTER edge (``hook_router.main``, the same ``main`` the installed
``claude_code_hook_adapter`` re-exports and Claude Code invokes), reproducing
Vera's exact zero-output observation.

DIAGNOSED ROOT CAUSE (tsunami/Read grounding, no assumption):

  ``hook_router.main()`` (``src/des/adapters/drivers/hooks/hook_router.py``
  lines 53-58) calls ``activation_gate.apply_gate(command, buffered_stdin)``
  BEFORE dispatching to any handler -- including ``user-prompt-submit`` ->
  ``handle_user_prompt_submit`` (line 75-76). ``apply_gate``
  (``src/des/adapters/drivers/hooks/activation_gate.py`` lines 79-102) exempts
  ONLY ``session-start`` (line 88-89: ``if command == _SESSION_START: return
  stdin_text``). For every other command -- including ``user-prompt-submit``
  -- when the project resolves INACTIVE per ADR-AG-002
  (``resolve_activation``: no per-project ``enabled_for_repo`` marker AND the
  global ``activation.mode`` is the fresh-install default ``"opt-in"``), the
  gate falls through to its final line:

      ``sys.exit(0)``                                    (activation_gate.py:102)

  This raises ``SystemExit(0)`` INSIDE ``hook_router.main()``, terminating the
  process before ``handle_user_prompt_submit()`` -- and therefore before the
  hourly-refresh logic living inside it
  (``_maybe_refresh_orchestrator_affordance``, called from
  ``user_prompt_submit_handler.py`` line 130) -- ever runs. Exit code 0, zero
  stdout, no sentinel write: exactly Vera's observation. A fresh throwaway
  project (only a bare ``.nwave/`` dir, no ``local-config.json`` marker, no
  ``~/.nwave/global-config.json`` opting the machine into ``"all"`` mode) is
  precisely the INACTIVE case this gate silences.

  The bug is a SCOPE mismatch, not a missing feature: the hourly refresh is
  documented (user_prompt_submit_handler.py module docstring) as a
  session-HYGIENE refresh mirroring SessionStart's unconditional injection --
  but SessionStart is activation-EXEMPT (gate line 88-89) while
  ``user-prompt-submit`` is not, so the refresh that piggybacks on
  ``user-prompt-submit`` inherits an activation gate it was never meant to
  observe.

CONTRACT under test: the discipline refresh fires INDEPENDENT of
wave-active/DES-activation state -- mirroring SessionStart's own activation
exemption -- so `user-prompt-submit` must reach `handle_user_prompt_submit`
(and therefore the refresh arm) through the router regardless of the
project's activation resolution.

ACTIVE-RED: this file imports ONLY symbols that already exist in production
code (``hook_router``, ``activation_gate``, ``session_start_handler``) --
zero new production modules, zero scaffolding needed. The positive scenario
fails today with a semantic ``AssertionError`` (empty captured stdout / no
sentinel written), never an ImportError or collection error.

TEST ONLY -- no production code authored in this pass.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_hook_in_process


_SENTINEL_RELATIVE = Path(".nwave") / "orchestrator-affordance-last-injected"
_ONE_HOUR_SECONDS = 3600
_ROUTER_ARGV = ["hook_router", "user-prompt-submit"]


def _sentinel_path(project_root: Path) -> Path:
    return project_root / _SENTINEL_RELATIVE


def _expected_affordance_text() -> str:
    """The real, currently-shipped SessionStart affordance content.

    Computed via the EXISTING production loader/asset-dir (never a hardcoded
    duplicate) -- proves the router-driven refresh emits the SAME content the
    SessionStart path already injects.
    """
    from des.adapters.drivers.hooks.session_start_handler import (
        _ORCHESTRATOR_AFFORDANCE_ASSETS_DIR,
        load_orchestrator_affordance,
    )

    text = load_orchestrator_affordance(_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR)
    assert text, (
        "shipped nWave/data/orchestrator-affordance/*.md assets must be "
        "present for this AT to ground its content-parity expectation"
    )
    return text


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway project reproducing Vera's exact inactive shape.

    - ``project_root`` carries only a bare ``.nwave/`` directory: no
      ``local-config.json`` marker (``enabled_for_repo`` unset -> ``None``).
    - ``HOME`` is redirected to an isolated sandbox with NO
      ``~/.nwave/global-config.json`` -- the real ``DESConfig`` /
      ``activation_gate._global_config_path()`` (``Path.home()``-anchored)
      resolves the fresh-install default ``"opt-in"`` mode.
    - No wave-active anchor is armed (no prior ``/nw-<wave>`` prompt).

    ``resolve_activation(marker_enabled=None, global_mode="opt-in")`` ->
    ``False`` -- exactly the "dir WITHOUT wave-active/DES-active state" Vera
    drove against, isolated from the developer machine's real
    ``~/.nwave/global-config.json`` so the scenario is deterministic.
    """
    project_root = tmp_path / "project"
    home_dir = tmp_path / "home"
    (project_root / ".nwave").mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    return project_root


def _dispatch_via_router(project_root: Path) -> tuple[int, str, str]:
    """Drive the REAL router entry (`hook_router.main`) over its stdin protocol.

    In-process analogue of
    ``python -m des.adapters.drivers.hooks.hook_router user-prompt-submit``
    (this repo's established fork-avoidance convention, see
    ``tests/common/in_process_cli.py``) -- faithful to the process boundary:
    same ``main()`` entry, same stdin contract, same ``cwd``, same
    ``SystemExit`` -> exit-code mapping a real subprocess would observe. This
    is the surface Vera drove and the router-level bug lives in
    ``hook_router.main`` -> ``activation_gate.apply_gate`` -- NOT in
    ``handle_user_prompt_submit`` itself, which the existing sibling suite
    already covers directly.
    """
    from des.adapters.drivers.hooks import hook_router

    stdin_payload = json.dumps({"cwd": str(project_root)})
    return run_hook_in_process(
        hook_router.main,
        stdin_text=stdin_payload,
        cwd=str(project_root),
        argv=_ROUTER_ARGV,
    )


class TestOrchestratorAffordanceHourlyRefreshRouterAcceptance:
    """AC: the hourly refresh fires through the REAL router entry point,
    independent of wave-active/DES-activation state -- mirroring
    SessionStart's own activation exemption (gate line 88-89)."""

    def test_missing_sentinel_reinjects_affordance_via_router_regardless_of_activation_state(
        self, sandbox: Path
    ) -> None:
        """AC (Vera's repro): a throwaway project with NO wave-active/DES-active
        state, no sentinel, driven through the REAL router -- must still exit 0
        AND emit the additionalContext injection AND write the sentinel.

        RED TODAY: `apply_gate` (activation_gate.py:102) calls `sys.exit(0)`
        before `handle_user_prompt_submit` ever runs on an inactive project,
        so stdout is empty and no sentinel is written -- exactly Vera's
        zero-output observation.
        """
        project_root = sandbox
        assert not _sentinel_path(project_root).exists()
        expected_text = _expected_affordance_text()

        exit_code, stdout, _stderr = _dispatch_via_router(project_root)

        assert exit_code == 0, (
            "the router must exit 0 for user-prompt-submit even on an "
            f"inactive project (fail-open contract); got {exit_code}"
        )
        assert stdout.strip(), (
            "the hourly refresh must fire through the REAL router entry "
            "regardless of wave-active/DES-activation state (mirroring "
            "SessionStart's activation exemption) -- got ZERO stdout bytes, "
            "reproducing Vera's exact router-level observation. Root cause: "
            "activation_gate.apply_gate() sys.exit(0)s before "
            "handle_user_prompt_submit() ever runs on an inactive project "
            "(activation_gate.py:102); user-prompt-submit is not exempted "
            "the way session-start is (activation_gate.py:88-89)."
        )
        output = json.loads(stdout.strip())
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert expected_text in ctx, (
            "router-injected content must be the SAME spine-discipline/"
            "throughput text as the SessionStart affordance"
        )
        assert _sentinel_path(project_root).exists(), (
            "the sentinel must be written after the router-driven injection "
            "so the NEXT prompt can correctly measure elapsed time"
        )

    def test_fresh_sentinel_does_not_reinject_via_router(self, sandbox: Path) -> None:
        """Negative AT: sentinel written 60s ago (<< 1h elapsed), driven through
        the REAL router -- must NOT emit additionalContext (no spam).

        Guards the fix: once the router correctly reaches the refresh arm for
        an inactive project, it must still honour the hourly cadence -- not
        re-inject on every submitted prompt.
        """
        project_root = sandbox
        sentinel = _sentinel_path(project_root)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()
        backdated_ts = time.time() - 60
        os.utime(sentinel, (backdated_ts, backdated_ts))

        exit_code, stdout, _stderr = _dispatch_via_router(project_root)

        assert exit_code == 0
        assert stdout.strip() == "", (
            "no re-injection expected within the hour, via the router, on a "
            "fresh sentinel -- the hourly cadence must hold regardless of "
            "which entry point (router vs direct handler) is driven"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
