"""SubagentStopService - application service for step completion validation.

Orchestrates domain logic (StepCompletionValidator) and driven ports
(ExecutionLogReader, ScopeChecker, AuditLogWriter, TimeProvider) to produce
allow/block decisions for step completion.

This service implements the SubagentStopPort driver port interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driven_ports.commit_verifier import CommitVerificationResult
from des.ports.driven_ports.execution_log_reader import (
    ExecutionLogReader,
    LogFileCorrupted,
    LogFileNotFound,
)
from des.ports.driver_ports.pre_tool_use_port import HookDecision
from des.ports.driver_ports.subagent_stop_port import (
    SubagentStopContext,
    SubagentStopPort,
)


if TYPE_CHECKING:
    from des.domain.step_completion_validator import StepCompletionValidator
    from des.ports.driven_ports.commit_verifier import CommitVerifier
    from des.ports.driven_ports.scope_checker import ScopeChecker
    from des.ports.driven_ports.time_provider_port import TimeProvider


class SubagentStopService(SubagentStopPort):
    """Validates step completion when a subagent finishes.

    Flow:
      1. Read project_id via ExecutionLogReader.read_project_id()
         - If not found: return block (LOG_FILE_NOT_FOUND)
         - If mismatch: return block (PROJECT_ID_MISMATCH)
      2. Read step events via ExecutionLogReader.read_step_events()
      3. Validate completion via StepCompletionValidator.validate()
         - If invalid: log HOOK_SUBAGENT_STOP_FAILED, return block
      3.5. Verify git commit via CommitVerifier (if cwd provided)
         - If no matching commit: return block (COMMIT_NOT_VERIFIED)
         - Fail-closed: git errors also block
      4. Check scope via ScopeChecker.check_scope()
         - If violations: log SCOPE_VIOLATION (warning, does not block)
      5. Log HOOK_SUBAGENT_STOP_PASSED, return allow
    """

    def __init__(
        self,
        log_reader: ExecutionLogReader,
        completion_validator: StepCompletionValidator,
        scope_checker: ScopeChecker,
        audit_writer: AuditLogWriter,
        time_provider: TimeProvider,
        commit_verifier: CommitVerifier | None = None,
    ) -> None:
        self._log_reader = log_reader
        self._completion_validator = completion_validator
        self._scope_checker = scope_checker
        self._audit_writer = audit_writer
        self._time_provider = time_provider
        self._commit_verifier = commit_verifier

    def validate(self, context: SubagentStopContext) -> HookDecision:
        """Validate step completion for a subagent.

        Args:
            context: Parsed context from the hook protocol

        Returns:
            HookDecision indicating allow or block
        """
        # Step 1: Read and validate project_id
        try:
            log_project_id = self._log_reader.read_project_id(
                context.execution_log_path
            )
        except LogFileNotFound:
            return HookDecision.block(
                reason=f"Execution log not found: {context.execution_log_path}",
                recovery_suggestions=[
                    "Create execution-log.yaml file",
                    "Run orchestrator to initialize log",
                ],
            )
        except LogFileCorrupted as e:
            return HookDecision.block(
                reason=f"Invalid YAML in execution log: {e}",
                recovery_suggestions=["Fix YAML syntax errors in execution-log.yaml"],
            )

        if log_project_id != context.project_id:
            return HookDecision.block(
                reason=f"Project ID mismatch: expected '{context.project_id}', found '{log_project_id}'",
                recovery_suggestions=[
                    f"Verify you're working on project '{context.project_id}'",
                    "Check DES-PROJECT-ID marker in prompt",
                ],
            )

        # Step 2: Read step events
        try:
            events = self._log_reader.read_step_events(
                context.execution_log_path,
                context.step_id,
            )
        except (LogFileNotFound, LogFileCorrupted) as e:
            return HookDecision.block(
                reason=f"Failed to read step events: {e}",
                recovery_suggestions=["Check execution-log.yaml file integrity"],
            )

        # Step 3: Validate completion
        completion = self._completion_validator.validate(events)

        if not completion.is_valid:
            error_parts = list(completion.error_messages)
            error_message = (
                "; ".join(error_parts) if error_parts else "Validation failed"
            )

            if context.stop_hook_active:
                # Second attempt: allow to prevent infinite loop, but still log FAILED
                self._log_failed(
                    context.project_id,
                    context.step_id,
                    error_parts,
                    allowed_despite_failure=True,
                )
                return HookDecision.allow()

            # First attempt: block so sub-agent can try to fix
            self._log_failed(context.project_id, context.step_id, error_parts)
            return HookDecision.block(
                reason=error_message,
                recovery_suggestions=completion.recovery_suggestions,
            )

        # Step 3.5: Verify git commit exists (only if phases passed and cwd provided)
        if context.cwd and self._commit_verifier:
            commit_result = self._commit_verifier.verify_commit(
                context.step_id, context.cwd
            )
            if not commit_result.verified:
                self._log_commit_not_verified(context, commit_result)
                return HookDecision.block(
                    reason=f"COMMIT_NOT_VERIFIED: {commit_result.error_reason}",
                    recovery_suggestions=[
                        f"Create a git commit with trailer 'Step-ID: {context.step_id}'",
                        "Ensure the COMMIT phase actually runs git commit",
                        "Check that git is available and you're in a git repository",
                    ],
                )
            self._log_commit_verified(context, commit_result)

        # Step 4: Check scope (warning only, does not block)
        self._check_and_log_scope(context)

        # Step 5: All valid
        self._log_passed(context.project_id, context.step_id)
        return HookDecision.allow()

    def _check_and_log_scope(self, context: SubagentStopContext) -> None:
        """Check scope violations and log warnings."""
        log_path = Path(context.execution_log_path)
        # execution-log.yaml is in docs/feature/{project}/
        project_root = log_path.parent.parent.parent

        scope_result = self._scope_checker.check_scope(
            project_root=project_root,
            # TODO: Extract allowed patterns from roadmap.yaml
            allowed_patterns=["**/*"],
        )

        if scope_result.has_violations:
            for file_path in scope_result.out_of_scope_files:
                self._audit_writer.log_event(
                    AuditEvent(
                        event_type="SCOPE_VIOLATION",
                        timestamp=self._time_provider.now_utc().isoformat(),
                        feature_name=context.project_id,
                        step_id=context.step_id,
                        data={
                            "out_of_scope_file": file_path,
                        },
                    )
                )

    def _log_passed(self, feature_name: str, step_id: str) -> None:
        """Log successful validation to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_PASSED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=feature_name,
                step_id=step_id,
            )
        )

    def _log_failed(
        self,
        feature_name: str,
        step_id: str,
        error_messages: list[str],
        allowed_despite_failure: bool = False,
    ) -> None:
        """Log failed validation to the audit trail."""
        data: dict = {
            "validation_errors": error_messages,
        }
        if allowed_despite_failure:
            data["allowed_despite_failure"] = True
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_FAILED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=feature_name,
                step_id=step_id,
                data=data,
            )
        )

    def _log_commit_verified(
        self,
        context: SubagentStopContext,
        result: CommitVerificationResult,
    ) -> None:
        """Log successful commit verification to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="COMMIT_VERIFIED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.step_id,
                data={
                    "commit_hash": result.commit_hash,
                    "commit_date": result.commit_date,
                    "commit_subject": result.commit_subject,
                },
            )
        )

    def _log_commit_not_verified(
        self,
        context: SubagentStopContext,
        result: CommitVerificationResult,
    ) -> None:
        """Log failed commit verification to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="COMMIT_NOT_VERIFIED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.step_id,
                data={
                    "error_reason": result.error_reason,
                },
            )
        )
