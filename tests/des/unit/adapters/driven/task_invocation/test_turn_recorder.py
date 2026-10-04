"""Every model turn leaves a diagnostic record, and nothing in DES reads it."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import uuid
from pathlib import Path

import pytest

from des.adapters.driven.task_invocation.turn_recorder import (
    RESERVED_RUN_ID_ENV,
    TURN_LOG_RELATIVE_DIR,
    IssuedTurn,
    TurnRecorder,
    TurnResult,
    TurnTiming,
    _publish_no_replace,
    _write_exclusive,
    reserve_d0,
)
from des.domain.filesystem_projection import STRICT_DELIVERY_POLICY, ProjectionPolicy


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


def _malformed_launcher(directory: Path) -> Path:
    """A real launcher whose stdout is not the enforced envelope."""
    launcher = directory / "malformed-claude"
    launcher.write_text(
        "#!/usr/bin/env python3\nprint('not the envelope')\n", encoding="utf-8"
    )
    launcher.chmod(0o755)
    return launcher


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
        turn=IssuedTurn(
            root=tmp_path, role_id="nw-software-crafter", prompt="craft", argv=None
        ),
        result=TurnResult(
            outcome=outcome,
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
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
            turn=IssuedTurn(
                root=tmp_path, role_id=ROLE, prompt="no advance", argv=None
            ),
            result=TurnResult(
                outcome="accepted",
                diagnostic="done",
                exit_status=0,
                retry_safe=False,
                provider_stdout=None,
                provider_stderr=None,
            ),
            timing=TurnTiming(started_at=0, ended_at=0),
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
        turn=IssuedTurn(
            root=tmp_path, role_id="nw-software-crafter", prompt="craft", argv=None
        ),
        result=TurnResult(
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
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
        turn=IssuedTurn(
            root=tmp_path, role_id="nw-software-crafter", prompt="craft", argv=None
        ),
        result=TurnResult(
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
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
        turn=IssuedTurn(
            root=tmp_path, role_id="nw-software-crafter", prompt="craft", argv=None
        ),
        result=TurnResult(
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
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


def _record_in_child(root: str, run_id: str) -> None:
    os.environ[RESERVED_RUN_ID_ENV] = run_id
    TurnRecorder(root=Path(root)).record(
        turn=IssuedTurn(root=Path(root), role_id=ROLE, prompt="concurrent", argv=None),
        result=TurnResult(
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
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
        turn=IssuedTurn(root=tmp_path, role_id=ROLE, prompt="orphan", argv=None),
        result=TurnResult(
            outcome="accepted",
            diagnostic="done",
            exit_status=0,
            retry_safe=False,
            provider_stdout=None,
            provider_stderr=None,
        ),
        timing=TurnTiming(started_at=0, ended_at=0),
    )

    assert written is None
    assert "reservation has no published record" in capsys.readouterr().err
