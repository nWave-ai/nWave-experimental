"""Mandate-8 universe + pure snapshot for the f-devops gate ATs.

Universe entries are PORT-EXPOSED observables on the subprocess `GateOutcome`
(exit code) — never Popen handles, never internal service fields. The gate is a
READ that emits a verdict; the only observable "mutation" per scenario is the
captured subprocess exit code, asserted via `assert_state_delta`.
"""

from __future__ import annotations


GATE_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
    }
)


def snapshot(composition_outcome) -> dict:
    """Pure snapshot of the universe from a (possibly absent) GateOutcome."""
    return {
        "outcome.exit_code": getattr(composition_outcome, "exit_code", None),
    }
