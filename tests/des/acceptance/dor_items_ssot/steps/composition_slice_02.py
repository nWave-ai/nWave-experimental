"""Composition root for dor-items-ssot slice-02 (cross-artifact skill render).

slice-02 of dor-items-ssot: the DoR-validation skill the reviewer ACTUALLY
loads (``nWave/skills/nw-dor-validation/SKILL.md``) stops claiming "8 Items" and
presents the same canonical nine the SSOT carries -- so the loaded enforcement
path no longer drops the Outcome-KPIs hard gate (AD-55 live-hole closure).

TWO real artifacts, no test doubles (Pillar 3, Mandate 9/11 example-only):

  1. The reviewer-loaded skill itself -- ``nWave/skills/nw-dor-validation/SKILL.md``
     -- read from the REAL repository tree (not a tmp_path fixture: the contract
     under test IS the shipped skill). This is the cross-artifact SUT, the SAME
     accepted shape as the sibling ``fix_design_reuse_first_gate_cli`` slice-05
     ``skill_assets.py`` (a real shipped skill file + structural-content
     assertions for a skill-text-change slice).

  2. The canonical SSOT, driven through the PRODUCTION driving port -- the real
     ``scripts/cli/read_dor_items.py`` standalone reader invoked as a subprocess
     (Layer 3 subprocess, Mandate-13 driving-port-only; the SAME driving surface
     slice-01 established). Used ONLY by the coherence AT to prove the skill's
     presented items agree with the SSOT items mechanically (render-not-drift,
     DESIGN DDD-4). The composition NEVER imports ``load_dor_items`` / the
     reader ``main`` and calls it at the step boundary (that would collapse the
     leg into a Layer-1 unit test, forbidden by Mandate-13 / S2): the only entry
     is the real subprocess.

WHY THIS RED-fails for the RIGHT reason (MISSING_FUNCTIONALITY, never BROKEN):
on master the skill enumerates only Items 1-8 and claims "8 Items" (``:10``); it
does NOT carry the Outcome-KPIs item and carries NO SSOT pointer. The skill-view
parser therefore reports ``presents_outcome_kpis_item=False``,
``claims_stale_count=True``, ``ssot_pointer_present=False`` -- each Then asserts
the GREEN-state opposite and fails with a semantic ``AssertionError``, never a
collection / import / setup error. The composition imports only test-local types
+ stdlib (``re`` / ``subprocess`` / ``json``), so the suite COLLECTS cleanly.

CRITICAL anti-trap (F-REUSE-GATE slice-05 hit this): the GREEN skill edit MUST
NOT contain the literal ``nWave/data/`` -- ``validate_no_data_refs.py`` forbids
it in any framework ``.md``. The slice-02 ATs therefore assert the skill's SSOT
pointer is present AND avoids that forbidden prefix (it cites the bare SSOT
filename + the standalone reader instead). A GREEN that satisfies these ATs
passes ``validate_no_data_refs.py`` by construction.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts.cli import read_dor_items
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import CanonicalReadinessSet, ReadinessItem
from .domain_types_slice_02 import (
    CANONICAL_ITEM_COUNT_CLAIM,
    CANONICAL_READINESS_ITEMS,
    FORBIDDEN_DATA_PREFIX,
    OUTCOME_KPIS_ITEM,
    SSOT_FILENAME_TOKEN,
    SSOT_READER_TOKEN,
    STALE_ITEM_COUNT_CLAIM,
    LoadedSkillView,
)


# THIS file lives at
# tests/des/acceptance/dor_items_ssot/steps/composition_slice_02.py -> 5 parents
# up is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The reviewer-loaded skill -- the cross-artifact SUT.
_DOR_SKILL_RELPATH = Path("nWave") / "skills" / "nw-dor-validation" / "SKILL.md"

# The DoR-checklist section heading the skill carries. The readiness-item
# enumeration the reviewer checks lives under THIS heading -- it is parsed
# distinctly from the unrelated "Antipattern Detection (8 Patterns)" section so
# the antipattern count is never mistaken for the readiness-item count.
_CHECKLIST_HEADING_RE = re.compile(
    r"^##\s+Definition of Ready Checklist.*$", re.MULTILINE
)

# The stale / canonical count claims appear in the checklist section heading
# itself ("(8 Items - Hard Gate)" today; "(9 Items - Hard Gate)" once GREEN).
#
# Render-shape tolerance (avoids over-constraining GREEN): DESIGN DDD-4 requires
# the skill items be "canonical-9 transcribed from SSOT", and the slice-04 drift
# gate compares "item count/ids" -- NOT a specific markdown heading shape. The
# crafter is free to render the nine as ``### Item N:`` sub-headings (today's
# shape) OR a numbered list (the ``nw-product-owner.md:176`` shape). The
# enumeration is therefore extracted by detecting which CANONICAL SSOT item
# strings appear verbatim in the checklist section (authority = the SSOT
# short-form strings the GREEN transcribes), in their canonical order -- a GREEN
# that transcribes the SSOT items passes regardless of the markdown container.


class LoadedSkillComposition:
    """Production composition root over the live nw-dor-validation skill asset.

    The asset is the shipped ``nWave/skills/nw-dor-validation/SKILL.md`` file
    itself -- this slice's contract is that the reviewer-loaded skill copy
    presents the canonical nine (incl. Outcome-KPIs) and points at the SSOT
    without the forbidden ``nWave/data/`` literal.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _REPO_ROOT
        self._skill_path = self._repo_root / _DOR_SKILL_RELPATH

    # --- cross-artifact read surface (the loaded skill) ---------------------

    def read_loaded_skill(self) -> LoadedSkillView:
        """Parse the shipped DoR-validation skill into its port-exposed view."""
        text = self._skill_text()
        return _parse_loaded_skill(text)

    def skill_bytes(self) -> bytes:
        """Raw shipped-skill bytes -- read-only universe snapshot (Mandate 8)."""
        return self._skill_path.read_bytes() if self._skill_path.is_file() else b""

    # --- coherence leg (the SSOT via the real driving port) -----------------

    def read_ssot_canonical_set(self) -> CanonicalReadinessSet:
        """Invoke the REAL ``scripts/cli/read_dor_items.py`` and parse its output.

        Layer 3 subprocess (Mandate-13): the coherence AT asks the production
        reader for the SSOT's canonical set so it can assert the skill presents
        the SAME items the SSOT carries (render-not-drift). An empty/non-zero
        result surfaces as the EMPTY set, never a raised setup error.
        """
        completed = self._run_reader(["--format", "json"])
        return _parse_ssot_set(completed.stdout, completed.returncode)

    # --- internals ----------------------------------------------------------

    def _skill_text(self) -> str:
        if not self._skill_path.is_file():
            return ""
        return self._skill_path.read_text(encoding="utf-8")

    def _run_reader(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        exit_code, stdout, stderr = run_cli_in_process(
            argv,
            cwd=self._repo_root,
            main=read_dor_items.main,
        )
        return subprocess.CompletedProcess(
            args=argv, returncode=exit_code, stdout=stdout, stderr=stderr
        )


# --- pure parsers -----------------------------------------------------------
# Each composition method is a single delegation (Mandate-12 criterion 3); the
# parsing logic is the single source of truth, kept out of step bodies.


def _checklist_section(text: str) -> str:
    """Return the DoR-checklist section text (heading -> next ``## `` heading).

    Scopes the readiness-item enumeration to the DoR checklist section so the
    unrelated "Antipattern Detection (8 Patterns)" section's "8" is never read
    as a readiness count. Whole-document fallback when the heading is absent so
    the assertions still run against *something* and fail loudly.
    """
    m = _CHECKLIST_HEADING_RE.search(text)
    if m is None:
        return text
    start = m.start()
    rest = text[m.end() :]
    nxt = rest.find("\n## ")
    end = m.end() + (nxt if nxt != -1 else len(rest))
    return text[start:end]


def _presented_items(section: str) -> tuple[str, ...]:
    """The canonical SSOT item strings the skill presents, in canonical order.

    Render-shape tolerant (see module note): an item counts as "presented" iff
    its canonical SSOT string appears verbatim in the checklist section. Returns
    them in canonical (id) order so the coherence AT can assert exact equality
    with the SSOT set. A GREEN that transcribes the SSOT items -- as headings or
    as a numbered list -- presents all nine; today's stale skill presents none
    of the canonical short-form strings (it carries verbose title-case headings
    and omits Item 9), so the count RED-fails honestly.
    """
    return tuple(item for item in CANONICAL_READINESS_ITEMS if item in section)


def _parse_loaded_skill(text: str) -> LoadedSkillView:
    """Extract the slice-02 cross-artifact contract from the shipped skill text."""
    section = _checklist_section(text)
    items = _presented_items(section)
    presents_outcome_kpis = OUTCOME_KPIS_ITEM in section
    claims_stale = STALE_ITEM_COUNT_CLAIM in section
    claims_canonical = CANONICAL_ITEM_COUNT_CLAIM in section
    pointer_present = SSOT_FILENAME_TOKEN in text or SSOT_READER_TOKEN in text
    pointer_uses_forbidden_prefix = FORBIDDEN_DATA_PREFIX in text
    return LoadedSkillView(
        enumerated_items=items,
        claims_stale_count=claims_stale,
        claims_canonical_count=claims_canonical,
        presents_outcome_kpis_item=presents_outcome_kpis,
        ssot_pointer_present=pointer_present,
        ssot_pointer_uses_forbidden_prefix=pointer_uses_forbidden_prefix,
    )


def _parse_ssot_set(stdout: str, returncode: int) -> CanonicalReadinessSet:
    """Parse the reader's JSON listing into the observable SSOT set."""
    if returncode != 0:
        return CanonicalReadinessSet(items=(), separate_hard_gates=())
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        return CanonicalReadinessSet(items=(), separate_hard_gates=())
    item_names = payload.get("items", []) if isinstance(payload, dict) else []
    hard_gates = payload.get("hard_gates", []) if isinstance(payload, dict) else []
    return CanonicalReadinessSet(
        items=tuple(ReadinessItem(name=str(name)) for name in item_names),
        separate_hard_gates=tuple(str(gate) for gate in hard_gates),
    )


__all__ = [
    "LoadedSkillComposition",
]
