"""A declared task prefix changes what one arm is ASKED, so it is guarded.

Five measurements on 2026-09-13 established that an agent handed an
implementation task never chooses the method on its own. Measuring what the
method costs therefore means asking for it -- which is legitimate, and which
the campaign must record rather than let a reader assume the arms read the same
words.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "analysis"))

import paired_campaign as pc


def test_an_arm_without_a_prefix_reads_the_request_unchanged() -> None:
    arm = pc.parse_arm("control", {"argv": ["claude"]})
    assert arm.task_prefix == ""


def test_a_declared_prefix_is_read_and_kept() -> None:
    arm = pc.parse_arm("nwave", {"argv": ["claude"], "task_prefix": "Route: X\n\n"})
    assert arm.task_prefix == "Route: X\n\n"


def test_a_non_string_prefix_is_refused() -> None:
    try:
        pc.parse_arm("nwave", {"argv": ["claude"], "task_prefix": 3})
    except ValueError as error:
        assert "task_prefix" in str(error)
    else:
        raise AssertionError("a non-string prefix must be refused")


def test_two_prefixed_arms_are_two_different_tasks() -> None:
    arms = [
        pc.ArmSpec("control", ("claude",), (), (), "A"),
        pc.ArmSpec("nwave", ("claude",), (), (), "B"),
    ]
    problems = pc.declared_identity_violations(arms)
    assert any("task_prefix" in problem for problem in problems)


def test_one_prefixed_arm_is_allowed() -> None:
    arms = [
        pc.ArmSpec("control", ("claude",), ()),
        pc.ArmSpec("nwave", ("claude",), (), (), "B"),
    ]
    problems = pc.declared_identity_violations(arms)
    assert not any("task_prefix" in problem for problem in problems)
