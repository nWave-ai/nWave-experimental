"""Pair barrier and delivery-only runner in `paired_campaign`.

Focused on the four behaviours the cutover changed:

* one arm's setup failing must not let its peer's delivery start, and must not
  start pair 2;
* both setups must complete before either delivery starts;
* a delivery's detached child must not outlive the runner;
* a delivery that is not valid JSON / is `is_error` / has no `session_id`
  must fail the pair and stop the campaign before the next pair.

Every fake "claude" is a small Python script invoked via `sys.executable`, so
no PATH lookup or shell is involved.
"""

from __future__ import annotations

import json
import os
import sys
import time

import pytest

from scripts.analysis.paired_campaign import ArmSpec, main


def _setup_step(marker: str) -> list[str]:
    return [sys.executable, "-c", f"open({marker!r}, 'w').write('done')"]


def _ok_setup_arm(name: str, marker_path) -> ArmSpec:
    return ArmSpec(
        name=name,
        argv=(sys.executable, "-c", _OK_DELIVERY_SRC, "{task}"),
        setup=(tuple(_setup_step(str(marker_path))),),
    )


def _failing_setup_arm(name: str) -> ArmSpec:
    return ArmSpec(
        name=name,
        argv=(sys.executable, "-c", _OK_DELIVERY_SRC, "{task}"),
        setup=((sys.executable, "-c", "import sys; sys.exit(1)"),),
    )


_OK_DELIVERY_SRC = (
    "import json, sys\n"
    "print(json.dumps({'is_error': False, 'session_id': 'sess-1', "
    "'result': sys.argv[1]}))\n"
)


def _write_arms(tmp_path, arm_a: ArmSpec, arm_b: ArmSpec, artifact=None) -> None:
    def _dump(arm: ArmSpec) -> dict:
        return {"setup": [list(s) for s in arm.setup], "argv": list(arm.argv)}

    payload = {
        "task": "do the thing",
        "arms": {arm_a.name: _dump(arm_a), arm_b.name: _dump(arm_b)},
    }
    if artifact is not None:
        payload["artifact"] = artifact
    (tmp_path / "arms.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _fake_auth_probe(monkeypatch):
    monkeypatch.setattr(
        "scripts.analysis.paired_campaign._auth_is_live", lambda: (True, "ok")
    )


def test_one_setup_fails_peer_delivery_sentinel_absent_and_pair_two_absent(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "control-setup-done"
    arm_control = _ok_setup_arm("control", marker)
    arm_treatment = _failing_setup_arm("treatment")
    _write_arms(tmp_path, arm_control, arm_treatment)

    out_dir = tmp_path / "campaign"
    code = main(
        [
            "--arms",
            str(tmp_path / "arms.json"),
            "--pairs",
            "2",
            "--out",
            str(out_dir),
        ]
    )

    assert code != 0
    pair_1 = out_dir / "pair-1"
    assert marker.exists(), "the successful arm's setup did run"
    assert not (pair_1 / "control.json").exists()
    assert not (pair_1 / "control.err").exists()
    assert (pair_1 / "treatment.json").exists()
    assert (pair_1 / "treatment.err").read_text().startswith("SETUP FAILED")
    assert not (out_dir / "pair-2").exists()


def test_both_setups_pass_deliveries_exist_only_after_both_setup_sentinels(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    marker_a = tmp_path / "a-setup-done"
    marker_b = tmp_path / "b-setup-done"
    arm_a = _ok_setup_arm("control", marker_a)
    arm_b = _ok_setup_arm("treatment", marker_b)
    artifact = {"kind": "wheel", "sha256": "a" * 64}
    _write_arms(tmp_path, arm_a, arm_b, artifact=artifact)

    out_dir = tmp_path / "campaign"
    code = main(
        ["--arms", str(tmp_path / "arms.json"), "--pairs", "1", "--out", str(out_dir)]
    )

    assert code == 0
    pair_1 = out_dir / "pair-1"
    assert json.loads((out_dir / "campaign.json").read_text())["artifact"] == artifact
    for name, marker in (("control", marker_a), ("treatment", marker_b)):
        setup_sentinel = pair_1 / f"{name}.setup.json"
        delivery_sentinel = pair_1 / f"{name}.json"
        assert marker.exists()
        assert setup_sentinel.exists()
        assert delivery_sentinel.exists()
        assert setup_sentinel.stat().st_mtime <= delivery_sentinel.stat().st_mtime
        payload = json.loads(delivery_sentinel.read_text())
        assert payload["session_id"] == "sess-1"
        assert payload["is_error"] is False


def test_delivery_child_process_group_is_gone_after_runner_returns(
    tmp_path, monkeypatch
):
    """The spawned child stays IN the runner's own process group (no
    `start_new_session`) and has its pipes redirected to DEVNULL, so it
    neither escapes the group `_run_delivery` kills nor keeps the parent's
    `communicate()` blocked on an inherited pipe. It sleeps 120s; the assertion
    is that the runner returns promptly (well under the 120s sleep) with the
    child's PID gone -- proof of cleanup, not of the child exiting on its own.
    """
    monkeypatch.chdir(tmp_path)
    pid_file = tmp_path / "child.pid"
    spawn_src = (
        "import json, os, subprocess, sys, time\n"
        f"pid_file = {str(pid_file)!r}\n"
        "child = subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(120)'],\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        ")\n"
        "open(pid_file, 'w').write(str(child.pid))\n"
        "print(json.dumps({'is_error': False, 'session_id': 'sess-2'}))\n"
    )
    arm = ArmSpec(name="control", argv=(sys.executable, "-c", spawn_src, "{task}"))
    peer = ArmSpec(
        name="treatment", argv=(sys.executable, "-c", _OK_DELIVERY_SRC, "{task}")
    )
    _write_arms(tmp_path, arm, peer)

    out_dir = tmp_path / "campaign"
    started = time.monotonic()
    code = main(
        ["--arms", str(tmp_path / "arms.json"), "--pairs", "1", "--out", str(out_dir)]
    )
    elapsed = time.monotonic() - started

    assert code == 0
    assert elapsed < 5, "runner must return promptly, not wait out the child's sleep"
    payload = json.loads((out_dir / "pair-1" / "control.json").read_text())
    assert payload["session_id"] == "sess-2"
    child_pid = int(pid_file.read_text())
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_nonzero_exit_with_apparently_valid_json_is_invalid_and_stops_pair_two(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    nonzero_but_valid_looking_src = (
        "import json, sys\n"
        "print(json.dumps({'is_error': False, 'session_id': 'sess-1'}))\n"
        "sys.exit(3)\n"
    )
    bad_arm = ArmSpec(
        name="control",
        argv=(sys.executable, "-c", nonzero_but_valid_looking_src, "{task}"),
    )
    good_arm = ArmSpec(
        name="treatment", argv=(sys.executable, "-c", _OK_DELIVERY_SRC, "{task}")
    )
    _write_arms(tmp_path, bad_arm, good_arm)

    out_dir = tmp_path / "campaign"
    code = main(
        ["--arms", str(tmp_path / "arms.json"), "--pairs", "2", "--out", str(out_dir)]
    )

    assert code != 0
    payload = json.loads((out_dir / "pair-1" / "control.json").read_text())
    assert payload["session_id"] == "sess-1"
    assert not (out_dir / "pair-2").exists()


_BAD_DELIVERY_CASES = {
    "not_json": "print('not json at all')",
    "is_error_true": (
        "import json; print(json.dumps({'is_error': True, 'session_id': 's', "
        "'result': 'boom'}))"
    ),
    "missing_session_id": "import json; print(json.dumps({'is_error': False}))",
    "empty_session_id": (
        "import json; print(json.dumps({'is_error': False, 'session_id': ''}))"
    ),
    "non_object_json": "print('[1, 2, 3]')",
}


@pytest.mark.parametrize("case", sorted(_BAD_DELIVERY_CASES))
def test_invalid_delivery_makes_main_nonzero_and_stops_pair_two(
    tmp_path, monkeypatch, case
):
    monkeypatch.chdir(tmp_path)
    bad_src = _BAD_DELIVERY_CASES[case]
    bad_arm = ArmSpec(name="control", argv=(sys.executable, "-c", bad_src, "{task}"))
    good_arm = ArmSpec(
        name="treatment", argv=(sys.executable, "-c", _OK_DELIVERY_SRC, "{task}")
    )
    _write_arms(tmp_path, bad_arm, good_arm)

    out_dir = tmp_path / "campaign"
    code = main(
        ["--arms", str(tmp_path / "arms.json"), "--pairs", "2", "--out", str(out_dir)]
    )

    assert code != 0
    assert not (out_dir / "pair-2").exists()
