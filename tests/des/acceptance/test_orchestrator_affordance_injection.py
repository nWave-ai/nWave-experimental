"""Acceptance tests -- orchestrator-affordance-injection (DISTILL, slice-01).

Charter: docs/product/expectations/orchestrator-affordance-injection/
         affordance-loaded-from-text-not-hardcoded.md
Feature-delta: docs/feature/orchestrator-affordance-injection/feature-delta.md

Contract under test (SHIPPED -- this suite is GREEN against the real
implementation, retained as a regression pin):
`src/des/adapters/drivers/hooks/session_start_handler.py:
load_orchestrator_affordance(assets_dir: Path) -> str | None` reads every
`*.md` file under `assets_dir` (sorted by name), concatenates their text
(with a separator), and returns the combined affordance string -- or `None`
when the dir is absent, empty, or unreadable (fail-open, never raises). The
CONTENT is loaded from text on every call, never hardcoded or cached, so
iterating the affordance needs only a text edit under
`nWave/data/orchestrator-affordance/`, zero code change.

Historical note (P1-P4, `nw-distill-red-scaffolding`): this suite was
originally authored active-RED, with the import happening INSIDE a helper
called from each test body (hidden-import) so the (then-)absent function
surfaced as a semantic AssertionError (MISSING_FUNCTIONALITY) at runtime,
never a collection ImportError (BROKEN). The hidden-import helper is kept
as-is now that the function is shipped -- it is a harmless indirection, not
a regression.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the pure `load_orchestrator_affordance` function driven
directly against a throwaway `tmp_path` assets dir -- the honest testable
seam for the content/iterability/fail-open observables, avoiding the
SessionStart activation-gate/subprocess complexity per the feature-delta
scope note.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3): keep the absent function out of collection
# scope; the absence surfaces as a runtime AssertionError inside a test body.
# ---------------------------------------------------------------------------


def _import_load_orchestrator_affordance():
    try:
        from des.adapters.drivers.hooks.session_start_handler import (
            load_orchestrator_affordance,
        )
    except ImportError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "load_orchestrator_affordance(assets_dir: Path) -> str | None "
            "does not exist yet in "
            "src/des/adapters/drivers/hooks/session_start_handler.py "
            f"({exc}). Implement it per the DESIGN contract (feature-delta "
            "[REF] Architecture & Contract Tests) before this AT can pass."
        ) from exc
    return load_orchestrator_affordance


# ---------------------------------------------------------------------------
# Fixture asset builders -- write REAL `.md` files into tmp_path so the tmp
# fixture content (never this AT file's own content) is what
# `load_orchestrator_affordance` reads.
# ---------------------------------------------------------------------------


def _write_md(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _discipline_asset_text() -> str:
    """Mirrors the shipped `spine-discipline` asset's STRUCTURAL anchors -- the
    heading, the ORCHESTRATOR identity line, and the DIRECT/DISPATCH section
    tokens -- not the surrounding persuasive prose, which gets Cialdini-
    retuned periodically (rewritten 2026-07-12) and would make a full-sentence
    mirror stale on every prose iteration.
    """
    return (
        "## Orchestrator discipline -- dispatch domain work, don't hand-edit\n\n"
        "You are the ORCHESTRATOR of the nWave spine.\n\n"
        "- DIRECT (legitimate, no dispatch): feature-delta authoring, "
        "staging/commit/push, running gates.\n"
        "- DISPATCH (never hand-edit): ANY new function, ANY new test, ANY "
        "change to production code.\n"
    )


def _catalog_asset_text() -> str:
    """Mirrors the shipped `des-command-catalog` asset's producing-tool wording."""
    return (
        "# des producing-tools + gates -- reach for these instead of hand-editing\n\n"
        "Reach for `des dispatch` instead of hand-editing a checked artifact.\n"
    )


def _missing_dir(tmp_path: Path) -> Path:
    """An assets dir path that does not exist on disk at all."""
    return tmp_path / "does-not-exist" / "orchestrator-affordance"


def _empty_existing_dir(tmp_path: Path) -> Path:
    """An assets dir that exists but carries zero `.md` files."""
    empty_dir = tmp_path / "orchestrator-affordance"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return empty_dir


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE: loaded content combines every shipped asset
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_loader_returns_content_containing_both_shipped_asset_substrings(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Loading a two-`.md`-file assets dir returns a single string containing
    recognizable substrings of BOTH the discipline asset and the
    des-command-catalog asset -- the port concatenates every asset's real
    text; it does not hardcode a fixed message in code.
    """
    load_orchestrator_affordance = _import_load_orchestrator_affordance()
    assets_dir = tmp_path / "orchestrator-affordance"
    _write_md(assets_dir / "spine-discipline.md", _discipline_asset_text())
    _write_md(assets_dir / "des-command-catalog.md", _catalog_asset_text())

    affordance = load_orchestrator_affordance(assets_dir)

    assert affordance is not None, "expected loaded affordance text, got None"
    assert "ORCHESTRATOR" in affordance, (
        f"expected the discipline asset's substring in the affordance: {affordance!r}"
    )
    assert "DISPATCH" in affordance, (
        f"expected the discipline asset's DISPATCH section token in the "
        f"affordance: {affordance!r}"
    )
    assert "des dispatch" in affordance, (
        "expected the des-command-catalog asset's substring in the "
        f"affordance: {affordance!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- POSITIVE: iterability -- a text edit surfaces on next load
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_loader_reflects_a_freshly_edited_marker_on_next_call(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Editing an existing asset's text (appending a unique marker line) and
    calling the loader again surfaces that new text in the result -- proving
    content is loaded from text on each call, never hardcoded or cached.
    """
    load_orchestrator_affordance = _import_load_orchestrator_affordance()
    assets_dir = tmp_path / "orchestrator-affordance"
    asset_path = _write_md(assets_dir / "spine-discipline.md", _discipline_asset_text())
    _write_md(assets_dir / "des-command-catalog.md", _catalog_asset_text())

    before = load_orchestrator_affordance(assets_dir)
    marker = "UNIQUE-MARKER-20260708-iterability-check"
    asset_path.write_text(
        asset_path.read_text(encoding="utf-8") + f"\n{marker}\n", encoding="utf-8"
    )

    after = load_orchestrator_affordance(assets_dir)

    assert before is not None and marker not in before, (
        f"marker must be absent before the edit: {before!r}"
    )
    assert after is not None and marker in after, (
        f"expected the freshly-edited marker in a re-loaded affordance: {after!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- POSITIVE: a newly added third `.md` file is included
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_loader_includes_a_newly_added_third_asset_file(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Adding a THIRD `.md` file to the assets dir after the initial load makes
    that file's content appear in a subsequent load -- the port reads the
    whole directory, never a hardcoded file list.
    """
    load_orchestrator_affordance = _import_load_orchestrator_affordance()
    assets_dir = tmp_path / "orchestrator-affordance"
    _write_md(assets_dir / "spine-discipline.md", _discipline_asset_text())
    _write_md(assets_dir / "des-command-catalog.md", _catalog_asset_text())

    before = load_orchestrator_affordance(assets_dir)

    marker = "UNIQUE-MARKER-20260708-third-file"
    _write_md(assets_dir / "new-affordance-topic.md", f"# New topic\n\n{marker}\n")

    after = load_orchestrator_affordance(assets_dir)

    assert before is not None and marker not in before, (
        f"marker must be absent before the third file exists: {before!r}"
    )
    assert after is not None and marker in after, (
        f"expected the new third file's marker after adding it to the dir: {after!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- NEGATIVE AT: fail-open -- missing/empty dir returns None,
# never a crash.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "build_assets_dir",
    [_missing_dir, _empty_existing_dir],
    ids=["dir_does_not_exist", "dir_exists_but_has_no_md_files"],
)
def test_loader_returns_none_and_does_not_raise_on_missing_or_empty_dir(
    tmp_path: Path,
    build_assets_dir: Callable[[Path], Path],
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Fail-open: a missing assets dir, or one that exists but carries no `.md`
    file, must NOT be produced as a crash (that WRONG outcome is what this
    negative AT asserts is absent) -- `load_orchestrator_affordance` must
    return `None` and never raise.
    """
    load_orchestrator_affordance = _import_load_orchestrator_affordance()
    assets_dir = build_assets_dir(tmp_path)

    try:
        result = load_orchestrator_affordance(assets_dir)
    except Exception as exc:
        pytest.fail(
            "fail-open violation: a missing/empty assets dir must return "
            f"None, not raise {type(exc).__name__}: {exc}"
        )

    assert result is None, (
        f"expected None for a missing/empty assets dir, got {result!r}"
    )
