"""K4 matrix row 21 -- correlated resource wall.

First divergence: both arms drew on ONE shared credit/quota pool, and
exhaustion hit them in a correlated way mid-pair, invalidating the pair.

ADMISSION falsifier: a planted exhausted-quota arm must make the pairing
script REFUSE to start -- never run a pair degraded. Checked per arm,
through that arm's own declared env, BEFORE `campaign.json` is written or
any pair begins.

Every fake "claude" here is a small Python script invoked via
`sys.executable`, matching `test_paired_campaign_pair_barrier.py`'s
convention -- no live provider call, no cost. What genuinely cannot be
proven locally (whether a REAL provider account has headroom) stays
INDETERMINATE; this suite proves the refusal MECHANISM, not live quota.
"""

from __future__ import annotations

import json
import sys

import pytest

from scripts.analysis.paired_campaign import (
    ArmSpec,
    _arm_headroom_is_sufficient,
    main,
)


def _healthy_arm(name: str) -> ArmSpec:
    src = (
        "import json, sys\n"
        "print(json.dumps({'is_error': False, 'session_id': 'sess-1', "
        "'result': sys.argv[1]}))\n"
    )
    return ArmSpec(name=name, argv=(sys.executable, "-c", src, "{task}"))


def _exhausted_arm(name: str) -> ArmSpec:
    src = (
        "import json\n"
        "print(json.dumps({'is_error': True, "
        "'result': 'Credit balance is too low'}))\n"
    )
    return ArmSpec(name=name, argv=(sys.executable, "-c", src, "{task}"))


def _unrelated_error_arm(name: str) -> ArmSpec:
    src = (
        "import json\n"
        "print(json.dumps({'is_error': True, "
        "'result': 'network unreachable'}))\n"
    )
    return ArmSpec(name=name, argv=(sys.executable, "-c", src, "{task}"))


def _write_arms(tmp_path, arm_a: ArmSpec, arm_b: ArmSpec) -> None:
    payload = {
        "task": "do the thing",
        "arms": {
            arm_a.name: {"setup": [], "argv": list(arm_a.argv)},
            arm_b.name: {"setup": [], "argv": list(arm_b.argv)},
        },
    }
    (tmp_path / "arms.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(autouse=True)
def _fake_auth_probe(monkeypatch):
    monkeypatch.setattr(
        "scripts.analysis.paired_campaign._auth_is_live", lambda: (True, "ok")
    )


def test_exhausted_arm_headroom_is_reported_insufficient(tmp_path):
    sufficient, detail = _arm_headroom_is_sufficient(_exhausted_arm("nwave"), tmp_path)

    assert sufficient is False
    assert "Credit balance is too low" in detail


def test_healthy_arm_headroom_is_sufficient(tmp_path):
    sufficient, _detail = _arm_headroom_is_sufficient(_healthy_arm("control"), tmp_path)

    assert sufficient is True


def test_unrelated_probe_error_is_not_classified_as_exhaustion(tmp_path):
    """A network hiccup must not read as "out of headroom" -- the wrong
    diagnosis in the refusal message would send an operator chasing quota
    that was never the problem."""
    sufficient, _detail = _arm_headroom_is_sufficient(
        _unrelated_error_arm("nwave"), tmp_path
    )

    assert sufficient is True


def test_main_refuses_before_any_pair_when_one_arm_is_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_arms(tmp_path, _healthy_arm("control"), _exhausted_arm("nwave"))

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

    assert code == 78
    assert not (out_dir / "campaign.json").exists()
    assert not (out_dir / "pair-1").exists()


def test_main_proceeds_when_both_arms_have_headroom(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_arms(tmp_path, _healthy_arm("control"), _healthy_arm("nwave"))

    out_dir = tmp_path / "campaign"
    code = main(
        [
            "--arms",
            str(tmp_path / "arms.json"),
            "--pairs",
            "1",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    assert (out_dir / "campaign.json").exists()
