"""Regression: orchestrator schema-versioning tests must not use the
banned `returns_N` technical-oracle naming pattern (Contract-Shape check c,
`des.cli.check_contract_shape_declarations`).

Two tests in tests/des/unit/test_orchestrator_schema_versioning.py used to be
named test_get_phase_count_for_schema_v1_0_returns_14 and
test_get_phase_count_for_schema_v2_0_returns_8 -- names that encode the
return VALUE instead of the observable behaviour, matching the banned
`^test_.*returns_\\d+` regex declared in check_contract_shape_declarations.py.
This pins that the file's test names never regress back to that pattern.
"""

import ast
from pathlib import Path

from des.cli.check_contract_shape_declarations import _BANNED_TECHNICAL_NAME_RE


TARGET = (
    Path(__file__).resolve().parents[3]
    / "des"
    / "unit"
    / "test_orchestrator_schema_versioning.py"
)


def _test_function_names() -> list[str]:
    module = ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))
    return [
        node.name
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def test_no_test_name_matches_the_banned_returns_n_pattern():
    names = _test_function_names()
    assert names, "expected to find test_* functions in the target file"
    offenders = [name for name in names if _BANNED_TECHNICAL_NAME_RE.match(name)]
    assert offenders == []
