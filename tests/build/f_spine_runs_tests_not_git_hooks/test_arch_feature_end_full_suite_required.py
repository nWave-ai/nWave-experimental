"""CT-7-coherence (slice-04, DDD-5): the feature-end full-suite leg is REQUIRED.

Arch-tier, pure-function (no subprocess, no behavioral execution): reads the
shipped feature-end ``required`` ledger-record SSOT as DATA and asserts the
full-suite-leg record (``FullSuiteLegRan``) is a member -- so the done-gate
REFUSES on its ABSENCE. This is the mechanical floor of the directive's "be
CERTAIN": the feature-end full suite is a REQUIRED, attested record, not an
optional claim. Recognized as an arch test (``test_arch_`` prefix under
``tests/build/``) per the AT-completeness S2 tolerable-variant rule.

Composes (does NOT duplicate) ``f-nonbypassable-attestation`` (which OWNS the
``FullSuiteLegRan`` ledger record + its required-set membership, DDD-4). This
feature CONSUMES that membership as the certainty the git-hook-removal STEP 2 is
gated on (DDD-5 / §The explicit pre-push interim transition). The assertion here
is a CONSUMER coherence check over the shipped SSOT, never a re-authoring of the
emitter.

DORMANT-SEAM (D11 / Mandate-15): the certainty seam (CT-7) is the feature-end
full-suite leg's required-set membership. This witnesses it by reading the SAME
shipped required-set the done-gate reads (a binding-resolved reach -- the record
name joined to its required-set identity), asserting the observable effect (the
record is required), never a claim the leg "exists".

ACTIVE-RED (atdd_pure -- NOT @skip): if ``f-nonbypassable-attestation`` has
landed ``FullSuiteLegRan`` into the required SSOT, this CONSUMER check is GREEN at
HEAD (it consumes an already-built leg -- the legitimate "already implemented"
case per nw-tdd-methodology "No Code Without a Requiring Test"). If that feature
has NOT yet landed it, this RED-fails NAMING the missing record -- a semantic
AssertionError, surfacing the cross-feature reconciliation gap. Either way it is a
contract over the shipped SSOT, not a self-fulfilling fixture.
"""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_PATH = _REPO_ROOT / "src" / "des" / "cli" / "verify_deliver_integrity.py"
_FLAVOR_PATH = _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"

_FULL_SUITE_RECORD = "FullSuiteLegRan"


def _cli_required_set() -> frozenset[str]:
    """The hardcoded ``required = {...}`` set in verify_deliver_integrity, as DATA.

    AST-parses the module and finds the assignment to ``required`` whose value is
    a set literal of string constants -- never executes the gate.
    """
    tree = ast.parse(_CLI_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "required" not in targets or not isinstance(node.value, ast.Set):
            continue
        return frozenset(
            elt.value
            for elt in node.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
    return frozenset()


def test_full_suite_leg_record_is_required() -> None:
    """The feature-end full-suite leg record is in the done-gate required set."""
    required = _cli_required_set()
    assert required, (
        "expected to read a non-empty `required` set literal from "
        f"{_CLI_PATH}; found none (the AST shape may have changed)."
    )
    assert _FULL_SUITE_RECORD in required, (
        f"expected {_FULL_SUITE_RECORD!r} in the feature-end `required` set (the "
        "certainty CT-7 the git-hook-removal is gated on -- the done-gate must "
        f"refuse on its absence, DDD-5); required set: {sorted(required)!r}. If "
        "RED, f-nonbypassable-attestation has not yet landed the required-set "
        "membership this feature consumes (cross-feature reconciliation gap)."
    )
