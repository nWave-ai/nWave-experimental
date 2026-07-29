"""Regression pin -- D50 (Mikado des-optimization) compaction of the
``Dispatching an agent while a wave floor is ACTIVE`` section in
``nWave/data/orchestrator-affordance/spine-discipline.md``.

Context: ``docs/mikado/2026-07-29-payload-classification.md`` +
``docs/mikado/2026-07-29-payload-residency-classification.md`` established
that this section's detailed marker-syntax prose (the exact
``<!-- DES-WAVE: <wave> -->`` line, the ``des dispatch --mode atdd_pure``
requirement, and the ``des wave-clear --reason`` stale-floor escape) is
DUPLICATED, verbatim-parameterized, by the live ``WAVE_MARKER_BYPASS`` /
``ATDD_PURE_DISPATCH`` guard refusal messages in
``src/des/application/pre_tool_use_service.py`` (``_evaluate``/``validate``
S2 branch and ``_validate_atdd_pure_dispatch``) -- confirmed by reading both
recovery_suggestions lists before compacting. The section was shortened from
~2.45KB to keep only what the REACTIVE guard message cannot supply
proactively (that a wave floor gates dispatch at all, the mode-dependent
branch, the GDP-2 pre-check) plus short pointers to the guard for the exact
syntax.

This test is the claim-set equality proof for that compaction: every
distinct normative fact from the ORIGINAL section is asserted present here.
It must stay GREEN across the edit (there is no code under test -- the guard
messages themselves are pinned by
``test_wave_marker_allows_matching_wave_child_non_atdd_pure.py`` and the
atdd_pure dispatch acceptance suite; this file only pins the DOC side).
A future edit that silently drops one of these facts from the payload must
turn this file RED.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_PAYLOAD_PATH = Path("nWave/data/orchestrator-affordance/spine-discipline.md")

_SECTION_HEADING = "## Dispatching an agent while a wave floor is ACTIVE"

# One entry per distinct normative claim the pre-compaction prose carried.
# Each is a short, case-sensitive substring that must survive verbatim (or
# near-verbatim for the wave-clear command) inside the section body.
_REQUIRED_CLAIMS: dict[str, str] = {
    "wave_floor_gates_dispatch": ".nwave/wave-active/",
    "proactive_precheck_before_wall": "before a bare dispatch",
    "atdd_pure_uses_des_dispatch": "des dispatch --mode atdd_pure",
    "atdd_pure_never_hand_assembled": "hand-assemble",
    "des_dispatch_not_for_other_waves": "generates NO markers for these waves",
    "non_atdd_pure_uses_des_wave_marker": "<!-- DES-WAVE: <wave> -->",
    "guard_self_explains_on_refusal": "guard",
    "wave_clear_escape_named": "des wave-clear",
    "wave_clear_is_human_authorized": "human-authorized",
    "never_self_clear_unowned_floor": "self-clear",
}


def _read_section_body() -> str:
    text = _PAYLOAD_PATH.read_text(encoding="utf-8")
    start = text.index(_SECTION_HEADING)
    # Section ends at the next top-level "## " heading, or EOF.
    next_heading = text.find("\n## ", start + len(_SECTION_HEADING))
    return text[start : next_heading if next_heading != -1 else len(text)]


def _normalized(body: str) -> str:
    """Collapse whitespace runs (including line-wraps inside a backticked
    command) to a single space, so a claim split across a soft line-wrap in
    the markdown source still matches as one contiguous phrase."""
    return " ".join(body.split())


class TestWaveMarkerPayloadClaimsSurviveCompaction:
    def test_section_exists(self) -> None:
        text = _PAYLOAD_PATH.read_text(encoding="utf-8")
        assert _SECTION_HEADING in text, (
            "MISSING_SECTION: the 'Dispatching an agent while a wave floor "
            f"is ACTIVE' section vanished from {_PAYLOAD_PATH}. If the "
            "section was renamed, update _SECTION_HEADING here to match; if "
            "it was deleted, its normative claims (see _REQUIRED_CLAIMS) "
            "must be re-homed somewhere reachable before this test may be "
            "removed."
        )

    @pytest.mark.parametrize("claim_id,needle", list(_REQUIRED_CLAIMS.items()))
    def test_claim_survives(self, claim_id: str, needle: str) -> None:
        body = _normalized(_read_section_body())
        assert needle in body, (
            f"LOST_NORMATIVE_CLAIM ({claim_id}): expected substring "
            f"{needle!r} inside the 'Dispatching an agent while a wave "
            f"floor is ACTIVE' section of {_PAYLOAD_PATH}, not found. This "
            "claim was preserved verbatim across the D50 compaction "
            "(docs/mikado/2026-07-29-payload-residency-classification.md, "
            "'Savings gated on the parallel gate/agent-prose work') -- "
            "restore it or fold it into the live guard message this "
            "section points at "
            "(src/des/application/pre_tool_use_service.py) before removing "
            "it here."
        )

    def test_section_is_compacted_below_pre_compaction_size(self) -> None:
        """Locks in the D50 win: the section must not silently regrow past
        its pre-compaction size (2,451 bytes measured 2026-07-29 before the
        edit). A future re-verbosification is not forbidden -- but it must
        be a deliberate choice that bumps this ceiling, not a silent drift.
        """
        body = _read_section_body()
        # Pre-compaction size measured 2026-07-29: 2,450 bytes. Post-
        # compaction target: 1,032 bytes. Ceiling set well above the target
        # (headroom for small future rewording) but well below pre-
        # compaction size, so drift toward the old verbosity trips this
        # before it fully regrows.
        ceiling_bytes = 1600
        assert len(body.encode("utf-8")) < ceiling_bytes, (
            "SECTION_REGREW: the wave-floor-dispatch section is now "
            f"{len(body.encode('utf-8'))} bytes, at or above the "
            f"{ceiling_bytes}-byte ceiling set after the D50 compaction "
            "(2026-07-29, compacted from 2,450 to 1,032 bytes). If this "
            "growth is intentional, update the ceiling here with a note "
            "explaining why; otherwise the D50 compaction regressed."
        )
