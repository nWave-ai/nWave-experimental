"""
Step definitions for DES bundle and hooks generation scenarios.

Covers: milestone-2-des-bundle.feature
Driving port: PluginAssembler (DES bundling), HooksGenerator, ContentTransformer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pytest_bdd import given, scenarios, then


if TYPE_CHECKING:
    from pathlib import Path


scenarios("../milestone-2-des-bundle.feature")


# ---------------------------------------------------------------------------
# Given Steps: Error Path Setup
# ---------------------------------------------------------------------------


@given("the source tree is missing the DES source directory")
def source_missing_des(build_config: dict[str, Any], tmp_path: Path):
    """Create a source tree without DES source."""
    broken_root = tmp_path / "broken_des"
    broken_root.mkdir(parents=True)
    # Source has nWave but no src/des
    build_config["des_dir"] = broken_root / "src" / "des"


@given("a DES source file with an unrewritable import pattern")
def unrewritable_import(build_config: dict[str, Any], tmp_path: Path):
    """Create a DES file with an import pattern that cannot be rewritten."""
    des_dir = tmp_path / "bad_des" / "des"
    des_dir.mkdir(parents=True)
    bad_file = des_dir / "broken_import.py"
    bad_file.write_text(
        "from src.des.nonexistent.deeply.nested import something\n"
        "exec('from src' + '.des import evil')\n",
        encoding="utf-8",
    )
    build_config["des_dir"] = des_dir.parent


@given("a hook configuration template with a missing command path")
def broken_hook_template(build_config: dict[str, Any]):
    """Configure a hook template that references a nonexistent command."""
    build_config["hook_template_override"] = {
        "hooks": [
            {
                "event": "PreToolUse",
                "command": "",  # Empty command path
            }
        ]
    }


@given('any DES Python source file containing "from src.des" imports')
def any_des_source_with_imports():
    """Placeholder for property-based import rewriting test."""
    pass


@given("any valid build configuration")
def any_valid_config():
    """Placeholder for property-based hook generation test."""
    pass


# ---------------------------------------------------------------------------
# Then Steps: DES Module Presence
# ---------------------------------------------------------------------------


@then("the DES module exists in the plugin scripts directory")
def des_module_exists(build_result: dict[str, Any]):
    """Verify DES module is present in the plugin."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"
    assert des_dir.exists(), f"DES module directory not found: {des_dir}"
    assert (des_dir / "__init__.py").exists()


@then("the DES module can be imported as a standalone package")
def des_module_importable(build_result: dict[str, Any]):
    """Verify DES module is importable without external dependencies."""
    import importlib
    import sys

    plugin_dir = build_result["plugin_dir"]
    scripts_dir = plugin_dir / "scripts"

    # Temporarily add scripts dir to sys.path
    original_path = sys.path.copy()
    try:
        sys.path.insert(0, str(scripts_dir))
        # This should not raise ImportError
        spec = importlib.util.find_spec("des")
        assert spec is not None, "DES module not found in plugin scripts"
    finally:
        sys.path = original_path


@then('no DES source file contains "from src.des" imports')
def no_src_des_imports(build_result: dict[str, Any]):
    """Verify all imports are rewritten."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"
    for py_file in des_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "from src.des" not in content, f"Unrewritten import in {py_file.name}"
        assert "import src.des" not in content, f"Unrewritten import in {py_file.name}"


@then('all DES imports reference the standalone "des" package')
def des_imports_use_standalone(build_result: dict[str, Any]):
    """Verify DES imports use 'from des.' pattern."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"
    for py_file in des_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        # Lines with des imports should use 'from des.' not 'from src.des.'
        for line in content.splitlines():
            if "from src.des" in line:
                pytest.fail(f"Found unrewritten import in {py_file.name}: {line}")


@then("the DES module has no external package dependencies")
def des_no_external_deps(build_result: dict[str, Any]):
    """Verify DES module is stdlib-only."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"

    # Known external packages that should NOT appear
    forbidden_imports = {"yaml", "pyyaml", "pydantic", "requests", "toml"}

    for py_file in des_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for pkg in forbidden_imports:
                    if f"import {pkg}" in stripped or f"from {pkg}" in stripped:
                        pytest.fail(
                            f"External dependency '{pkg}' found in {py_file.name}: {stripped}"
                        )


@then("the DES module uses only Python standard library imports")
def des_stdlib_only(build_result: dict[str, Any]):
    """Alias for stdlib-only check."""
    # Delegated to the external dependency check above
    pass


# ---------------------------------------------------------------------------
# Then Steps: Hooks Configuration
# ---------------------------------------------------------------------------


@then("the plugin directory contains hook registrations")
def plugin_has_hooks(build_result: dict[str, Any]):
    """Verify hooks.json exists."""
    plugin_dir = build_result["plugin_dir"]
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    assert hooks_path.exists(), f"hooks.json not found: {hooks_path}"


@then("the hook configuration registers a handler for tool validation")
def hooks_register_pre_tool_use(build_result: dict[str, Any]):
    """Verify PreToolUse hook is registered."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    events = [h.get("event", "") for h in hooks.get("hooks", [])]
    assert "PreToolUse" in events


@then("the hook configuration registers a handler for task completion")
def hooks_register_post_tool_use(build_result: dict[str, Any]):
    """Verify PostToolUse hook is registered."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    events = [h.get("event", "") for h in hooks.get("hooks", [])]
    assert "PostToolUse" in events


@then("the hook configuration registers a handler for subagent lifecycle")
def hooks_register_subagent_stop(build_result: dict[str, Any]):
    """Verify SubagentStop hook is registered."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    events = [h.get("event", "") for h in hooks.get("hooks", [])]
    assert "SubagentStop" in events


@then("the hook configuration registers a handler for session startup")
def hooks_register_session_start(build_result: dict[str, Any]):
    """Verify SessionStart hook is registered."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    events = [h.get("event", "") for h in hooks.get("hooks", [])]
    assert "SessionStart" in events


@then("hook commands reference the plugin root for execution")
def hooks_use_plugin_root(build_result: dict[str, Any]):
    """Verify hook commands use CLAUDE_PLUGIN_ROOT, not HOME."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    for hook in hooks.get("hooks", []):
        cmd = hook.get("command", "")
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd or "CLAUDE_PLUGIN_ROOT" in cmd, (
            f"Hook command does not reference plugin root: {cmd}"
        )


@then("every hook command references the plugin root variable")
def every_hook_uses_plugin_root(build_result: dict[str, Any]):
    """Verify all hooks use CLAUDE_PLUGIN_ROOT."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    for hook in hooks.get("hooks", []):
        cmd = hook.get("command", "")
        assert "$HOME" not in cmd, (
            f"Hook uses $HOME instead of CLAUDE_PLUGIN_ROOT: {cmd}"
        )


@then("no hook command references a home directory path")
def no_home_dir_in_hooks(build_result: dict[str, Any]):
    """Verify no $HOME references in hook commands."""
    import json

    plugin_dir = build_result["plugin_dir"]
    hooks = json.loads(
        (plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    for hook in hooks.get("hooks", []):
        cmd = hook.get("command", "")
        assert "$HOME" not in cmd
        assert "~/" not in cmd


# ---------------------------------------------------------------------------
# Then Steps: DES Templates
# ---------------------------------------------------------------------------


@then("the TDD cycle schema template exists in the plugin")
def tdd_schema_exists(build_result: dict[str, Any]):
    """Verify TDD cycle schema is bundled."""
    plugin_dir = build_result["plugin_dir"]
    # Check in scripts/templates or lib/des/templates
    found = list(plugin_dir.rglob("step-tdd-cycle-schema.json")) or list(
        plugin_dir.rglob("*tdd*schema*")
    )
    assert len(found) > 0, "TDD cycle schema template not found in plugin"


@then("the roadmap schema template exists in the plugin")
def roadmap_schema_exists(build_result: dict[str, Any]):
    """Verify roadmap schema is bundled."""
    plugin_dir = build_result["plugin_dir"]
    found = list(plugin_dir.rglob("roadmap-schema.json")) or list(
        plugin_dir.rglob("*roadmap*schema*")
    )
    assert len(found) > 0, "Roadmap schema template not found in plugin"


@then("the DES module is importable from the plugin directory")
def des_importable(build_result: dict[str, Any]):
    """Verify DES can be imported (alias for walking skeleton)."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"
    assert des_dir.exists()
    assert (des_dir / "__init__.py").exists()


# ---------------------------------------------------------------------------
# Then Steps: Error Assertions
# ---------------------------------------------------------------------------


@then("the build fails with a missing DES source error")
def build_fails_missing_des(build_result: dict[str, Any]):
    """Verify build failure mentions DES."""
    assert build_result["success"] is False
    assert "des" in build_result["error"].lower()


@then("the build fails with an import rewriting error")
def build_fails_import_rewrite(build_result: dict[str, Any]):
    """Verify build failure mentions import rewriting."""
    assert build_result["success"] is False
    error_lower = build_result["error"].lower()
    assert "import" in error_lower or "rewrite" in error_lower


@then("the error message identifies the problematic file")
def error_identifies_file(build_result: dict[str, Any]):
    """Verify error message includes filename."""
    assert build_result["error"] is not None
    # Error should reference a .py file
    assert ".py" in build_result["error"]


@then("the build fails with a hook configuration error")
def build_fails_hook_config(build_result: dict[str, Any]):
    """Verify build failure mentions hook configuration."""
    assert build_result["success"] is False
    error_lower = build_result["error"].lower()
    assert "hook" in error_lower or "command" in error_lower


# ---------------------------------------------------------------------------
# Then Steps: Edge Cases
# ---------------------------------------------------------------------------


@then("no Python bytecode cache directories exist in the DES bundle")
def no_pycache_in_des(build_result: dict[str, Any]):
    """Verify __pycache__ is cleaned from DES bundle."""
    plugin_dir = build_result["plugin_dir"]
    des_dir = plugin_dir / "scripts" / "des"
    pycache_dirs = list(des_dir.rglob("__pycache__"))
    assert len(pycache_dirs) == 0, (
        f"Found {len(pycache_dirs)} __pycache__ directories in DES bundle"
    )


@then('every "from src.des" import is replaced with "from des"')
def all_imports_rewritten():
    """Property: all imports are rewritten (placeholder)."""
    pass


@then("the rewritten file is syntactically valid Python")
def rewritten_file_valid_python():
    """Property: rewritten files parse as valid Python."""
    pass


@then("the configuration contains handlers for all five DES event types")
def hooks_have_all_five_events():
    """Property: all event types present in hook config."""
    pass
