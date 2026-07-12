"""Acceptance tests: 30-minute affordance refresh at the ROUTER surface
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

  The bug is a SCOPE mismatch, not a missing feature: the 30-minute refresh
  is documented (user_prompt_submit_handler.py module docstring) as a
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
_REFRESH_THRESHOLD_SECONDS = 1800
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
    """AC: the 30-minute refresh fires through the REAL router entry point,
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
            "the 30-minute refresh must fire through the REAL router entry "
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
        """Negative AT: sentinel written 60s ago (<< 30min elapsed), driven
        through the REAL router -- must NOT emit additionalContext (no spam).

        Guards the fix: once the router correctly reaches the refresh arm for
        an inactive project, it must still honour the 30-minute cadence --
        not re-inject on every submitted prompt.
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
            "no re-injection expected within the 30-minute threshold, via "
            "the router, on a fresh sentinel -- the cadence must hold "
            "regardless of which entry point (router vs direct handler) is "
            "driven"
        )

    def test_elapsed_sentinel_reinjects_affordance_via_router(
        self, sandbox: Path
    ) -> None:
        """AC: sentinel older than 30 minutes, driven through the REAL
        router -- the next submitted prompt re-injects the SAME
        spine-discipline content, exactly mirroring the direct-handler
        sibling suite's threshold
        (test_orchestrator_affordance_hourly_refresh_acceptance.py).

        RED TODAY: the production threshold is still 3600s
        (user_prompt_submit_handler.py:48) -- a 1801s-old sentinel does not
        yet elapse, so the router observes no re-injection.
        """
        project_root = sandbox
        sentinel = _sentinel_path(project_root)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()
        backdated_ts = time.time() - (_REFRESH_THRESHOLD_SECONDS + 1)
        os.utime(sentinel, (backdated_ts, backdated_ts))
        expected_text = _expected_affordance_text()

        exit_code, stdout, _stderr = _dispatch_via_router(project_root)

        assert exit_code == 0
        assert stdout.strip(), (
            "expected 30-minute re-injection additionalContext via the "
            "router on a stale (1801s) sentinel, got no stdout output"
        )
        output = json.loads(stdout.strip())
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert expected_text in ctx, (
            "router-injected content must be the SAME spine-discipline/"
            "throughput text as the SessionStart affordance"
        )

    def test_sentinel_just_under_the_threshold_boundary_not_reinjected_via_router(
        self, sandbox: Path
    ) -> None:
        """Negative AT (boundary): sentinel backdated to 1799s (just under
        the 1800s/30-minute threshold), driven through the REAL router --
        still no re-injection. Mirrors the direct-handler sibling suite's
        boundary pin."""
        project_root = sandbox
        sentinel = _sentinel_path(project_root)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()
        backdated_ts = time.time() - (_REFRESH_THRESHOLD_SECONDS - 1)
        os.utime(sentinel, (backdated_ts, backdated_ts))

        exit_code, stdout, _stderr = _dispatch_via_router(project_root)

        assert exit_code == 0
        assert stdout.strip() == "", (
            "1799s elapsed is still under the 1800s threshold -- must not "
            "re-inject yet, via the router"
        )


def _dispatch_via_router_raw_stdin(
    project_root: Path, stdin_text: str
) -> tuple[int, str, str]:
    """Drive the REAL router entry with an EXACT stdin payload (no JSON
    ``{"cwd": ...}`` wrapping) -- used for the malformed/empty-stdin
    fail-open regression (Vera's feature-end hostile probe:
    ``echo 'garbage' | python -m des.adapters.drivers.hooks.hook_router
    user-prompt-submit`` crashed with exit 1 + a raw Python traceback).
    """
    from des.adapters.drivers.hooks import hook_router

    return run_hook_in_process(
        hook_router.main,
        stdin_text=stdin_text,
        cwd=str(project_root),
        argv=_ROUTER_ARGV,
    )


_MALFORMED_STDIN_PAYLOADS = [
    pytest.param("garbage", id="bare-word"),
    pytest.param("{not valid json", id="truncated-object"),
    pytest.param("{'single': 'quotes'}", id="python-repr-not-json"),
    pytest.param("null,null", id="trailing-comma-scalars"),
]


class TestUserPromptSubmitMalformedStdinFailsOpen:
    """AC (Vera's feature-end hostile probe -- `des feature-end` reloop):
    ``echo 'garbage' | python -m des.adapters.drivers.hooks.hook_router
    user-prompt-submit`` crashed with **exit 1 + a raw Python traceback**.

    A session-lifecycle hook must NEVER crash: malformed stdin must be
    dropped gracefully (fail-open, exit 0, no traceback) -- mirroring the
    fail-open discipline ``handle_session_start()`` already applies to the
    IDENTICAL parse (``session_start_handler.py`` lines 450-456: the
    ``json.loads`` call is wrapped in ``try/except json.JSONDecodeError``).

    DIAGNOSED ROOT CAUSE (tsunami + Read grounding, no assumption):
    ``handle_user_prompt_submit()``
    (``src/des/adapters/drivers/hooks/user_prompt_submit_handler.py``
    lines 120-121)::

        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}

    has NO try/except around ``json.loads`` -- unlike its session-start
    sibling. A non-empty, non-JSON stdin raises ``json.JSONDecodeError`` (a
    ``ValueError`` subclass) that propagates UNCAUGHT through
    ``hook_router.main()`` (``hook_router.py`` line 76 calls
    ``handle_user_prompt_submit()`` with no try/except around the dispatch),
    crashing the interpreter: exit code 1, raw traceback on stderr -- exactly
    Vera's observation. ``callers_of(handle_user_prompt_submit)`` confirms
    the ONLY production caller is ``hook_router.main`` -- there is no other
    path to patch around.

    ACTIVE-RED: imports only symbols that already exist in production code
    (``hook_router``, ``run_hook_in_process``) -- zero new production
    modules, zero scaffolding needed. Fails today via ``pytest.fail`` (the
    uncaught ``json.JSONDecodeError`` converted to a proper semantic RED
    assertion, never a raw pytest ERROR/collection failure).

    TEST ONLY -- no production code authored in this pass.
    """

    @pytest.mark.parametrize("malformed_stdin", _MALFORMED_STDIN_PAYLOADS)
    def test_malformed_stdin_fails_open_via_router(
        self, sandbox: Path, malformed_stdin: str
    ) -> None:
        """AC (Vera's repro): non-JSON stdin on user-prompt-submit -- driven
        through the REAL router -- must exit 0 with no traceback, exactly
        mirroring session-start's own fail-open contract.

        RED TODAY: `json.loads(raw)` in `handle_user_prompt_submit()` has no
        try/except, so a `json.JSONDecodeError` propagates uncaught through
        `hook_router.main()` -- the interpreter crashes with exit code 1 and
        a raw traceback on stderr instead of failing open.
        """
        project_root = sandbox
        try:
            exit_code, _stdout, stderr = _dispatch_via_router_raw_stdin(
                project_root, malformed_stdin
            )
        except Exception as exc:
            pytest.fail(
                "user-prompt-submit crashed on malformed (non-JSON) stdin "
                f"{malformed_stdin!r} instead of failing open: "
                f"{type(exc).__name__}: {exc}. Root cause: "
                "handle_user_prompt_submit() "
                "(user_prompt_submit_handler.py:120-121) calls "
                "json.loads(raw) with NO try/except -- unlike "
                "handle_session_start() (session_start_handler.py:450-456), "
                "which wraps the IDENTICAL parse in "
                "try/except json.JSONDecodeError. Fix: apply the same "
                "fail-open idiom (default to an empty/None payload on "
                "json.JSONDecodeError) in handle_user_prompt_submit()."
            )
        assert exit_code == 0, (
            "a session-lifecycle hook must NEVER crash on malformed stdin "
            f"(fail-open contract); got exit code {exit_code} for "
            f"{malformed_stdin!r}, stderr: {stderr!r}"
        )
        assert "Traceback" not in stderr, (
            "malformed stdin must be dropped gracefully -- no raw Python "
            f"traceback on stderr for {malformed_stdin!r}; got: {stderr!r}"
        )

    @pytest.mark.parametrize(
        "boundary_stdin",
        [pytest.param("", id="empty"), pytest.param("   \n", id="whitespace-only")],
    )
    def test_empty_or_whitespace_stdin_fails_open_via_router(
        self, sandbox: Path, boundary_stdin: str
    ) -> None:
        """Boundary: empty / whitespace-only stdin on user-prompt-submit is
        ALREADY handled by the `if raw.strip() else {}` guard -- pinned here
        (chained off the same router-dispatch narrative as the malformed
        case above) so a future fail-open fix cannot regress this bar."""
        project_root = sandbox
        exit_code, _stdout, stderr = _dispatch_via_router_raw_stdin(
            project_root, boundary_stdin
        )
        assert exit_code == 0, (
            f"empty/whitespace stdin must fail open too; got exit code "
            f"{exit_code} for {boundary_stdin!r}, stderr: {stderr!r}"
        )
        assert "Traceback" not in stderr, (
            f"got an unexpected traceback for {boundary_stdin!r}: {stderr!r}"
        )

    @pytest.mark.negative_at
    def test_malformed_stdin_does_not_raise_uncaught_exception_via_router(
        self, sandbox: Path
    ) -> None:
        """Negative AT (GS-8 guard, detected by the `_not_` stem + the
        `negative_at` marker): the WRONG outcome -- an uncaught exception
        escaping the router on malformed stdin -- must NOT be produced.
        This is the exact crash class Vera's feature-end hostile probe
        exhibited; a presence-only positive assertion would not catch a
        regression that merely narrows the exception type still escaping.
        """
        project_root = sandbox
        try:
            _dispatch_via_router_raw_stdin(project_root, "garbage")
        except Exception as exc:
            pytest.fail(
                "the WRONG outcome was produced: an uncaught "
                f"{type(exc).__name__} ({exc}) escaped hook_router.main() "
                "on malformed stdin, instead of the router failing open "
                "(exit 0, no exception, no traceback)."
            )


# ---------------------------------------------------------------------------
# Deep-review blocking finding (scope-creep, adversarial-refutation reloop):
#
# Widening `_ACTIVATION_EXEMPT_COMMANDS` to `user-prompt-submit`
# (activation_gate.py:47) makes the ENTIRE `handle_user_prompt_submit`
# dispatch unconditionally -- including
# `CommandLiteralWaveActiveAnchor.on_prompt_submitted`
# (wave_active_anchor.py), which on a literal `/nw-<wave>` prompt calls
# `WaveActiveFilesystemStore.arm()` and WRITES
# `{project_root}/.nwave/wave-active/active.json`. On an INACTIVE
# (never-adopted) project this bypasses the controlled adoption path
# (DDD-9): before the exemption, `apply_gate`'s `sys.exit(0)` made such
# prompts inert.
#
# `_write_active_marker` mirrors the activation-gating fixture convention
# established in `tests/des/acceptance/activation_gating/test_gap_fixes_real_
# entry_points.py::_write_marker` -- `.nwave/local-config.json` with
# `enabled_for_repo: true` resolves the project ACTIVE via
# `resolve_activation` (a marker value dominates the global mode,
# `activation_policy.py:26-27`), independent of the `sandbox` fixture's
# isolated-HOME/no-global-config-opt-in shape.
# ---------------------------------------------------------------------------

_WAVE_ACTIVE_FLOOR_RELATIVE = Path(".nwave") / "wave-active" / "active.json"
_NW_WAVE_PROMPT = "/nw-deliver something"


def _wave_active_floor_path(project_root: Path) -> Path:
    return project_root / _WAVE_ACTIVE_FLOOR_RELATIVE


def _write_active_marker(project_root: Path) -> None:
    nwave = project_root / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": True}) + "\n", encoding="utf-8"
    )


def _dispatch_prompt_via_router(
    project_root: Path, prompt: str
) -> tuple[int, str, str]:
    """Drive the REAL router entry with a literal `/nw-<wave>` prompt (the
    exact stdin shape `handle_user_prompt_submit` -> `CommandLiteralWaveActive
    Anchor` reads: `{"prompt": ..., "cwd": ...}`)."""
    from des.adapters.drivers.hooks import hook_router

    stdin_payload = json.dumps({"prompt": prompt, "cwd": str(project_root)})
    return run_hook_in_process(
        hook_router.main,
        stdin_text=stdin_payload,
        cwd=str(project_root),
        argv=_ROUTER_ARGV,
    )


class TestUserPromptSubmitExemptionDoesNotBypassControlledAdoption:
    """AC (deep-review blocking finding, scope-creep): the `user-prompt-submit`
    activation exemption must free ONLY the hourly-affordance refresh, never
    the wave-active anchor's arm() write -- that write stays gated on the
    project's OWN activation resolution, exactly as it was before the
    exemption widened."""

    @pytest.mark.negative_at
    def test_inactive_project_nw_wave_prompt_via_router_does_not_arm_wave_active_floor(
        self, sandbox: Path
    ) -> None:
        """AC (the finding's repro): an INACTIVE project (no local-config.json
        marker, no global opt-in -- the same shape `sandbox` builds for the
        hourly-refresh scenarios above) submitting a literal `/nw-deliver ...`
        prompt through the REAL router must still exit 0, and the hourly
        affordance refresh MAY fire (unrelated to this finding, not asserted
        here), but must NOT write `.nwave/wave-active/active.json` -- the
        WRONG outcome the finding names. Detected by name (`_not_`) +
        `@pytest.mark.negative_at` per the GS-8 negative-AT convention.

        RED TODAY: `apply_gate` (activation_gate.py:78-79) exempts
        `user-prompt-submit` UNCONDITIONALLY -- before any activation check
        -- so `handle_user_prompt_submit` always reaches
        `CommandLiteralWaveActiveAnchor.on_prompt_submitted`, which calls
        `WaveActiveFilesystemStore.arm()` and writes the floor file even on
        an INACTIVE, never-adopted project.
        """
        project_root = sandbox
        floor = _wave_active_floor_path(project_root)
        assert not floor.exists()

        exit_code, _stdout, _stderr = _dispatch_prompt_via_router(
            project_root, _NW_WAVE_PROMPT
        )

        assert exit_code == 0, (
            "user-prompt-submit must exit 0 regardless of activation state "
            f"(fail-open contract); got {exit_code}"
        )
        assert not floor.exists(), (
            "the WRONG outcome was produced: .nwave/wave-active/active.json "
            "was written for a literal /nw-<wave> prompt on an INACTIVE "
            "(never-adopted) project. Widening _ACTIVATION_EXEMPT_COMMANDS to "
            "user-prompt-submit (activation_gate.py:47, applied at "
            "activation_gate.py:78-79) makes the ENTIRE "
            "handle_user_prompt_submit dispatch unconditionally -- including "
            "CommandLiteralWaveActiveAnchor.on_prompt_submitted "
            "(wave_active_anchor.py), which arms the wave-active floor via "
            "WaveActiveFilesystemStore.arm() with no activation check of its "
            "own. Before the exemption widened, apply_gate's sys.exit(0) "
            "made such prompts inert on an inactive project -- this bypasses "
            "the controlled adoption path (DDD-9). Fix: gate the anchor's "
            "arm (or the anchor dispatch itself) on the project's own "
            "activation resolution, independent of the "
            "user-prompt-submit activation-gate exemption that now exists "
            "only for the hourly-affordance refresh."
        )

    def test_active_project_nw_wave_prompt_via_router_still_arms_wave_active_floor(
        self, sandbox: Path
    ) -> None:
        """GUARD (must stay true post-fix): an ACTIVE project (adopted via the
        `.nwave/local-config.json` `enabled_for_repo: true` marker) submitting
        the SAME literal `/nw-<wave>` prompt must still arm the wave-active
        floor exactly as before -- the fix for the finding above must not
        regress adoption on an already-active project.
        """
        project_root = sandbox
        _write_active_marker(project_root)
        floor = _wave_active_floor_path(project_root)
        assert not floor.exists()

        exit_code, _stdout, _stderr = _dispatch_prompt_via_router(
            project_root, _NW_WAVE_PROMPT
        )

        assert exit_code == 0
        assert floor.exists(), (
            "an ACTIVE project must still have the wave-active floor armed "
            "by a literal /nw-<wave> prompt through the router -- adoption "
            "on active projects must not regress while fixing the "
            "inactive-project scope-creep above"
        )
        payload = json.loads(floor.read_text(encoding="utf-8"))
        assert payload.get("wave") == "deliver", (
            f"expected the /nw-deliver literal to arm wave='deliver'; got "
            f"floor payload {payload!r}"
        )
        assert payload.get("provenance") == "command", (
            f"expected COMMAND provenance (the deterministic literal-match "
            f"anchor); got floor payload {payload!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
