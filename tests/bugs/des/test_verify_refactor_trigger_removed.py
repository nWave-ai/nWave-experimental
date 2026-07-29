"""Regression AT: ``des verify-refactor-trigger`` is REMOVED from every
public des surface (mikado D24; evolution-plan P1.3 WITHDRAWN;
human-authorized by Ale 2026-07-29).

Charter: docs/product/expectations/remove-verify-refactor-trigger/
         the-signal-driven-refactor-trigger-is-gone-from-every-des-surface.md
Feature-delta: docs/feature/remove-verify-refactor-trigger/feature-delta.md

Not a behaviour-preserving refactor (feature-delta): ``des --help``, the
argparse ``invalid choice`` valid-set, and the shipped orchestrator-affordance
catalog all printed the command before this change -- so the oracle below
pins the AFTER state (the command gone) rather than a before/after-equal
green-before/green-after exemption.

Driving surfaces (Mandate-16 driving-port-only -- NEVER imports the doomed
module ``des.cli.verify_refactor_trigger``, which is exactly what this AT
proves is gone):

  1. The CLI registry SOURCE FILE ``src/des/cli/__main__.py``, read as text
     (never imported) -- mirrors the existing reuse-first precedent
     ``des.cli.verify_catalog_coherence._parse_registry_names``.
  2. ``des.cli.verify_catalog_coherence.compute_catalog_coherence`` -- the
     EXISTING three-way registry<->catalog<->per-gate-file comparator
     (feature-delta Reuse Analysis: "EXTEND ... no new gate is written for
     this removal"). Driven, not reimplemented: this AT parses zero YAML
     itself.
  3. The generated orchestrator-affordance catalog markdown
     ``nWave/data/orchestrator-affordance/des-command-catalog.md``, read as
     text (GENERATED region, docgen output -- never hand-edited, but a
     public surface an operator reads).
  4. The filesystem presence/absence of the per-gate contract file
     ``nWave/gates/verify-refactor-trigger.yaml`` and the doomed module file
     ``src/des/cli/verify_refactor_trigger.py``.

RED today (current tree): the command still exists on all four surfaces --
every POSITIVE (removal) assertion below fails with a semantic
``AssertionError`` naming the surface that still advertises it. GREEN once
the removal (module delete + registry/catalog/per-gate-file shrink + docgen
re-render) lands. The NEGATIVE arm (survivor coherence) is already GREEN
today and must STAY green after the removal -- it is what stops a vacuous
green from someone deleting the whole neighbourhood instead of just this one
command.

Stdlib + pytest only. No git, no network, no subprocess -- runs on any
Python-only target machine (genericity/agnosticism mandate).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.verify_catalog_coherence import compute_catalog_coherence


# tests/bugs/des/<this file> -> parents[2] = repo root
# (tests/bugs/des/test_x.py: parents[0]=des, [1]=bugs, [2]=tests, [3]=repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]

_DOOMED_GATE_ID = "verify-refactor-trigger"
_DOOMED_MODULE_PATH = "des.cli.verify_refactor_trigger"
_DOOMED_MODULE_FILE = _REPO_ROOT / "src" / "des" / "cli" / "verify_refactor_trigger.py"
_DOOMED_PER_GATE_FILE = _REPO_ROOT / "nWave" / "gates" / f"{_DOOMED_GATE_ID}.yaml"
_MAIN_PY = _REPO_ROOT / "src" / "des" / "cli" / "__main__.py"
_AFFORDANCE_CATALOG_MD = (
    _REPO_ROOT / "nWave" / "data" / "orchestrator-affordance" / "des-command-catalog.md"
)

# Survivors -- neighbouring gates the removal must NOT gut. Each must still be
# declared coherently in ALL THREE of registry / catalog / per-gate-file, AND
# still be advertised in the generated affordance catalog.
_SURVIVOR_GATE_IDS = (
    "verify-catalog-coherence",
    "verify-red-green",
    "verify-negative-at",
    "verify-doc-coherence",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover -- defensive, not the RED path
        raise AssertionError(
            f"WHAT: could not read {path}. "
            f"WHY: this AT needs the file to exist and be readable to assert "
            f"on its content ({exc}). "
            f"HOW: confirm {path} is present in this checkout -- if this file "
            "itself was deleted, the removal went further than the "
            "feature-delta's [REF] Component decomposition table specifies."
        ) from exc


# ===========================================================================
# 1. POSITIVE (removal) arm -- RED today, GREEN once the command is gone.
#    One row per public surface the feature-delta names.
# ===========================================================================


@pytest.mark.parametrize(
    "surface_name,path,forbidden_needles",
    [
        pytest.param(
            "CLI registry source",
            _MAIN_PY,
            (
                f'"{_DOOMED_GATE_ID}"',
                _DOOMED_MODULE_PATH,
            ),
            id="registry-no-subcommand-row",
        ),
        pytest.param(
            "orchestrator-affordance catalog (generated)",
            _AFFORDANCE_CATALOG_MD,
            (
                f"`{_DOOMED_GATE_ID}`",
                _DOOMED_MODULE_PATH,
            ),
            id="affordance-catalog-no-row",
        ),
    ],
)
def test_surface_no_longer_advertises_the_doomed_command(
    surface_name: str, path: Path, forbidden_needles: tuple[str, ...]
) -> None:
    """WHAT: `verify-refactor-trigger` / `des.cli.verify_refactor_trigger`
    must not appear on this public surface.
    WHY: mikado D24 removed the command; a surviving reference means the
    removal is incomplete and the surface still lies about what `des` can do.
    HOW: finish the [REF] Component decomposition row for this surface
    (registry: drop the `_SubcommandRow`; affordance catalog: re-render via
    `scripts/docgen.py` after the registry/catalog shrink).
    CONTRACT_SHAPE: bounded-change
    """
    # covers: R1
    # covers: R2
    text = _read(path)
    for needle in forbidden_needles:
        assert needle not in text, (
            f"WHAT: {surface_name} ({path}) still contains {needle!r}. "
            f"WHY: `des verify-refactor-trigger` was removed by mikado D24 -- "
            "no public surface may still advertise it. "
            f"HOW: finish the feature-delta's [REF] Component decomposition "
            f"row for {surface_name!r} (drop the row / re-render the "
            "generated catalog via `scripts/docgen.py`)."
        )


def test_doomed_module_file_is_absent() -> None:
    """WHAT: `src/des/cli/verify_refactor_trigger.py` must not exist.
    WHY: the feature-delta's [REF] Component decomposition marks it DELETE
    -- 698 lines, zero executing consumers besides its own (also-deleted)
    unit test.
    HOW: `rm src/des/cli/verify_refactor_trigger.py` (and its unit pins
    `tests/des/unit/cli/test_verify_refactor_trigger.py`) in the same commit
    as the registry/catalog/per-gate-file shrink (@coupled slice-01).
    CONTRACT_SHAPE: bounded-change
    """
    # covers: R3
    assert not _DOOMED_MODULE_FILE.exists(), (
        f"WHAT: {_DOOMED_MODULE_FILE} still exists on disk. "
        "WHY: the feature-delta's [REF] Component decomposition marks this "
        "module DELETE -- it must not survive the removal. "
        f"HOW: delete {_DOOMED_MODULE_FILE}."
    )


def test_doomed_per_gate_file_is_absent() -> None:
    """WHAT: `nWave/gates/verify-refactor-trigger.yaml` must not exist.
    WHY: keeps registry/catalog/per-gate-file 1:1 -- a per-gate file with no
    catalog row (or vice versa) is exactly the drift class
    `des verify-catalog-coherence` exists to catch.
    HOW: delete `nWave/gates/verify-refactor-trigger.yaml` alongside the
    catalog row it backs.
    CONTRACT_SHAPE: bounded-change
    """
    # covers: R4
    assert not _DOOMED_PER_GATE_FILE.exists(), (
        f"WHAT: {_DOOMED_PER_GATE_FILE} still exists on disk. "
        "WHY: the feature-delta's [REF] Component decomposition marks the "
        "per-gate contract file DELETE, in lockstep with the catalog row "
        "and registry row. "
        f"HOW: delete {_DOOMED_PER_GATE_FILE}."
    )


def test_doomed_gate_id_absent_from_three_way_coherence_sets() -> None:
    """WHAT: `compute_catalog_coherence` must report the doomed gate_id in
    NONE of its three parsed sets (registry / catalog / per-gate-file).
    WHY: driving the assertion through the EXISTING coherence comparator
    (feature-delta Reuse Analysis: EXTEND, no new gate written) proves the
    removal from all three declarations at once, without this AT
    reimplementing YAML/registry parsing itself.
    HOW: see the per-surface tests above -- each names the concrete file/row
    to drop.
    CONTRACT_SHAPE: bounded-change
    """
    # covers: R5
    result = compute_catalog_coherence(_REPO_ROOT)
    assert _DOOMED_GATE_ID not in result.registry_names, (
        f"WHAT: {_DOOMED_GATE_ID!r} is still present in the CLI registry "
        f"names set {sorted(result.registry_names)!r} (via "
        "compute_catalog_coherence). WHY: mikado D24 removed this command. "
        f'HOW: drop the `_SubcommandRow("{_DOOMED_GATE_ID}", ...)` row '
        "from src/des/cli/__main__.py _REGISTRY."
    )
    assert _DOOMED_GATE_ID not in result.catalog_gate_ids, (
        f"WHAT: {_DOOMED_GATE_ID!r} is still present in the catalog "
        f"gate_ids set {sorted(result.catalog_gate_ids)!r}. "
        "WHY: mikado D24 removed this command. "
        f"HOW: drop the `gate_id: {_DOOMED_GATE_ID}` block from "
        "nWave/gates/_catalog.yaml."
    )
    assert _DOOMED_GATE_ID not in result.per_gate_stems, (
        f"WHAT: {_DOOMED_GATE_ID!r} is still present in the per-gate-file "
        f"stems set {sorted(result.per_gate_stems)!r}. "
        "WHY: mikado D24 removed this command. "
        f"HOW: delete nWave/gates/{_DOOMED_GATE_ID}.yaml."
    )


# ===========================================================================
# 2. NEGATIVE arm -- survivor coherence. Stops a vacuous green from a
#    removal that gutted the whole neighbourhood instead of one command.
#    Already GREEN today; must STAY green after the removal.
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize("survivor_gate_id", _SURVIVOR_GATE_IDS)
def test_survivor_gate_still_declared_coherently_in_all_three_places(
    survivor_gate_id: str,
) -> None:
    """WHAT: each neighbouring gate must still appear in ALL THREE of the
    registry, the catalog, and its own per-gate file after this removal.
    WHY: the removal is scoped to exactly ONE command (`verify-refactor-
    trigger`) -- a fix that accidentally deletes a wider block, or a
    catalog/registry edit that drops an unrelated neighbour, must be
    caught here rather than shipping silently. This is the oracle that
    would fail if someone "cleaned up" the whole catalog section instead
    of the one targeted block.
    HOW: restore the dropped survivor's row/file -- it was never part of
    this feature-delta's [REF] Component decomposition table.
    CONTRACT_SHAPE: unbounded-preservation
    """
    # covers: R7
    result = compute_catalog_coherence(_REPO_ROOT)
    assert survivor_gate_id in result.registry_names, (
        f"WHAT: survivor gate {survivor_gate_id!r} is MISSING from the CLI "
        "registry names set after the removal. "
        "WHY: this removal is scoped to `verify-refactor-trigger` only -- "
        f"{survivor_gate_id!r} must be untouched. "
        f'HOW: restore its `_SubcommandRow("{survivor_gate_id}", ...)` '
        "row in src/des/cli/__main__.py _REGISTRY."
    )
    assert survivor_gate_id in result.catalog_gate_ids, (
        f"WHAT: survivor gate {survivor_gate_id!r} is MISSING from the "
        "catalog gate_ids set after the removal. "
        f"WHY: this removal is scoped to `verify-refactor-trigger` only -- "
        f"{survivor_gate_id!r} must be untouched. "
        f"HOW: restore its `gate_id: {survivor_gate_id}` block in "
        "nWave/gates/_catalog.yaml."
    )
    assert survivor_gate_id in result.per_gate_stems, (
        f"WHAT: survivor gate {survivor_gate_id!r} is MISSING from the "
        "per-gate-file stems set after the removal. "
        f"WHY: this removal is scoped to `verify-refactor-trigger` only -- "
        f"{survivor_gate_id!r} must be untouched. "
        f"HOW: restore nWave/gates/{survivor_gate_id}.yaml."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("survivor_gate_id", _SURVIVOR_GATE_IDS)
def test_survivor_still_advertised_in_affordance_catalog(
    survivor_gate_id: str,
) -> None:
    """WHAT: each survivor's backtick-quoted command name must still appear
    in the generated orchestrator-affordance catalog markdown.
    WHY: the affordance catalog is docgen-rendered FROM the registry/gate
    catalog -- a re-render that drops a survivor row (rather than only the
    doomed one) is a regression this removal must not introduce.
    HOW: re-run `scripts/docgen.py` against the post-removal registry/
    catalog and confirm the survivor's row reappears; if it doesn't, the
    registry/catalog edit dropped more than the [REF] Component
    decomposition table specifies.
    CONTRACT_SHAPE: unbounded-preservation
    """
    # covers: R8
    text = _read(_AFFORDANCE_CATALOG_MD)
    assert f"`{survivor_gate_id}`" in text, (
        f"WHAT: survivor command `{survivor_gate_id}` is MISSING from "
        f"{_AFFORDANCE_CATALOG_MD}. "
        "WHY: this removal is scoped to `verify-refactor-trigger` only -- "
        f"`{survivor_gate_id}` must still be advertised there. "
        "HOW: re-render the affordance catalog via `scripts/docgen.py` "
        "against the post-removal registry/catalog."
    )


def test_three_way_coherence_result_is_coherent_after_the_removal() -> None:
    """WHAT: `compute_catalog_coherence(repo_root).coherent` must be True.
    WHY: the removal's own acceptance bar (feature-delta [REF] Architecture
    & Contract Tests: "three-way symmetric difference is empty ... exit 0")
    -- proves the removal did not merely drop the doomed gate_id from one
    of the three sets while leaving a dangling reference in another
    (registry-only-drop, catalog-only-drop, or an orphaned per-gate file
    are all drift the coherence gate would otherwise report).
    HOW: run `des verify-catalog-coherence --repo-root .` locally -- its
    JSON verdict names the exact drifting id(s) and the concrete row/file
    to add or remove.
    CONTRACT_SHAPE: unbounded-preservation
    """
    # covers: R6
    result = compute_catalog_coherence(_REPO_ROOT)
    assert result.coherent, (
        "WHAT: the registry/catalog/per-gate-file three-way comparison is "
        f"NOT coherent -- drifting ids: {result.drifting_ids!r}. "
        "WHY: the removal's own acceptance bar requires the three-way "
        "symmetric difference to be empty (feature-delta [REF] "
        "Architecture & Contract Tests). "
        "HOW: run `des verify-catalog-coherence --repo-root .` for the "
        "per-id HOW guidance, or re-check this removal's [REF] Component "
        "decomposition table -- one of the three declarations "
        "(registry row / catalog row / per-gate file) was dropped without "
        "its siblings."
    )
