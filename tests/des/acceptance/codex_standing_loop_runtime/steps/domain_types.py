"""Acceptance vocabulary for the operator-visible bounded continuation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LimitKind(StrEnum):
    """Unsafe bounded-control requests the public surface must refuse."""

    MISSING = "no limit"
    ZERO = "zero limit"
    NEGATIVE = "negative limit"


@dataclass(frozen=True)
class SessionObservation:
    """Only facts an operator can observe at the public command/hook surface."""

    exit_code: int
    public_text: str
    loop_state: str | None
    attestation_claimed: bool
    refusal_has_what_why_how: bool
    offered_opportunity_count: int


@dataclass(frozen=True)
class BudgetObservation:
    """Operator-visible evidence for a bounded continued-work attempt."""

    first_exit_code: int
    first_event: dict[str, object]
    second_exit_code: int
    second_event: dict[str, object]
    inspection_exit_code: int
    inspection: dict[str, object]
