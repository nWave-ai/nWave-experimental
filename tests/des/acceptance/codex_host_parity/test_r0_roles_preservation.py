# @feature-codex-host-parity
# @slice-01
"""R0 acceptance contracts for lossless Claude-role source extraction.

These tests deliberately drive the stable public-role catalogue boundary.  The
future canonical extractor must be introduced there before either host renderer
can consume a role; importing a future Codex renderer here would turn absence
of that renderer into a collection failure instead of an active RED assertion.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.shared import agent_catalog


_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_EXPECTED_PUBLIC_ROLE_NAMES = (
    "acceptance-designer",
    "acceptance-designer-reviewer",
    "agent-builder",
    "agent-builder-reviewer",
    "data-engineer",
    "data-engineer-reviewer",
    "ddd-architect",
    "ddd-architect-reviewer",
    "diverger",
    "diverger-reviewer",
    "documentarist",
    "documentarist-reviewer",
    "functional-software-crafter",
    "nwave-buddy",
    "platform-architect",
    "platform-architect-reviewer",
    "plugin-validator",
    "product-discoverer",
    "product-discoverer-reviewer",
    "product-owner",
    "product-owner-reviewer",
    "researcher",
    "researcher-reviewer",
    "skill-reviewer",
    "software-crafter",
    "software-crafter-reviewer",
    "solution-architect",
    "solution-architect-reviewer",
    "system-designer",
    "system-designer-reviewer",
    "test-optimizer",
    "test-optimizer-reviewer",
    "troubleshooter",
    "troubleshooter-reviewer",
    "user-examiner",
)
_EXPECTED_SOURCE_POPULATION_SHA256 = (
    "039de1a906369f057c0c53fc997199f4f462715f87d3b1b81bdb53a095481b9b"
)


def _public_claude_role_sources() -> dict[str, bytes]:
    """Return the public Claude-role source bytes from the current catalogue."""
    nwave_root = _PROJECT_ROOT / "nWave"
    public_names = agent_catalog.load_public_agents(nwave_root)
    agents_dir = nwave_root / "agents"
    return {
        name: (agents_dir / f"nw-{name}.md").read_bytes()
        for name in sorted(public_names)
    }


def _population_digest(sources: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, source in sorted(sources.items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(source)
        digest.update(b"\0")
    return digest.hexdigest()


def _extract_canonical_role_sources() -> tuple[object, ...]:
    """Drive the R0 source-contract boundary before any Codex compilation."""
    extractor = getattr(agent_catalog, "extract_canonical_role_sources", None)
    assert callable(extractor), (
        "R0 requires scripts.shared.agent_catalog.extract_canonical_role_sources "
        "so canonical source contracts are created before Claude or Codex "
        "rendering; add that source-only extraction boundary."
    )
    return tuple(extractor(_PROJECT_ROOT / "nWave"))


def test_r0_roles_preservation_extracts_every_public_claude_role_in_catalogue_order():
    """Every public Claude role remains one canonical source-contract record."""
    expected_sources = _public_claude_role_sources()
    assert tuple(expected_sources) == _EXPECTED_PUBLIC_ROLE_NAMES
    assert _population_digest(expected_sources) == _EXPECTED_SOURCE_POPULATION_SHA256
    contracts = _extract_canonical_role_sources()

    extracted_names = [contract.identity.name for contract in contracts]

    assert extracted_names == sorted(expected_sources), (
        "R0 source-contract extraction must preserve the complete public Claude "
        "role inventory in deterministic catalogue order; do not omit, duplicate, "
        "or invent a role before host compilation."
    )


def test_r0_roles_preservation_keeps_each_public_claude_role_source_byte_exact():
    """Canonical extraction retains the exact frontmatter-and-Markdown payload."""
    expected_sources = _public_claude_role_sources()
    contracts = _extract_canonical_role_sources()

    extracted_bytes = {
        contract.identity.name: contract.source_bytes for contract in contracts
    }

    assert extracted_bytes == expected_sources, (
        "R0 canonical source contracts must retain byte-exact public Claude role "
        "sources, including frontmatter, Markdown, quoting, whitespace, and line "
        "endings; host-specific rendering may happen only after this boundary."
    )
