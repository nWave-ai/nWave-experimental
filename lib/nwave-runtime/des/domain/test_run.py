"""Language-neutral observations produced by a test runner.

``TestRun`` is deliberately smaller than any workflow policy: it records the
three facts consumed by the refactor drain, plus whether a runner actually
observed them.  A runner that cannot start is represented explicitly as
``observed=False``; it is never made to look like a green test run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


TEST_RESULT_SCHEMA = "nwave.test_result.v1"
TEST_OBSERVATION_SCHEMA = "nwave.test_observation.v1"
UNOBSERVED = "unobserved"
RUNNER_ABSENT = "runner-absent"


@dataclass(frozen=True)
class TestRun:
    """Counts from one test-runner invocation, or an explicit non-observation."""

    runner: str
    passed: int
    failed: int
    exit_code: int
    observed: bool = True


def test_run_from_envelope(envelope: dict[str, object]) -> TestRun:
    """Parse a real test result or an explicit unobserved runner outcome.

    Unknown envelopes are rejected rather than being interpreted as a green
    result.  This makes a runner/protocol failure unsafe for the refactor
    drain without inventing pass counts.
    """

    schema = envelope.get("schema")
    if schema == TEST_RESULT_SCHEMA:
        return TestRun(
            runner=str(envelope["runner"]),
            passed=_count(envelope["passed"]),
            failed=_count(envelope["failed"]),
            exit_code=_count(envelope["exit_code"]),
        )
    if (
        schema == TEST_OBSERVATION_SCHEMA
        and envelope.get("observation") == UNOBSERVED
        and envelope.get("reason") == RUNNER_ABSENT
    ):
        return TestRun(
            runner=str(envelope.get("runner", "unknown")),
            passed=0,
            failed=0,
            exit_code=2,
            observed=False,
        )
    raise ValueError("unsupported test-run envelope")


def _count(value: object) -> int:
    return int(cast("int", value))
