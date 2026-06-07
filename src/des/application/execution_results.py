"""Execution result DTOs for DES orchestrator.

Extracted from orchestrator.py as part of P3 decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.stale_execution import StaleExecution


@dataclass
class ExecuteStepResult:
    """Result from execute_step() method execution.

    Attributes:
        turn_count: Total number of turns (iterations) executed
        phase_name: Name of the phase being executed (required, loaded from step file)
        status: Execution status (e.g., "COMPLETED", "IN_PROGRESS")
        warnings_emitted: List of timeout warnings emitted during execution (deprecated, use timeout_warnings)
        timeout_warnings: List of timeout warning strings emitted during execution
        execution_path: Execution path identifier for validation (e.g., "DESOrchestrator.execute_step")
        features_validated: List of DES features validated during execution
    """

    turn_count: int
    phase_name: str  # Required - loaded from step file, no hardcoded default
    status: str = "COMPLETED"
    warnings_emitted: list[str] = field(
        default_factory=list
    )  # Deprecated, use timeout_warnings
    timeout_warnings: list[str] = field(default_factory=list)
    execution_path: str = "DESOrchestrator.execute_step"
    features_validated: list[str] = field(default_factory=list)


@dataclass
class ExecuteStepWithStaleCheckResult:
    """Result from execute_step_with_stale_check() method execution.

    Attributes:
        blocked: True if execution was blocked due to stale detection
        blocking_reason: Reason for blocking (e.g., "STALE_EXECUTION_DETECTED")
        stale_alert: StaleExecution object with alert details (if blocked)
        execute_result: ExecuteStepResult from normal execution (if not blocked)
    """

    blocked: bool
    blocking_reason: str | None = None
    stale_alert: StaleExecution | None = None
    execute_result: ExecuteStepResult | None = None
