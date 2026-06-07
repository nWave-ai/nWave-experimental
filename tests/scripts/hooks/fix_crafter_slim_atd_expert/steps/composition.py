"""Composition root for slice-01 — the agent-prose surface audit.

slice-01 of F-CRAFTER-SLIM-ATD-EXPERT (DDD-7 walking-skeleton-first).

The driving port is the FILESYSTEM read of three asset files (one OOP
crafter agent, one FP crafter agent, one ``nw-execute`` dispatch skill).
The observable surface is the set of contract-clause presence/absence
verdicts produced by grep against the file content.

Layer 3 (filesystem / project asset). Example-only per Mandate 9/11 — sad
paths enumerated explicitly. No PBT machinery. Step bodies delegate to
``CrafterSurfaceAuditComposition`` methods; no inline logic (Mandate-12
criterion 3).

This composition is the PRODUCTION-wired audit (Pillar 3): the assets it
reads are the same assets shipped to users. No fixture-uniform substitute
ledger; the read is against the live repo tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    AssetPath,
    CrafterSurface,
    EscalationToken,
    LoopholePhrase,
)


# ---------------------------------------------------------------------------
# Asset-path map — the live, production-shipped repo paths under audit.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[5]

_SURFACE_TO_PATH: dict[CrafterSurface, AssetPath] = {
    CrafterSurface.OOP_CRAFTER_AGENT: AssetPath(
        str(_REPO_ROOT / "nWave/agents/nw-software-crafter.md")
    ),
    CrafterSurface.FP_CRAFTER_AGENT: AssetPath(
        str(_REPO_ROOT / "nWave/agents/nw-functional-software-crafter.md")
    ),
    CrafterSurface.NW_EXECUTE_DISPATCH: AssetPath(
        str(_REPO_ROOT / "nWave/skills/nw-execute/SKILL.md")
    ),
}


@dataclass(frozen=True)
class AuditOutcome:
    """The observable result of a contract-clause audit over an asset surface.

    Fields:
      ``surface``       — the audited surface (typed).
      ``asset_path``    — the resolved repo path the audit grepped.
      ``loophole_hits`` — dict of loophole phrase -> hit count; a SLIM-
                          compliant surface has every value equal to 0.
      ``escalation_hits`` — dict of escalation token -> hit count; a SLIM-
                            compliant surface that closed the loophole has
                            every value > 0.
    """

    surface: CrafterSurface
    asset_path: AssetPath
    loophole_hits: dict[LoopholePhrase, int]
    escalation_hits: dict[EscalationToken, int]


class CrafterSurfaceAuditComposition:
    """Production-wired composition root for the slice-01 agent-prose audit.

    The composition reads the live repo asset files (production composition
    root — Pillar 3) and returns typed audit outcomes. The crafter-slim
    contract is satisfied iff every loophole-phrase count is 0 AND every
    escalation-token count is > 0 for every surface.
    """

    def __init__(self) -> None:
        # No mutable state; the audit is a pure read against the repo tree.
        pass

    def asset_path_for(self, surface: CrafterSurface) -> AssetPath:
        """Resolve the repo-relative asset path for an audit surface."""
        return _SURFACE_TO_PATH[surface]

    def audit_surface(self, surface: CrafterSurface) -> AuditOutcome:
        """Run the SLIM-crafter contract audit against one asset surface.

        Returns the typed ``AuditOutcome``. The fail-for-the-right-reason
        contract is asserted by the step layer against the outcome's
        ``loophole_hits`` and ``escalation_hits`` dicts.
        """
        asset_path = self._SUT_lookup(surface)
        content = Path(asset_path).read_text(encoding="utf-8")
        loophole_hits = {
            phrase: content.count(phrase.value) for phrase in LoopholePhrase
        }
        escalation_hits = {
            token: content.count(token.value) for token in EscalationToken
        }
        return AuditOutcome(
            surface=surface,
            asset_path=asset_path,
            loophole_hits=loophole_hits,
            escalation_hits=escalation_hits,
        )

    def _SUT_lookup(self, surface: CrafterSurface) -> AssetPath:
        """Pure typed-lookup (Mandate-12 criterion 3 — no branching)."""
        return _SURFACE_TO_PATH[surface]
