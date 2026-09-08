"""Every model turn leaves a diagnostic record, and nothing in DES reads it."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.adapters.driven.task_invocation.turn_recorder import TURN_LOG_RELATIVE_DIR
from des.ports.driven_ports.task_invocation_port import MalformedModelEnvelope
from tests.des.unit.adapters.driven.task_invocation.test_claude_code_task_adapter import (
    _fake_launcher,
    _repo_with_spec,
)


#: Any role will do -- recording is role-agnostic -- so this one is chosen for
#: carrying NO payload: a role whose envelope grows a field would make these
#: tests fail for a reason that has nothing to do with the recorder.
#:
#: It moved once, and the note above is why it moved cleanly. It was the
#: whole-diff reviewer until ADR-DES-003 §5 retired the pre-craft oracle judge
#: and made that reviewer the oracle's only independent judge, so its envelope
#: grew the ownership word `defect_owner`. The source-blind examiner carries no
#: payload and is the current choice.
ROLE = "nw-user-examiner"


def _records(root: Path) -> list[Path]:
    return sorted((root / TURN_LOG_RELATIVE_DIR).rglob("*.json"))


def test_every_turn_is_recorded_as_a_diagnostic_document(tmp_path: Path) -> None:
    """A run that leaves no trace cannot be read by a human or replayed."""
    root = _repo_with_spec(tmp_path, ROLE)
    adapter = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path))

    run = adapter.invoke(role_id=ROLE, prompt="review this", cwd=root)

    written = _records(root)
    assert [path.name for path in written] == [f"01-{ROLE}.json"]
    assert written[0].parent.name == adapter.run_id
    document = json.loads(written[0].read_text(encoding="utf-8"))
    assert document["role_id"] == ROLE
    assert document["prompt"] == "review this"
    assert document["outcome"] == run.outcome.value
    assert document["diagnostic"] == run.diagnostic
    assert document["exit_status"] == run.exit_status
    assert document["retry_safe"] == run.retry_safe
    assert document["sequence"] == 1
    # The raw provider envelope, recorded and never re-parsed into a decision.
    assert json.loads(document["provider_stdout"])["structured_output"]["outcome"]
    assert document["provider_stderr"] == ""
    assert document["duration_seconds"] >= 0
    assert document["started_at"].endswith("Z")
    assert document["ended_at"].endswith("Z")
    # argv is recorded whole, which is only safe because the prompt left it.
    assert "-p" in document["argv"]
    assert "review this" not in document["argv"]


def test_a_turn_refused_before_any_spawn_is_recorded_too(tmp_path: Path) -> None:
    """The refusals that cost nothing are the ones a reader most needs explained."""
    root = tmp_path / "repo"
    root.mkdir()
    adapter = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path))

    run = adapter.invoke(role_id="nw-absent-role", prompt="classify", cwd=root)

    written = _records(root)
    assert [path.name for path in written] == ["01-nw-absent-role.json"]
    document = json.loads(written[0].read_text(encoding="utf-8"))
    assert document["argv"] is None
    assert document["provider_stdout"] is None
    assert document["outcome"] == run.outcome.value
    assert document["diagnostic"] == run.diagnostic


def test_turns_are_numbered_in_order_within_one_run(tmp_path: Path) -> None:
    """The order IS the run: a replay reads these files in name order."""
    root = _repo_with_spec(tmp_path, ROLE)
    adapter = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path))

    adapter.invoke(role_id=ROLE, prompt="first", cwd=root)
    adapter.invoke(role_id=ROLE, prompt="second", cwd=root)

    written = _records(root)
    assert [path.name for path in written] == [
        f"01-{ROLE}.json",
        f"02-{ROLE}.json",
    ]
    assert [
        json.loads(path.read_text(encoding="utf-8"))["prompt"] for path in written
    ] == ["first", "second"]


def test_a_hundred_kilobyte_prompt_is_recorded_whole(tmp_path: Path) -> None:
    """A silently shortened record is a replay that diverges from its run."""
    root = _repo_with_spec(tmp_path, ROLE)
    prompt = "x" * (100 * 1024)

    ClaudeCodeTaskAdapter(_fake_launcher(tmp_path)).invoke(
        role_id=ROLE, prompt=prompt, cwd=root
    )

    document = json.loads(_records(root)[0].read_text(encoding="utf-8"))
    assert document["prompt"] == prompt


def test_a_failed_recording_is_a_stderr_line_and_never_an_outcome(
    tmp_path: Path, capsys
) -> None:
    """A diagnostic that can fail a delivery is worse than no diagnostic."""
    root = _repo_with_spec(tmp_path, ROLE)
    # The log directory's parent is a FILE, so every write under it fails.
    blocked = root / TURN_LOG_RELATIVE_DIR
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text("not a directory", encoding="utf-8")

    run = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path)).invoke(
        role_id=ROLE, prompt="review this", cwd=root
    )

    assert run.outcome.value == "accepted"
    assert run.exit_status == 0
    assert "could not record turn 1" in capsys.readouterr().err


def test_nothing_in_des_reads_the_turn_log() -> None:
    """The property, on two axes, because one is not locally inspectable.

    Axis 1, the whole package: only the writer names the directory at all.
    Axis 2, the writer's own AST: it performs no read operation, so naming the
    path there cannot smuggle a reader in behind the string check.
    """
    package = Path(__file__).resolve().parents[6] / "src" / "des"
    naming = sorted(
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if "logs/turns" in path.read_text(encoding="utf-8")
    )

    assert naming == ["adapters/driven/task_invocation/turn_recorder.py"]

    writer = package / "adapters/driven/task_invocation/turn_recorder.py"
    tree = ast.parse(writer.read_text(encoding="utf-8"))
    reads = {"read_text", "read_bytes", "open", "iterdir", "glob", "rglob", "listdir"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called & reads == set()


def test_every_turn_of_one_run_lands_in_the_runs_own_root(tmp_path: Path) -> None:
    """Measured 2026-09-05: recording per-cwd lost a turn.

    The implementation reviewer runs with the CANDIDATE WORKTREE as its cwd, so
    a per-cwd recorder split one run across two roots and the cleanup destroyed
    the half in the candidate: a full Success left records 01..05 and 07, with
    the reviewer's turn simply gone. A replay built from that is a different run.
    """
    root = _repo_with_spec(tmp_path / "run-root", ROLE)
    elsewhere = _repo_with_spec(tmp_path / "candidate", ROLE)
    adapter = ClaudeCodeTaskAdapter(_fake_launcher(tmp_path), record_root=root)

    adapter.invoke(role_id=ROLE, prompt="first", cwd=root)
    adapter.invoke(role_id=ROLE, prompt="in the candidate", cwd=elsewhere)

    assert [path.name for path in _records(root)] == [
        f"01-{ROLE}.json",
        f"02-{ROLE}.json",
    ]
    assert _records(elsewhere) == []


def _malformed_launcher(directory: Path) -> Path:
    """A real launcher whose stdout is not the enforced envelope."""
    launcher = directory / "malformed-claude"
    launcher.write_text(
        "#!/usr/bin/env python3\nprint('not the envelope')\n", encoding="utf-8"
    )
    launcher.chmod(0o755)
    return launcher


def test_a_turn_that_raises_a_malformed_envelope_is_still_recorded(
    tmp_path: Path,
) -> None:
    """A turn that RAISES is the one a reader most needs, and it cost real money.

    `extract_model_run` raises out of the turn, so recording only the returned
    `ModelRun` recorded nothing at all for the provider runs that went wrong.
    """
    root = _repo_with_spec(tmp_path, ROLE)

    with pytest.raises(MalformedModelEnvelope):
        ClaudeCodeTaskAdapter(_malformed_launcher(tmp_path)).invoke(
            role_id=ROLE, prompt="review this", cwd=root
        )

    written = _records(root)
    assert [path.name for path in written] == [f"01-{ROLE}.json"]
    document = json.loads(written[0].read_text(encoding="utf-8"))
    assert document["raised"] == "MalformedModelEnvelope"
    assert document["outcome"] == "indeterminate"
    assert document["prompt"] == "review this"
    assert "not the envelope" in document["provider_stdout"]


def test_a_turn_whose_provider_never_started_is_still_recorded(tmp_path: Path) -> None:
    """This is run 12's own failure: `[Errno 7] Argument list too long`.

    The spawn raised OSError before any provider existed, and the lane that
    exists to explain that failure recorded nothing about it.
    """
    root = _repo_with_spec(tmp_path, ROLE)

    with pytest.raises(OSError):
        ClaudeCodeTaskAdapter(tmp_path / "absent-claude").invoke(
            role_id=ROLE, prompt="review this", cwd=root
        )

    document = json.loads(_records(root)[0].read_text(encoding="utf-8"))
    assert document["raised"] == "FileNotFoundError"
    assert document["outcome"] == "indeterminate"
    assert document["exit_status"] == -1
    assert document["retry_safe"] is False
    assert document["provider_stdout"] is None


def test_a_turn_that_returns_records_no_raise_marker(tmp_path: Path) -> None:
    """The falsifier: an ordinary turn must not look like a raised one."""
    root = _repo_with_spec(tmp_path, ROLE)

    ClaudeCodeTaskAdapter(_fake_launcher(tmp_path)).invoke(
        role_id=ROLE, prompt="review this", cwd=root
    )

    assert json.loads(_records(root)[0].read_text(encoding="utf-8"))["raised"] is None
