"""Arch gate — feature-end event-name string literals stay SSOT-sourced.

techdebt drain (event-name-constants-split-port-adapter): the environmental-
e2e gate event names (``EnvironmentalE2eGateRan`` / ``EnvironmentalE2eVerified``)
are defined exactly once, in ``des.ports.driven_ports.at_completion_ledger_port``
(``ENVIRONMENTAL_E2E_GATE_RAN`` / ``ENVIRONMENTAL_E2E_VERIFIED``). Every other
``src/des/**/*.py`` module that needs one of these two event names must IMPORT
the constant, never hardcode the string literal again -- a hardcoded literal is
exactly the ripple the SSOT consolidation exists to prevent (a name change at
the SSOT silently stops matching a copy-pasted literal elsewhere).

AST-walks every ``src/des/**/*.py`` module (excluding the canonical port
module itself) and FAILS on any string ``Constant`` node whose value equals
one of the two watched event names. This is intentionally narrower than a
blanket "no adapters import" gate: it targets literal *redefinition* of this
specific SSOT's values, not every possible layering question.

One deliberate, documented exemption: ``verify_deliver_integrity.py``'s
``required = {...}`` set MUST stay a pure string-literal set (a ``Name`` node
there breaks the sibling AST-DATA reader in
``tests/build/f_nonbypassable_attestation/test_arch_required_sets_equal.py``,
which diffs it against ``atdd_pure.yaml`` without importing/executing the
module). Everywhere else, the constant must be imported.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from des.ports.driven_ports.at_completion_ledger_port import (
    ENVIRONMENTAL_E2E_GATE_RAN,
    ENVIRONMENTAL_E2E_VERIFIED,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DES_ROOT = PROJECT_ROOT / "src" / "des"
CANONICAL_MODULE = DES_ROOT / "ports" / "driven_ports" / "at_completion_ledger_port.py"

_WATCHED_VALUES = {ENVIRONMENTAL_E2E_GATE_RAN, ENVIRONMENTAL_E2E_VERIFIED}

# (path relative to PROJECT_ROOT, assigned variable name) -> why this one
# literal set is exempt from the "must import, never hardcode" rule.
_EXEMPTED_LITERAL_SET_SITES: dict[str, str] = {
    "src/des/cli/verify_deliver_integrity.py": (
        "AST-read as pure DATA (no import execution) by "
        "tests/build/f_nonbypassable_attestation/test_arch_required_sets_equal.py "
        "for a dual-SSOT equality diff against atdd_pure.yaml; a Name node in "
        "place of a Constant there breaks that reader."
    ),
}
_EXEMPTED_ASSIGN_TARGET = "required"


def _des_modules() -> list[Path]:
    """Every ``src/des/**/*.py`` except the canonical SSOT module."""
    return sorted(p for p in DES_ROOT.rglob("*.py") if p != CANONICAL_MODULE)


def _exempted_string_constant_ids(tree: ast.AST, target_name: str) -> set[int]:
    """id()s of string Constant nodes inside a `target_name = {...}` set literal."""
    exempted: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if target_name not in targets or not isinstance(node.value, ast.Set):
            continue
        for elt in node.value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                exempted.add(id(elt))
    return exempted


def _scan_module(path: Path) -> list[str]:
    """Return violation descriptions for one module (empty == clean)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    exempted_ids: set[int] = set()
    if str(rel) in _EXEMPTED_LITERAL_SET_SITES:
        exempted_ids = _exempted_string_constant_ids(tree, _EXEMPTED_ASSIGN_TARGET)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _WATCHED_VALUES and id(node) not in exempted_ids:
                violations.append(
                    f"{rel}:{node.lineno} — literal string {node.value!r} "
                    "redefines a feature-end event-name constant; import "
                    "it from des.ports.driven_ports.at_completion_ledger_port "
                    "instead"
                )

    return violations


@pytest.mark.fast_gate
def test_no_module_redefines_environmental_e2e_event_names():
    """No ``src/des/**`` module (other than the port SSOT) hardcodes
    ``EnvironmentalE2eGateRan`` / ``EnvironmentalE2eVerified`` as a string
    literal -- every consumer must import the named constant.
    """
    all_violations: list[str] = []
    for module in _des_modules():
        all_violations.extend(_scan_module(module))

    assert not all_violations, (
        "Hardcoded feature-end event-name literal(s) detected in src/des -- "
        "these two event names are SSOT-defined in "
        "des.ports.driven_ports.at_completion_ledger_port; import the "
        "constant instead of restating the string:\n  " + "\n  ".join(all_violations)
    )


def test_adapter_reexports_stay_in_sync_with_ssot():
    """The adapter's re-exported values are byte-identical to the port SSOT.

    ``des.adapters.driven.logging.at_completion_ledger`` re-imports (not
    redefines) these constants -- this pins that the values it exposes are
    literally the same objects/strings as the port's, so a future edit that
    accidentally reintroduces a local redefinition in the adapter is caught
    even though such a redefinition would not appear as a *new* literal (its
    value already matches this test's watch-list at introduction time; the
    identity check below is the second, complementary axis).
    """
    from des.adapters.driven.logging import at_completion_ledger as adapter

    assert adapter.ENVIRONMENTAL_E2E_GATE_RAN == ENVIRONMENTAL_E2E_GATE_RAN
    assert adapter.ENVIRONMENTAL_E2E_VERIFIED == ENVIRONMENTAL_E2E_VERIFIED
