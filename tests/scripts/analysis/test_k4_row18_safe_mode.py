"""K4 matrix row 18 -- launcher economics.

First divergence: a launcher friction note measured three external Claude
writers spending ~USD 3.70 and 3.5M cached/read tokens over ~3 minutes with
ZERO edits under a non-safe-mode cold start; safe-mode reached edits
quickly. `--safe-mode` disables every customization (CLAUDE.md, skills,
plugins, hooks, MCP servers, agents...), so it must default ONLY for a
narrow external writer that needs none of that -- `probe_delivery_
permissions`'s Edit/Write canary -- never for the real nWave/control
delivery arms, whose measured behavior depends on those customizations.

ADMISSION falsifier: the canary's constructed subprocess argv actually
carries `--safe-mode`; the real delivery arms' argv does not.
"""

from __future__ import annotations

import json

from scripts.analysis.k4 import preflight


def test_delivery_argv_omits_safe_mode_by_default():
    argv = preflight.delivery_argv("claude-sonnet-5", "/probe/bin:/usr/bin")

    assert "--safe-mode" not in argv


def test_delivery_argv_opts_into_safe_mode_when_requested():
    argv = preflight.delivery_argv(
        "claude-sonnet-5", "/probe/bin:/usr/bin", safe_mode=True
    )

    assert "--safe-mode" in argv


def test_permission_canary_actually_invokes_the_delivery_runner_with_safe_mode(
    tmp_path, monkeypatch
):
    """Execution-observing: no subprocess.run mock. A fake `claude` executable
    on PATH logs the exact argv it receives, and the probe's own captured
    argv (the one `subprocess.run` would spawn) is inspected directly for
    `--safe-mode` -- proving the flag reaches the real invocation, not just
    a helper function in isolation."""
    workspace = tmp_path / "workspace"
    (workspace / ".claude-k4").mkdir(parents=True)

    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {"is_error": False, "result": preflight._PERMISSION_CANARY_RESULT}
        )

    def _capturing_runner(argv, *, cwd, env, timeout, **kwargs):
        captured["argv"] = list(argv)
        (workspace / "k4-permission-edit.txt").write_text("CANARY_AFTER\n")
        (workspace / "k4-permission-write.txt").write_text("CANARY_WRITE_OK\n")
        return _Completed()

    monkeypatch.setattr(preflight.subprocess, "run", _capturing_runner)

    problems = preflight.probe_delivery_permissions(workspace, "claude-sonnet-5")

    assert problems == []
    assert "--safe-mode" in captured["argv"], (
        "the canary's real constructed argv must carry --safe-mode"
    )


def test_main_writes_the_real_delivery_arms_without_safe_mode(monkeypatch):
    """The real nWave/control delivery arms must NOT carry --safe-mode: their
    whole measured point is nWave's installed customizations, which
    --safe-mode disables. Guards against a future default-everywhere
    regression at the one call site `main` uses to build both arms."""
    arm_env = preflight._arm_env()
    argv = preflight.delivery_argv("claude-sonnet-5", arm_env["PATH"])

    assert "--safe-mode" not in argv
