"""K4 test-substrate handoff (ADR-SSOT-002 Axis 1): source-level projections.

This module reads the checked-in prose of the architect, ATD, the two PBT/
completeness skills and the thin-delivery-contract schema and asserts stable
textual/token properties. It never hard-codes a line number and never
inspects AST/implementation shape.
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
AGENTS_DIR = NWAVE_DIR / "agents"
SKILLS_DIR = NWAVE_DIR / "skills"
ADR_PATH = (
    PROJECT_ROOT
    / "docs"
    / "product"
    / "architecture"
    / "ADR-SSOT-002-canonical-delivery-model.md"
)
CONTRACT_SCHEMA_PATH = NWAVE_DIR / "schemas" / "thin-delivery-contract.schema.json"

ARCHITECT = (AGENTS_DIR / "nw-solution-architect.md").read_text(encoding="utf-8")
ACCEPTANCE_DESIGNER = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(
    encoding="utf-8"
)
PBT_SKILL = (SKILLS_DIR / "nw-property-based-testing" / "SKILL.md").read_text(
    encoding="utf-8"
)
AT_COMPLETENESS_SKILL = (
    SKILLS_DIR / "nw-at-completeness-check" / "SKILL.md"
).read_text(encoding="utf-8")
CONTRACT_SCHEMA = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
OBLIGATION_ENUM = CONTRACT_SCHEMA["$defs"]["obligations"]["items"]["enum"]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _required_terms_present(haystack: str, terms) -> list:
    normalized = _norm(haystack)
    return [term for term in terms if term not in normalized]


def test_architect_owns_substrate_facts_and_closed_obligation_enum():
    architect = _norm(ARCHITECT)
    missing = _required_terms_present(
        ARCHITECT,
        [
            "the real observation point — driving/observing port",
            "the base-revision production symbols plus canonical repository test helper/import",
            "canonical-manifest/lock declaration",
            "fixture construction",
            "executor/lifecycle isolation",
            "owner, exact version/identity, declared=yes, present=yes",
            "exact repository-native verification",
            "exact authority-grounded manifest delta and direct dependency-delta install",
            "facts for DISTILL, never test cases or a new artifact/schema field",
            "derive obligations only from its closed enum",
            "emitting only exact enum members",
        ],
    )
    assert not missing, f"architect substrate handoff missing: {missing}"
    assert set(OBLIGATION_ENUM) == {
        "CONTESTED_LAW",
        "REPRESENTATION_CHANGE",
        "INVALID_STATE",
        "PRESERVATION",
        "BROAD_INPUT_DOMAIN",
        "REUSE_CANDIDATE",
        "ARCHITECTURE_BOUNDARY_CHANGE",
    }
    assert architect


def test_atd_consumes_sealed_dependency_readiness_without_inventing():
    missing = _required_terms_present(
        ACCEPTANCE_DESIGNER,
        [
            "name every promised observable",
            "its real driving/observing port",
            "test substrate, fixture and lifecycle facts",
            "final owner/version plus declared=yes, present=yes readiness facts",
            "Any dependency recorded as undeclared or absent returns `EVIDENCE_GAP` immediately",
        ],
    )
    assert not missing, f"ATD sealed-input consumption missing: {missing}"

    compact = _norm(ACCEPTANCE_DESIGNER)
    assert "never edits a manifest/lock file" in compact
    assert "never installs, repairs, executes or validates a dependency" in compact
    assert "EVIDENCE_GAP" in ACCEPTANCE_DESIGNER
    assert "RED_TO_GREEN" in compact
    assert "BROKEN" in ACCEPTANCE_DESIGNER


def test_atd_reads_contract_schema_first_for_grammar_only() -> None:
    compact = _norm(ACCEPTANCE_DESIGNER)
    assert (
        "CONTRACT-SCHEMA: <absolute installed thin-delivery-contract.schema.json>"
        in compact
    )
    assert "this role's first `Read` is exactly `CONTRACT-SCHEMA`" in compact
    assert (
        "A missing, unreadable or non-schema JSON `CONTRACT-SCHEMA` is "
        "`EVIDENCE_GAP` with zero artifact writes" in compact
    )
    assert "The schema owns serialization grammar only" in compact
    assert "never invents or widens a semantic fact to satisfy the schema" in compact
    assert (
        "`CONTRACT-SCHEMA` is ephemeral dispatch context, never a contract "
        "field or persistent output" in compact
    )


def test_semantic_pbt_non_vacuity_preservation_and_fresh_lifecycle():
    pbt_start = PBT_SKILL.index("## Non-vacuous generator construction")
    pbt_section = _norm(PBT_SKILL[pbt_start:])

    assert "SemanticCase -> ConcreteInput -> SUT -> Observation" in pbt_section
    assert "every generated component must influence" in pbt_section
    assert "independent oracle" in pbt_section
    assert "generate the case tag first" in pbt_section
    assert "does not prove" in pbt_section and "reachability" in pbt_section
    assert "diagnostics only" in pbt_section
    assert "never substitute for constructive reachability" in pbt_section
    assert "proxies unless that is the declared law itself" in pbt_section
    assert "does not discharge `BROAD_INPUT_DOMAIN`" in pbt_section

    missing = _required_terms_present(
        ACCEPTANCE_DESIGNER,
        [
            "Every generated value must influence SUT input or an independent oracle",
            "Rare branches are generated by construction, not filtering",
            "require an explicit preservation map to the same promised observation",
            "own fresh mutable fixture/lifecycle state per generated case",
            "never downgrade the law to example-only coverage",
        ],
    )
    assert not missing, f"ATD non-vacuity/preservation obligations missing: {missing}"

    assert "obligation-to-observation closure" in AT_COMPLETENESS_SKILL
    assert "every declared obligation -> one or more falsifiable observations" in _norm(
        AT_COMPLETENESS_SKILL
    )


def test_both_routes_closed_and_terminal_handoff_contract_ready():
    green_start = ACCEPTANCE_DESIGNER.index("### GREEN_TO_GREEN")
    green_section = _norm(ACCEPTANCE_DESIGNER[green_start : green_start + 1200])
    assert "Do not search for, create, edit or broaden it" in green_section
    assert (
        "delivery-route: GREEN_TO_GREEN" in green_section
        or "delivery-route" in green_section
    )
    assert "write one complete schema-valid DeliveryContract" in green_section
    assert "without any test edit" in green_section.lower()
    assert "never executes the stored scope" in green_section
    assert (
        "`des dispatch` alone validates, resolves and hashes the contract"
        in green_section
    )
    assert (
        "the crafter's own BASELINE step alone classifies RED, GREEN or "
        "BROKEN" in green_section
    )
    assert "locator-only" not in ACCEPTANCE_DESIGNER

    red_start = ACCEPTANCE_DESIGNER.index("### RED_TO_GREEN")
    red_end = ACCEPTANCE_DESIGNER.index("### GREEN_TO_GREEN", red_start)
    red_section = _norm(ACCEPTANCE_DESIGNER[red_start:red_end])
    assert "write one complete schema-valid DeliveryContract" in red_section
    assert "exact given `CONTRACT-LOCATOR`" in red_section
    assert (
        "`des dispatch` alone validates, resolves and hashes the contract "
        "after this role" in red_section
    )
    assert (
        "the crafter's own BASELINE step alone classifies RED, GREEN or "
        "BROKEN" in red_section
    )
    assert "Any later oracle edit invalidates readiness" in red_section

    idx = ACCEPTANCE_DESIGNER.index("DISTILL-RESULT:")
    block = ACCEPTANCE_DESIGNER[idx : idx + 300]
    for field in (
        "DISTILL-RESULT: CONTRACT_READY",
        "REPO-ROOT: <absolute physical repository root>",
        "DELIVERY-CONTRACT: <repo-relative locator>",
    ):
        assert field in block
    assert "DELIVERY-CONTRACT-SHA256:" not in block
    assert "ORACLE-SHA256:" not in block
    assert "oracle" not in block.lower()
