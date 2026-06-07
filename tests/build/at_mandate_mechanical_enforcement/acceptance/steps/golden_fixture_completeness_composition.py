"""Composition-root service for the Tier-M golden-fixture-completeness meta-gate.

Provenance: feature `at-mandate-mechanical-enforcement`, slice-11 (DISTILL,
re-shaped to pytest-bdd after the carpaccio entry-gate required Gherkin
scenarios tagged @slice-11). ADR-TEST-002 D-D 3-tier model: Tier-S = the static
gates (slices 01-10), Tier-M = THIS meta-tier, Tier-J = agent-audit.

Mandate-12 (criteria 2+3): the structural-walk business logic lives HERE as the
single source of truth; step bodies invoke this service via typed parameters and
never inline logic. The "driving port" of the meta-gate is its own structural
filesystem walk over the OTHER gates' golden-fixture coverage — there is no
production rule module to drive (the meta-gate is a self-application contract,
not a Tier-S AST rule). It consumes NO capability and never touches
``src/des/testarch/capabilities.py``.

Genericità / no-AST / git-free (AD-21): pure ``pathlib`` filesystem-PRESENCE
walk — no AST, no git, no subprocess. Honest tagging: @component (auto-``unit``
under ``tests/build/``), NEVER @wiring_e2e/@subprocess — no spawn, no real I/O
beyond reading directory entries. (The meta-gate practises the honesty the
sibling seam-tag-honesty gate enforces.)

RED scaffold (Mandate-7 / ADR-025): ``GoldenFixtureCompletenessGate.outcome_of``
raises ``AssertionError`` (the RED token — NOT NotImplementedError, NOT
ImportError) until A_GREEN wires the body against ``required_artifacts(...)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    META_COMPLETE_ACCEPTANCE,
    META_INCOMPLETE_ACCEPTANCE,
    META_REAL_FIXTURES_DIR,
    GateCompletenessOutcome,
    GateCorpusKind,
)


@dataclass(frozen=True)
class GateUnderInspection:
    """One enumerated gate the meta-gate inspects for golden-fixture coverage.

    ``name``           : the gate fixture-dir name (snake_case, e.g.
                         ``seam_tag_honesty``).
    ``fixture_dir``    : the gate's fixture directory (holds clean_/violation_).
    ``acceptance_dir`` : the ``acceptance/`` dir holding the sibling ``.feature``
                         self-AT (the parent of ``fixtures/``).
    """

    name: str
    fixture_dir: Path
    acceptance_dir: Path


# Each corpus kind → the ``acceptance/`` dir whose ``fixtures/`` subtree the
# meta-gate enumerates. The real shipped gates live under the feature's own
# acceptance tree; the planted complete/incomplete corpora live off-tree under
# ``_meta_gate_fixtures/`` so the meta-gate never self-references.
_ACCEPTANCE_BY_KIND = {
    GateCorpusKind.REAL_SHIPPED: META_REAL_FIXTURES_DIR.parent,
    GateCorpusKind.PLANTED_COMPLETE: META_COMPLETE_ACCEPTANCE,
    GateCorpusKind.PLANTED_INCOMPLETE: META_INCOMPLETE_ACCEPTANCE,
}


class GoldenFixtureCompletenessGate:
    """The Tier-M meta-gate: walks a gate corpus and judges golden coverage."""

    def enumerate_gates(self, corpus: GateCorpusKind) -> list[GateUnderInspection]:
        """Filesystem walk: every gate fixture dir under the corpus' tree.

        SSOT for "which gates shipped" is the fixtures tree itself — NOT the
        production rule modules and NOT ``capabilities.py``. A directory is a
        gate iff it is a direct child of ``<acceptance>/fixtures/`` and is not a
        Python cache dir.
        """
        acceptance_dir = _ACCEPTANCE_BY_KIND[corpus]
        fixtures_dir = acceptance_dir / "fixtures"
        if not fixtures_dir.is_dir():
            return []
        gates: list[GateUnderInspection] = []
        for child in sorted(fixtures_dir.iterdir()):
            if not child.is_dir() or child.name == "__pycache__":
                continue
            gates.append(
                GateUnderInspection(
                    name=child.name,
                    fixture_dir=child,
                    acceptance_dir=acceptance_dir,
                )
            )
        return gates

    def required_artifacts(self, gate: GateUnderInspection) -> dict[str, bool]:
        """Presence map of the three golden artifacts the D-E meta-rule requires.

        Pure filesystem presence — no AST, no git. The self-AT is resolved by
        the structural rule established for this feature: ``<dir-name>`` kebab-
        cased is a PREFIX of exactly one ``.feature`` stem under ``acceptance/``
        (e.g. ``capability_registry`` -> ``capability-registry`` -> prefixes
        ``capability-registry-ssot.feature``; ``seam_tag_honesty`` ->
        ``seam-tag-honesty`` -> prefixes ``seam-tag-honesty-gate.feature``).
        """
        kebab = gate.name.replace("_", "-")
        has_violation = any(
            p.is_file() and p.name.startswith("violation_")
            for p in gate.fixture_dir.iterdir()
        )
        has_clean = any(
            p.is_file() and p.name.startswith("clean_")
            for p in gate.fixture_dir.iterdir()
        )
        has_self_at = any(
            f.stem.startswith(kebab) for f in gate.acceptance_dir.glob("*.feature")
        )
        return {
            "violation_fixture": has_violation,
            "clean_fixture": has_clean,
            "self_at_feature": has_self_at,
        }

    def outcome_of(self, gate: GateUnderInspection) -> GateCompletenessOutcome:
        """Project the golden-artifact presence onto the port-exposed verdict.

        RED-READY SCAFFOLD (Mandate-7 / ADR-025). A_GREEN replaces the body with::

            artifacts = self.required_artifacts(gate)
            return (
                GateCompletenessOutcome.COMPLETE
                if all(artifacts.values())
                else GateCompletenessOutcome.INCOMPLETE
            )

        Until then this raises the RED token (AssertionError) so both the
        precision and recall scenarios fail for the RIGHT reason on author — not
        ImportError, not a collection error, not a skip.
        """
        artifacts = self.required_artifacts(gate)
        return (
            GateCompletenessOutcome.COMPLETE
            if all(artifacts.values())
            else GateCompletenessOutcome.INCOMPLETE
        )


def build_gate() -> GoldenFixtureCompletenessGate:
    """Composition-root entry — the production object graph for the meta-gate AT."""
    return GoldenFixtureCompletenessGate()
