"""Regression guard -- techdebt row
`ten-of-twelve-audit-trail-acceptance-tests-have-an-empty-body`.

`tests/installer/acceptance/test_us004_audit_trail.py` had ten of its twelve
`test_scenario_*` methods reduced to a docstring plus every Arrange/Act/Assert
line commented out. They ran, asserted nothing, and passed GREEN -- a test
file titled after the audit trail that declared ten scenarios covered and
verified two. The stub scenarios referenced a `DESExecutor` /
`des_executor.execute_all_phases` / `audit_log.read_entries_for_step` API
that never existed in `src/des`, keyed on a 14-phase execution model this
repo's own CLAUDE.md marks as the retired legacy contract (the current canon
is the 3-phase RED/GREEN/COMMIT cycle, ADR-025). The concrete event-logging
behaviour they gestured at (TASK_INVOCATION_*, PHASE_*, SUBAGENT_STOP_*,
COMMIT_* events) is exercised for real, against the current architecture, by
`tests/des/unit/application/test_orchestrator_audit_helper.py`,
`tests/des/unit/adapters/driven/logging/test_audit_events.py`, and
`test_audit_events_hook_types.py` -- so deleting the fictional-API stubs from
this file does not remove any coverage; it removes a placeholder that was
never redeemed and duplicated an intent the codebase already meets elsewhere.

This is an AST-level check (a test whose body -- past its docstring -- is
empty must not exist), scoped to this ONE file: it is the local regression
guard for the specific removal this row demands, not a tree-wide gate (that
larger oracle is a separate, unclaimed piece of work this row does not
authorize taking on).
"""

from __future__ import annotations

import ast
from pathlib import Path


_TARGET = Path(__file__).resolve().parent / "test_us004_audit_trail.py"


def _non_docstring_body(func: ast.FunctionDef) -> list[ast.stmt]:
    body = func.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def test_no_test_scenario_function_has_an_empty_body():
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"), filename=str(_TARGET))
    empty: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            remaining = _non_docstring_body(node)
            if not remaining or all(isinstance(stmt, ast.Pass) for stmt in remaining):
                empty.append(node.name)
    assert not empty, (
        f"{_TARGET.name} has test function(s) with no executable body past "
        f"their docstring (asserts nothing, passes vacuously): {empty!r}. "
        "Either implement the scenario for real or delete it -- an empty "
        "test that runs GREEN is indistinguishable from a real pass."
    )
