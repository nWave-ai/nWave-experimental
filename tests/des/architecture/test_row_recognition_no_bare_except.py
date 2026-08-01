"""Structural safety-net for DD-17 (ADR-EVT-002 "Read-Path Row Recognition
Contract -- Deny-by-Default", `docs/product/architecture/ADR-EVT-002-
row-recognition-contract.md`, "Enforcement (principle 11)").

`UnifiedEventStoreAdapter._classify_line` (and every DD-17 helper it calls:
`_classify_primary_new_row`, `_classify_derived_row`) inverts the row-shape
layer from open-ended "recognise known-bad, else accept" to closed
"recognise known-good, else could_not_verify" -- a VALUE-driven predicate
that needs no exception at all for row shape. The mechanical backstop this
test provides: a bare `except Exception`/`except BaseException` inside any
of these methods would silently re-widen the row-shape layer back into an
open-ended, exception-driven recogniser the next time a round-5 bad-value
form is found -- exactly the D1..D4 whack-a-mole pattern ADR-EVT-002 exists
to close.

AST-based, stdlib-only -- same enforcement family as the sibling structural
check `tests/des/architecture/test_gate_outcome_wired_criterion.py`
(presence-of-a-shape rather than name-matching / text-grepping).
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_PATH = (
    REPO_ROOT
    / "src"
    / "des"
    / "adapters"
    / "driven"
    / "logging"
    / "unified_event_store_adapter.py"
)

_GUARDED_METHOD_NAMES = frozenset(
    {
        "_classify_line",
        "_classify_primary_new_row",
        "_classify_derived_row",
    }
)


def _parse_module() -> ast.Module:
    return ast.parse(
        ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(ADAPTER_PATH)
    )


def _find_guarded_function_defs(tree: ast.AST) -> list[ast.FunctionDef]:
    """Every `def` in the module whose name is one of the DD-17 row-shape
    methods -- walks the whole tree so it does not matter whether the
    method is a plain function, a `@staticmethod`, or nested inside the
    `UnifiedEventStoreAdapter` class body."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in _GUARDED_METHOD_NAMES
    ]


def _bare_except_handlers(func: ast.FunctionDef) -> list[ast.ExceptHandler]:
    """Every `except Exception` / `except BaseException` / bare `except:`
    handler inside `func`'s own body (does not descend into a NESTED
    function/class definition, if any -- there are none in the guarded
    methods today, but this keeps the check scoped to what the method
    itself actually executes)."""
    violations: list[ast.ExceptHandler] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            # bare `except:` -- catches BaseException, the widest possible
            # net, forbidden for the same reason.
            violations.append(node)
            continue
        names = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
        if "Exception" in names or "BaseException" in names:
            violations.append(node)
    return violations


class TestRowRecognitionNoBareExcept:
    def test_guarded_methods_exist(self) -> None:
        """Sanity precondition: fail LOUD (not a silent pass) if a rename
        ever drops one of the three DD-17 method names this test polices."""
        tree = _parse_module()
        found_names = {fn.name for fn in _find_guarded_function_defs(tree)}
        missing = _GUARDED_METHOD_NAMES - found_names
        assert not missing, (
            f"WHAT: expected DD-17 row-recognition methods {sorted(missing)} "
            f"not found in {ADAPTER_PATH}. "
            "WHY: this architecture test polices these methods by name -- a "
            "silent rename would make the no-bare-except check below "
            "vacuously pass. "
            "HOW: update _GUARDED_METHOD_NAMES in this test to match the "
            "renamed method(s)."
        )

    def test_no_bare_except_exception_or_base_exception(self) -> None:
        tree = _parse_module()
        offenders: list[str] = []
        for func in _find_guarded_function_defs(tree):
            for handler in _bare_except_handlers(func):
                offenders.append(f"{func.name}:{handler.lineno}")
        assert not offenders, (
            "WHAT: found a bare `except Exception`/`except BaseException`/"
            f"`except:` inside {offenders!r} in {ADAPTER_PATH}. "
            "WHY: DD-17 (ADR-EVT-002) closes the row-shape layer as a "
            "VALUE-driven predicate -- no exception should ever need "
            "catching for row shape; a broad except here silently "
            "re-widens the layer back into the open-ended, exception-"
            "driven recogniser the D1..D4 rounds already proved does not "
            "terminate. "
            "HOW: replace the broad except with the specific, named "
            "value-driven check the row-shape gate requires (Gate 0 / "
            "agent_id / reduction_key / reduction_seq admissibility), or "
            "narrow the except to the ONE exception type genuinely "
            "expected at that call site."
        )
