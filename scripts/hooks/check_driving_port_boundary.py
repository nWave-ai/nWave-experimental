"""Pre-commit check: acceptance test When steps must not import driven adapters.

RCA fix P2 (2026-04-11): The acceptance test designer (ATD) repeatedly wrote
walking skeleton tests that entered from driven adapters instead of the
application service (driving port). This check makes the violation
structurally detectable.

Rule: In acceptance test step definition files (test_*.py under acceptance/),
any function decorated with @when must not contain imports from
`des.adapters.driven.*`. Adapter imports belong in fixtures (conftest.py),
not in When steps.

Exit codes:
    0 = All clean
    1 = Violations found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _find_when_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    """Find functions decorated with @when (from pytest_bdd)."""
    results: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            # Match @when(...) or @when
            dec_name = ""
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                dec_name = dec.func.id
            elif isinstance(dec, ast.Name):
                dec_name = dec.id
            if dec_name == "when":
                results.append(node)
                break
    return results


def _find_adapter_imports_in_function(func: ast.FunctionDef) -> list[tuple[int, str]]:
    """Find imports from des.adapters.driven.* inside a function body."""
    violations: list[tuple[int, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "des.adapters.driven" in node.module:
                violations.append((node.lineno, node.module))
    return violations


_ADAPTER_TEST_PATTERNS = {
    "test_real_adapters",
    "test_wiring",
    "test_contract_smoke",
    "test_claude_cli_runner",
    "test_gate_evaluation",  # @adapter-integration scenarios test CEL syntax validation
}

# Legacy files with known violations — these predate the driving port check.
# Each should be fixed when its feature is next touched.
_LEGACY_EXEMPT_FILES = {
    "test_backlog_bridge",
    "test_catalog_bridge",
    "test_contribution_registry",
    "test_directory_discovery",
    "test_lock_file",
    "test_workflow_definition",
    "test_payload_recording",
    "test_des_feedback",
    "test_observer_registry",
}

_EXEMPT_MARKER = "# noqa: DPB001"


def _is_adapter_integration_file(filepath: Path) -> bool:
    """Check if file is an adapter integration test (legitimate adapter imports)."""
    return filepath.stem in _ADAPTER_TEST_PATTERNS


def _is_legacy_exempt(filepath: Path) -> bool:
    """Check if file is a known legacy violation (to be fixed when feature is next touched)."""
    return filepath.stem in _LEGACY_EXEMPT_FILES


def check_file(filepath: Path) -> list[str]:
    """Check a single file for driving port boundary violations."""
    if _is_adapter_integration_file(filepath) or _is_legacy_exempt(filepath):
        return []

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    # File-level exempt marker
    if _EXEMPT_MARKER in source:
        return []

    when_fns = _find_when_functions(tree)
    issues: list[str] = []

    for func in when_fns:
        for lineno, module in _find_adapter_imports_in_function(func):
            issues.append(
                f"{filepath}:{lineno}: @when step '{func.name}' imports "
                f"driven adapter '{module}' — use application service (driving port) instead"
            )

    return issues


def main(argv: list[str] | None = None) -> int:
    """Scan acceptance test files for driving port boundary violations."""
    if argv is None:
        argv = sys.argv[1:]

    # Find all acceptance test step definition files
    base = Path("tests/des/acceptance")
    if not base.exists():
        return 0

    test_files = sorted(base.rglob("test_*.py"))
    all_issues: list[str] = []

    for tf in test_files:
        all_issues.extend(check_file(tf))

    if all_issues:
        print("DRIVING PORT BOUNDARY VIOLATIONS:")
        print()
        for issue in all_issues:
            print(f"  {issue}")
        print()
        print(
            f"{len(all_issues)} violation(s) found. "
            "When steps must enter from the driving port (application service), "
            "not from driven adapters. Move adapter imports to conftest.py fixtures."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
