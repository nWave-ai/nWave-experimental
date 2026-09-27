"""Every model turn leaves a diagnostic record, and nothing in DES reads it."""

from __future__ import annotations

import ast
import hashlib
import json
import multiprocessing
import os
import uuid
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.adapters.driven.task_invocation.codex_task_adapter import CodexTaskAdapter
from des.adapters.driven.task_invocation.turn_recorder import (
    RESERVED_RUN_ID_ENV,
    TURN_LOG_RELATIVE_DIR,
    TurnRecorder,
    _publish_no_replace,
    _write_exclusive,
    reserve_d0,
)
from des.domain.filesystem_projection import STRICT_DELIVERY_POLICY, ProjectionPolicy
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


def test_only_recorder_and_projection_policy_name_the_turn_log() -> None:
    """The recorder owns records; the projection owns their exclusion policy."""
    package = Path(__file__).resolve().parents[6] / "src" / "des"
    naming = sorted(
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if "logs/turns" in path.read_text(encoding="utf-8")
    )

    assert naming == [
        "adapters/driven/task_invocation/turn_recorder.py",
        "domain/filesystem_projection.py",
    ]

    writer = package / "adapters/driven/task_invocation/turn_recorder.py"
    tree = ast.parse(writer.read_text(encoding="utf-8"))
    # Reservation validation uses descriptor reads.  It must not treat an old
    # turn document as an input authority or use pathlib's replay helpers.
    reads = {"read_text", "read_bytes", "glob", "rglob", "listdir"}
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


def test_crafter_projection_preserves_binary_mode_link_and_delete(
    tmp_path: Path,
) -> None:
    """The native artifact is built from the canonical byte observer."""
    old = tmp_path / "gone"
    old.write_bytes(b"old")
    recorder = TurnRecorder(root=tmp_path)

    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    old.unlink()
    binary = tmp_path / "binary"
    binary.write_bytes(b"\x00\xff")
    binary.chmod(0o755)
    (tmp_path / "target").write_bytes(b"target")
    (tmp_path / "link").symlink_to("target")

    projection = recorder.finish(started=started, role_id="nw-software-crafter")

    assert projection["state"] == "captured"
    raw = (
        tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id / projection["path"]
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == projection["sha256"]
    document = json.loads(raw)
    transitions = {item["path"]: item for item in document["transitions"]}
    assert transitions["YmluYXJ5"]["after"]["mode"] == "100755"
    assert transitions["Z29uZQ=="]["after"] == {"kind": "absent"}
    assert transitions["bGluaw=="]["after"]["kind"] == "symlink"


@pytest.mark.parametrize("outcome", ["accepted", "rejected"])
def test_crafter_noop_is_captured_for_both_terminals(
    tmp_path: Path, outcome: str
) -> None:
    """No change is evidence, irrespective of the provider terminal."""
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")
    recorder.record(
        root=tmp_path,
        role_id="nw-software-crafter",
        prompt="craft",
        argv=None,
        outcome=outcome,
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
        producer_projection=projection,
    )
    document = json.loads(_records(tmp_path)[0].read_text(encoding="utf-8"))
    assert document["producer_projection"]["state"] == "captured"
    assert document["producer_projection"]["transition_count"] == 0


def test_bad_reserved_run_id_is_diagnostic_not_a_model_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RESERVED_RUN_ID_ENV, "not-a-uuid")
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")

    assert projection["state"] == "indeterminate"
    assert not (tmp_path / TURN_LOG_RELATIVE_DIR).exists()


def test_reserve_d0_binds_a_zero_high_water_run_to_the_child_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reservation = reserve_d0(tmp_path, ProjectionPolicy.native_capture())

    assert uuid.UUID(reservation.run_id).version == 4
    assert reservation.environment_delta == {RESERVED_RUN_ID_ENV: reservation.run_id}
    assert not list(reservation.directory.glob("*.sequence"))
    assert hashlib.sha256(
        (reservation.directory / "policy").read_bytes()
    ).hexdigest() == (reservation.policy_sha256)
    assert (
        hashlib.sha256((reservation.directory / "reservation").read_bytes()).hexdigest()
        == reservation.reservation_sha256
    )

    monkeypatch.setenv(RESERVED_RUN_ID_ENV, reservation.run_id)
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id=ROLE)
    assert started.problem is None
    assert recorder.run_id == reservation.run_id


def test_inherited_recorder_uses_the_reserved_strict_delivery_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reservation = reserve_d0(tmp_path, STRICT_DELIVERY_POLICY)
    fixture = tmp_path / "k4-fixture-venv" / "bin"
    fixture.mkdir(parents=True)
    (fixture / "python3.12").symlink_to("/usr/bin/python3.12")
    monkeypatch.setenv(RESERVED_RUN_ID_ENV, reservation.run_id)
    recorder = TurnRecorder(root=tmp_path)

    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    (tmp_path / "delivery.txt").write_text("delivery\n", encoding="utf-8")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")

    assert started.problem is None
    assert projection["state"] == "captured"
    raw = (reservation.directory / projection["path"]).read_text(encoding="utf-8")
    assert "k4-fixture-venv" not in raw
    assert "ZGVsaXZlcnkudHh0" in raw


def test_inherited_recorder_refuses_a_tampered_reserved_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reservation = reserve_d0(tmp_path, STRICT_DELIVERY_POLICY)
    (reservation.directory / "policy").write_bytes(b"{}\n")
    monkeypatch.setenv(RESERVED_RUN_ID_ENV, reservation.run_id)

    started = TurnRecorder(root=tmp_path).begin(root=tmp_path, role_id=ROLE)

    assert started.problem is not None
    assert "reserved projection policy" in started.problem


def test_inherited_recorder_refuses_noncanonical_reserved_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reservation = reserve_d0(tmp_path, STRICT_DELIVERY_POLICY)
    policy = reservation.directory / "policy"
    policy.write_bytes(b" " + policy.read_bytes())
    monkeypatch.setenv(RESERVED_RUN_ID_ENV, reservation.run_id)

    started = TurnRecorder(root=tmp_path).begin(root=tmp_path, role_id=ROLE)

    assert started.problem is not None
    assert "reserved projection policy is not canonical" in started.problem


def test_malformed_existing_turn_never_advances_sequence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = TurnRecorder(root=tmp_path)
    recorder.begin(root=tmp_path, role_id=ROLE)
    directory = tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id
    (directory / "01.sequence").write_bytes(b"")
    (directory / f"01-{ROLE}.json").write_bytes(b"not-json\n")

    assert (
        recorder.record(
            root=tmp_path,
            role_id=ROLE,
            prompt="no advance",
            argv=None,
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
            started_at=0,
            ended_at=0,
        )
        is None
    )
    assert "turn record is not JSON" in capsys.readouterr().err
    assert not (directory / f"02-{ROLE}.json").exists()


def test_tampered_projection_reference_never_publishes_its_turn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    (tmp_path / "change").write_bytes(b"a")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")
    path = tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id / projection["path"]
    path.write_bytes(b"{}\n")

    written = recorder.record(
        root=tmp_path,
        role_id="nw-software-crafter",
        prompt="craft",
        argv=None,
        outcome="accepted",
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
        producer_projection=projection,
    )

    assert written is None
    assert "hash differs" in capsys.readouterr().err


def test_boolean_transition_count_is_not_a_valid_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")
    projection["transition_count"] = True

    written = recorder.record(
        root=tmp_path,
        role_id="nw-software-crafter",
        prompt="craft",
        argv=None,
        outcome="accepted",
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
        producer_projection=projection,
    )

    assert written is None
    assert "does not name this sequence" in capsys.readouterr().err


def test_forged_symlink_mode_is_not_a_native_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    (tmp_path / "target").write_bytes(b"target")
    (tmp_path / "link").symlink_to("target")
    projection = recorder.finish(started=started, role_id="nw-software-crafter")
    path = tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id / projection["path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    link = next(item for item in payload["transitions"] if item["path"] == "bGluaw==")
    link["after"]["mode"] = "100644"
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw)
    projection["sha256"] = hashlib.sha256(raw).hexdigest()

    written = recorder.record(
        root=tmp_path,
        role_id="nw-software-crafter",
        prompt="craft",
        argv=None,
        outcome="accepted",
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
        producer_projection=projection,
    )

    assert written is None
    assert "symlink projection mode" in capsys.readouterr().err


def test_exclusive_writer_retries_short_writes_and_refuses_zero_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_write = os.write

    def short_write(descriptor: int, raw: bytes) -> int:
        return original_write(descriptor, raw[:1])

    monkeypatch.setattr(
        "des.adapters.driven.task_invocation.turn_recorder.os.write", short_write
    )
    path = tmp_path / "short"
    _write_exclusive(path, b"complete")
    assert path.read_bytes() == b"complete"

    monkeypatch.setattr(
        "des.adapters.driven.task_invocation.turn_recorder.os.write",
        lambda _descriptor, _raw: 0,
    )
    with pytest.raises(OSError, match="complete"):
        _write_exclusive(tmp_path / "zero", b"no")


def test_existing_projection_is_never_overwritten(tmp_path: Path) -> None:
    recorder = TurnRecorder(root=tmp_path)
    started = recorder.begin(root=tmp_path, role_id="nw-software-crafter")
    (tmp_path / "changed").write_bytes(b"first")
    first = recorder.finish(started=started, role_id="nw-software-crafter")
    assert first["state"] == "captured"
    path = tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id / first["path"]
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        _publish_no_replace(path, b"overwrite")
    assert path.read_bytes() == original


def _crafter_repo(root: Path) -> Path:
    spec = root / "nWave" / "agents" / "nw-software-crafter.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("---\nmodel: test\ntools: Edit\n---\ncraft\n", encoding="utf-8")
    return root


def test_claude_crafter_records_its_native_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _crafter_repo(tmp_path)

    def spawn(argv: list[str], **kwargs: object) -> CompletedProcess[str]:
        Path(str(kwargs["cwd"])).joinpath("claude.bin").write_bytes(b"\x00claude")
        return CompletedProcess(
            argv,
            0,
            '{"structured_output":{"outcome":"accepted","diagnostic":"done","blocked_by":null}}',
            "",
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", spawn)
    run = ClaudeCodeTaskAdapter(Path("/bin/claude")).invoke(
        role_id="nw-software-crafter", prompt="craft", cwd=root
    )

    document = json.loads(_records(root)[0].read_text(encoding="utf-8"))
    assert run.outcome.value == "accepted"
    assert document["producer_projection"]["state"] == "captured"
    assert document["sequence"] == 1


def test_codex_crafter_records_its_native_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _crafter_repo(tmp_path)

    def spawn(argv: list[str], **kwargs: object) -> CompletedProcess[str]:
        Path(str(kwargs["cwd"])).joinpath("codex.bin").write_bytes(b"\x00codex")
        terminal = Path(argv[argv.index("--output-last-message") + 1])
        terminal.write_text(
            '{"answer":{"outcome":"accepted","diagnostic":"done","blocked_by":null}}',
            encoding="utf-8",
        )
        return CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("des.runtime.spawn.spawn", spawn)
    run = CodexTaskAdapter(Path("/bin/codex"), model="test").invoke(
        role_id="nw-software-crafter", prompt="craft", cwd=root
    )

    document = json.loads(_records(root)[0].read_text(encoding="utf-8"))
    assert run.outcome.value == "accepted"
    assert document["producer_projection"]["state"] == "captured"
    assert document["sequence"] == 1


def _record_in_child(root: str, run_id: str) -> None:
    os.environ[RESERVED_RUN_ID_ENV] = run_id
    TurnRecorder(root=Path(root)).record(
        root=Path(root),
        role_id=ROLE,
        prompt="concurrent",
        argv=None,
        outcome="accepted",
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
    )


@pytest.mark.skipif(os.name == "nt", reason="fork probe is POSIX-specific")
def test_reserved_run_allocates_one_sequence_per_process(tmp_path: Path) -> None:
    """The on-disk lock, rather than process-local state, orders producers."""
    recorder = TurnRecorder(root=tmp_path)
    recorder.begin(root=tmp_path, role_id=ROLE)
    context = multiprocessing.get_context("fork")
    children = [
        context.Process(target=_record_in_child, args=(str(tmp_path), recorder.run_id))
        for _ in range(4)
    ]
    for child in children:
        child.start()
    for child in children:
        child.join()

    assert [child.exitcode for child in children] == [0, 0, 0, 0]
    assert [path.name[:2] for path in _records(tmp_path)] == ["01", "02", "03", "04"]


def test_orphaned_sequence_reservation_refuses_a_later_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = TurnRecorder(root=tmp_path)
    recorder.begin(root=tmp_path, role_id=ROLE)
    directory = tmp_path / TURN_LOG_RELATIVE_DIR / recorder.run_id
    (directory / "01.sequence").write_bytes(b"")

    written = recorder.record(
        root=tmp_path,
        role_id=ROLE,
        prompt="orphan",
        argv=None,
        outcome="accepted",
        diagnostic="done",
        exit_status=0,
        retry_safe=False,
        provider_stdout=None,
        provider_stderr=None,
        started_at=0,
        ended_at=0,
    )

    assert written is None
    assert "reservation has no published record" in capsys.readouterr().err
