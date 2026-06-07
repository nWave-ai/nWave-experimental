"""Regression test: all read_text/write_text calls in plugin files must specify encoding.

On Windows, Python defaults to the system encoding (charmap/cp1252) which cannot
handle unicode characters (emojis, special chars) present in .md command/agent/skill
files. This test ensures every read_text()/write_text() call explicitly sets
encoding="utf-8" to prevent charmap decode errors on Windows.

See: https://github.com/nWave-ai/nWave/issues/26
"""

import ast
from pathlib import Path

import pytest


_PLUGINS_DIR = Path(__file__).resolve().parents[3] / "scripts" / "install" / "plugins"


def _collect_plugin_files() -> list[Path]:
    """Return all .py files under the plugins directory."""
    return sorted(_PLUGINS_DIR.glob("*.py"))


def _find_bare_read_write_calls(source: str) -> list[tuple[int, str]]:
    """Find read_text()/write_text() calls missing encoding= parameter.

    Uses AST parsing for accuracy -- no false positives from comments or strings.

    Args:
        source: Python source code to analyze

    Returns:
        List of (line_number, description) for each violation found
    """
    violations = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        method_name = node.func.attr
        if method_name not in ("read_text", "write_text"):
            continue

        has_encoding = any(kw.arg == "encoding" for kw in node.keywords)
        if not has_encoding:
            violations.append(
                (node.lineno, f"{method_name}() without encoding= parameter")
            )

    return violations


@pytest.mark.parametrize(
    "plugin_file",
    _collect_plugin_files(),
    ids=lambda p: p.name,
)
def test_all_read_write_calls_specify_encoding(plugin_file: Path) -> None:
    """Every read_text()/write_text() in plugin files must include encoding='utf-8'.

    Without explicit encoding, Windows uses charmap/cp1252 which fails on unicode
    characters (emojis in .md files). This is a regression guard for issue #26.
    """
    source = plugin_file.read_text(encoding="utf-8")
    violations = _find_bare_read_write_calls(source)

    if violations:
        details = "\n".join(f"  line {line}: {desc}" for line, desc in violations)
        pytest.fail(
            f"{plugin_file.name} has read_text/write_text calls without "
            f"encoding= parameter:\n{details}"
        )
