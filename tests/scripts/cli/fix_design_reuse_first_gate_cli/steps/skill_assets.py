"""Skill-asset composition root for slice-05 (cross-artifact checks).

F-DESIGN-REUSE-FIRST-GATE-CLI slice-05 (F-REUSE-GATE-COVER-METHODOLOGY-
COMPONENTS). DDD-12 (skill scope extension). Mandate-12 + Pillar 3.

slice-05 closes the seam at the PRODUCING end of the gate. The gate's
methodology file-component unit (slice-03) is non-vacuous only if the upstream
artifact-producing skill instructs the architect to declare methodology
components. The SUT of AT1/AT2 is therefore the relationship between two real
repository assets:

  - the human-facing copy in ``nWave/skills/nw-design/SKILL.md`` (the
    Reuse-first DESIGN exit-gate prose + the lenient-match note), and
  - the production gate's methodology-path defaults
    (``MethodologyPathKind`` -- ``nWave/data`` / ``nWave/skills`` /
    ``scripts/cli``) that the prose MUST name for the gate to be non-vacuous.

This mirrors the sibling ``fix-design-reuse-first-gate`` slice-03
``framework_assets.py`` cross-artifact pattern (skill template heading/columns
== a normative constant) -- the accepted shape for a skill-text-change slice.

Layer 3 (framework-asset acceptance): the skill is read from the real
repository tree (not a tmp_path fixture -- the contract under test IS the
shipped skill). Example-only, no PBT (Mandate 9/11): each check is a single
structural-content assertion over a shipped asset; there is no input domain to
generate.

Business logic lives here as the single source of truth; step bodies delegate
to ``SkillAssetComposition`` methods and never inline logic (Mandate-12
criterion 3).

RED contract (Mandate 7): on master the nw-design skill's Reuse-first exit-gate
prose scopes only NEW *classes* under ``src/`` (L115-116: "For each NEW class
declared under the feature's scoped-path (default ``src/``)") and the
lenient-match note has only the class-name form (L121-123: "the NEW class name
appearing anywhere..."). It names NONE of the methodology-path kinds and has NO
file-component path/stem form. The slice-05 assertions FAIL with a semantic
``AssertionError`` (MISSING_FUNCTIONALITY RED) and PASS once the slice-05
crafter EXTENDS the prose (DDD-12). Imports resolve cleanly -- the production
``MethodologyPathKind`` enum is shipped (slice-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    SKILL_NAMED_METHODOLOGY_PATHS,
    FileComponentMatchForm,
)


# Repository root -- five parents up from this file
# (.../tests/scripts/cli/fix_design_reuse_first_gate_cli/steps/skill_assets.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]

_NW_DESIGN_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-design" / "SKILL.md"


@dataclass
class ReuseFirstExitGateProseView:
    """The nw-design skill's Reuse-first DESIGN exit-gate prose surface.

    ``named_methodology_paths`` is the subset of the gate's methodology-path
    defaults (``nWave/data`` / ``nWave/skills`` / ``scripts/cli``) the prose
    actually names. ``names_all_methodology_paths`` is True iff the prose names
    every one of them -- the coherence condition that makes the gate's
    file-component unit non-vacuous (DDD-12).
    """

    named_methodology_paths: tuple[str, ...]
    names_all_methodology_paths: bool


@dataclass
class LenientMatchNoteView:
    """The nw-design skill's lenient-match note surface.

    ``documents_path_form`` is True iff the note documents the file-component
    *path* form (a methodology file's repo-relative path named in a cell).
    ``documents_stem_form`` is True iff it documents the *stem* form. slice-05
    requires BOTH (DDD-10: path-form and stem-form are both accepted).
    """

    documents_path_form: bool
    documents_stem_form: bool


@dataclass
class SkillAssetComposition:
    """Production composition root over the live nw-design skill asset.

    The asset is the shipped ``nWave/skills/nw-design/SKILL.md`` file itself --
    this slice's contract is that the human-facing skill copy instructs the
    architect to declare methodology components in lockstep with the gate's
    methodology-path defaults. ``capture_universe`` snapshots the skill's bytes
    so the cross-artifact check proves it is read-only (Mandate 8).
    """

    nw_design_skill: Path = field(default=_NW_DESIGN_SKILL)

    # --- normative source ----------------------------------------------------

    @property
    def gate_methodology_paths(self) -> tuple[str, ...]:
        """The gate's methodology-path defaults the prose MUST name (DDD-12)."""
        return SKILL_NAMED_METHODOLOGY_PATHS

    # --- skill surface views -------------------------------------------------

    def read_exit_gate_prose(self) -> ReuseFirstExitGateProseView:
        """Parse the skill's Reuse-first DESIGN exit-gate prose surface."""
        text = self.nw_design_skill.read_text(encoding="utf-8")
        return _parse_exit_gate_prose(text)

    def read_lenient_match_note(self) -> LenientMatchNoteView:
        """Parse the skill's lenient-match note surface."""
        text = self.nw_design_skill.read_text(encoding="utf-8")
        return _parse_lenient_match_note(text)

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed snapshot for assert_state_delta (Mandate 8)."""
        return {"nw_design_skill.bytes": self.nw_design_skill.read_bytes()}


# --- pure parsers -----------------------------------------------------------
# Keep each composition method a single delegation (Mandate-12 criterion 3).

# The exit-gate prose block runs from its "### Reuse-first DESIGN exit gate"
# heading to the next "###"/"##" heading or the numbered step 6 that follows it.
_EXIT_GATE_HEADING = "### Reuse-first DESIGN exit gate"


def _exit_gate_prose_block(text: str) -> str:
    """Return the Reuse-first DESIGN exit-gate prose block of the skill text.

    Runs from the exit-gate heading up to (exclusive) the next ``##``/``###``
    heading or the numbered ``6.`` step that follows. The whole-document text is
    the fallback when the heading is absent (a malformed skill) so the
    coherence assertions still run against *something* and fail loudly.
    """
    start = text.find(_EXIT_GATE_HEADING)
    if start == -1:
        return text
    rest = text[start + len(_EXIT_GATE_HEADING) :]
    end_markers = ["\n## ", "\n### ", "\n6. "]
    end = min(
        (pos for pos in (rest.find(m) for m in end_markers) if pos != -1),
        default=len(rest),
    )
    return rest[:end]


def _parse_exit_gate_prose(text: str) -> ReuseFirstExitGateProseView:
    """Extract which gate methodology-path defaults the exit-gate prose names."""
    block = _exit_gate_prose_block(text)
    named = tuple(path for path in SKILL_NAMED_METHODOLOGY_PATHS if path in block)
    return ReuseFirstExitGateProseView(
        named_methodology_paths=named,
        names_all_methodology_paths=(len(named) == len(SKILL_NAMED_METHODOLOGY_PATHS)),
    )


def _parse_lenient_match_note(text: str) -> LenientMatchNoteView:
    """Detect the file-component path/stem forms in the lenient-match note.

    The slice-05 crafter extends the lenient-match note to document that a
    methodology file-component is justified iff its repo-relative *path* OR its
    *stem* appears in an Existing Component cell. The two forms are detected by
    their domain vocabulary inside the exit-gate prose block.
    """
    block = _exit_gate_prose_block(text).lower()
    return LenientMatchNoteView(
        documents_path_form=(
            FileComponentMatchForm.PATH.value in block and "file-component" in block
        ),
        documents_stem_form=(
            FileComponentMatchForm.STEM.value in block and "file-component" in block
        ),
    )
