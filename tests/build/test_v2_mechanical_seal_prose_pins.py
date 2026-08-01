"""P1.1(b) prose regression pins — the mechanical-seal default cannot drift back.

The skill edits of P1.1(b) are prose; hooks guard their FORM (template,
coherence) but nothing guarded their CONTENT. These pins assert the two
load-bearing prose facts so a future edit cannot silently restore the
mandatory reviewer dispatch on the pytest-regression path.
"""

from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def test_bugfix_defaults_to_the_mechanical_seal() -> None:
    """nw-bugfix Phase 3a: mechanical pair is the default entry evidence."""
    text = _read("nWave/skills/nw-bugfix/SKILL.md")
    assert "verify-red-green" in text and "--record-red" in text
    assert "verify-negative-at" in text
    # The reviewer verdict survives ONLY as the optional branch.
    idx_mech = text.find("verify-red-green")
    idx_verdict = text.find("record-at-review-verdict")
    assert idx_verdict != -1, "optional reviewer branch must remain documented"
    assert idx_mech < idx_verdict, (
        "the reader must meet the mechanical route BEFORE the optional "
        "reviewer branch (P1.1b contract)"
    )
    assert "opt-in" in text.lower() or "optional" in text.lower()


def test_execute_documents_mechanical_default_and_keeps_gherkin_reviewer() -> None:
    """nw-execute: pytest-regression defaults mechanical; Gherkin keeps reviewer."""
    text = _read("nWave/skills/nw-execute/SKILL.md")
    assert "mechanical" in text.lower()
    assert "verify-red-green" in text
    # The Gherkin route must still name the reviewer-verdict path (the seal
    # is NOT wired there yet — deleting this line requires wiring it first).
    assert "ATReviewVerdict" in text or "reviewer-verdict" in text


def test_deliver_examine_slot_dispatches_examiner_armed_by_charter() -> None:
    """nw-deliver: the C_REVIEWER_AUDIT slot is EXAMINE when a charter exists.

    P2.1/P1.2 producer<->consumer wiring: the middle slot dispatches
    nw-user-examiner and records via `des record-examine-verdict`, armed by a
    charter under docs/product/expectations/{feature-id}/. Deleting this route
    requires removing the commit-slice examine gate first.
    """
    text = _read("nWave/skills/nw-deliver/SKILL.md")
    assert "EXAMINE" in text
    assert "nw-user-examiner" in text
    assert "record-examine-verdict" in text
    # The arming condition must match the code (_examine_gate_armed).
    assert "docs/product/expectations/" in text
    # The legacy audit survives only as the UNARMED fallback.
    assert "unarmed" in text.lower()


#: The hand-authoring commands 36d3ca2e0 retired from nw-discuss. Re-introducing
#: any of them puts a from-scratch template recipe back on the DISCUSS path,
#: which is what produced the 2026-07-12 charter dialect-mismatch incident.
_RETIRED_DISCUSS_HAND_AUTHORING = (
    "author the Expectation Charters",
    "write its charter",
    "WRITE `docs/product/expectations/",
)


def test_discuss_seeds_the_charter_the_producing_tool_scaffolds() -> None:
    """nw-discuss: DISCUSS seeds the charter Intent; the tool produces the file.

    Supersedes the pre-2026-07-30 pin that required nw-discuss to COMMAND
    hand-authoring at wave close. 36d3ca2e0 (AUDIT P2/S1) retired that
    instruction: `des charter-scaffold` produces the charter at DISTILL-open
    (path, filename and heading dialect already correct) and a fresh
    nw-product-owner context fills it, with `des verify-charter-filled` as the
    backstop. Restoring a hand-authoring command here requires unwiring those
    two gates first.
    """
    text = _read("nWave/skills/nw-discuss/SKILL.md")
    assert "Expectation Charter" in text
    # The arming condition must match the code (_examine_gate_armed).
    assert "docs/product/expectations/" in text
    assert "arm" in text.lower()
    # GDP-4: the HOW names the PRODUCING TOOL, never a manual recipe.
    assert "des charter-scaffold" in text
    # Seeding must stay an IMPERATIVE STEP in the dispatch — a documented
    # deliverable alone did NOT trigger the PO (dogfood friction 2026-07-03).
    assert "REQUIRED step" in text
    for retired in _RETIRED_DISCUSS_HAND_AUTHORING:
        assert retired not in text, (
            f"nw-discuss re-introduced the retired hand-authoring command "
            f"{retired!r}. Charters are SCAFFOLDED by `des charter-scaffold` at "
            "DISTILL-open and filled by a fresh nw-product-owner context — "
            "DISCUSS owes the seeding Slice Plan Value statement only."
        )


def test_expectation_charter_skill_owns_the_negative_observation_oracle() -> None:
    """The >=1-negative-observation oracle rule is pinned at its SSOT.

    It used to be pinned in nw-discuss. Charter authoring moved to DISTILL-open,
    so the rule is pinned where it is now taught AND where the mechanical gate
    `des verify-charter-filled` enforces it — a strictly stronger location than
    prose in the wave that no longer authors charters.
    """
    text = _read("nWave/skills/nw-expectation-charter/SKILL.md")
    assert "negative observation" in text.lower()
    assert "des charter-scaffold" in text
    assert "verify-charter-filled" in text


def test_distill_authors_requirement_checklist_and_spec_coverage_advisory() -> None:
    """nw-distill: the checklist is a DISTILL-open deliverable; spec-coverage is
    the DISTILL-out advisory gate (P3.1/P3.2). Deleting either requires unwiring
    the spec-coverage gate from distill.yaml first."""
    text = _read("nWave/skills/nw-distill/SKILL.md")
    assert "Requirement Checklist" in text
    assert "requirement-checklist.md" in text  # the template / the extract path
    assert "verify-spec-coverage" in text or "spec-coverage gate" in text
    # Advisory, not veto — armed only when the checklist exists.
    assert "advisory" in text.lower()
    # The mandatory categories must be named as the eval's silent-absence class.
    assert "security" in text.lower() and "validation" in text.lower()


def test_distill_classifies_assembled_surfaces_at_authoring_time() -> None:
    """DISTILL induces consumer-lineage proof before scenario authoring."""
    text = _read("nWave/skills/nw-distill/SKILL.md")
    normalized = " ".join(text.split())
    assert "Assembly-boundary classification (AUTHORING-time)" in text
    assert "DIRECT-SURFACE" in text and "ASSEMBLED-SURFACE" in text
    assert "one immutable candidate" in normalized
    assert "does not discharge the obligation" in normalized


def test_composition_contract_closes_the_immutable_artifact_lineage() -> None:
    """The canonical mandate proves the produced artifact, not its designation."""
    text = _read("nWave/skills/nw-test-design-mandates-composition-contract/SKILL.md")
    assert "Artifact Lineage Closure" in text
    for link in (
        "real production pipeline",
        "one immutable candidate",
        "clean consumer environment",
        "public user journey",
        "user-observable capability",
    ):
        assert link in text
    assert "produced PROPERTY, never its DESIGNATION" in text


def test_acceptance_designer_inventory_reaches_the_consumer_boundary() -> None:
    """The operational agent applies the rule before authoring ATs."""
    text = _read("nWave/agents/nw-acceptance-designer.md")
    assert "Consumer Boundary Inventory" in text
    assert "do not defer this classification to review" in text
    assert "ASSEMBLED-SURFACE WS closes Artifact Lineage Closure" in text
    assert "produced PROPERTY, never its DESIGNATION" in text


def test_rigor_reflects_v2_flow_floor_examiner_uncapped_mutation_offaxis() -> None:
    """/nw-rigor: the v2 back-prop (P-CONFIG) — examiner axis + always-on floor.

    The rigor SSOT must describe the v2 flow, not the dead reviewer-based one:
    the execution-observing gates are a fixed floor (not rigor-gated), the
    examiner swarm axis exists, agent_model is uncapped, mutation is off-axis.
    """
    text = _read("nWave/skills/nw-rigor/SKILL.md")
    assert "examine_swarm_n" in text  # the new examiner axis
    # The floor is always-on, never rigor-gated.
    assert "floor" in text.lower()
    assert "verify-red-green" in text and "examine-verdict" in text
    assert "NOT rigor-gated" in text or "not rigor-gated" in text.lower()
    # agent_model uncapped (opus stays available for high-stakes profiles).
    assert "UNCAPPED" in text or "uncapped" in text.lower()
    # mutation is no longer a rigor axis.
    assert "no longer a rigor axis" in text.lower()
