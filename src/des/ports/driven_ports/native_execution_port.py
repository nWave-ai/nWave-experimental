"""Native argv execution contract shared by host adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from des.domain.codex_parity import Digest, ReceiptState, WhatWhyHow


@dataclass(frozen=True)
class NativeCommand:
    executable: str
    argv: tuple[str, ...]
    cwd: str
    environment: tuple[tuple[str, str], ...]
    timeout_seconds: float


class TerminationState(str, Enum):
    EXITED = "exited"
    TIMED_OUT_TREE_TERMINATED = "timed-out-tree-terminated"
    TERMINATION_UNPROVED = "termination-unproved"
    START_REFUSED = "start-refused"


@dataclass(frozen=True)
class NativeExecutionReceipt:
    command_digest: Digest
    state: ReceiptState
    exit_code: int | None
    stdout_digest: Digest
    stderr_digest: Digest
    termination_state: TerminationState
    diagnostic: WhatWhyHow | None = None


class NativeExecutionPort(Protocol):
    def execute(self, command: NativeCommand) -> NativeExecutionReceipt:
        ...


__all__ = [
    "NativeCommand",
    "NativeExecutionPort",
    "NativeExecutionReceipt",
    "TerminationState",
]
