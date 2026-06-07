"""slice-00 (T-A) — atdd_pure DES dispatch template acceptance tests.

Epic F-DES-ATDD-PURE-DISPATCH-LIFECYCLE. Transformation T-A: add a verbatim
`atdd_pure` DES dispatch template to `nWave/skills/nw-execute/SKILL.md` beside
the existing classic one, so an `atdd_pure` carpaccio-slice crafter dispatch has
a canonical, copy-fill-verbatim path.

Three ATs, slice ≤ 3:
  * AT-1 (@wiring_e2e @walking_skeleton) — render the REAL production template
    and round-trip it through the production `DesMarkerParser` +
    `classify_atdd_pure_dispatch`, asserting `valid`. Genuine composition,
    no fixture-folding: the input is the production skill file on disk.
  * AT-2 — the atdd_pure template carries the atdd_pure-shaped section set
    (A→G phases, AT-completion-ledger sections) and NOT the classic-only
    sections (`DES-STEP-ID`, `TDD_PHASES`, execution-log `OUTCOME_RECORDING` /
    `RECORDING_INTEGRITY`).
  * AT-3 — the Dispatcher Workflow has a `workflow.mode` selection step that
    chooses between the classic and atdd_pure templates.

The template is delimited in the skill file by the anchor markers
`<!-- ATDD-PURE-DISPATCH-TEMPLATE:BEGIN -->` /
`<!-- ATDD-PURE-DISPATCH-TEMPLATE:END -->` so the production prompt block can
be extracted deterministically (the same discipline the classic template's
fenced block follows).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from des.domain.des_marker_parser import (
    DesMarkerParser,
    classify_atdd_pure_dispatch,
)


_SKILL_PATH = Path("nWave/skills/nw-execute/SKILL.md")

_TEMPLATE_BEGIN = "<!-- ATDD-PURE-DISPATCH-TEMPLATE:BEGIN -->"
_TEMPLATE_END = "<!-- ATDD-PURE-DISPATCH-TEMPLATE:END -->"


def _skill_content() -> str:
    """Read the production nw-execute skill file (repo-root-relative path)."""
    return _SKILL_PATH.read_text(encoding="utf-8")


def _extract_atdd_pure_template() -> str:
    """Extract the verbatim atdd_pure dispatch template block from the skill.

    The block is delimited by the BEGIN/END anchor comments. Returns the raw
    text between them — the copy-fill-verbatim crafter dispatch prompt.
    """
    content = _skill_content()
    begin = content.find(_TEMPLATE_BEGIN)
    end = content.find(_TEMPLATE_END)
    assert begin != -1, (
        f"{_TEMPLATE_BEGIN} anchor missing from {_SKILL_PATH} — the atdd_pure "
        "dispatch template has not been added"
    )
    assert end != -1, f"{_TEMPLATE_END} anchor missing from {_SKILL_PATH}"
    assert end > begin, "atdd_pure template END anchor precedes BEGIN anchor"
    return content[begin + len(_TEMPLATE_BEGIN) : end]


def _fill_placeholders(template: str) -> str:
    """Fill the template's {placeholders} with a representative slice-00 dispatch.

    Mirrors what the /nw-execute dispatcher does at render time: substitute the
    feature-id / slice / phase placeholders with concrete values.
    """
    return (
        template.replace("{feature-id}", "atdd-pure-dispatch-lifecycle")
        .replace("{slice-id}", "slice-00")
        .replace("{slice-NN}", "slice-00")
        .replace("{phase}", "A_GREEN_ATS")
        .replace("{ATDDPurePhase}", "A_GREEN_ATS")
        .replace("{agent-name}", "nw-software-crafter")
        .replace("{agent}", "nw-software-crafter")
    )


# ---------------------------------------------------------------------------
# AT-1 — walking skeleton: real template round-trips through production parser
# ---------------------------------------------------------------------------


@pytest.mark.wiring_e2e
@pytest.mark.walking_skeleton
def test_at1_rendered_atdd_pure_template_classified_valid_by_production_parser():
    """Property: a /nw-execute atdd_pure dispatch is recognised by the parser.

    Given the REAL production nw-execute/SKILL.md atdd_pure dispatch template,
    When it is rendered (placeholders filled) and parsed by the production
         DesMarkerParser,
    Then classify_atdd_pure_dispatch returns 'valid' — the dispatch carries a
         complete, in-vocabulary atdd_pure marker set.

    This is genuine end-to-end composition: the input is the production skill
    file on disk, the parser is the production domain class. No fixture folds
    the expected end-state — if the template lacks a marker, this test stays
    RED.
    """
    template = _extract_atdd_pure_template()
    rendered = _fill_placeholders(template)

    markers = DesMarkerParser().parse(rendered)
    classification = classify_atdd_pure_dispatch(markers)

    assert classification == "valid", (
        f"production atdd_pure dispatch template classified {classification!r}, "
        f"expected 'valid' — markers: mode={markers.mode!r} "
        f"phase={markers.atdd_pure_phase!r} slice={markers.slice_id!r}"
    )
    # The three U0 markers must each be present and in-vocabulary.
    assert markers.mode == "atdd_pure"
    assert markers.atdd_pure_phase == "A_GREEN_ATS"
    assert markers.slice_id == "slice-00"
    # An atdd_pure dispatch carries NO DES-STEP-ID (that is classic-only).
    assert markers.step_id is None, (
        "atdd_pure dispatch template must not emit DES-STEP-ID — it is a "
        "classic-only marker; the slice is identified by DES-SLICE"
    )


# ---------------------------------------------------------------------------
# AT-2 — atdd_pure-shaped section set, not the classic execution-log shape
# ---------------------------------------------------------------------------


def test_at2_template_carries_atdd_pure_sections_not_classic_log_sections():
    """The atdd_pure template has the A→G / ledger section set, not classic's.

    Given the production atdd_pure dispatch template block,
    Then it carries the atdd_pure-shaped sections — the A→G phase block and the
         AT-completion-ledger contract,
    And it does NOT carry the classic-only sections — DES-STEP-ID, the classic
         TDD_PHASES RED/GREEN/COMMIT block, and the execution-log-shaped
         OUTCOME_RECORDING / RECORDING_INTEGRITY sections.
    """
    template = _extract_atdd_pure_template()

    # --- atdd_pure-shaped sections that MUST be present --------------------
    assert "DES-MODE : atdd_pure" in template, (
        "atdd_pure template must emit the DES-MODE:atdd_pure marker"
    )
    assert "DES-PHASE" in template, "atdd_pure template must emit a DES-PHASE marker"
    assert "DES-SLICE" in template, "atdd_pure template must emit a DES-SLICE marker"

    # The seven canonical ATDDPurePhase members must all appear — the A→G
    # phase block replaces the classic TDD_PHASES block.
    for phase in (
        "A_GREEN_ATS",
        "B_COVERAGE_CLEANUP",
        "C_REVIEWER_AUDIT",
        "D_GAP_ROUTING",
        "E_BATCH_REFACTOR",
        "F_FINAL_REVIEW",
        "G_COMMIT",
    ):
        assert phase in template, (
            f"atdd_pure template missing A→G phase {phase!r} — the phase block "
            "must enumerate all seven ATDDPurePhase members"
        )

    # The AT-completion-ledger contract replaces classic execution-log recording.
    assert "AT-completion ledger" in template or "AT_COMPLETION_LEDGER" in template, (
        "atdd_pure template must reference the AT-completion ledger contract"
    )

    # --- classic-only sections that MUST be absent -------------------------
    assert "DES-STEP-ID" not in template, (
        "atdd_pure dispatch template must not carry the classic DES-STEP-ID "
        "marker — the slice is identified by DES-SLICE"
    )
    assert not re.search(r"^#\s*TDD_PHASES", template, re.MULTILINE), (
        "atdd_pure template must not carry the classic '# TDD_PHASES' section — "
        "it is replaced by the A→G phase block"
    )
    assert "execution-log.json" not in template, (
        "atdd_pure template must not reference execution-log.json — atdd_pure "
        "produces no execution-log (it is classic-only)"
    )
    assert "des-log-phase" not in template, (
        "atdd_pure template must not invoke des-log-phase — that CLI writes the "
        "classic execution-log; atdd_pure records via the AT-completion ledger"
    )


# ---------------------------------------------------------------------------
# AT-3 — Dispatcher Workflow selects the template by workflow.mode
# ---------------------------------------------------------------------------


def test_at3_dispatcher_workflow_selects_template_by_workflow_mode():
    """The Dispatcher Workflow chooses classic vs atdd_pure by workflow.mode.

    Given the nw-execute skill file,
    Then the 'Agent Invocation' section presents both the classic and the
         atdd_pure dispatch template,
    And a selection instruction keys on workflow.mode = atdd_pure to pick the
         atdd_pure template.
    """
    content = _skill_content()

    # Both templates must be present, distinguishable.
    assert _TEMPLATE_BEGIN in content, "atdd_pure template block missing"
    assert "<!-- DES-STEP-ID : {step-id} -->" in content, (
        "classic dispatch template must still be present (unchanged)"
    )

    # A selection step keying on workflow.mode must instruct which template to use.
    assert re.search(
        r"workflow\.mode.*atdd_pure.*template", content, re.IGNORECASE | re.DOTALL
    ) or re.search(
        r"atdd_pure.*template.*workflow\.mode", content, re.IGNORECASE | re.DOTALL
    ), (
        "nw-execute/SKILL.md must carry an instruction selecting the atdd_pure "
        "dispatch template when workflow.mode = atdd_pure"
    )
