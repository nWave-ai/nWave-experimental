# @feature-declared-facts-reachable-recorded
# @slice-04
"""M-III: `des-command-catalog.md`'s verb table is GENERATED from the 76-row
`des.cli.__main__._REGISTRY`, not hand-typed at 23 (declared-facts-reachable-
recorded, slice-04).

Value statement (feature-delta.md [REF] Slice Plan, slice-04): the catalog's
verb table is generated from the registry, not hand-typed, so the two can
never silently drift apart the way M-III's defect found them.

Design commitments this slice authors ATs against (feature-delta.md DD-10,
DD-11, Contract-Tests row "docgen command-catalog GENERATED region (M-III)"):

  DD-10 — `scan()` gains a 5th key `orchestrator_affordance`
          (`nWave/data/orchestrator-affordance/*.md`); `project_generated_
          regions` includes those files in its scanned file list; a NEW pure
          function renders the `des-command-catalog` GENERATED region by
          reading `des.cli.__main__._REGISTRY` (76 rows) plus each target
          module's first docstring line via `ast.get_docstring` -- parse
          only, NEVER import-and-execute.
  DD-11 — `check_documentation_freshness.py:main()` gains a 4th freshness
          leg: `docgen.project_generated_regions` + `docgen.
          check_generated_regions`, alongside the existing 3 (stale,
          disagreements, lane_drift).

Oracle (feature-delta.md line 155): the rendered region byte-matches a
fixture registry snapshot, and `check_generated_regions` reports STALE when
the on-disk file diverges from a re-render.

Driving surface (Mandate 13 / Driving-Port-Only Boundary, `nw-test-design-
mandates`): `scripts/docgen.py` is a build-time script with no hexagonal
domain of its own -- its module-level PUBLIC functions (`scan`,
`project_generated_regions`, `check_generated_regions`, `write_generated_
regions`) already ARE the composition-root driving surface this repo's own
precedent tests directly (`tests/test_docgen.py`; the identical GENERATED-
region mechanism is driven the same way, via the `docgen` module, in
`tests/des/acceptance/mode_registry_single_locus/`). No `_render_region_body`
private-signature guess is made anywhere below -- every assertion drives
through the four PUBLIC entry points named above, or reads structure via
`ast`/the module's own pre-existing, unchanged `_GENERATED_REGION_RE`
(a stable parsing tool, not new behavior).

DISTILL-pinned table contract: DESIGN specifies "a markdown table" without
fixing its exact column shape. This slice PINS the shape (`| Verb | Module |
Description |`, one row per registry entry, in `_REGISTRY` declaration
order) as the executable contract the crafter implements to -- the
independent-derivation oracle in `_expected_catalog_table_body()` below
computes it from the SAME public data source (`_REGISTRY` + `ast.get_
docstring`) the production renderer must read, never from the renderer's
own output.

RED-for-right-reason (P1-P4, `nw-distill-red-scaffolding`): every test below
imports only STABLE, already-existing names (`scripts.docgen`,
`des.cli.__main__._REGISTRY`, stdlib `ast`/`importlib`) -- never a
not-yet-defined name, so the module always collects. Each test either
(a) asserts directly against production's CURRENT (missing) behavior, which
fails with a genuine `AssertionError`, or (b) wraps a call that currently
raises `DocgenError` in a `try/except` that re-raises as `AssertionError`
with a WHAT/WHY message, so RED is never a raw, unexplained traceback.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from tests.common.orchestrator_affordance_paths import (
    affordance_asset_names,
    resolve_affordance_asset,
)

from des.cli.__main__ import _REGISTRY
from scripts import docgen


_REPO_ROOT = Path(docgen.__file__).resolve().parent.parent
_CATALOG_ASSET = resolve_affordance_asset(_REPO_ROOT, "des-command-catalog")
_REGION_ID = "des-command-catalog"


def _wrap_region(body: str) -> str:
    """Hand-written marker pair matching the EXISTING, unchanged grammar
    ``docgen._GENERATED_REGION_RE`` parses (used only to build fixture
    "given" state -- production's own ``_generated_region`` helper rebuilds
    the START/END comment text independently on write, so this fixture
    helper does not presume its exact wording)."""
    return (
        f"<!-- GENERATED:{_REGION_ID} START -->\n"
        f"{body}\n"
        f"<!-- GENERATED:{_REGION_ID} END -->"
    )


def _minimal_asset_paths(orchestrator_affordance: list[Path]) -> dict[str, list[Path]]:
    """The exact dict shape ``project_generated_regions(root, asset_paths)``
    consumes (DD-10's 5th key), with the three pre-existing keys emptied so
    the ONLY variable under test is orchestrator_affordance inclusion."""
    return {
        "agents": [],
        "commands": [],
        "skills": [],
        "orchestrator_affordance": orchestrator_affordance,
    }


def _first_docstring_line(module_path: str) -> str:
    """Independent re-derivation of DD-10's own stated algorithm: resolve a
    registry row's dotted module path to its real source file under
    ``src/`` and read its first module-docstring line via ``ast.get_
    docstring`` -- parse only, matching the "no import-and-execute"
    contract the renderer itself must honor."""
    file_path = (
        (_REPO_ROOT / "src").joinpath(*module_path.split(".")).with_suffix(".py")
    )
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    doc = ast.get_docstring(tree)
    assert doc, f"expected {module_path} ({file_path}) to carry a module docstring"
    return doc.splitlines()[0]


def _expected_catalog_table_body() -> str:
    """The DISTILL-pinned exact markdown table, computed independently from
    the SAME public data source (``_REGISTRY`` + real module docstrings) the
    production renderer must read -- never from the renderer's own output."""
    header = "| Verb | Module | Description |"
    sep = "| --- | --- | --- |"
    rows = [
        f"| `{row.name}` | `{row.module_path}` | {_first_docstring_line(row.module_path)} |"
        for row in _REGISTRY
    ]
    return "\n".join([header, sep, *rows])


def _project_or_fail(
    asset_paths: dict[str, list[Path]],
) -> list[docgen.AssetProjection]:
    """Drive the real ``project_generated_regions`` composition-root entry;
    convert any raised exception into a semantic ``AssertionError`` (RED-
    not-BROKEN) rather than letting an unexplained traceback surface."""
    try:
        return docgen.project_generated_regions(_REPO_ROOT, asset_paths)
    except Exception as exc:
        assert False, (  # noqa: B011
            "project_generated_regions(root, asset_paths) must run to "
            f"completion over an orchestrator_affordance file -- raised "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# T1 -- scan() gains the 5th key (DD-10, first clause)
# ---------------------------------------------------------------------------


def test_scan_includes_orchestrator_affordance_asset_paths() -> None:
    """DD-10: ``scan()`` must discover ``nWave/data/orchestrator-affordance/
    *.md`` under a NEW 5th key, ``orchestrator_affordance``, alongside the
    existing ``agents``/``commands``/``skills``/``templates`` keys."""
    paths = docgen.scan(_REPO_ROOT)
    assert "orchestrator_affordance" in paths, (
        "docgen.scan() must return a 5th key 'orchestrator_affordance' "
        "listing nWave/data/orchestrator-affordance/*.md (DD-10) -- got "
        f"keys {sorted(paths)}"
    )
    names = {p.name for p in paths["orchestrator_affordance"]}
    # Independent filesystem read of the real shipped basenames (genuine
    # two-source comparison: scan() output vs. a direct directory read) --
    # never a literal name list, since the numeric injection-order prefix
    # is expected to churn (mikado D50).
    expected = affordance_asset_names(_REPO_ROOT)
    missing = expected - names
    assert not missing, (
        f"scan()['orchestrator_affordance'] must include {sorted(expected)} "
        f"-- missing {sorted(missing)}, found {sorted(names)}"
    )


# ---------------------------------------------------------------------------
# T2 -- project_generated_regions includes orchestrator_affordance files
#       carrying markers (DD-10, second clause)
# ---------------------------------------------------------------------------


def test_project_generated_regions_includes_a_marked_orchestrator_affordance_file(
    tmp_path: Path,
) -> None:
    """DD-10: ``project_generated_regions`` must include ANY orchestrator_
    affordance file carrying a GENERATED marker in its scanned file list --
    today it only walks ``agents``/``commands``/``skills``."""
    working_copy = tmp_path / "des-command-catalog.md"
    working_copy.write_text(
        "hand-authored lane guidance\n\n" + _wrap_region("STALE-PLACEHOLDER") + "\n",
        encoding="utf-8",
    )

    projections = _project_or_fail(_minimal_asset_paths([working_copy]))

    matches = [p for p in projections if p.path == working_copy]
    assert matches, (
        "project_generated_regions must include orchestrator_affordance "
        "files carrying a GENERATED marker in its scanned file list (DD-10) "
        f"-- {working_copy} produced NO projection at all "
        f"(projections cover: {[str(p.path) for p in projections]})"
    )


# ---------------------------------------------------------------------------
# T3 -- rendered region byte-matches the registry-snapshot oracle (DD-10)
# ---------------------------------------------------------------------------


def test_rendered_catalog_region_byte_matches_the_registry_snapshot(
    tmp_path: Path,
) -> None:
    """Oracle (feature-delta.md line 155): the rendered region byte-matches
    a fixture registry snapshot -- here, the table independently
    re-derived from the SAME 76-row ``_REGISTRY`` + real module docstrings."""
    working_copy = tmp_path / "des-command-catalog.md"
    working_copy.write_text(_wrap_region("STALE") + "\n", encoding="utf-8")

    projections = _project_or_fail(_minimal_asset_paths([working_copy]))
    matches = [p for p in projections if p.path == working_copy]
    assert matches, (
        "project_generated_regions produced no projection for the marked "
        f"working copy {working_copy} -- cannot verify the render oracle"
    )

    rendered = matches[0].projected_text
    match = docgen._GENERATED_REGION_RE.search(rendered)
    assert match is not None and match.group("region_id") == _REGION_ID, (
        f"expected a '{_REGION_ID}' GENERATED region in the rendered text -- "
        f"got:\n{rendered}"
    )
    rendered_body = match.group("body").strip("\n")

    expected_body = _expected_catalog_table_body()
    assert rendered_body == expected_body, (
        "the rendered des-command-catalog region must byte-match the table "
        "computed independently from des.cli.__main__._REGISTRY (76 rows) "
        "via ast.get_docstring (DD-10) -- got a mismatch.\n\n"
        f"--- expected ---\n{expected_body}\n\n--- rendered ---\n{rendered_body}"
    )


# ---------------------------------------------------------------------------
# T4 (NEGATIVE) -- the renderer NEVER imports-and-executes a target module
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_render_never_imports_and_executes_target_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DD-10: the renderer resolves each target module's docstring via
    ``ast.get_docstring`` -- parse only. It must NEVER call
    ``importlib.import_module`` on a registry target module, because that
    EXECUTES the module's top-level code (a real side-effect risk across 76
    modules -- CLI argument parsing, ledger writes, etc.)."""
    working_copy = tmp_path / "des-command-catalog.md"
    working_copy.write_text(_wrap_region("STALE") + "\n", encoding="utf-8")

    forbidden = {row.module_path for row in _REGISTRY}
    real_import_module = importlib.import_module

    def _spy(name: str, package: str | None = None):
        assert name not in forbidden, (
            f"the des-command-catalog renderer must resolve {name!r}'s "
            "docstring via ast.get_docstring (parse only) -- it called "
            "importlib.import_module on a REGISTRY target module instead, "
            "which EXECUTES the module's top-level code. DD-10 explicitly "
            "forbids import-and-execute: use ast.parse on the module's "
            "source file instead."
        )
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _spy)

    projections = _project_or_fail(_minimal_asset_paths([working_copy]))
    matches = [p for p in projections if p.path == working_copy]
    assert matches, (
        "project_generated_regions produced no projection for the marked "
        f"working copy {working_copy} under the import-module spy"
    )


# ---------------------------------------------------------------------------
# T5 -- check_generated_regions: stale before write, fresh after, stale
#       again after an on-disk mutation (DD-10 oracle, full round trip)
# ---------------------------------------------------------------------------


def test_check_generated_regions_flags_stale_fresh_then_stale_across_a_mutation(
    tmp_path: Path,
) -> None:
    """Oracle (feature-delta.md line 155): ``check_generated_regions``
    reports STALE when the on-disk file diverges from a re-render, clears
    once the fresh render is written, and reports STALE again if the
    on-disk region is mutated behind the projector's back."""
    working_copy = tmp_path / "des-command-catalog.md"
    prose = "# hand-authored lane guidance\n\nRun `des dispatch` for X.\n\n"
    working_copy.write_text(
        prose + _wrap_region("STALE-PLACEHOLDER") + "\n", encoding="utf-8"
    )
    asset_paths = _minimal_asset_paths([working_copy])

    projections_before = _project_or_fail(asset_paths)
    stale_before = docgen.check_generated_regions(_REPO_ROOT, projections_before)
    assert any(working_copy.name in s for s in stale_before), (
        "check_generated_regions must report the placeholder body as STALE "
        f"before any write -- got {stale_before!r}"
    )

    docgen.write_generated_regions(projections_before)

    projections_after = _project_or_fail(asset_paths)
    stale_after = docgen.check_generated_regions(_REPO_ROOT, projections_after)
    assert stale_after == [], (
        "a freshly written region must be reported FRESH (idempotent "
        f"re-render) -- check_generated_regions still reports {stale_after!r}"
    )

    on_disk = working_copy.read_text(encoding="utf-8")
    mutated = on_disk.replace("`loop`", "`LOOP-CORRUPTED`", 1)
    assert mutated != on_disk, (
        "fixture sanity: expected '`loop`' to appear exactly once in the "
        "freshly-rendered catalog table so the corruption is observable"
    )
    working_copy.write_text(mutated, encoding="utf-8")

    projections_mutated = _project_or_fail(asset_paths)
    stale_mutated = docgen.check_generated_regions(_REPO_ROOT, projections_mutated)
    assert any(working_copy.name in s for s in stale_mutated), (
        "check_generated_regions must NEVER report a hand-mutated region as "
        f"fresh -- got {stale_mutated!r} after corrupting one cell of the "
        "on-disk table"
    )


# ---------------------------------------------------------------------------
# T6 (NEGATIVE) -- re-render NEVER swallows the hand-authored lane prose
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_rerender_never_mutates_hand_authored_prose_outside_the_region(
    tmp_path: Path,
) -> None:
    """DD-10 scope boundary: the marker wraps ONLY the new verb table -- the
    curated "which lane" prose stays hand-authored and untouched. Re-render
    must NEVER alter a single byte outside the markers."""
    real_prose = _CATALOG_ASSET.read_text(encoding="utf-8")
    working_copy = tmp_path / "des-command-catalog.md"
    working_copy.write_text(
        real_prose + "\n" + _wrap_region("STALE") + "\n", encoding="utf-8"
    )

    projections = _project_or_fail(_minimal_asset_paths([working_copy]))
    matches = [p for p in projections if p.path == working_copy]
    assert matches, (
        "project_generated_regions produced no projection for the marked "
        f"working copy {working_copy}"
    )

    rendered = matches[0].projected_text
    assert rendered.startswith(real_prose), (
        "re-rendering the GENERATED region must NEVER alter the "
        "hand-authored prose preceding it -- the curated 'which lane' "
        "guidance must survive byte-for-byte outside the markers (DD-10 "
        "scope boundary) -- got a prefix mismatch.\n\n"
        f"--- expected prefix (real shipped prose) ---\n{real_prose[:200]}...\n\n"
        f"--- actual prefix of rendered text ---\n{rendered[: len(real_prose)][:200]}..."
    )


# ---------------------------------------------------------------------------
# T7 -- check_documentation_freshness.py:main() wires the 4th leg (DD-11)
# ---------------------------------------------------------------------------


def test_check_documentation_freshness_wires_the_generated_region_freshness_leg() -> (
    None
):
    """DD-11: ``check_documentation_freshness.py:main()`` must call BOTH
    ``docgen.project_generated_regions`` and ``docgen.check_generated_
    regions`` as its 4th freshness leg (alongside the existing 3: stale,
    disagreements, lane_drift) -- verified structurally via ``ast`` rather
    than by import (the hook self-bootstraps ``docgen`` by file path and is
    not safely importable at collection time under a bare interpreter)."""
    freshness_path = (
        _REPO_ROOT / "scripts" / "hooks" / "check_documentation_freshness.py"
    )
    tree = ast.parse(
        freshness_path.read_text(encoding="utf-8"), filename=str(freshness_path)
    )
    main_fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ),
        None,
    )
    assert main_fn is not None, f"expected a top-level main() in {freshness_path}"

    called_attrs = {
        node.func.attr
        for node in ast.walk(main_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "docgen"
    }
    required = {"project_generated_regions", "check_generated_regions"}
    missing = required - called_attrs
    assert not missing, (
        "check_documentation_freshness.py:main() must call docgen."
        "project_generated_regions AND docgen.check_generated_regions as "
        f"its 4th freshness leg (DD-11) -- missing {sorted(missing)}; "
        f"docgen.* calls found in main(): {sorted(called_attrs)}"
    )
