"""Structural drift-guard regression AT — WS-2 (M1) of the
feature-delta-doctor-and-ssot bugfix.

FR-11 traced a 7-rejection friction cascade to a duplicated gated-section
grammar: `validate_feature_delta.py` holds the canonical Reuse-Analysis
heading (`REUSE_ANALYSIS_HEADING = "## Reuse Analysis"`, DDD-8 SSOT), but
`scripts/cli/check_reuse_first_design.py` re-declares its OWN
`_REUSE_ANALYSIS_HEADING_RE` from an INDEPENDENT hardcoded "Reuse Analysis"
literal (deliberately a lenient superset match, DDD-6, matching both the bare
form and `## Wave: <W> / [REF] Reuse Analysis`). Two definitions of one
grammar concept drift silently: change the canonical heading text in
`validate_feature_delta.py` and the script's matcher stays stale.

WS-2 (M1) requires the script's heading matcher to DERIVE from the canonical
constant so this class of drift becomes structurally impossible, not merely
absent-today-by-coincidence.

covers: R-M1
"""

from __future__ import annotations

import ast
import importlib
import inspect

import pytest

from des.cli import validate_feature_delta
from scripts.cli import check_reuse_first_design


def test_reuse_first_design_heading_matcher_tracks_the_canonical_ssot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioral drift-guard: change the canonical
    `validate_feature_delta.REUSE_ANALYSIS_HEADING` constant to a DIFFERENT
    heading text, reload `check_reuse_first_design`, and confirm its heading
    matcher recognizes the NEW text. A matcher that DERIVES from the SSOT
    tracks the change; a matcher that hardcodes its own literal does not.

    FAILS TODAY (MISSING_FUNCTIONALITY, semantic AssertionError):
    `check_reuse_first_design.py` builds `_REUSE_ANALYSIS_HEADING_RE` from
    its own hardcoded "Reuse Analysis" string at import time -- it never
    reads `validate_feature_delta.REUSE_ANALYSIS_HEADING`. Changing the
    canonical constant and reloading the script leaves the OLD heading text
    as the only one its matcher recognizes -- the exact drift class FR-11
    hit (an independent duplicate regex, `check_reuse_first_design.py:77`).
    """
    monkeypatch.setattr(
        validate_feature_delta,
        "REUSE_ANALYSIS_HEADING",
        "## Existing-Component Ledger",
    )
    reloaded = importlib.reload(check_reuse_first_design)
    try:
        sections = reloaded._extract_reuse_analysis_sections(
            "## Existing-Component Ledger\n\n"
            "| Existing Component | File | Overlap | Decision | Justification |\n"
            "|---|---|---|---|---|\n"
            "| Foo | src/foo.py | none | EXTEND | reused |\n"
        )
        assert sections, (
            "check_reuse_first_design's heading matcher did not recognize "
            "the NEW canonical heading text after "
            "validate_feature_delta.REUSE_ANALYSIS_HEADING changed -- it "
            "must DERIVE its heading matcher from the canonical constant "
            "(des.cli.validate_feature_delta.REUSE_ANALYSIS_HEADING), not "
            "hardcode an independent 'Reuse Analysis' literal in its own "
            "_REUSE_ANALYSIS_HEADING_RE. Fix: import REUSE_ANALYSIS_HEADING "
            "from des.cli.validate_feature_delta and build the lenient "
            "superset regex (DDD-6) from that constant's core text."
        )
    finally:
        # Undo the reload-induced module mutation for every test that runs
        # after this one in the same pytest process (monkeypatch alone only
        # restores the attribute, not the reloaded module's derived state).
        importlib.reload(validate_feature_delta)
        importlib.reload(reloaded)


def test_reuse_first_design_imports_canonical_heading_from_validate_feature_delta() -> (
    None
):
    """Structural companion (AST fact, not a text-substring guess):
    `check_reuse_first_design.py` must import `REUSE_ANALYSIS_HEADING` from
    `des.cli.validate_feature_delta`.

    A naive `"REUSE_ANALYSIS_HEADING" in source` substring check would
    FALSE-POSITIVE today: the script's own variable name
    `_REUSE_ANALYSIS_HEADING_RE` contains that exact substring despite
    carrying no coupling to the canonical constant. AST import inspection
    avoids that false positive.

    FAILS TODAY: no such import exists in check_reuse_first_design.py.
    """
    tree = ast.parse(inspect.getsource(check_reuse_first_design))
    imports_canonical_heading = any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith("validate_feature_delta")
        and any(alias.name == "REUSE_ANALYSIS_HEADING" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_canonical_heading, (
        "scripts/cli/check_reuse_first_design.py must "
        "'from des.cli.validate_feature_delta import REUSE_ANALYSIS_HEADING' "
        "and build its heading matcher from that constant -- an "
        "independently hardcoded 'Reuse Analysis' literal is exactly the "
        "SSOT drift FR-11 traced (one gated-section grammar, duplicated "
        "across des/cli/validate_feature_delta.py and "
        "scripts/cli/check_reuse_first_design.py)."
    )
