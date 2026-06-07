"""pytest-bdd configuration for the fix-design-component-manifest AT set.

ATDD-pure carpaccio: five slice feature files, each authored + reviewed ahead
of its slice's implementation, so every scenario is RED-by-design until the
slice's DELIVER crafter lands the implementation.

The CLIs and schema (``validate_component_manifest``, ``resolve_manifest_state``,
``component-manifest.schema.json``) are RED scaffolds on master -- their entry
points raise ``AssertionError`` (RED: missing functionality, Mandate 7), so the
scenarios FAIL for the right reason rather than erroring on a broken import.
slices 04-05 additionally assert against framework assets not yet edited.

No xfail rewrite hook: under atdd_pure each slice's scenarios go GREEN when its
slice lands. The carpaccio DELIVER spine unskips per slice; on master the whole
set is RED-for-the-right-reason, which is the intended pre-DELIVER state.
"""

from __future__ import annotations
