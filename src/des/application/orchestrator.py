"""DES Orchestrator — thin facade over extracted services.

Delegates to:
- prompt_rendering_service (render_prompt, render_full_prompt)
- step_execution_service (execute_step, execute_step_with_stale_check)
- audit_bridge (log_audit_event)
- execution_results (DTOs)

All public method signatures are preserved for backward compatibility.
"""

from pathlib import Path

from des.adapters.driven.logging.audit_events import AuditEvent, EventType
from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
from des.application.execution_results import (
    ExecuteStepResult,
    ExecuteStepWithStaleCheckResult,
)
from des.application.invocation_limits_validator import (
    InvocationLimitsResult,
    InvocationLimitsValidator,
)
from des.application.prompt_rendering_service import (
    generate_des_markers,
    get_validation_level,
)
from des.application.prompt_rendering_service import (
    render_full_prompt as _render_full_prompt,
)
from des.application.prompt_rendering_service import (
    render_prompt as _render_prompt,
)
from des.application.step_execution_service import (
    execute_step as _execute_step,
)
from des.application.step_execution_service import (
    execute_step_with_stale_check as _execute_step_with_stale_check,
)
from des.domain.des_marker_generator import DESMarkerGenerator
from des.domain.prompt_metadata_extractor import PromptMetadataExtractor
from des.domain.schema_version_detector import SchemaVersionDetector
from des.domain.step_file_repository import StepFileRepository
from des.domain.timeout_warning_builder import TimeoutWarningBuilder
from des.domain.value_objects import CommandName
from des.ports.driven_ports.audit_log_writer import AuditEvent as PortAuditEvent
from des.ports.driven_ports.filesystem_port import FileSystemPort
from des.ports.driven_ports.hook_port import HookPort, HookResult
from des.ports.driven_ports.time_provider_port import TimeProvider
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


class DESOrchestrator:
    """Orchestrates DES validation by analyzing command origin.

    Thin facade that delegates to extracted service modules.
    """

    VALIDATION_COMMANDS = CommandName.VALIDATION_COMMANDS

    def __init__(
        self,
        hook: HookPort,
        validator: ValidatorPort,
        filesystem: FileSystemPort,
        time_provider: TimeProvider,
    ):
        self._hook = hook
        self._validator = validator
        self._filesystem = filesystem
        self._time_provider = time_provider
        self._subagent_lifecycle_completed = False
        self._step_file_path: Path | None = None

        # Domain services shared by facade methods
        self._schema_detector = SchemaVersionDetector(filesystem)
        self._marker_generator = DESMarkerGenerator()
        self._metadata_extractor = PromptMetadataExtractor()
        self._warning_builder = TimeoutWarningBuilder()
        self._step_repository = StepFileRepository(filesystem)

    # ========================================================================
    # Factory
    # ========================================================================

    @classmethod
    def create_with_defaults(cls) -> "DESOrchestrator":
        """Create an orchestrator with default real adapters."""
        from des.adapters.driven.filesystem.real_filesystem import RealFileSystem
        from des.adapters.driven.hooks.noop_hook import NoOpHook
        from des.adapters.driven.time.system_time import SystemTimeProvider
        from des.application.validator import TemplateValidator

        return cls(
            hook=NoOpHook(),
            validator=TemplateValidator(),
            filesystem=RealFileSystem(),
            time_provider=SystemTimeProvider(),
        )

    # ========================================================================
    # Schema Version Detection
    # ========================================================================

    def detect_schema_version(self, step_file_path: Path) -> str:
        """Detect schema version from step file."""
        return self._schema_detector.detect_version(step_file_path)

    def get_phase_count_for_schema(self, schema_version: str) -> int:
        """Get expected phase count for schema version."""
        return self._schema_detector.get_phase_count(schema_version)

    # ========================================================================
    # Prompt Validation (audit-aware)
    # ========================================================================

    def validate_prompt(self, prompt: str) -> ValidationResult:
        """Validate a prompt for mandatory sections and TDD phases."""
        result = self._validator.validate_prompt(prompt)

        feature_name = self._metadata_extractor.extract_feature_name(prompt)
        step_id = self._metadata_extractor.extract_step_id(prompt)
        agent_name = self._metadata_extractor.extract_agent_name(prompt)

        event = self._build_validation_audit_event(
            result, feature_name, step_id, agent_name
        )
        self._log_audit_event_if_enabled(event, feature_name, step_id)

        self._subagent_lifecycle_completed = True
        return result

    def _build_validation_audit_event(
        self,
        result: ValidationResult,
        feature_name: str | None,
        step_id: str | None,
        agent_name: str | None,
    ) -> AuditEvent:
        """Build audit event for validation result."""
        timestamp = self._time_provider.now_utc().isoformat()
        extra_context = {"agent": agent_name} if agent_name else None

        if result.task_invocation_allowed:
            return AuditEvent(
                timestamp=timestamp,
                event=EventType.HOOK_PRE_TASK_PASSED.value,
                feature_name=feature_name,
                step_id=step_id,
                extra_context=extra_context,
            )

        rejection_reason = str(result.errors) if result.errors else "Validation failed"
        return AuditEvent(
            timestamp=timestamp,
            event=EventType.HOOK_PRE_TASK_BLOCKED.value,
            feature_name=feature_name,
            step_id=step_id,
            rejection_reason=rejection_reason,
            extra_context=extra_context,
        )

    def _log_audit_event_if_enabled(
        self,
        event: AuditEvent,
        feature_name: str | None,
        step_id: str | None,
    ) -> None:
        """Log audit event if audit logging is enabled."""
        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig()
        if not config.audit_logging_enabled:
            return

        writer = JsonlAuditLogWriter()
        excluded_keys = ("event", "timestamp", "feature_name", "step_id")
        data = {
            k: v
            for k, v in event.to_dict().items()
            if k not in excluded_keys and v is not None
        }
        writer.log_event(
            PortAuditEvent(
                event_type=event.event,
                timestamp=event.timestamp,
                feature_name=feature_name,
                step_id=step_id,
                data=data,
            )
        )

    # ========================================================================
    # Invocation Limits Validation
    # ========================================================================

    def validate_invocation_limits(
        self, step_file: str, project_root: Path | str
    ) -> InvocationLimitsResult:
        """Validate turn and timeout limits before sub-agent invocation."""
        step_file_path = self._step_repository.resolve_path(project_root, step_file)
        validator = InvocationLimitsValidator(filesystem=self._filesystem)
        return validator.validate_limits(step_file_path)

    def _get_validation_level(self, command: str | None) -> str:
        """Determine validation level based on command type."""
        return get_validation_level(command)

    # ========================================================================
    # Prompt Rendering (delegates to prompt_rendering_service)
    # ========================================================================

    def _generate_des_markers(self, command: str | None, step_file: str | None) -> str:
        """Generate DES validation markers for execute/develop commands."""
        return generate_des_markers(self._marker_generator, command, step_file)

    def render_prompt(
        self,
        command: str | None,
        agent: str | None = None,
        step_file: str | None = None,
        project_root: str | None = None,
        topic: str | None = None,
        timeout_thresholds: list[int] | None = None,
        timeout_budget_minutes: int | None = None,
        project_id: str | None = None,
    ) -> str:
        """Render Task prompt with DES validation markers and timeout warnings.

        Thin delegate to ``prompt_rendering_service.render_prompt`` (the SSOT).
        Mirrors ``render_full_prompt`` — forwards the orchestrator's shared
        domain collaborators and all call arguments. Audit events
        (TASK_INVOCATION_STARTED / VALIDATED) are emitted by the service's
        audit seam.
        """
        return _render_prompt(
            marker_generator=self._marker_generator,
            step_repository=self._step_repository,
            warning_builder=self._warning_builder,
            time_provider=self._time_provider,
            command=command,
            agent=agent,
            step_file=step_file,
            project_root=project_root,
            topic=topic,
            timeout_thresholds=timeout_thresholds,
            timeout_budget_minutes=timeout_budget_minutes,
            project_id=project_id,
        )

    def render_full_prompt(
        self,
        command: str,
        agent: str,
        step_file: str,
        project_root: str | Path,
    ) -> str:
        """Render complete Task prompt with all DES sections."""
        return _render_full_prompt(
            marker_generator=self._marker_generator,
            step_repository=self._step_repository,
            command=command,
            agent=agent,
            step_file=step_file,
            project_root=project_root,
        )

    def prepare_ad_hoc_prompt(
        self, prompt: str, project_root: str | None = None
    ) -> str:
        """Prepare ad-hoc prompt without DES validation markers."""
        return prompt

    # ========================================================================
    # Hook Integration
    # ========================================================================

    def on_subagent_complete(self, step_file_path: str) -> HookResult:
        """Invoke post-execution validation hook after sub-agent completion."""
        return self._hook.on_agent_complete(step_file_path)

    # ========================================================================
    # Step Execution (delegates to step_execution_service)
    # ========================================================================

    def execute_step_with_stale_check(
        self,
        command: str,
        agent: str,
        step_file: str,
        project_root: Path | str,
        simulated_iterations: int = 0,
        timeout_thresholds: list[int] | None = None,
        mocked_elapsed_times: list[int] | None = None,
    ) -> ExecuteStepWithStaleCheckResult:
        """Execute step with pre-execution stale detection check."""
        return _execute_step_with_stale_check(
            filesystem=self._filesystem,
            time_provider=self._time_provider,
            step_repository=self._step_repository,
            warning_builder=self._warning_builder,
            command=command,
            agent=agent,
            step_file=step_file,
            project_root=project_root,
            simulated_iterations=simulated_iterations,
            timeout_thresholds=timeout_thresholds,
            mocked_elapsed_times=mocked_elapsed_times,
        )

    def execute_step(
        self,
        command: str,
        agent: str,
        step_file: str,
        project_root: Path | str,
        simulated_iterations: int = 0,
        timeout_thresholds: list[int] | None = None,
        mocked_elapsed_times: list[int] | None = None,
    ) -> ExecuteStepResult:
        """Execute step with TurnCounter and TimeoutMonitor integration."""
        return _execute_step(
            filesystem=self._filesystem,
            time_provider=self._time_provider,
            step_repository=self._step_repository,
            warning_builder=self._warning_builder,
            command=command,
            agent=agent,
            step_file=step_file,
            project_root=project_root,
            simulated_iterations=simulated_iterations,
            timeout_thresholds=timeout_thresholds,
            mocked_elapsed_times=mocked_elapsed_times,
        )
