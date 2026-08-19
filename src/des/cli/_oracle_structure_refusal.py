"""Shared oracle-structure refusal (K4 Run 10).

Mirrors `_declared_import_refusal.py`/`_verification_command_refusal.py`'s
shape exactly: `des dispatch` and `des validate-delivery-contract` both
call this, one WHAT/WHY/HOW message per finding, no drifting second copy
across the two point-of-use verification call sites (ADR-SSOT-002 Section
4a item 9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.oracle_structure_resolver import oracle_file_findings
from des.domain.verification_command_resolver import resolve_existing_oracle_files


if TYPE_CHECKING:
    from pathlib import Path


_FINDING_WHY = {
    "does-not-compile": (
        "an oracle that fails to parse can never run as RED or GREEN "
        "evidence for anything"
    ),
    "nested-test": (
        "a test function defined inside another function/method body is "
        "never collected by any test runner, and the outer function "
        "silently absorbs whatever code follows it at that indentation "
        "(K4 Run 10: a spliced test method swallowed its host method's own "
        "tail assertions, undetected, until a crafter hit it at BASELINE "
        "after implementing a full production change)"
    ),
    "no-assertion": (
        "a test with zero assertion-shaped statements can never fail, so "
        "it proves nothing about the behavior it claims to verify"
    ),
}

_FINDING_HOW = {
    "does-not-compile": "fix the syntax error at the cited line so the file parses",
    "nested-test": (
        "move the nested `def test_*` to the class body (a TestCase "
        "method) or the module body (a pytest function) at its own "
        "top-level indentation, and read the file back whole afterward to "
        "confirm the method it was spliced out of still has its complete "
        "original body"
    ),
    "no-assertion": (
        "add at least one assertion-shaped statement (`assert ...`, "
        "`self.assert*(...)`, or `pytest.raises(...)`) to the cited test"
    ),
}


def all_oracle_structure_findings(
    repo_root: Path, contract: dict
) -> list[tuple[str, str, str]]:
    """One `(what, why, how)` per structural defect, across every existing
    oracle/test file this contract names -- not only the first."""
    findings: list[tuple[str, str, str]] = []
    for path in resolve_existing_oracle_files(repo_root, contract):
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = str(path)
        for kind, lineno in oracle_file_findings(path):
            findings.append(
                (
                    f"{relative}:{lineno} is structurally broken ({kind})",
                    _FINDING_WHY[kind],
                    f"{_FINDING_HOW[kind]} (at {relative}:{lineno})",
                )
            )
    return findings
