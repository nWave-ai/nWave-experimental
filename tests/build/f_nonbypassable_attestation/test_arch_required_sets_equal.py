"""AT-A6 (slice-01, DDD-8): the two dual-SSOT feature-end `required` sets are EQUAL
and BOTH contain the net-new full-suite-leg record.

Arch-tier, pure-function (no subprocess, no behavioral execution): reads the two
SSOTs as DATA and asserts equality. Recognized as an arch test (``test_arch_``
prefix under ``tests/build/``) per the AT-completeness S2 tolerable-variant rule.

Self-application of Principle 13: D4 mutates the `required` set in TWO places --
the hardcoded set at ``verify_deliver_integrity.py:519`` AND
``nWave/flavors/atdd_pure.yaml feature_end_required_records``. A future edit that
touches only ONE location would silently re-open the authored-but-half-wired hole
this feature exists to kill. This test holds them equal.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD NEITHER SSOT contains
``FullSuiteLegRan`` (both carry 6 records, equal but incomplete). The equality
sub-assertion is green; the contains-FullSuiteLegRan sub-assertion RED-fails with
a semantic AssertionError. GREEN once DELIVER adds ``FullSuiteLegRan`` to BOTH
SSOTs (slice-01). The test reads the REAL shipped files -- it is a contract over
the shipped artifacts, not a self-fulfilling fixture (Mandate-13 protocol-driver:
assert a shipped artifact, never a test-fabricated oracle).
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_PATH = _REPO_ROOT / "src" / "des" / "cli" / "verify_deliver_integrity.py"
_FLAVOR_PATH = _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"

_FULL_SUITE_RECORD = "FullSuiteLegRan"


def _cli_required_set() -> frozenset[str]:
    """The hardcoded `required = {...}` set in verify_deliver_integrity, read as a literal.

    AST-parses the module and finds the assignment to ``required`` whose value is a
    set literal of string constants -- never executes the gate.
    """
    tree = ast.parse(_CLI_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "required" not in targets or not isinstance(node.value, ast.Set):
            continue
        elts = node.value.elts
        if all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts):
            return frozenset(e.value for e in elts)  # type: ignore[union-attr]
    raise AssertionError(
        "could not locate the hardcoded `required = {...}` string-set literal in "
        f"{_CLI_PATH} -- the AT-A6 reader is bound to a stale SSOT shape"
    )


def _flavor_required_set() -> frozenset[str]:
    """The `feature_end_required_records` list under the subagent.stop composition."""
    doc = yaml.safe_load(_FLAVOR_PATH.read_text(encoding="utf-8"))
    lifecycle = doc.get("lifecycle_events", {})
    composition = lifecycle.get("subagent.stop", [])
    for gate_spec in composition:
        if isinstance(gate_spec, dict) and "feature_end_required_records" in gate_spec:
            return frozenset(gate_spec["feature_end_required_records"])
    raise AssertionError(
        "could not locate `feature_end_required_records` under subagent.stop in "
        f"{_FLAVOR_PATH} -- the AT-A6 reader is bound to a stale SSOT shape"
    )


def test_arch_dual_ssot_required_sets_are_equal() -> None:
    """The two SSOTs hold the SAME required set (no drift)."""
    cli = _cli_required_set()
    flavor = _flavor_required_set()
    assert cli == flavor, (
        "the two dual-SSOT feature-end `required` sets MUST be EQUAL (DDD-8) so a "
        "future single-location edit cannot silently re-open the half-wired hole; "
        f"CLI-only={sorted(cli - flavor)} flavor-only={sorted(flavor - cli)}"
    )


def test_arch_both_ssots_require_full_suite_leg() -> None:
    """ACTIVE-RED: both SSOTs must require the net-new full-suite-leg record (DDD-4)."""
    cli = _cli_required_set()
    flavor = _flavor_required_set()
    missing_from = [
        name
        for name, s in (
            ("verify_deliver_integrity.py", cli),
            ("atdd_pure.yaml", flavor),
        )
        if _FULL_SUITE_RECORD not in s
    ]
    assert not missing_from, (
        f"the net-new {_FULL_SUITE_RECORD!r} feature-end record (DDD-4) must be in "
        f"the `required` set of BOTH SSOTs so a done declared over an unrun full "
        f"suite is refused on record-absence; it is missing from {missing_from}. "
        "GREEN once DELIVER adds it to both."
    )
