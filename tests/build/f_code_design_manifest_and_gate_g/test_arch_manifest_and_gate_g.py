"""Arch tests for f-code-design-manifest-and-gate-g (AT-A2 / AT-A3 / AT-A6).

Structural-invariant layer of the Earned-Trust three-layer contract (arch-tier).
These are NOT behavioral ATs -- they import production surface to INTROSPECT
structure (the S2 tolerable variant: ``tests/build/*`` arch tests legitimately
import for structural assertion, never to exercise behavior).

active-RED scaffold (atdd_pure -- NOT @skip): each test fails for the RIGHT reason
at HEAD because the net-new artifact it asserts is absent:

  * AT-A6: ``nWave/schemas/code-design-manifest.schema.json`` does not exist yet ->
    the schema-absorption ``$ref`` cannot be asserted (RED until DELIVER slice-01
    ships the broad schema that ``$ref``s the existing component-manifest schema).
  * AT-A3: the 5-verdict ``GateVerdict`` SSOT is ALREADY frozen at HEAD -> this test
    GREENS at HEAD by construction. It is a NO-REGRESSION guard, not active-RED; it
    is included so the reviewer can confirm DELIVER adds no sixth verdict. It is
    marked clearly below and is the ONE structural guard whose role is preservation,
    not red-then-green.
  * AT-A2: gate-G holds no write capability -> partially assertable at HEAD (the
    CodeFactPort already exposes no write method); the manifest-source branch DELIVER
    adds must keep this true. A no-regression guard over the read-only universe.

AT-A1-now (registry + catalog + gate-stack membership) is witnessed BEHAVIORALLY by
the slice-04 acceptance scenarios (``tests/des/acceptance/.../slice-04-*``), not
here -- membership is a driving-port observable, not a pure structural import.
AT-A1-after (the full catalog<->wiring coherence harness) is authored by
f-nonbypassable-attestation slice-04 and is OUT OF SCOPE (DDD-5b ledger
precondition).
AT-A5 (gate-G actually degrades to INDETERMINATE on an unsupported AT language) is
witnessed by the slice-03 ``@real-io`` unsupported-language acceptance scenario.
"""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPONENT_SCHEMA = _REPO_ROOT / "nWave" / "schemas" / "component-manifest.schema.json"
_CODE_DESIGN_SCHEMA = (
    _REPO_ROOT / "nWave" / "schemas" / "code-design-manifest.schema.json"
)
_GATE_G = _REPO_ROOT / "src" / "des" / "cli" / "gate_g.py"
_CODE_FACT_PORT = _REPO_ROOT / "src" / "des" / "ports" / "code_fact_port.py"


def test_at_a6_broad_schema_absorbs_component_manifest_by_ref() -> None:
    """AT-A6 (self-application): the broad ``code-design-manifest.schema.json`` exists
    and ABSORBS the component-manifest schema by ``$ref`` (one SSOT, no fork) -- it
    references the existing ``component-manifest.schema.json``, never duplicating it.

    active-RED: the broad schema does not exist at HEAD.
    """
    assert _CODE_DESIGN_SCHEMA.is_file(), (
        "AT-A6: the broad code-design-manifest.schema.json must exist at "
        f"{_CODE_DESIGN_SCHEMA.relative_to(_REPO_ROOT)} (DDD-1 / ADR-FLOW-003 D1). "
        "It is ABSENT at HEAD (active-RED; DELIVER slice-01 ships it)."
    )
    schema_text = _CODE_DESIGN_SCHEMA.read_text(encoding="utf-8")
    document = json.loads(schema_text)
    # The component-manifest schema must be REFERENCED (absorbed as a section), not
    # re-authored. Either a $ref to the component-manifest schema file, or the
    # component-manifest keys re-declared inline would be a FORK (forbidden).
    assert "component-manifest.schema.json" in schema_text, (
        "AT-A6: the broad schema must $ref the existing "
        "component-manifest.schema.json (absorb-as-section, ONE SSOT) -- the "
        "reference is absent. A re-authored copy of the component-manifest keys is a "
        f"FORK (flow-design §C2 forbids it). schema keys present: {sorted(document)!r}"
    )


def test_at_a3_no_sixth_gate_verdict() -> None:
    """AT-A3 (NO-REGRESSION guard, green at HEAD): the GateVerdict SSOT has exactly
    the 5 §17 values -- the manifest upgrades verdict PRECISION, never adds a sixth.

    This is the ONE structural guard whose role is preservation (already green at
    HEAD); DELIVER must keep it green. Included so the reviewer can confirm no sixth
    verdict is introduced by the manifest-source branch.
    """
    from des.domain.gate_outcome import GateVerdict

    actual = {v.value for v in GateVerdict}
    expected = {"pass", "fail", "not_applicable", "unverified", "indeterminate"}
    assert actual == expected, (
        "AT-A3: GateVerdict must hold EXACTLY the 5 §17 values (ADR-GV-001, no "
        f"sixth -- DDD-7). Got {sorted(actual)!r}, expected {sorted(expected)!r}. "
        "The manifest upgrades precision; it must add no verdict."
    )


def test_at_a2_gate_g_holds_no_write_capability() -> None:
    """AT-A2 (NO-REGRESSION guard): gate-G reads facts about code only -- the
    CodeFactPort is a read-only universe (no write method); "gate-G mutates the
    design/ATs" is non-representable. DELIVER's manifest-source branch must not
    introduce a write port.
    """
    port_text = _CODE_FACT_PORT.read_text(encoding="utf-8")
    # The read-only universe contract (Principle 12): the port exposes one query
    # method and no write/mutate/save method.
    forbidden = ("def write(", "def save(", "def mutate(", "def persist(")
    leaked = [token for token in forbidden if token in port_text]
    assert not leaked, (
        f"AT-A2: the CodeFactPort must stay read-only (Principle 12 / ADR-LA-001) -- "
        f"a write method leaked: {leaked!r}. gate-G mutating the design/ATs must be "
        "non-representable."
    )
    if _GATE_G.is_file():
        gate_text = _GATE_G.read_text(encoding="utf-8")
        # The manifest-source branch must read, never write, the design/AT artifacts.
        assert ".write_text(" not in gate_text and ".write_bytes(" not in gate_text, (
            "AT-A2: gate_g.py must not WRITE to the design contract or the AT module "
            "(read-only universe). A write call leaked into the gate logic."
        )
