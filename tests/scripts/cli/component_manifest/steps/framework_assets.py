"""Framework-asset inspection composition for slices 04 and 05.

F-DESIGN-COMPONENT-MANIFEST slices 04-05 are framework-asset edit slices: they
make the manifest *produced* (the DESIGN wave's task/agent/skill changes) and
*wired* (the DESIGN-exit reviewer check + the quality_gates catalog entry).

This composition reads the real repo's framework assets -- the production
files, not fixtures (Pillar 3). Step bodies delegate to its query methods; no
inline parsing logic. Slices 04-05 carry no PBT universe (framework-asset
edits) -- example-based assertions per Mandate 11.

RED-scaffold note: on master the DESIGN-wave assets do NOT yet mention the
component manifest, and this feature's own component-manifest.yaml does not yet
exist -- so every slice-04/05 query returns the not-yet-present value and the
scenarios are RED (missing functionality), not BROKEN. slices 04-05 edit the
real assets at GREEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[5]

_DESIGN_TASK = _REPO_ROOT / "nWave" / "tasks" / "nw" / "design.md"
_ARCHITECT_AGENT = _REPO_ROOT / "nWave" / "agents" / "nw-solution-architect.md"
_ARCH_PATTERNS_SKILL = (
    _REPO_ROOT / "nWave" / "skills" / "nw-architecture-patterns" / "SKILL.md"
)
_CATALOG = _REPO_ROOT / "nWave" / "framework-catalog.yaml"
_OWN_MANIFEST = (
    _REPO_ROOT
    / "docs"
    / "feature"
    / "fix-design-component-manifest"
    / "design"
    / "component-manifest.yaml"
)
_REVIEWER_PROTOCOL = (
    _REPO_ROOT
    / "docs"
    / "feature"
    / "fix-design-component-manifest"
    / "design"
    / "reviewer-check-protocol.md"
)

# The artifact name every producer-side asset must mention.
_ARTIFACT = "component-manifest.yaml"


@dataclass(frozen=True)
class AssetText:
    """The text of a framework asset, or empty when the file is absent."""

    text: str

    def mentions(self, needle: str) -> bool:
        return needle in self.text


def _read(path: Path) -> AssetText:
    if not path.is_file():
        return AssetText(text="")
    return AssetText(text=path.read_text(encoding="utf-8"))


class FrameworkAssetComposition:
    """Reads the production framework assets the manifest producer touches."""

    # --- slice-04: the DESIGN-wave producer change ---------------------------

    def design_task_lists_manifest_as_output(self) -> bool:
        """True iff design.md names the manifest in its Expected Outputs."""
        return _read(_DESIGN_TASK).mentions(_ARTIFACT)

    def architect_quality_gates_check_manifest(self) -> bool:
        """True iff the architect agent's Quality Gates name the manifest gate."""
        text = _read(_ARCHITECT_AGENT).text
        return _ARTIFACT in text and "Quality Gates" in text

    def architecture_patterns_skill_documents_manifest(self) -> bool:
        """True iff the nw-architecture-patterns skill documents the artifact."""
        text = _read(_ARCH_PATTERNS_SKILL).text
        return _ARTIFACT in text and "Component Manifest" in text

    # --- slice-04: the self-dogfood manifest ---------------------------------

    @property
    def own_manifest_path(self) -> Path:
        return _OWN_MANIFEST

    def own_manifest_exists(self) -> bool:
        """True iff this feature ships its own component-manifest.yaml (V2)."""
        return _OWN_MANIFEST.is_file()

    # --- slice-05: the wiring ------------------------------------------------

    def catalog_registers_manifest_gate(self) -> bool:
        """True iff framework-catalog.yaml has the manifest quality_gates entry."""
        text = _read(_CATALOG).text
        return "component-manifest" in text and "quality_gates" in text

    def catalog_exposes_not_applicable_signal(self) -> bool:
        """True iff the catalog entry exposes the countable not_applicable signal."""
        return _read(_CATALOG).mentions("manifest.not_applicable")

    def reviewer_protocol_exists(self) -> bool:
        """True iff the DESIGN-exit reviewer-check protocol document exists."""
        return _REVIEWER_PROTOCOL.is_file()

    def reviewer_protocol_names_semantic_veto_item(self) -> bool:
        """True iff the protocol names the semantic declaration-correctness veto.

        A presence check on the protocol document (W1 / B2): the protocol must
        name the semantic check as a reviewer-veto item -- it does NOT test the
        veto judgment itself, which has no deterministic oracle.
        """
        text = _read(_REVIEWER_PROTOCOL).text
        return "reviewer-veto" in text and "declaration-correctness" in text
