"""Focused D0 runner and ledger checks.

Run: ``uv run pytest -q tests/scripts/analysis/test_d0_single_arm_campaign.py``
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from des.domain.filesystem_projection import FileState, GitPath, PathTransition
from scripts.analysis import blind_review, paired_campaign, single_arm_campaign
from scripts.analysis.k4 import (
    delivery_attribution,
    exercise_precondition,
    intervention_ledger,
)
from scripts.analysis.single_arm_campaign import main


@pytest.fixture(autouse=True)
def _isolated_single_arm_load_lock(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Give every test its own single-arm load-lock directory.

    Production takes the load lock at ``tempfile.gettempdir() /
    nwave-single-arm-campaign.lock`` deliberately — a real host-global lock
    that must serialise concurrent local D0 runs (see the comment at the
    lock's production call site). Under pytest-xdist, several tests in this
    module call :func:`single_arm_campaign.main` in parallel workers that all
    share the SAME real temp directory, so they collide on that host-global
    lock file and one worker's diagnostic spuriously reports "another local
    single-arm diagnostic holds the load lock" (CI run 35873792020, shard 4).
    That collision is a TEST-ISOLATION defect, not a production one: tests
    are not separate hosts and must not contend for a host-global resource.
    Patching only ``tempfile.gettempdir`` as observed by the production
    module gives each test invocation (each pytest-xdist worker, each test
    function) its own lock location without changing the production lock
    path, semantics, or call site.
    """
    lock_directory = tmp_path_factory.mktemp("single-arm-lock")
    monkeypatch.setattr(
        single_arm_campaign.tempfile, "gettempdir", lambda: str(lock_directory)
    )


def _git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _source_repo(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    _git("init", "-q", cwd=source)
    _git("config", "user.email", "test@example.com", cwd=source)
    _git("config", "user.name", "test", cwd=source)
    (source / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _git("add", "-A", cwd=source)
    _git("commit", "-q", "-m", "baseline", cwd=source)
    return source, _git("rev-parse", "HEAD", cwd=source)


def _fake_treatment_install(tmp_path: Path) -> Path:
    launcher = tmp_path / "bin" / "nwave-ai"
    launcher.parent.mkdir(exist_ok=True)
    launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    return launcher


def _transcript_profile(tmp_path: Path, name: str = "turn") -> Path:
    profile = tmp_path / f"profile-{name}"
    transcript = profile / "projects" / "opaque" / f"{name}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"turn": 1}\n', encoding="utf-8")
    return profile


def _minimal_diagnostic_arms_path(tmp_path: Path) -> Path:
    treatment_install = _fake_treatment_install(tmp_path)
    arms = {
        "task": "diagnostic task",
        "arms": {
            "nwave": {
                "setup": [
                    [str(treatment_install), "install", "--platform", "claude-code"]
                ],
                "argv": [sys.executable, "-c", "pass"],
            }
        },
    }
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(json.dumps(arms), encoding="utf-8")
    return arms_path


def test_load_lock_collision_reproduces_the_ci_observed_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same mechanism as the CI shard-4 failure, reproduced on demand.

    Two callers sharing ONE lock directory collide: whichever acquires the
    ``fcntl.flock`` first wins, the other gets the "holds the load lock"
    refusal. This is the exact collision the isolation fixture prevents
    between test WORKERS by giving each its own lock directory; it does not
    change (and must not change) the production within-host serialisation
    this lock exists for.
    """
    shared_lock_directory = tmp_path / "shared-host-tmp"
    shared_lock_directory.mkdir()
    monkeypatch.setattr(
        single_arm_campaign.tempfile, "gettempdir", lambda: str(shared_lock_directory)
    )
    holder = (shared_lock_directory / "nwave-single-arm-campaign.lock").open(
        "a+", encoding="utf-8"
    )
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        arms_path = _minimal_diagnostic_arms_path(tmp_path)
        exit_code = main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
    finally:
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
    assert exit_code == 2
    assert "holds the load lock" in capsys.readouterr().err


def test_isolation_fixture_redirects_the_lock_away_from_the_shared_host_tmp() -> None:
    """Control: production's own ``tempfile.gettempdir()`` call is redirected.

    ``tempfile`` is a process-global singleton module, so any test that also
    imports it observes the SAME patched ``gettempdir`` — there is no way to
    hold a lock at "the real /tmp" from inside a patched test to prove
    non-collision without colliding with itself. The observable, honest
    control is: production's lookup path (``single_arm_campaign.tempfile
    .gettempdir()``) resolves under THIS test's own pytest-xdist-unique
    base temp directory, never under a bare shared ``/tmp``.
    """
    lock_directory = Path(single_arm_campaign.tempfile.gettempdir())
    assert "single-arm-lock" in lock_directory.name
    assert lock_directory != Path("/tmp")


def test_reservation_environment_refuses_an_unequal_arm_collision(
    tmp_path: Path,
) -> None:
    arm = paired_campaign.ArmSpec(
        "nwave",
        (sys.executable, "-c", "raise SystemExit('must not spawn')"),
        env=(("NWAVE_DES_RESERVED_RUN_ID", "declared-other-run"),),
    )

    with pytest.raises(ValueError, match="conflicts with declared arm environment"):
        paired_campaign.execute_declared_arm_once(
            arm,
            task="x",
            run_dir=tmp_path / "run",
            timeout=1,
            before_delivery=lambda _workspace: {
                "NWAVE_DES_RESERVED_RUN_ID": "reserved-native-run"
            },
        )
    assert not (tmp_path / "run" / "nwave.json").exists()


def test_single_runner_touches_only_selected_arm_and_stays_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, baseline = _source_repo(tmp_path)
    treatment_install = _fake_treatment_install(tmp_path)
    control_sentinel = tmp_path / "control-touched"
    treatment_sentinel = tmp_path / "treatment-touched"
    transcript_root = tmp_path / "transcripts"
    transcript = transcript_root / "projects" / "opaque" / "turn.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"turn": 1}\n', encoding="utf-8")
    delivery_source = (
        "import json, pathlib; "
        f"pathlib.Path({str(treatment_sentinel)!r}).write_text('delivery'); "
        "print(json.dumps({'is_error': False, 'session_id': 'd0-session'}))"
    )
    arms = {
        "task": "diagnostic task",
        "arms": {
            "control": {
                "setup": [
                    [
                        sys.executable,
                        "-c",
                        f"open({str(control_sentinel)!r}, 'w').write('wrong arm')",
                    ]
                ],
                "argv": [sys.executable, "-c", delivery_source],
            },
            "nwave": {
                "setup": [
                    ["git", "clone", str(source), "."],
                    ["git", "checkout", "--detach", baseline],
                    [str(treatment_install), "install", "--platform", "claude-code"],
                ],
                "env": {"CLAUDE_CONFIG_DIR": str(transcript_root)},
                "task_prefix": "use nWave\n",
                "argv": [sys.executable, "-c", delivery_source],
            },
        },
    }
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(json.dumps(arms), encoding="utf-8")

    output = tmp_path / "out"
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(output),
            ]
        )
        == 1
    )

    observed = capsys.readouterr()
    rendered = observed.out + observed.err
    assert control_sentinel.exists() is False
    assert treatment_sentinel.exists()
    assert (
        intervention_ledger.verify(output / "run-1" / "ledger").classification
        == "INDETERMINATE"
    )
    assert (output / "run-1" / "specimen" / "delivery.json").is_file()
    references = json.loads(
        (output / "run-1" / "specimen" / "references.json").read_text(encoding="utf-8")
    )
    copied_transcript = references["transcripts"][0]
    assert "path" not in copied_transcript
    assert copied_transcript["specimen_path"].endswith(".jsonl")
    assert (
        output / "run-1" / "specimen" / copied_transcript["specimen_path"]
    ).read_bytes() == transcript.read_bytes()
    assert "ratio" not in rendered.lower()
    assert "ADMIT" not in rendered
    assert "CLASSIFICATION: INDETERMINATE" in rendered
    campaign = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
    assert campaign["state"] == "CLOSED"
    assert campaign["classification"] == "INDETERMINATE"
    assert campaign["declaration"]["task_prefix"] == "use nWave\n"
    request = output / "run-1" / "specimen" / "request"
    assert (request / "task-prefix.txt").read_text() == "use nWave\n"
    assert (request / "task.txt").read_text() == "diagnostic task"
    assert (request / "effective-request.txt").read_text() == (
        "use nWave\ndiagnostic task"
    )
    exercises = exercise_precondition.examine_campaign(output)
    assert len(exercises) == 1
    assert exercises[0].arm == "run-1/nwave"
    open_record = json.loads(
        (output / "run-1" / "ledger" / "open.json").read_text(encoding="utf-8")
    )
    assert {
        "single_arm_runner",
        "intervention_ledger",
        "exercise_precondition",
        "delivery_attribution",
    } <= set(open_record["payload"]["bound_instruments"])


def test_treatment_diagnostic_uses_the_public_strict_capture_api(
    tmp_path: Path,
) -> None:
    source, baseline = _source_repo(tmp_path)
    treatment_install = _fake_treatment_install(tmp_path)
    transcript_root = _transcript_profile(tmp_path)
    runtime_source = Path(__file__).resolve().parents[3] / "src"
    delivery_source = (
        "import json, pathlib, sys; "
        f"sys.path.insert(0, {str(runtime_source)!r}); "
        "from des.adapters.driven.task_invocation.turn_recorder import TurnRecorder; "
        "root = pathlib.Path('.'); fixture = root / 'k4-fixture-venv' / 'bin'; "
        "fixture.mkdir(parents=True); (fixture / 'python3.12').symlink_to('/usr/bin/python3.12'); "
        "recorder = TurnRecorder(root=root); "
        "started = recorder.begin(root=root, role_id='nw-software-crafter'); "
        "pathlib.Path('delivery.txt').write_text('delivery\\n'); "
        "projection = recorder.finish(started=started, role_id='nw-software-crafter'); "
        "recorder.record(root=root, role_id='nw-software-crafter', prompt='craft', "
        "argv=None, outcome='accepted', diagnostic='done', exit_status=0, "
        "retry_safe=False, provider_stdout=None, provider_stderr=None, "
        "started_at=0, ended_at=1, producer_projection=projection); "
        "pathlib.Path('unrelated.txt').write_text('unrelated\\n'); "
        "print(json.dumps({'is_error': False, 'session_id': 'strict-capture'}))"
    )
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(
        json.dumps(
            {
                "task": "diagnostic task",
                "arms": {
                    "nwave": {
                        "setup": [
                            ["git", "clone", str(source), "."],
                            ["git", "checkout", "--detach", baseline],
                            [
                                str(treatment_install),
                                "install",
                                "--platform",
                                "claude-code",
                            ],
                        ],
                        "env": {"CLAUDE_CONFIG_DIR": str(transcript_root)},
                        "argv": [sys.executable, "-c", delivery_source],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "out"
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    packet = output / "run-1" / "specimen" / "delivery-packet"
    assert sorted(path.name for path in packet.iterdir()) == [
        "DELIVERY-CHANGES.txt",
        "DELIVERY.patch",
    ]
    assert (
        intervention_ledger.verify(output / "run-1" / "ledger").classification
        == "DIAGNOSTIC"
    )
    attribution = output / "run-1" / "specimen" / "delivery-attribution-v2.json"
    assert attribution.is_file()
    assert (
        exercise_precondition.examine_campaign(output)[0].attributions[0].status
        == "ATTRIBUTED"
    )
    retained = json.loads(attribution.read_text(encoding="utf-8"))
    assert [item["path"] for item in retained["retained_transitions"]] == [
        GitPath(b"delivery.txt").base64
    ]
    assert {item["path"] for item in retained["strict_transitions"]} == {
        GitPath(b"delivery.txt").base64,
        GitPath(b"unrelated.txt").base64,
    }
    marker = next(
        item
        for item in retained["native_artifacts"]
        if item["source_name"] == "01.sequence"
    )
    marker_path = attribution.parent / marker["specimen_path"]
    marker_bytes = marker_path.read_bytes()
    marker_path.unlink()
    assert delivery_attribution.assess(attribution).status == "INDETERMINATE"
    marker_path.write_bytes(marker_bytes)

    ledger_root = output / "run-1" / "ledger"
    captured_path = next((ledger_root / "events").glob("000002-*.json"))
    captured = json.loads(captured_path.read_text(encoding="utf-8"))
    captured["payload"]["retained_transitions_sha256"] = "0" * 64
    captured["hash"] = intervention_ledger._record_hash(
        {key: value for key, value in captured.items() if key != "hash"}
    )
    captured_path.unlink()
    rewritten_capture = ledger_root / "events" / f"000002-{captured['hash']}.json"
    rewritten_capture.write_bytes(intervention_ledger._canonical(captured) + b"\n")
    close_path = ledger_root / "close.json"
    close = json.loads(close_path.read_text(encoding="utf-8"))
    close["previous_hash"] = captured["hash"]
    close["hash"] = intervention_ledger._record_hash(
        {key: value for key, value in close.items() if key != "hash"}
    )
    close_path.write_bytes(intervention_ledger._canonical(close) + b"\n")
    assert intervention_ledger.verify(ledger_root).classification == "DIAGNOSTIC"
    assert delivery_attribution.assess(attribution).status == "INDETERMINATE"


def test_retained_intersection_excludes_restored_and_unrelated_changes() -> None:
    baseline = FileState.regular(0o100644, 1, "a" * 64)
    crafted = FileState.regular(0o100644, 1, "b" * 64)
    unrelated = FileState.regular(0o100644, 1, "c" * 64)
    delivery = GitPath(b"delivery.txt")
    other = GitPath(b"unrelated.txt")
    producer = PathTransition.changed(delivery, baseline, crafted)
    restored_strict: tuple[PathTransition, ...] = ()
    assert (
        delivery_attribution._retained_intersection((producer,), restored_strict) == ()
    )

    strict_delivery = PathTransition.changed(delivery, baseline, crafted)
    strict_unrelated = PathTransition.changed(other, baseline, unrelated)
    retained = delivery_attribution._retained_intersection(
        (producer,), (strict_delivery, strict_unrelated)
    )
    assert retained == (producer,)
    assert delivery_attribution._retained_transition_values(retained) == [
        {
            "path": delivery.base64,
            "before": {
                "kind": "regular",
                "mode": "100644",
                "sha256": "a" * 64,
                "size": 1,
            },
            "after": {
                "kind": "regular",
                "mode": "100644",
                "sha256": "b" * 64,
                "size": 1,
            },
        }
    ]


def test_retained_transition_order_uses_raw_paths_not_base64_text() -> None:
    """The Base64 alphabet sorts ``+`` before ``0`` unlike the source bytes."""
    first = GitPath(b"\xd0")
    second = GitPath(b"\xf8")
    assert first.raw < second.raw
    assert first.base64 > second.base64
    after = FileState.regular(0o100644, 1, "a" * 64)
    transitions = (
        PathTransition.changed(first, FileState.absent(), after),
        PathTransition.changed(second, FileState.absent(), after),
    )
    values = delivery_attribution._retained_transition_values(transitions)
    assert [GitPath.from_base64(item["path"]).raw for item in values] == [
        b"\xd0",
        b"\xf8",
    ]
    round_tripped = tuple(
        PathTransition.changed(
            GitPath.from_base64(item["path"]),
            delivery_attribution._state(item["before"]),
            delivery_attribution._state(item["after"]),
        )
        for item in values
    )
    assert delivery_attribution._retained_transition_values(round_tripped) == values
    with pytest.raises(delivery_attribution.AttributionError, match="sorted"):
        delivery_attribution._retained_transition_values(tuple(reversed(transitions)))


def test_native_turn_rejects_a_forged_minimal_schema() -> None:
    with pytest.raises(delivery_attribution.AttributionError, match="invalid schema"):
        delivery_attribution._turn_projection(
            b'{"outcome":"accepted"}\n',
            run_id="00000000-0000-4000-8000-000000000000",
            sequence=1,
            role="nw-software-crafter",
            projection_raw=None,
        )


def test_native_members_refuse_extra_marker_and_orphan_projection(
    tmp_path: Path,
) -> None:
    specimen = tmp_path / "specimen"
    artifacts = specimen / "native-artifacts"
    artifacts.mkdir(parents=True)

    def retained(name: str, raw: bytes) -> dict[str, object]:
        digest = delivery_attribution._sha256(raw)
        (artifacts / digest).write_bytes(raw)
        return {
            "source_name": name,
            "specimen_path": f"native-artifacts/{digest}",
            "sha256": digest,
        }

    names = {
        item["source_name"]: item
        for item in (
            retained("reservation", b"reservation"),
            retained("policy", b"policy"),
            retained("01.sequence", b""),
            retained("01-nw-software-crafter.projection", b"{}\n"),
        )
    }
    with pytest.raises(
        delivery_attribution.AttributionError, match="orphan projection"
    ):
        delivery_attribution._validated_native_turns(
            names, specimen, "00000000-0000-4000-8000-000000000000"
        )


@pytest.mark.parametrize("kind", ["missing", "symlink"])
def test_native_artifacts_refuse_missing_or_symlink_lock(
    tmp_path: Path, kind: str
) -> None:
    workspace = tmp_path / "workspace"
    run_id = "00000000-0000-4000-8000-000000000000"
    directory = workspace / ".nwave/des/logs/turns" / run_id
    directory.mkdir(parents=True)
    if kind == "symlink":
        target = tmp_path / "lock-target"
        target.write_bytes(b"")
        (directory / ".sequence.lock").symlink_to(target)
    reservation = SimpleNamespace(run_id=run_id, directory=directory)
    with pytest.raises(delivery_attribution.AttributionError, match="sequence lock"):
        delivery_attribution._native_artifacts(
            workspace, reservation, tmp_path / "specimen"
        )


def test_native_artifacts_refuse_a_symlinked_reservation_directory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    run_id = "00000000-0000-4000-8000-000000000000"
    directory = workspace / ".nwave/des/logs/turns" / run_id
    directory.parent.mkdir(parents=True)
    target = tmp_path / "native-target"
    target.mkdir()
    directory.symlink_to(target, target_is_directory=True)
    reservation = SimpleNamespace(run_id=run_id, directory=directory)
    with pytest.raises(delivery_attribution.AttributionError, match="directory"):
        delivery_attribution._native_artifacts(
            workspace, reservation, tmp_path / "specimen"
        )


def test_ledger_rejects_reformatted_stored_record(tmp_path: Path) -> None:
    instrument = tmp_path / "instrument"
    instrument.write_text("stable\n", encoding="utf-8")
    ledger = intervention_ledger.open_ledger(
        tmp_path / "ledger", bound_instruments={"instrument": instrument}
    )
    ledger.close(classification="DIAGNOSTIC")
    open_record = json.loads((ledger.root / "open.json").read_text(encoding="utf-8"))
    (ledger.root / "open.json").write_text(
        json.dumps(open_record, indent=2) + "\n", encoding="utf-8"
    )
    assert intervention_ledger.verify(ledger.root).classification == "INDETERMINATE"


def test_exclusive_writers_complete_short_writes_and_refuse_zero_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_write = intervention_ledger.os.write

    def short_write(descriptor: int, raw: bytes) -> int:
        return original_write(descriptor, raw[:1])

    monkeypatch.setattr(intervention_ledger.os, "write", short_write)
    target = tmp_path / "short"
    intervention_ledger._publish_no_replace(target, b"complete")
    assert target.read_bytes() == b"complete"
    monkeypatch.setattr(intervention_ledger.os, "write", lambda _fd, _raw: 0)
    with pytest.raises(OSError, match="complete"):
        intervention_ledger._publish_no_replace(tmp_path / "zero", b"no")
    assert not (tmp_path / "zero").exists()


def test_d0_refuses_non_diagnostic_intent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "--arms",
                str(tmp_path / "unread.json"),
                "--arm",
                "nwave",
                "--intent",
                "measurement",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    observed = capsys.readouterr()
    refusal = observed.err
    assert "WHAT:" in refusal
    assert "WHY:" in refusal
    assert "HOW:" in refusal


def test_d0_refuses_a_control_arm_even_with_diagnostic_intent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(
        json.dumps(
            {
                "task": "diagnostic task",
                "arms": {"control": {"argv": [sys.executable, "-c", "pass"]}},
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "control",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert "not the declared treatment" in capsys.readouterr().err


@pytest.mark.parametrize("spoof", [{}, {"diagnostic": True}])
def test_d0_refuses_a_spoofed_nwave_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], spoof: dict[str, bool]
) -> None:
    arms_path = tmp_path / "arms.json"
    declared = {"argv": [sys.executable, "-c", "pass"], **spoof}
    arms_path.write_text(
        json.dumps({"task": "x", "arms": {"nwave": declared}}), encoding="utf-8"
    )
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert "not the declared treatment" in capsys.readouterr().err


def test_capture_failure_has_structured_diagnostic(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source, baseline = _source_repo(tmp_path)
    treatment_install = _fake_treatment_install(tmp_path)
    transcript_root = _transcript_profile(tmp_path)
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(
        json.dumps(
            {
                "task": "diagnostic task",
                "arms": {
                    "nwave": {
                        "setup": [
                            ["git", "clone", str(source), "."],
                            ["git", "checkout", "--detach", baseline],
                            [
                                str(treatment_install),
                                "install",
                                "--platform",
                                "claude-code",
                            ],
                        ],
                        "env": {"CLAUDE_CONFIG_DIR": str(transcript_root)},
                        "argv": [
                            sys.executable,
                            "-c",
                            "import json; print(json.dumps({'is_error': False, 'session_id': 'x'}))",
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def refused_capture(*_args, **_kwargs):
        raise RuntimeError("capture falsifier")

    monkeypatch.setattr(blind_review, "capture_delivery_packet", refused_capture)
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    observed = capsys.readouterr()
    refusal = observed.err
    assert "WHAT:" in refusal
    assert "WHY:" in refusal
    assert "HOW:" in refusal
    assert "CLASSIFICATION: INDETERMINATE" in observed.out
    campaign = json.loads(
        (tmp_path / "out" / "campaign.json").read_text(encoding="utf-8")
    )
    assert campaign["state"] == "CLOSED"
    assert campaign["classification"] == "INDETERMINATE"
    copied = tmp_path / "out" / "run-1" / "specimen" / "transcripts"
    assert list(copied.glob("*.jsonl"))


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("cleanup_failure", [None, "event", "close"])
def test_interrupt_closes_open_campaign_and_ledger(
    tmp_path: Path,
    monkeypatch,
    interrupt: type[BaseException],
    cleanup_failure: str | None,
) -> None:
    source, baseline = _source_repo(tmp_path)
    treatment_install = _fake_treatment_install(tmp_path)
    transcript_root = _transcript_profile(tmp_path)
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(
        json.dumps(
            {
                "task": "diagnostic task",
                "arms": {
                    "nwave": {
                        "setup": [
                            ["git", "clone", str(source), "."],
                            ["git", "checkout", "--detach", baseline],
                            [
                                str(treatment_install),
                                "install",
                                "--platform",
                                "claude-code",
                            ],
                        ],
                        "env": {"CLAUDE_CONFIG_DIR": str(transcript_root)},
                        "argv": [sys.executable, "-c", "raise AssertionError"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def interrupted_delivery(*_args, **_kwargs) -> bool:
        raise interrupt()

    monkeypatch.setattr(paired_campaign, "_run_delivery", interrupted_delivery)
    if cleanup_failure == "event":
        original_event = intervention_ledger.InterventionLedger.event

        def refusing_interruption_event(self, kind: str, **payload: object) -> None:
            if kind == "delivery_interrupted":
                raise OSError("event cleanup failure")
            original_event(self, kind, **payload)

        monkeypatch.setattr(
            intervention_ledger.InterventionLedger,
            "event",
            refusing_interruption_event,
        )
    if cleanup_failure == "close":

        def refusing_interruption_close(self, *, classification: str):
            if classification == "INDETERMINATE":
                raise OSError("close cleanup failure")
            raise AssertionError("unexpected ledger close classification")

        monkeypatch.setattr(
            intervention_ledger.InterventionLedger,
            "close",
            refusing_interruption_close,
        )
    output = tmp_path / "out"
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(output),
            ]
        )
        == 1
    )

    campaign = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
    assert campaign["state"] == "CLOSED"
    assert campaign["classification"] == "INDETERMINATE"
    assert interrupt.__name__ in campaign["failure"]
    if cleanup_failure is not None:
        assert (
            f"ledger interruption {cleanup_failure} failed: "
            f"OSError: {cleanup_failure} cleanup failure"
        ) in campaign["failure"]
    ledger_root = output / "run-1" / "ledger"
    if cleanup_failure == "close":
        assert not (ledger_root / "close.json").exists()
    else:
        assert (ledger_root / "close.json").is_file()
        assert intervention_ledger.verify(ledger_root).classification == "INDETERMINATE"
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ledger_root / "events").iterdir())
    ]
    if cleanup_failure == "event":
        assert events[-1]["kind"] == "delivery_started"
    else:
        assert events[-1]["kind"] == "delivery_interrupted"
        assert events[-1]["payload"]["interrupt"] == interrupt.__name__


def test_missing_treatment_transcript_is_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, baseline = _source_repo(tmp_path)
    treatment_install = _fake_treatment_install(tmp_path)
    arms_path = tmp_path / "arms.json"
    arms_path.write_text(
        json.dumps(
            {
                "task": "diagnostic task",
                "arms": {
                    "nwave": {
                        "setup": [
                            ["git", "clone", str(source), "."],
                            ["git", "checkout", "--detach", baseline],
                            [
                                str(treatment_install),
                                "install",
                                "--platform",
                                "claude-code",
                            ],
                        ],
                        "argv": [
                            sys.executable,
                            "-c",
                            "import json; print(json.dumps({'is_error': False, 'session_id': 'x'}))",
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--arms",
                str(arms_path),
                "--arm",
                "nwave",
                "--intent",
                "diagnostic",
                "--runs",
                "1",
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    observed = capsys.readouterr()
    assert "CLASSIFICATION: INDETERMINATE" in observed.out
    assert "transcript" in observed.err


def test_ledger_detects_tampering_bound_changes_and_events_after_close(
    tmp_path: Path,
) -> None:
    instrument = tmp_path / "instrument.py"
    instrument.write_text("first\n", encoding="utf-8")
    ledger = intervention_ledger.open_ledger(
        tmp_path / "ledger", bound_instruments={"instrument": instrument}
    )
    ledger.event("observed", value="one")
    ledger.close(classification="DIAGNOSTIC")
    assert intervention_ledger.verify(ledger.root).classification == "DIAGNOSTIC"
    assert (ledger.root / "open.json").is_file()
    assert (ledger.root / "close.json").is_file()
    event_paths = list((ledger.root / "events").iterdir())
    assert len(event_paths) == 1
    assert event_paths[0].name.startswith("000001-")

    with pytest.raises(RuntimeError, match="closed"):
        ledger.event("late")
    with pytest.raises(RuntimeError, match="closed"):
        intervention_ledger.InterventionLedger(ledger.root).event("late")
    close = json.loads((ledger.root / "close.json").read_text(encoding="utf-8"))
    late = {
        "sequence": close["sequence"] + 1,
        "kind": "late",
        "previous_hash": close["hash"],
        "payload": {},
    }
    late["hash"] = intervention_ledger._record_hash(late)
    (ledger.root / "events" / f"{late['sequence']:06d}-{late['hash']}.json").write_text(
        intervention_ledger._canonical(late).decode("utf-8") + "\n", encoding="utf-8"
    )
    after_close = intervention_ledger.verify(ledger.root)
    assert after_close.classification == "INDETERMINATE"
    assert "event follows close" in after_close.problems

    second = intervention_ledger.open_ledger(
        tmp_path / "ledger-2", bound_instruments={"instrument": instrument}
    )
    instrument.write_text("changed\n", encoding="utf-8")
    verdict = second.close(classification="DIAGNOSTIC")
    assert verdict.classification == "INDETERMINATE"
    close_check = json.loads((second.root / "close.json").read_text(encoding="utf-8"))
    assert (
        close_check["payload"]["instrument_check"]["instrument"]["status"] == "CHANGED"
    )

    stable = intervention_ledger.open_ledger(
        tmp_path / "ledger-stable", bound_instruments={"instrument": instrument}
    )
    stable.close(classification="DIAGNOSTIC")
    instrument.write_text("changed after closure\n", encoding="utf-8")
    assert intervention_ledger.verify(stable.root).classification == "DIAGNOSTIC"

    third = intervention_ledger.open_ledger(
        tmp_path / "ledger-3", bound_instruments={"instrument": instrument}
    )
    third.event("observed", value="one")
    third.close(classification="DIAGNOSTIC")
    event = next((third.root / "events").iterdir())
    content = event.read_text(encoding="utf-8")
    event.write_text(content.replace('"one"', '"two"'), encoding="utf-8")
    assert intervention_ledger.verify(third.root).classification == "INDETERMINATE"
