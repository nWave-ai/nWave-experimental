"""Structural drift-guard regression AT — WS-2 (M1) of the
feature-delta-doctor-and-ssot bugfix, reconciled onto the DD-7 contract
(declared-facts-reachable-recorded, slice-02).

FR-11 traced a 7-rejection friction cascade to a duplicated gated-section
grammar: `validate_feature_delta.py` holds the canonical Reuse-Analysis
heading (`REUSE_ANALYSIS_HEADING = "## Reuse Analysis"`, DDD-8 SSOT), but
`scripts/cli/check_reuse_first_design.py` used to re-declare its OWN
`_REUSE_ANALYSIS_HEADING_RE` from an INDEPENDENT hardcoded "Reuse Analysis"
literal (a deliberately lenient superset match, DDD-6, matching both the bare
form and `## Wave: <W> / [REF] Reuse Analysis`).

WS-2 (M1) originally required the script's heading matcher to DERIVE from the
canonical constant so this class of drift becomes structurally impossible.
DD-7 supersedes that partial fix with a stronger structure: there is no
second matcher left to derive from anything — `check_reuse_first_design.py`
carries ZERO heading-recognition logic of its own. It imports and calls the
single unified predicate, `des.cli.validate_feature_delta.
is_reuse_analysis_heading` (bare, whitespace-tolerant `## Reuse Analysis`
ONLY; the former Wave-form leniency is gone — that inconsistency IS the D2
defect DD-7 fixes). This file's two tests still guard the SAME drift class
FR-11 traced, on their ORIGINAL two axes, re-pointed at the DD-7 contract:

- a BEHAVIORAL guard (this consumer's observable output tracks a change to
  the canonical heading text, because it routes through the shared
  predicate rather than a private copy); and
- a STRUCTURAL guard (an AST fact: the consumer imports the canonical
  predicate by name — a substring check on the source text would
  false-positive on the script's own now-deleted `_REUSE_ANALYSIS_HEADING_RE`
  variable name, so AST inspection is used instead of text matching).

These are a DIFFERENT mechanism than the slice's own AT
(`tests/des/acceptance/declared_facts/test_slice_02_reuse_heading_predicate.py
::test_check_reuse_first_design_never_defines_its_own_reuse_analysis_heading_regex`),
which AST-scans the whole tree for a `_REUSE_ANALYSIS_HEADING_RE` name binding
outside `validate_feature_delta.py`. Two guards on different mechanisms
against the same drift class are not duplication — verifying both the
NEGATIVE fact (no rogue definition exists anywhere) and the POSITIVE facts
(this specific consumer imports the real predicate, and consuming it actually
changes behavior) closes the loop from two independent directions.

covers: R-M1
"""

from __future__ import annotations

import ast
import inspect

import pytest

from des.cli import validate_feature_delta
from scripts.cli import check_reuse_first_design


def test_check_reuse_first_designs_section_extraction_tracks_the_canonical_ssot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioral drift-guard: change the canonical heading text at its
    single point of derivation and confirm `check_reuse_first_design`'s
    section extraction recognizes the NEW text — proving it routes through
    the shared `is_reuse_analysis_heading` predicate rather than carrying an
    independent, frozen copy.

    Mechanics: `is_reuse_analysis_heading` reads the module-global
    `validate_feature_delta._REUSE_ANALYSIS_HEADING_RE` via a normal Python
    global lookup performed AT CALL TIME (not at `def`-time) — and
    `check_reuse_first_design.is_reuse_analysis_heading` is the exact same
    function object, bound once via `from ... import` (JOB: DD-7 import,
    `check_reuse_first_design.py:60`). So patching that one module-level
    regex on `validate_feature_delta` — re-derived through the module's own
    real `_exact_heading_regex` helper, the identical derivation
    `_REUSE_ANALYSIS_HEADING_RE = _exact_heading_regex(REUSE_ANALYSIS_HEADING)`
    performs at import time — is visible to BOTH call sites without
    reloading either module. No manual `importlib.reload` + `finally`
    cleanup is needed here (unlike the pre-DD-7 version of this test): there
    is no second, independently-derived regex living inside
    `check_reuse_first_design` for a reload to resynchronize, and
    `monkeypatch` already reverts both patched attributes at teardown — a
    manual reload dance would only reintroduce complexity DD-7's
    single-predicate structure made unnecessary.

    FAILS FOR THE PRE-DD-7 SHAPE: before DD-7, `check_reuse_first_design.py`
    built its own `_REUSE_ANALYSIS_HEADING_RE` from a hardcoded "Reuse
    Analysis" literal at import time — patching `validate_feature_delta`'s
    regex would never have been visible to it, exactly the drift FR-11
    caught (`check_reuse_first_design.py:77`, pre-DD-7).
    """
    new_heading = "## Existing-Component Ledger"
    monkeypatch.setattr(validate_feature_delta, "REUSE_ANALYSIS_HEADING", new_heading)
    monkeypatch.setattr(
        validate_feature_delta,
        "_REUSE_ANALYSIS_HEADING_RE",
        validate_feature_delta._exact_heading_regex(new_heading),
    )

    sections = check_reuse_first_design._extract_reuse_analysis_sections(
        "## Existing-Component Ledger\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| Foo | src/foo.py | none | EXTEND | reused |\n"
    )

    assert sections, (
        "check_reuse_first_design's section extraction did not recognize "
        "the NEW canonical heading text after validate_feature_delta's "
        "derived heading regex changed -- it must consume "
        "is_reuse_analysis_heading (des.cli.validate_feature_delta) live at "
        "call time, not carry an independently-derived copy of its own."
    )


def test_check_reuse_first_design_imports_canonical_predicate_from_validate_feature_delta() -> (
    None
):
    """Structural companion (AST fact, not a text-substring guess):
    `check_reuse_first_design.py` must import `is_reuse_analysis_heading`
    from `des.cli.validate_feature_delta`.

    A naive `"is_reuse_analysis_heading" in source` substring check would be
    fragile against an unrelated local helper of the same name; AST import
    inspection asserts the concrete binding fact instead: a
    `from des.cli.validate_feature_delta import is_reuse_analysis_heading`
    (or an equivalently-resolving qualified import) node exists in the
    module.
    """
    tree = ast.parse(inspect.getsource(check_reuse_first_design))
    imports_canonical_predicate = any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith("validate_feature_delta")
        and any(alias.name == "is_reuse_analysis_heading" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_canonical_predicate, (
        "scripts/cli/check_reuse_first_design.py must "
        "'from des.cli.validate_feature_delta import is_reuse_analysis_heading' "
        "and route ALL Reuse Analysis heading recognition through that "
        "single predicate (DD-7) -- an independently hardcoded or "
        "independently-derived heading matcher is exactly the SSOT drift "
        "FR-11 traced (one gated-section grammar, duplicated across "
        "des/cli/validate_feature_delta.py and "
        "scripts/cli/check_reuse_first_design.py)."
    )
