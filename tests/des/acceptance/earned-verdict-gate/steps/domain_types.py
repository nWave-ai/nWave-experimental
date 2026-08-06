"""Typed vocabulary for the retained TestRunnerPort acceptance scenarios."""

from __future__ import annotations

from enum import Enum


class TargetHealth(str, Enum):
    """The observable state of a staged test target."""

    ALL_PASS = "all pass"
    HAS_FAILURE = "at least one failing test"
    RUNNER_ABSENT = "cannot be invoked"


TARGET_HEALTH_BY_PHRASE: dict[str, TargetHealth] = {
    target.value: target for target in TargetHealth
}
