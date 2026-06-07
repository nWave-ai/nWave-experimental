"""Step execution service for DES orchestrator.

Handles step execution with turn counting, timeout monitoring,
stale execution detection, and step file persistence.

Extracted from orchestrator.py as part of P3 decomposition (step 3d).
"""

from pathlib import Path

from des.application.execution_results import (
    ExecuteStepResult,
    ExecuteStepWithStaleCheckResult,
)
from des.application.stale_execution_detector import StaleExecutionDetector
from des.domain.step_file_repository import StepFileRepository
from des.domain.timeout_monitor import TimeoutMonitor
from des.domain.timeout_warning_builder import TimeoutWarningBuilder
from des.domain.turn_counter import TurnCounter
from des.ports.driven_ports.filesystem_port import FileSystemPort
from des.ports.driven_ports.time_provider_port import TimeProvider


def execute_step(
    *,
    filesystem: FileSystemPort,
    time_provider: TimeProvider,
    step_repository: StepFileRepository,
    warning_builder: TimeoutWarningBuilder,
    command: str,
    agent: str,
    step_file: str,
    project_root: Path | str,
    simulated_iterations: int = 0,
    timeout_thresholds: list[int] | None = None,
    mocked_elapsed_times: list[int] | None = None,
) -> ExecuteStepResult:
    """Execute step with TurnCounter and TimeoutMonitor integration."""
    counter = TurnCounter()
    step_file_path = step_repository.resolve_path(project_root, step_file)
    step_data = step_repository.load(step_file_path)

    current_phase = step_repository.get_current_phase(step_data)
    phase_name = current_phase["phase_name"]

    timeout_monitor = None
    warnings: list[str] = []
    if timeout_thresholds:
        started_at = current_phase.get("started_at")
        if started_at:
            timeout_monitor = TimeoutMonitor(
                started_at=started_at, time_provider=time_provider
            )

    _restore_turn_count(counter, current_phase, phase_name)

    features_validated: list[str] = []

    for i in range(simulated_iterations):
        counter.increment_turn(phase_name)
        features_validated.append("turn_counting")

        _check_timeout_thresholds_for_iteration(
            warning_builder=warning_builder,
            iteration_index=i,
            phase_name=phase_name,
            step_data=step_data,
            timeout_thresholds=timeout_thresholds,
            mocked_elapsed_times=mocked_elapsed_times,
            timeout_monitor=timeout_monitor,
            warnings=warnings,
            features_validated=features_validated,
        )

    final_turn_count = counter.get_current_turn(phase_name)
    current_phase["turn_count"] = final_turn_count
    filesystem.write_json(step_file_path, step_data)

    # Deduplicate features_validated
    features_validated = list(dict.fromkeys(features_validated))

    return ExecuteStepResult(
        turn_count=final_turn_count,
        phase_name=phase_name,
        status="COMPLETED",
        warnings_emitted=warnings,  # Deprecated field
        timeout_warnings=warnings,
        execution_path="DESOrchestrator.execute_step",
        features_validated=features_validated,
    )


def execute_step_with_stale_check(
    *,
    filesystem: FileSystemPort,
    time_provider: TimeProvider,
    step_repository: StepFileRepository,
    warning_builder: TimeoutWarningBuilder,
    command: str,
    agent: str,
    step_file: str,
    project_root: Path | str,
    simulated_iterations: int = 0,
    timeout_thresholds: list[int] | None = None,
    mocked_elapsed_times: list[int] | None = None,
) -> ExecuteStepWithStaleCheckResult:
    """Execute step with pre-execution stale detection check."""
    if isinstance(project_root, str):
        project_root = Path(project_root)

    detector = StaleExecutionDetector(project_root=project_root)
    scan_result = detector.scan_for_stale_executions()

    if scan_result.is_blocked:
        first_stale = (
            scan_result.stale_executions[0] if scan_result.stale_executions else None
        )
        return ExecuteStepWithStaleCheckResult(
            blocked=True,
            blocking_reason="STALE_EXECUTION_DETECTED",
            stale_alert=first_stale,
            execute_result=None,
        )

    result = execute_step(
        filesystem=filesystem,
        time_provider=time_provider,
        step_repository=step_repository,
        warning_builder=warning_builder,
        command=command,
        agent=agent,
        step_file=step_file,
        project_root=project_root,
        simulated_iterations=simulated_iterations,
        timeout_thresholds=timeout_thresholds,
        mocked_elapsed_times=mocked_elapsed_times,
    )

    return ExecuteStepWithStaleCheckResult(
        blocked=False,
        blocking_reason=None,
        stale_alert=None,
        execute_result=result,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _restore_turn_count(
    counter: TurnCounter, current_phase: dict, phase_name: str
) -> None:
    """Restore existing turn count from phase data if resuming execution."""
    existing_turn_count = current_phase.get("turn_count", 0)
    for _ in range(existing_turn_count):
        counter.increment_turn(phase_name)


def _check_timeout_thresholds_for_iteration(
    *,
    warning_builder: TimeoutWarningBuilder,
    iteration_index: int,
    phase_name: str,
    step_data: dict,
    timeout_thresholds: list[int] | None,
    mocked_elapsed_times: list[int] | None,
    timeout_monitor: TimeoutMonitor | None,
    warnings: list[str],
    features_validated: list[str],
) -> None:
    """Check timeout thresholds for a single iteration."""
    if mocked_elapsed_times and timeout_thresholds:
        _check_mocked_thresholds(
            warning_builder=warning_builder,
            iteration_index=iteration_index,
            phase_name=phase_name,
            step_data=step_data,
            timeout_thresholds=timeout_thresholds,
            mocked_elapsed_times=mocked_elapsed_times,
            warnings=warnings,
            features_validated=features_validated,
        )
    elif timeout_monitor and timeout_thresholds:
        _check_real_thresholds(
            warning_builder=warning_builder,
            iteration_index=iteration_index,
            phase_name=phase_name,
            step_data=step_data,
            timeout_thresholds=timeout_thresholds,
            timeout_monitor=timeout_monitor,
            warnings=warnings,
            features_validated=features_validated,
        )


def _check_mocked_thresholds(
    *,
    warning_builder: TimeoutWarningBuilder,
    iteration_index: int,
    phase_name: str,
    step_data: dict,
    timeout_thresholds: list[int],
    mocked_elapsed_times: list[int],
    warnings: list[str],
    features_validated: list[str],
) -> None:
    """Check thresholds using mocked elapsed times (for testing)."""
    if iteration_index >= len(mocked_elapsed_times):
        return

    mocked_elapsed_minutes = mocked_elapsed_times[iteration_index] // 60
    duration_minutes = step_data.get("tdd_cycle", {}).get("duration_minutes")

    for threshold in timeout_thresholds:
        if mocked_elapsed_minutes >= threshold:
            warning = warning_builder.build_warning(
                phase_name, mocked_elapsed_minutes, threshold, duration_minutes
            )
            if warning not in warnings:
                warnings.append(warning)

    if "timeout_monitoring" not in features_validated:
        features_validated.append("timeout_monitoring")


def _check_real_thresholds(
    *,
    warning_builder: TimeoutWarningBuilder,
    iteration_index: int,
    phase_name: str,
    step_data: dict,
    timeout_thresholds: list[int],
    timeout_monitor: TimeoutMonitor,
    warnings: list[str],
    features_validated: list[str],
) -> None:
    """Check thresholds using real TimeoutMonitor (production path)."""
    if iteration_index % 5 != 0 and iteration_index != 0:
        return

    crossed = timeout_monitor.check_thresholds(timeout_thresholds)
    duration_minutes = step_data.get("tdd_cycle", {}).get("duration_minutes")

    for threshold in crossed:
        elapsed_seconds = timeout_monitor.get_elapsed_seconds()
        elapsed_minutes = int(elapsed_seconds / 60)
        warning = warning_builder.build_warning(
            phase_name, elapsed_minutes, threshold, duration_minutes
        )
        if warning not in warnings:
            warnings.append(warning)

    if crossed and "timeout_monitoring" not in features_validated:
        features_validated.append("timeout_monitoring")
