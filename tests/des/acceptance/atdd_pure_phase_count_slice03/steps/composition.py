"""Composition root for the skill-prose-to-runtime parity slice.

Mandate-13 (driving-port-only): the SUT is driven exclusively through two real
observables at Layer 3 subprocess + artifact-read:

* the shipped ``python -m des.cli.phases`` CLI (real subprocess) — yields the
  runtime canonical phase model;
* the real nw-deliver ``SKILL.md`` prose artifact on disk — yields the
  documented phase model.

There is ZERO ``from des.domain`` / ``des.application`` / ``des.adapters``
import here: the runtime set is obtained only through the CLI driving port, so
the test cannot bypass the boundary and read the enum directly.

All parity logic is SSOT here (Mandate-12 criterion 3): step bodies invoke
these service methods and never inline business logic.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .domain_types import (
    DeliverySkill,
    DocumentedPhaseModel,
    PhaseFormat,
    RuntimePhaseModel,
)


# Repo root: this file is tests/des/acceptance/atdd_pure_phase_count_slice03/steps/
_REPO_ROOT = Path(__file__).resolve().parents[5]

_SKILL_PATHS = {
    DeliverySkill.NW_DELIVER: _REPO_ROOT
    / "nWave"
    / "skills"
    / "nw-deliver"
    / "SKILL.md",
}

# Phase-member tokens the legacy 7-phase A-to-G sequence used (the actual member
# names the legacy nw-deliver prose + the LEGACY_PHASE_ALIASES replay map speak:
# A_GREEN_ATS / B_COVERAGE_CLEANUP / C_REVIEWER_AUDIT / D_GAP_ROUTING /
# E_BATCH_REFACTOR / F_FINAL_REVIEW / G_COMMIT). A token counts as "retired" only
# if the live runtime no longer lists it as canonical — the verdict is DERIVED
# from the runtime set (subtraction below), never hard-coded. C_REVIEWER_AUDIT
# survives the 7->3 reduction, so it is correctly NOT flagged once subtracted
# against the live canonical names; D_REFACTOR_COMMIT is canonical (not a legacy
# token) so it is absent from this set by construction.
_LEGACY_PHASE_TOKENS = frozenset(
    {
        "A_GREEN_ATS",
        "B_COVERAGE_CLEANUP",
        "C_REVIEWER_AUDIT",
        "D_GAP_ROUTING",
        "E_BATCH_REFACTOR",
        "F_FINAL_REVIEW",
        "G_COMMIT",
    }
)

# Count-claim phrases the legacy prose used to assert a seven-phase model.
_SEVEN_PHASE_PHRASES = frozenset({"seven phases", "7-phase", "seven-phase"})

# Human-readable spellings of the retired DELIVER phases. Unlike the member
# tokens above (whose retired-status is DERIVED from the live runtime by
# subtraction), these are PURE-LEGACY spellings with no canonical equivalent
# that survives the 7->3 reduction: a 3-phase model has no "Phase G" / "Phase
# F" / "Phase E" / "Phase B" and no "A-G" / "A→G" span by construction, so they
# can NEVER become canonical. A static retired-narrative set is therefore the
# correct guard here. Phase A / Phase C / Phase D human spellings are
# deliberately EXCLUDED — they can legitimately name the surviving canonical
# phases (A_GREEN / C_REVIEWER_AUDIT / D_REFACTOR_COMMIT).
#
# Each phrase is matched on a WORD BOUNDARY (compiled below), not as a bare
# substring: "Phase B" must not match inside legitimate prose like "Phase
# Boundary". Word-boundary matching makes the guard MORE precise (it still
# catches a standalone "Phase B" retired-phase reference) without raising a
# false positive on an unrelated English word that merely shares the prefix.
_RETIRED_NARRATIVE_PHRASES = frozenset(
    {
        "Phase G",
        "Phase F",
        "Phase E",
        "Phase B",
        "A-G",
        "A→G",
    }
)

_RETIRED_NARRATIVE_PATTERNS = {
    phrase: re.compile(rf"{re.escape(phrase)}\b")
    for phrase in _RETIRED_NARRATIVE_PHRASES
}


class ParityComposition:
    """Single source of truth for the prose-to-runtime parity computation."""

    def runtime_phase_model(self) -> RuntimePhaseModel:
        """Project the canonical phase model through the shipped CLI."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.phases",
                "--format",
                PhaseFormat.JSON.value,
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
        return RuntimePhaseModel.from_cli_json(result.stdout)

    def documented_phase_model(self, skill: DeliverySkill) -> DocumentedPhaseModel:
        """Read the real skill prose artifact."""
        prose = _SKILL_PATHS[skill].read_text(encoding="utf-8")
        return DocumentedPhaseModel(prose=prose)

    def canonical_names_absent_from_prose(
        self, documented: DocumentedPhaseModel, runtime: RuntimePhaseModel
    ) -> frozenset[str]:
        """Runtime canonical phase names that the prose fails to mention."""
        return frozenset(
            name for name in runtime.canonical_names if name not in documented.prose
        )

    def retired_phase_tokens_in_prose(
        self, documented: DocumentedPhaseModel, runtime: RuntimePhaseModel
    ) -> frozenset[str]:
        """Legacy phase tokens + human spellings present in the prose.

        Two retired classes are folded into one result so the single wired
        Then-step asserts both:

        * member tokens (``A_GREEN_ATS`` … ``G_COMMIT``): retired-status is
          DERIVED from the live runtime — a token counts as retired iff it is
          NOT in the runtime canonical names. This keeps the guard from
          drifting: if a future runtime re-promoted a member, the guard would
          automatically stop flagging it.
        * human-readable narrative spellings (``Phase G`` / ``A-G`` / …): a
          static set of pure-legacy spellings that can never be canonical in a
          3-phase model (see ``_RETIRED_NARRATIVE_PHRASES``).
        """
        retired_tokens = _LEGACY_PHASE_TOKENS - runtime.canonical_names
        present_tokens = frozenset(
            token for token in retired_tokens if token in documented.prose
        )
        return present_tokens | self.retired_narrative_phrases_in_prose(
            documented, runtime
        )

    def retired_narrative_phrases_in_prose(
        self, documented: DocumentedPhaseModel, runtime: RuntimePhaseModel
    ) -> frozenset[str]:
        """Human-readable retired-phase spellings present in the prose.

        ``_RETIRED_NARRATIVE_PHRASES`` is a static set of pure-legacy spellings
        with no surviving canonical equivalent in the 3-phase model. The
        ``runtime`` argument is accepted for signature symmetry with the other
        parity computations and to keep the guard honest if the model ever
        expands past three phases — but the set is static by construction
        because these spellings can never re-enter a 3-phase canonical model.

        Matching is word-boundary anchored so "Phase B" does not false-positive
        on "Phase Boundary" and "A-G" does not match inside a longer token.
        """
        return frozenset(
            phrase
            for phrase, pattern in _RETIRED_NARRATIVE_PATTERNS.items()
            if pattern.search(documented.prose)
        )

    def stale_count_phrases_in_prose(
        self, documented: DocumentedPhaseModel, runtime: RuntimePhaseModel
    ) -> frozenset[str]:
        """Seven-phase count phrases present in prose while runtime count != 7."""
        if runtime.count == 7:
            return frozenset()
        return frozenset(
            phrase for phrase in _SEVEN_PHASE_PHRASES if phrase in documented.prose
        )
