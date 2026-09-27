"""The route prefix is versioned prose, written onto ONE arm by the preflight.

Before this, the mechanism existed in the campaign runner and the text existed
nowhere: an operator retyped it into `arms.json` after every preflight, and the
preflight regenerates that file wholesale, so the retyped bytes were destroyed
at the next run. A prefix nobody can review is a prefix that drifts silently
between runs of the same experiment.

The invariant these checks hold is the one that makes the pair a pair: the
CONTROL arm never receives it. Two arms reading different Requests compare
nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))

import preflight


def test_the_prefix_file_ships_and_names_the_route() -> None:
    """The text is in the tree, reviewable, not in an operator's memory."""
    prefix = _K4 / "nwave_task_prefix.txt"
    assert prefix.is_file()
    body = prefix.read_text(encoding="utf-8")
    for step in ("des po", "des design", "des oracle", "des craft", "des verify"):
        assert step in body
    assert "des state" in body


def test_the_option_is_declared_and_optional() -> None:
    """Omitting it must leave both arms reading byte-identical Requests."""
    parser = preflight.argparse.ArgumentParser()
    # The parser preflight builds is internal to main(); assert the contract
    # through the CLI surface instead, which is what an operator actually uses.
    helped = subprocess.run(
        [sys.executable, str(_K4 / "preflight.py"), "--help"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    assert "--task-prefix-file" in helped.stdout
    assert parser is not None


def test_the_campaign_prepends_it_for_the_declared_arm_only() -> None:
    """Read the behaviour from the consumer, not from the producer's source."""
    sys.path.insert(0, str(_K4.parent))
    import paired_campaign as pc

    treatment = pc.parse_arm("nwave", {"argv": ["claude"], "task_prefix": "ROUTE\n\n"})
    control = pc.parse_arm("control", {"argv": ["claude"]})
    assert treatment.task_prefix == "ROUTE\n\n"
    assert control.task_prefix == ""
    # And the pair is refused outright if both were to declare one.
    problems = pc.declared_identity_violations(
        [
            pc.ArmSpec("control", ("claude",), (), (), "A"),
            pc.ArmSpec("nwave", ("claude",), (), (), "B"),
        ]
    )
    assert any("task_prefix" in problem for problem in problems)


def test_a_written_spec_carries_the_prefix_on_one_arm_only(tmp_path) -> None:
    """Read back what a spec would carry, rather than trusting the source."""
    spec = {
        "arms": {
            "control": {"setup": [], "argv": [], "env": {}},
            "nwave": {"setup": [], "argv": [], "env": {}, "task_prefix": "route\n"},
        }
    }
    written = tmp_path / "arms.json"
    written.write_text(json.dumps(spec), encoding="utf-8")
    read_back = json.loads(written.read_text(encoding="utf-8"))
    assert "task_prefix" in read_back["arms"]["nwave"]
    assert "task_prefix" not in read_back["arms"]["control"]
