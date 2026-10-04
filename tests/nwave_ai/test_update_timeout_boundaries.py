"""Real escaped-pipe cleanup and advisory admission failure boundaries."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX fork and setsid")
def test_escaped_pipe_cannot_hold_update_cleanup_or_lock_forever(
    tmp_path: Path,
) -> None:
    """A real escaped writer survives killpg, but cannot hide the refusal."""
    home = tmp_path / "home"
    home.mkdir()
    pid_file = tmp_path / "escaped.pid"
    installer = tmp_path / "nwave-ai"
    installer.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, time\n"
        "if os.fork() == 0:\n"
        "    os.setsid()\n"
        f"    pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "    os._exit(0)\n"
        "print('replace-package: started', flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    installer.chmod(0o755)
    # Only clocks are substituted; processes, pipes and file locks are real.
    script = f"""
import json, sys
from dataclasses import asdict, replace
from pathlib import Path
from des.domain import update_timing
from des.adapters.driven.activity.session_registry import SessionActivityRegistry
from nwave_ai.update import process_control
from nwave_ai.update.service import UpdateService
clock = replace(update_timing.UPDATE_TIMING, stage_seconds=1.0,
                pipe_drain_seconds=0.2, reap_seconds=0.2, margin_seconds=0.2)
update_timing.UPDATE_TIMING = process_control.UPDATE_TIMING = clock
registry = SessionActivityRegistry(Path({str(home)!r}))
with registry.exclusive(0) as acquired:
    assert acquired
    result = UpdateService()._run_stage('replace-package', ({str(installer)!r},))
    outcome = asdict(result)
with registry.exclusive(0) as reacquired:
    print(json.dumps({{'outcome': outcome, 'lock_reacquired': reacquired}}))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=os.environ
            | {
                "HOME": str(home),
                "NWAVE_AGENTS_HOME": str(home),
                "PYTHONPATH": f"{REPO / 'src'}:{REPO}",
            },
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert observed["lock_reacquired"], "bounded cleanup retained the update lock"
        assert pid_file.exists(), "the escaped writer did not reach the pipe boundary"
        os.kill(int(pid_file.read_text()), 0)
        outcome = observed["outcome"]
        assert outcome["state"] == "refused"
        assert outcome["termination_unknown"] is True
        assert outcome["completed_stages"] == []
        detail = outcome["cause"]
        assert "unknown" in detail and "escaped descendant" in detail
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize("boundary", ["inactive-project", "unavailable-notice"])
def test_admission_timeout_warning_survives_activation_and_notice_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    boundary: str,
) -> None:
    from des.adapters.driven.activity.session_registry import SessionActivityRegistry
    from des.adapters.drivers.hooks import (
        hook_router,
        session_lifecycle_handler,
        session_start_notice_handler,
    )

    home, root = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    root.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.chdir(root)
    registry = SessionActivityRegistry(home)
    monkeypatch.setattr(
        SessionActivityRegistry, "selected", classmethod(lambda cls: registry)
    )
    monkeypatch.setattr(session_lifecycle_handler, "REGISTRATION_WAIT_SECONDS", 0.01)
    envelope = json.dumps(
        {"session_id": "waiting", "source": "startup", "cwd": str(root)}
    )
    with registry.exclusive(0) as acquired:
        assert acquired
        if boundary == "inactive-project":
            monkeypatch.setattr(sys, "argv", ["hook", "session-start"])
            monkeypatch.setattr(sys, "stdin", io.StringIO(envelope))
            with pytest.raises(SystemExit) as stopped:
                hook_router.main()
            assert stopped.value.code == 0  # Advisory, not proof of host blocking.
        else:
            monkeypatch.setattr(
                session_start_notice_handler, "_read_route_notice", lambda: None
            )
            registration = session_lifecycle_handler.register_session_start(
                envelope, "claude-code"
            )
            assert registration.admission_state == "busy" and not registration.admitted
            assert session_start_notice_handler.handle_session_start(registration) == 0
    captured = capsys.readouterr()
    reply = json.loads(captured.out)
    warning = reply["hookSpecificOutput"]["additionalContext"]
    assert "admission timed out" in warning
    assert reply["systemMessage"] == warning
    assert "admission timed out" in captured.err
    assert [record.host for record in registry.sessions()] == ["claude-code"]


def test_malformed_update_marker_produces_explicit_failed_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from des.adapters.driven.activity.session_registry import SessionActivityRegistry
    from des.adapters.drivers.hooks.session_lifecycle_handler import (
        register_session_start,
    )

    registry = SessionActivityRegistry(tmp_path)
    registry.in_progress_path.parent.mkdir(parents=True)
    registry.in_progress_path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(
        SessionActivityRegistry, "selected", classmethod(lambda cls: registry)
    )
    registration = register_session_start(
        json.dumps({"session_id": "after-crash", "cwd": str(tmp_path)}), "claude-code"
    )
    assert registration.admission_state == "update-incomplete"
    assert not registration.admitted and registration.key is not None
    assert "unknown" in registration.notice
