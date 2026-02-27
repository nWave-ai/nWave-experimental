"""Property-based tests for plugin build pipeline pure functions.

Standalone Hypothesis tests that verify algebraic properties of pure functions
independently of the BDD scenarios. These complement the @property-tagged BDD
scenarios by testing properties with generated inputs.

Properties tested:
  1. Version string round-trip through metadata generation
  2. DES import rewriting is idempotent
  3. Import rewriting preserves non-DES content
  4. Hook entries always produce exactly 5 events with correct names
  5. Validation is deterministic (same input -> same output)
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.build_plugin import (
    generate_hook_entries,
    generate_plugin_metadata,
    rewrite_des_imports,
)


# ---------------------------------------------------------------------------
# Property 1: Version string round-trip
# ---------------------------------------------------------------------------


@given(version=st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True))
@settings(max_examples=30)
def test_property_version_preserved_in_metadata(version: str):
    """generate_plugin_metadata always preserves the exact version string."""
    metadata = generate_plugin_metadata("nw", version)
    assert metadata["version"] == version
    assert metadata["name"] == "nw"


# ---------------------------------------------------------------------------
# Property 2: Import rewriting is idempotent
# ---------------------------------------------------------------------------


@given(
    content=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z", "S")),
        min_size=0,
        max_size=500,
    )
)
@settings(max_examples=50)
def test_property_import_rewriting_idempotent(content: str):
    """Applying rewrite_des_imports twice yields the same result as once."""
    once = rewrite_des_imports(content)
    twice = rewrite_des_imports(once)
    assert once == twice, "Import rewriting is not idempotent"


# ---------------------------------------------------------------------------
# Property 3: Import rewriting preserves non-DES content
# ---------------------------------------------------------------------------


@given(
    content=st.from_regex(
        r"(import os\n|from pathlib import Path\n|# comment\n|import json\n){1,5}",
        fullmatch=True,
    )
)
@settings(max_examples=30)
def test_property_rewrite_preserves_non_des_imports(content: str):
    """Content without src.des references is returned unchanged."""
    assert rewrite_des_imports(content) == content


# ---------------------------------------------------------------------------
# Property 4: Hook entries always produce 5 events with correct names
# ---------------------------------------------------------------------------


def test_property_hook_entries_always_five_events():
    """generate_hook_entries always produces exactly 5 entries with expected events."""
    entries = generate_hook_entries()
    assert len(entries) == 5
    events = {entry["event"] for entry in entries}
    assert events == {
        "PreToolUse",
        "PostToolUse",
        "SubagentStop",
        "SessionStart",
        "SubagentStart",
    }
    # Every entry must have a non-empty command
    for entry in entries:
        assert entry["command"].strip(), f"Empty command for event {entry['event']}"


# ---------------------------------------------------------------------------
# Property 5: Import rewriting correctly transforms src.des references
# ---------------------------------------------------------------------------


@given(
    module_path=st.from_regex(r"[a-z][a-z_]{0,20}", fullmatch=True),
)
@settings(max_examples=30)
def test_property_rewrite_transforms_src_des(module_path: str):
    """Every 'from src.des.X' becomes 'from des.X' after rewriting."""
    original = f"from src.des.{module_path} import something\n"
    rewritten = rewrite_des_imports(original)
    assert "src.des" not in rewritten, f"src.des not rewritten: {rewritten}"
    assert f"from des.{module_path}" in rewritten
