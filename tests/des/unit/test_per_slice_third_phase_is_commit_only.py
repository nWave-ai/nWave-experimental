"""Regression: the per-slice THIRD phase (`D_REFACTOR_COMMIT`) must be
documented as commit-only, unconditional -- no separate crafter instance
("crafter-B"), no per-slice review/refactor sub-dispatch -- matching the
mode registry's `deliver_phase_shape: "A_GREEN -> EXAMINE -> COMMIT"`
(`nWave/flavors/atdd_pure.yaml`) and the already-3-phase-canonical runtime
(`src/des/domain/atdd_pure_phases.py`).

DEFECT (RCA by Rex, nw-troubleshooter, fix-slice-third-phase-commit-only):
two skill-prose loci still mandated a per-slice L1-L6 refactor + reviewer
sub-dispatch (a SEPARATE "crafter-B" instance) AFTER the mode descriptor and
the runtime had already collapsed to the 3-phase canon --

  1. `nWave/skills/nw-deliver/SKILL.md` -- the `D_REFACTOR_COMMIT` phase
     table row named `crafter-B (separate instance) then reviewer then
     crafter` as the owner and mandated `L1-L6 batch refactor` + a
     `Reviewed-by:` (verdict_hash) trailer as part of the PER-SLICE commit.
  2. `nWave/skills/nw-deliver-atdd-pure-slice-gates/SKILL.md` -- the
     "Separation Enforcement" section actively required a crafter instance
     distinct from `A_GREEN` for `D_REFACTOR_COMMIT` (Ale 2026-05-19
     mandate), a rule that only makes sense when `D_REFACTOR_COMMIT` DOES
     refactor+review work to separate from the implementer.

WHY this recurs the a91bf4f6b (2026-07-04) class and how this fix differs:
a91bf4f6b restored `D_REFACTOR_COMMIT` as the per-slice COMMIT step after a
PRIOR total drop left slices uncommitted, but ALSO restored the per-slice
refactor mandate this test now retires -- WITHOUT a substitute. This fix
retires the refactor mandate a second time, but WITH a substitute: the
mandatory per-feature Prefactoring Assessment (upstream, DESIGN wave,
behaviour-preserving, green-to-green -- `src/des/cli/validate_feature_delta.py`
`--require-prefactoring-assessment`) moves the refactor EARLIER instead of
skipping it. `D_REFACTOR_COMMIT` stays the live phase-word (audit trail);
only its per-slice CONTENT changes to commit-only.

Driving surface: reads the shipped skill-prose files directly (the fix IS
prose -- there is no live dispatch-shape assertion point to drive instead,
since the crafter-B/review sub-dispatch these files used to mandate was
never itself a DES-enforced runtime gate, only orchestrator-read prose).
Cross-checks against `nWave/flavors/atdd_pure.yaml`'s `deliver_phase_shape`
descriptor -- the mode registry SSOT this prose must agree with.

RED-for-right-reason (verified manually before authoring GREEN prose, see
crafter's commit message): reading the pre-fix prose, `_d_refactor_commit_row`
contained the literal substring `crafter-B`, and the gates skill contained
the literal substring `MUST use a SEPARATE crafter instance from A_GREEN` --
both assertions below failed with a semantic `AssertionError` naming the
found substring, never an import/collection error.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DELIVER_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"
_GATES_SKILL = (
    _REPO_ROOT / "nWave" / "skills" / "nw-deliver-atdd-pure-slice-gates" / "SKILL.md"
)
_ATDD_PURE_FLAVOR = _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"

#: The retired owner-cell token: a SEPARATE crafter instance running a
#: refactor+review pass before the commit. Absence proves the per-slice
#: third phase no longer forks a second implementer.
_RETIRED_CRAFTER_B_TOKEN = "crafter-B"

#: The retired action-cell fragment: the old owner chain literally read
#: "then reviewer then crafter" -- a three-hop per-slice dispatch sequence.
_RETIRED_REVIEW_CHAIN_TOKEN = "then reviewer then crafter"

#: The retired ACTIVE (non-historical) enforcement sentence from the gates
#: skill's old "Separation Enforcement" section. The fix keeps the section
#: heading for audit continuity but neutralizes this exact live mandate.
_RETIRED_SEPARATION_MANDATE = "MUST use a SEPARATE crafter instance from A_GREEN"

#: The new commit-only marker text both loci must carry.
_COMMIT_ONLY_MARKER = "commit-only"

#: The gates-skill sentence that replaces the old mandate -- explicit proof
#: the neutralization is INTENTIONAL prose, not an accidental deletion.
_SEPARATION_SUPERSEDED_MARKER = "No separate crafter instance is required"

#: The mode registry's canonical descriptor (SSOT) both prose loci's
#: 3-phase table must agree with.
_CANONICAL_PHASE_SHAPE = 'deliver_phase_shape: "A_GREEN -> EXAMINE -> COMMIT"'


#: The EXACT header line of the per-slice phase table (nw-deliver/SKILL.md).
#: Scanning is anchored to the rows immediately following THIS header, until
#: the first blank line -- not a whole-file substring search, which would
#: false-positive on prose mentions of the same phase names elsewhere in the
#: file (e.g. the "Composition (load by trigger)" module table above it,
#: which prints "C_REVIEWER_AUDIT verdict routing, D_REFACTOR_COMMIT
#: dispatch" inside an unrelated cell).
_PHASE_TABLE_HEADER = "| Phase | Owner | Action | Gate |"


def _per_slice_phase_table_rows(deliver_skill_text: str) -> list[str]:
    """Return the data rows of the per-slice phase table, anchored on its
    exact header line (see `_PHASE_TABLE_HEADER`). Pure; no whole-file
    substring search."""
    lines = deliver_skill_text.splitlines()
    header_index = None
    for idx, line in enumerate(lines):
        if line.strip() == _PHASE_TABLE_HEADER:
            header_index = idx
            break
    if header_index is None:
        raise AssertionError(
            f"no exact '{_PHASE_TABLE_HEADER}' header line found in "
            f"{_DELIVER_SKILL} -- the per-slice phase table itself is "
            "missing or its header was reworded"
        )
    # Skip the header and the GFM separator row (|---|---|...|) immediately
    # below it; collect data rows until the first blank line.
    rows: list[str] = []
    for line in lines[header_index + 2 :]:
        if not line.strip():
            break
        rows.append(line)
    return rows


def _d_refactor_commit_row(deliver_skill_text: str) -> str:
    """Return the `| D_REFACTOR_COMMIT | ...` table row line. Raises
    AssertionError (not IndexError) if the row is missing entirely -- a
    missing row is itself evidence the phase table shape drifted."""
    for line in deliver_skill_text.splitlines():
        if line.strip().startswith("| D_REFACTOR_COMMIT |"):
            return line
    raise AssertionError(
        "no '| D_REFACTOR_COMMIT |' table row found in "
        f"{_DELIVER_SKILL} -- the per-slice phase table itself is missing "
        "or the phase was renamed; this test cannot verify commit-only "
        "content without locating the row first"
    )


def test_deliver_skill_drops_crafter_b_and_review_chain() -> None:
    """POSITIVE: the `D_REFACTOR_COMMIT` table row in nw-deliver/SKILL.md
    must NOT mandate a separate crafter-B instance or a reviewer-then-crafter
    chain, and MUST say commit-only."""
    text = _DELIVER_SKILL.read_text(encoding="utf-8")
    row = _d_refactor_commit_row(text)

    assert _RETIRED_CRAFTER_B_TOKEN not in row, (
        f"the D_REFACTOR_COMMIT table row still mandates a separate "
        f"'{_RETIRED_CRAFTER_B_TOKEN}' instance -- the per-slice third "
        f"phase must be commit-only (same crafter instance as A_GREEN), "
        f"not a second implementer. Row: {row!r}"
    )
    assert _RETIRED_REVIEW_CHAIN_TOKEN not in row, (
        f"the D_REFACTOR_COMMIT table row still contains the retired "
        f"owner chain '{_RETIRED_REVIEW_CHAIN_TOKEN}' -- no per-slice "
        f"review/refactor sub-dispatch should remain. Row: {row!r}"
    )
    assert _COMMIT_ONLY_MARKER in row.lower(), (
        "the D_REFACTOR_COMMIT table row must explicitly say "
        f"'{_COMMIT_ONLY_MARKER}' -- the phase's per-slice content is "
        f"nothing but `des commit-slice`. Row: {row!r}"
    )


def test_gates_skill_drops_active_separation_mandate() -> None:
    """POSITIVE: the gates skill's "Separation Enforcement" section must no
    longer ACTIVELY require a separate crafter instance for
    `D_REFACTOR_COMMIT` -- it must instead say the supersession is
    intentional (never a silent, unexplained deletion)."""
    text = _GATES_SKILL.read_text(encoding="utf-8")

    assert _RETIRED_SEPARATION_MANDATE not in text, (
        f"the gates skill still contains the ACTIVE mandate "
        f"'{_RETIRED_SEPARATION_MANDATE}' -- this rule only makes sense "
        f"when D_REFACTOR_COMMIT does refactor/review work to separate "
        f"from the implementer; the per-slice third phase is now "
        f"commit-only, so this mandate must be neutralized, not merely "
        f"restated. File: {_GATES_SKILL}"
    )
    assert _SEPARATION_SUPERSEDED_MARKER in text, (
        f"the gates skill must explicitly say "
        f"'{_SEPARATION_SUPERSEDED_MARKER}' -- the neutralization must be "
        f"a documented, intentional supersession (GDP-2: WHY inline at "
        f"the authoring surface), not a silent deletion of the rule. "
        f"File: {_GATES_SKILL}"
    )


def test_both_loci_agree_with_the_mode_registry_descriptor() -> None:
    """Cross-check: `nWave/flavors/atdd_pure.yaml` (the mode registry SSOT)
    still declares the 3-phase `A_GREEN -> EXAMINE -> COMMIT` shape, and the
    deliver skill's own phase table has exactly 3 rows (A_GREEN,
    C_REVIEWER_AUDIT, D_REFACTOR_COMMIT) -- proving the prose fix did not
    drift the phase COUNT while fixing the D_REFACTOR_COMMIT row's content."""
    flavor_text = _ATDD_PURE_FLAVOR.read_text(encoding="utf-8")
    assert _CANONICAL_PHASE_SHAPE in flavor_text, (
        f"expected {_ATDD_PURE_FLAVOR} to declare "
        f"{_CANONICAL_PHASE_SHAPE!r} -- this is the SSOT the deliver "
        f"skill's phase table must agree with; got a different or "
        f"missing descriptor"
    )

    deliver_text = _DELIVER_SKILL.read_text(encoding="utf-8")
    phase_rows = _per_slice_phase_table_rows(deliver_text)
    assert len(phase_rows) == 3, (
        "expected exactly 3 phase rows (A_GREEN, C_REVIEWER_AUDIT, "
        f"D_REFACTOR_COMMIT) in the deliver skill's per-slice phase table "
        f"-- got {len(phase_rows)}: {phase_rows!r}. A row count drift "
        "means the prose no longer matches the mode registry's 3-phase "
        "descriptor."
    )


@pytest.mark.negative_at
def test_d_refactor_commit_marker_survives_as_the_live_phase_word() -> None:
    """NEGATIVE AT (no-overcorrection control -- must stay GREEN before AND
    after the fix): `D_REFACTOR_COMMIT` must remain the live per-slice
    COMMIT phase-word in BOTH skill files -- the fix drops the per-slice
    REFACTOR content, not the phase marker itself (audit-trail continuity,
    per the crafter dispatch's explicit PRESERVE instruction)."""
    deliver_text = _DELIVER_SKILL.read_text(encoding="utf-8")
    gates_text = _GATES_SKILL.read_text(encoding="utf-8")

    assert "D_REFACTOR_COMMIT" in deliver_text, (
        f"expected the 'D_REFACTOR_COMMIT' phase-word to remain present in "
        f"{_DELIVER_SKILL} -- the fix retires the per-slice REFACTOR "
        f"CONTENT, not the phase marker itself"
    )
    assert "D_REFACTOR_COMMIT" in gates_text, (
        f"expected the 'D_REFACTOR_COMMIT' phase-word to remain present in "
        f"{_GATES_SKILL} -- the fix retires the per-slice REFACTOR "
        f"CONTENT, not the phase marker itself"
    )
