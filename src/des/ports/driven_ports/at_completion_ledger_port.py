"""Driven ports for the AT-completion ledger -- the DIP boundary the domain uses.

AD-02 DIP fix (ARCH_TECH_DEBT): the domain (`conversion_planner`, `done_gate`)
must depend on an ABSTRACTION, never on the concrete
``des.adapters.driven.logging.at_completion_ledger.AtCompletionLedger``. This
module declares the MINIMAL abstractions the domain actually consumes:

  * ``AtCompletionLedgerPort`` -- the write surface the conversion planner's
    ledger-seeding path invokes (``append_gate_event`` only).
  * ``LedgerFactoryPort`` -- a factory the domain accepts as an injected
    collaborator so it never CONSTRUCTS the concrete adapter itself. The
    ``feature_id`` / ``project_root`` a ledger is rooted at are known only at
    ``execute``-time, so the inversion is a factory port (the adapter is built
    at the composition root and the factory is threaded down).

The two environmental-e2e event-name constants live here as the SSOT (domain
vocabulary the ``done_gate`` consumes). The concrete adapter re-exports them so
every existing importer that reads them off the adapter stays unbroken.

Defined by: domain ledger-seeding + done-gate requirements.
Implemented by: ``AtCompletionLedger`` / ``AtCompletionLedgerFactory``
(infrastructure adapters under ``des.adapters.driven.logging``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path


# Environmental-e2e gate event-name constants -- the SSOT. The done-gate domain
# consumes these names to compute its verdict; the concrete adapter re-exports
# them (backward-compatible for every caller that reads them off the adapter).
ENVIRONMENTAL_E2E_GATE_RAN = "EnvironmentalE2eGateRan"
ENVIRONMENTAL_E2E_VERIFIED = "EnvironmentalE2eVerified"

# Applicability NA-marker event-name constants (fix-feature-end-ws-gate-
# applicability slice-04) -- the SSOT. Each is the DISTINCT not-applicable marker
# a leg mints on its un-gameable NA signal; the downstream done-gate reconciles
# the required record by itself OR its NA marker (never a false `*Verified*`).
ENVIRONMENTAL_E2E_NOT_APPLICABLE = "EnvironmentalE2eNotApplicable"
COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT = "CoverageMapNotApplicableAtDistillExit"
COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT = "CoverageMapNotApplicableAtDeliverExit"


class AtCompletionLedgerPort(ABC):
    """Driven port: the AT-completion ledger write surface the domain uses.

    The conversion planner's ledger-seeding path consumes only
    ``append_gate_event`` -- the port surface is kept minimal to exactly what
    the domain invokes, per the hexagonal DIP boundary.
    """

    @abstractmethod
    def append_gate_event(
        self,
        event: str,
        slice_id: str,
        *,
        feature_id: str | None = None,
    ) -> dict[str, Any]:
        """Append one slice gate-boundary audit record. Returns the record."""
        ...


class LedgerFactoryPort(ABC):
    """Driven port: builds an ``AtCompletionLedgerPort`` for a feature/root.

    The domain accepts this factory as an injected collaborator so it never
    imports or constructs the concrete adapter. The ``feature_id`` /
    ``project_root`` are execute-time inputs, so construction is inverted
    behind this factory rather than handed a pre-built ledger.
    """

    @abstractmethod
    def create_for_seeding(
        self, feature_id: str, project_root: Path
    ) -> AtCompletionLedgerPort:
        """Build the per-feature ledger writer rooted at ``project_root``."""
        ...


__all__ = [
    "COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT",
    "COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT",
    "ENVIRONMENTAL_E2E_GATE_RAN",
    "ENVIRONMENTAL_E2E_NOT_APPLICABLE",
    "ENVIRONMENTAL_E2E_VERIFIED",
    "AtCompletionLedgerPort",
    "LedgerFactoryPort",
]
