"""Factory functions for hook handler application services.

Creates production-wired instances of PreToolUseService and SubagentStopService
with all required dependencies injected.

All factories accept an optional ``audit_writer_factory`` callable, enabling
the adapter to pass its own patchable factory for test isolation.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition (step 4c).
"""

from collections.abc import Callable

from des.adapters.driven.filesystem.feature_delta_filesystem_reader import (
    FeatureDeltaFilesystemReader,
)
from des.adapters.driven.filesystem.product_ssot_filesystem_reader import (
    ProductSsotFilesystemReader,
)
from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.design_review_ledger_reader import (
    DesignReviewLedgerReader,
)
from des.adapters.driven.logging.devops_review_ledger_reader import (
    DevopsReviewLedgerReader,
)
from des.adapters.driven.logging.discuss_review_ledger_reader import (
    DiscussReviewLedgerReader,
)
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import hook_protocol
from des.application.atdd_pure_prompt_validator import AtddPurePromptValidator
from des.application.pre_tool_use_service import PreToolUseService
from des.application.subagent_stop_service import SubagentStopService
from des.application.wave_activation_service import WaveActivationService
from des.domain.des_enforcement_policy import DesEnforcementPolicy
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
from des.ports.driven_ports.audit_log_writer import AuditLogWriter


def create_pre_tool_use_service(
    *,
    audit_writer_factory: Callable[[], AuditLogWriter] | None = None,
    deliverable_type: str | None = None,
) -> PreToolUseService:
    """Create PreToolUseService with production dependencies.

    Args:
        audit_writer_factory: Optional callable returning an AuditLogWriter.
            Falls back to ``create_audit_writer`` if None.
        deliverable_type: Resolved project deliverable type (ADR-PST-001,
            feature plugin-skill-deliverable-type). Threaded into the service so
            ``validate()`` can pass it pure into ``DesEnforcementPolicy.check``.
            ``None`` (default) preserves the existing app-code behaviour exactly.

    Returns:
        PreToolUseService configured for production use
    """
    factory = audit_writer_factory or hook_protocol._audit_writer_factory
    time_provider = SystemTimeProvider()
    audit_writer = factory()

    return PreToolUseService(
        marker_parser=DesMarkerParser(),
        audit_writer=audit_writer,
        time_provider=time_provider,
        enforcement_policy=DesEnforcementPolicy(),
        completeness_policy=MarkerCompletenessPolicy(),
        atdd_pure_validator=AtddPurePromptValidator(),
        wave_active_reader=WaveActiveFilesystemStore(),
        product_ssot_reader=ProductSsotFilesystemReader(),
        deliverable_type=deliverable_type,
    )


def create_wave_activation_service() -> WaveActivationService:
    """Create WaveActivationService over the production wave-active floor store.

    The ONLY application-side holder of the floor Reader+Writer at the
    PreToolUse seam (slice-07c): the hook adapter peeks the anchor-owned
    entry_pending flag through it and clears it ONLY on an allowed entering
    dispatch (clear-on-allow NORMATIVE).
    """
    store = WaveActiveFilesystemStore()
    return WaveActivationService(reader=store, writer=store)


def create_subagent_stop_service(
    *,
    audit_writer_factory: Callable[[], AuditLogWriter] | None = None,
) -> SubagentStopService:
    """Create SubagentStopService with production dependencies.

    Args:
        audit_writer_factory: Optional callable returning an AuditLogWriter.
            Falls back to ``create_audit_writer`` if None.

    Returns:
        SubagentStopService configured for production use
    """
    factory = audit_writer_factory or hook_protocol._audit_writer_factory
    time_provider = SystemTimeProvider()
    audit_writer = factory()

    # fix-floor-auto-close-cross-wave: one floor store instance serves BOTH the
    # read-only reader (the gate-OUT active-wave read) and the writer capability
    # (the cross-wave auto-close clear()) -- the single SSOT floor adapter.
    wave_active_store = WaveActiveFilesystemStore()

    return SubagentStopService(
        audit_writer=audit_writer,
        time_provider=time_provider,
        wave_active_reader=wave_active_store,
        wave_active_writer=wave_active_store,
        feature_delta_reader=FeatureDeltaFilesystemReader(),
        discuss_review_reader=DiscussReviewLedgerReader(),
        # f-design-devops-review-gate slice-02 (the literal-lift): per-wave
        # review-verdict readers for the DESIGN / DEVOPS gate-out consumer rows.
        # The SAME generic ReviewVerdictGate core serves both waves; only the
        # ledger-record family the reader selects on differs.
        review_readers={
            "design": DesignReviewLedgerReader(),
            "devops": DevopsReviewLedgerReader(),
        },
    )
