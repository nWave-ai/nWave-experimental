"""Prompt rendering service for DES orchestrator.

Pure functions for rendering DES prompts with validation markers,
timeout warnings, and boundary rules.

Extracted from orchestrator.py as part of P3 decomposition (step 3c).
"""

import os
from pathlib import Path

from des.application.audit_bridge import log_audit_event
from des.domain.des_marker_generator import DESMarkerGenerator
from des.domain.step_file_repository import StepFileRepository
from des.domain.timeout_monitor import TimeoutMonitor
from des.domain.timeout_warning_builder import TimeoutWarningBuilder
from des.domain.value_objects import CommandName
from des.ports.driven_ports.time_provider_port import TimeProvider


# Commands that require full DES validation — references the domain SSOT
# (CommandName.VALIDATION_COMMANDS) rather than re-declaring the list.
VALIDATION_COMMANDS = CommandName.VALIDATION_COMMANDS


def get_validation_level(command: str | None) -> str:
    """Determine validation level based on command type.

    Returns:
        "full" for execute/develop commands, "none" otherwise.
    """
    if not command:
        return "none"
    if command in VALIDATION_COMMANDS:
        return "full"
    return "none"


def generate_des_markers(
    marker_generator: DESMarkerGenerator,
    command: str | None,
    step_file: str | None,
) -> str:
    """Generate DES validation markers for execute/develop commands.

    Raises:
        ValueError: If command or step_file is None or empty.
    """
    if not command:
        raise ValueError("Command cannot be None or empty")
    if not step_file:
        raise ValueError("Step file cannot be None or empty")
    return marker_generator.generate_markers(command, step_file)


def render_prompt(
    *,
    marker_generator: DESMarkerGenerator,
    step_repository: StepFileRepository,
    warning_builder: TimeoutWarningBuilder,
    time_provider: TimeProvider,
    command: str | None,
    agent: str | None = None,
    step_file: str | None = None,
    project_root: str | None = None,
    topic: str | None = None,
    timeout_thresholds: list[int] | None = None,
    timeout_budget_minutes: int | None = None,
    project_id: str | None = None,
) -> str:
    """Render Task prompt with appropriate DES validation markers and timeout warnings.

    Raises:
        ValueError: If command is None or empty, or if step_file is missing
                   for validation commands.
    """
    if not command:
        raise ValueError("Command cannot be None or empty")

    # Extract step_id from step_file path for audit logging
    step_id = None
    if step_file:
        step_id = os.path.splitext(os.path.basename(step_file))[0]

    # Log TASK_INVOCATION_STARTED for audit trail
    log_audit_event(
        "TASK_INVOCATION_STARTED",
        command=command,
        step_id=step_id,
        feature_name=project_id,
        agent=agent,
    )

    validation_level = get_validation_level(command)

    if validation_level == "full":
        if not step_file:
            raise ValueError("Step file required for validation commands")

        des_markers = generate_des_markers(marker_generator, command, step_file)

        # Log TASK_INVOCATION_VALIDATED for audit trail
        log_audit_event(
            "TASK_INVOCATION_VALIDATED",
            command=command,
            step_id=step_id,
            feature_name=project_id,
            status="VALIDATED",
            outcome="success",
        )

        # Add timeout warnings if threshold monitoring is enabled
        if timeout_thresholds and project_root and step_file:
            warnings = generate_timeout_warnings(
                step_repository=step_repository,
                warning_builder=warning_builder,
                time_provider=time_provider,
                step_file=step_file,
                project_root=project_root,
                timeout_thresholds=timeout_thresholds,
                timeout_budget_minutes=timeout_budget_minutes,
            )
            if warnings:
                return f"{des_markers}\n\n{warnings}"

        return des_markers

    # Research and other commands bypass DES validation
    return ""


def render_full_prompt(
    *,
    marker_generator: DESMarkerGenerator,
    step_repository: StepFileRepository,
    command: str,
    agent: str,
    step_file: str,
    project_root: str | Path,
) -> str:
    """Render complete Task prompt with all DES sections including TIMEOUT_INSTRUCTION.

    Raises:
        ValueError: If command is not a validation command.
    """
    from des.application.boundary_rules_generator import BoundaryRulesGenerator
    from des.application.boundary_rules_template import BoundaryRulesTemplate
    from des.domain.timeout_instruction_template import TimeoutInstructionTemplate

    validation_level = get_validation_level(command)
    if validation_level != "full":
        raise ValueError(
            f"render_full_prompt only supports validation commands, got: {command}"
        )

    des_markers = generate_des_markers(marker_generator, command, step_file)

    step_file_path = step_repository.resolve_path(project_root, step_file)
    generator = BoundaryRulesGenerator(step_file_path=step_file_path)
    allowed_patterns = generator.generate_allowed_patterns()

    boundary_rules_template = BoundaryRulesTemplate()
    boundary_rules = boundary_rules_template.render(allowed_patterns=allowed_patterns)

    timeout_template = TimeoutInstructionTemplate()
    timeout_instruction = timeout_template.render()

    return f"{des_markers}\n\n{boundary_rules}\n{timeout_instruction}"


def generate_timeout_warnings(
    *,
    step_repository: StepFileRepository,
    warning_builder: TimeoutWarningBuilder,
    time_provider: TimeProvider,
    step_file: str,
    project_root: str | Path,
    timeout_thresholds: list[int],
    timeout_budget_minutes: int | None,
) -> str:
    """Generate timeout warnings for agent prompt context.

    Returns:
        Formatted warning string, or empty string if no thresholds crossed.
    """
    step_file_path = step_repository.resolve_path(project_root, step_file)
    step_data = step_repository.load(step_file_path)
    current_phase = step_repository.get_current_phase(step_data)

    started_at = current_phase.get("started_at")
    if not started_at:
        return ""

    monitor = TimeoutMonitor(started_at=started_at, time_provider=time_provider)

    crossed_thresholds = monitor.check_thresholds(timeout_thresholds)
    if not crossed_thresholds:
        return ""

    elapsed_seconds = monitor.get_elapsed_seconds()
    elapsed_minutes = int(elapsed_seconds / 60)
    phase_name = current_phase["phase_name"]

    first_threshold = crossed_thresholds[0]

    return warning_builder.build_warning(
        phase_name, elapsed_minutes, first_threshold, timeout_budget_minutes
    )
