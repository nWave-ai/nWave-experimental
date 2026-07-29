"""General-purpose unit tests for ``PreToolUseService`` (d48-hook-check-timing).

WHY-NEW-FILE: tests/des/unit/application/test_pre_tool_use_service.py
  CLOSEST-EXISTING: tests/des/unit/application/test_pre_tool_use_service_refactor_mode_ordering.py
  EXTENSION-COST: that file's module docstring, fixtures, and control-case tests
    are scoped narrowly to the refactor/find-mode-ordering regression
    (bugfix-refactor-dispatch-mode-recognition-order); appending an unrelated
    per-check-timing/audit-shape test would blur its single regression purpose.
  PARALLEL-RATIONALE: this is the first general-purpose unit-test home for
    ``PreToolUseService`` (audit event shape, per-check timing instrumentation)
    -- not a competing implementation of the refactor-mode-ordering regression,
    the first file to cover the service generically.

Covers the per-check wall-clock timing instrumentation added to
``PreToolUseService.validate()`` for the RCA behind the pre_tool_use hook p99
tail (11132 invocations/8 days, sum=87% of hook wall-clock, worst single
invocation 329569ms) -- the 3 sequential checks on the atdd_pure allow path
(wave/enforcement resolution incl. the wave-active file read; marker
completeness policy; atdd_pure prompt validation) each get a wall-clock
bucket, threaded ADDITIVELY into the existing HOOK_PRE_TOOL_USE_ALLOWED /
HOOK_PRE_TOOL_USE_BLOCKED audit events (same audit_writer, same hook_id join
key already correlated against HOOK_COMPLETED.duration_ms) via a
``check_durations_ms`` field.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.application.pre_tool_use_service import PreToolUseService
from des.application.validator import TemplateValidator
from des.domain.des_enforcement_policy import DesEnforcementPolicy
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
from des.ports.driven_ports.audit_log_writer import AuditEvent
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


pytestmark = pytest.mark.unit


class _FixedTime:
    """Minimal deterministic TimeProvider double (null I/O) -- the service only
    calls ``now_utc().isoformat()`` when writing an audit event."""

    def now_utc(self) -> datetime:
        return datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)


class _CapturingAuditWriter(NullAuditLogWriter):
    """Appends every logged event to a list for post-hoc assertion."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)


class _AllowingAtddPureValidator(ValidatorPort):
    """A ValidatorPort double that always allows -- exercises the real
    ``self._atdd_pure_validator.validate_prompt(prompt)`` call site so the
    ``atdd_pure_validation`` timing bucket has real work to measure."""

    def validate_prompt(self, prompt: str) -> ValidationResult:
        return ValidationResult(
            status="ok",
            errors=[],
            task_invocation_allowed=True,
            duration_ms=0.0,
        )


def _atdd_pure_dispatch_prompt() -> str:
    """A complete, coherent atdd_pure dispatch: DES-MODE:atdd_pure + a per-slice
    DES-PHASE (A_GREEN) + a matching per-slice DES-SLICE -- reaches Step 4b via
    the main ``is_des_task`` path (completeness policy + orchestrator-mode both
    fall through), the checkpoint-2 path this timing instrumentation covers.
    """
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : d48-hook-check-timing -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        "\n"
        "Implement the per-check timing instrumentation.\n"
    )


def _build_gate(
    *, atdd_pure_validator: ValidatorPort | None
) -> tuple[PreToolUseService, _CapturingAuditWriter]:
    writer = _CapturingAuditWriter()
    gate = PreToolUseService(
        marker_parser=DesMarkerParser(),
        prompt_validator=TemplateValidator(),
        audit_writer=writer,
        time_provider=_FixedTime(),
        enforcement_policy=DesEnforcementPolicy(),
        completeness_policy=MarkerCompletenessPolicy(),
        atdd_pure_validator=atdd_pure_validator,
    )
    return gate, writer


def test_validate_records_per_check_duration_buckets_on_allowed_atdd_pure_dispatch() -> (
    None
):
    """covers: d48-hook-check-timing slice-01

    Given a complete atdd_pure dispatch that reaches ALLOW via the main
    ``is_des_task`` path (wave/enforcement resolution -> marker completeness
    -> atdd_pure prompt validation, all three checks actually run), When
    ``PreToolUseService.validate`` decides, Then the emitted
    HOOK_PRE_TOOL_USE_ALLOWED audit event carries a ``check_durations_ms``
    dict with exactly the three buckets that ran (``wave_enforcement``,
    ``completeness``, ``atdd_pure_validation``), each a non-negative float,
    correlated on the SAME ``hook_id`` join key HOOK_COMPLETED.duration_ms
    already uses.
    """
    gate, writer = _build_gate(atdd_pure_validator=_AllowingAtddPureValidator())

    decision = gate.validate(
        PreToolUseInput(prompt=_atdd_pure_dispatch_prompt()),
        hook_id="hook-abc-123",
    )

    assert decision.action == "allow", (
        f"expected allow, got {decision.action!r} ({decision.reason!r})"
    )

    allowed_events = [
        e for e in writer.events if e.event_type == "HOOK_PRE_TOOL_USE_ALLOWED"
    ]
    assert len(allowed_events) == 1, (
        f"expected exactly 1 HOOK_PRE_TOOL_USE_ALLOWED event, got {len(allowed_events)}"
    )
    event = allowed_events[0]
    assert event.hook_id == "hook-abc-123", (
        "the audit event must carry the same hook_id join key correlated "
        "against HOOK_COMPLETED.duration_ms"
    )

    assert "check_durations_ms" in event.data, (
        "HOOK_PRE_TOOL_USE_ALLOWED must carry a check_durations_ms field on "
        f"the atdd_pure allow path; got data={event.data!r}"
    )
    durations = event.data["check_durations_ms"]
    assert set(durations.keys()) == {
        "wave_enforcement",
        "completeness",
        "atdd_pure_validation",
    }, f"expected exactly the 3 checkpoint buckets that ran, got {durations!r}"
    for bucket, value in durations.items():
        assert isinstance(value, float), (
            f"{bucket} duration must be a float, got {value!r}"
        )
        assert value >= 0.0, f"{bucket} duration must be non-negative, got {value!r}"


def test_validate_omits_check_durations_ms_on_blocked_enforcement_path() -> None:
    """covers: d48-hook-check-timing slice-01 (additive-only contract)

    Given a dispatch blocked at Step 2 (DesEnforcementPolicy, BEFORE the
    checkpoint-1 wave_enforcement bucket is even recorded -- a step-id pattern
    with no DES markers at all), When ``PreToolUseService.validate`` blocks,
    Then the emitted HOOK_PRE_TOOL_USE_BLOCKED event carries NO
    ``check_durations_ms`` key at all -- proving the additive-only,
    byte-identical-when-absent contract: this early exit is untouched by the
    instrumentation.
    """
    gate, writer = _build_gate(atdd_pure_validator=None)

    decision = gate.validate(
        PreToolUseInput(prompt="Please execute step 01-01 of the plan."),
        hook_id="hook-def-456",
    )

    assert decision.action == "block", (
        f"expected block, got {decision.action!r} ({decision.reason!r})"
    )

    blocked_events = [
        e for e in writer.events if e.event_type == "HOOK_PRE_TOOL_USE_BLOCKED"
    ]
    assert len(blocked_events) == 1, (
        f"expected exactly 1 HOOK_PRE_TOOL_USE_BLOCKED event, got {len(blocked_events)}"
    )
    event = blocked_events[0]
    assert "check_durations_ms" not in event.data, (
        "a block that happens BEFORE the wave_enforcement checkpoint must emit "
        f"byte-identical data (no check_durations_ms key); got data={event.data!r}"
    )
