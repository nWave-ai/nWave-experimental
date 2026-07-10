"""Regression AT for bug #46 -- redundant hand-maintained `== 60` total-count pins.

RCA verdict: `catalog_steps/steps_catalog.py:124,127` and
`catalog_steps/steps_slice_02.py:171` hardcode an expected TOTAL catalog-size
literal (`== 60`) that a maintainer must hand-bump on every catalog addition
(operator-cost, GDP-5). The pins are REDUNDANT: the same coverage is already
provided (a) by the scale-invariant subset checks
`then_catalog_subset`/`then_registry_subset` (steps_catalog.py:132-141) and (b)
by the already-shipped `compute_catalog_coherence()`
(`src/des/cli/verify_catalog_coherence.py`, stdlib-only, named
symmetric-difference drift sets).

Charter: docs/product/expectations/fix-catalog-count-pin-derived/
         adding-a-gate-goes-green-without-hunting-a-magic-count.md

This AT witnesses:
  1. The DEFECT itself (structural) -- a size-driven `== <catalog_size>` total
     pin still exists in the two step files. RED now; GREEN once the fix
     retires the three redundant assertions.
  2. The COVERAGE THAT MUST SURVIVE the retirement -- `compute_catalog_coherence`
     stays correct on (a) a well-formed, in-sync fixture set at any scale
     (positive, scale-invariant) and (b) a fixture set carrying a KNOWN
     injected drift, named by id, never silently swallowed (negative oracle).
  3. The degrade-LOUD floor -- a malformed catalog (unparsable / no `gates:`
     block / zero gate_id entries) never produces a false green.

Out of scope (per RCA, do NOT touch): the two `@regression-pin`-tagged
semantic pins -- `language_neutral_contract:false count == 2` and the
`carpaccio-slice-gate` byte-for-byte field-check. Neither is size-driven;
both stay as-is.

Driving surface: `des.cli.verify_catalog_coherence.compute_catalog_coherence`
(production, stdlib-only, already shipped) over synthetic fixture repo trees
built under `tmp_path` -- never internal introspection of its regex
constants (Mandate-13). `CoherenceComposition` wraps the call so test bodies
stay thin, mirroring the `CatalogComposition`/`PerGateComposition` precedent
already established in this directory (Mandate-12).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from des.cli.verify_catalog_coherence import (
    CatalogMalformedError,
    CoherenceResult,
    compute_catalog_coherence,
)


# ---------------------------------------------------------------------------
# Composition root (Mandate-12/13: step/test bodies stay thin, delegate here)
# ---------------------------------------------------------------------------


class CoherenceComposition:
    """Wraps `compute_catalog_coherence` over a fixture repo tree."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._result: CoherenceResult | None = None
        self._malformed_error: CatalogMalformedError | None = None

    def compute(self) -> None:
        try:
            self._result = compute_catalog_coherence(self._repo_root)
        except CatalogMalformedError as exc:
            self._malformed_error = exc

    @property
    def result(self) -> CoherenceResult | None:
        return self._result

    @property
    def malformed_error(self) -> CatalogMalformedError | None:
        return self._malformed_error


# ---------------------------------------------------------------------------
# Fixture repo builder -- registry (.py, regex-parsed) + catalog + per-gate
# files (.yaml, regex-parsed), never a real production checkout.
# ---------------------------------------------------------------------------


def _write_fixture_repo(
    tmp_path: Path,
    *,
    registry_ids: tuple[str, ...] = (),
    catalog_ids: tuple[str, ...] | None = None,
    catalog_text: str | None = None,
    per_gate_ids: tuple[str, ...] = (),
) -> Path:
    repo = tmp_path / "fixture-repo"
    cli_dir = repo / "src" / "des" / "cli"
    cli_dir.mkdir(parents=True)
    registry_rows = "\n".join(
        f'    _SubcommandRow("{gid}", module="x", entry_function="main"),'
        for gid in registry_ids
    )
    (cli_dir / "__main__.py").write_text(f"_REGISTRY = (\n{registry_rows}\n)\n")

    gates_dir = repo / "nWave" / "gates"
    gates_dir.mkdir(parents=True)
    if catalog_text is None:
        catalog_rows = "\n".join(f'  - gate_id: "{gid}"' for gid in (catalog_ids or ()))
        catalog_text = f"gates:\n{catalog_rows}\n"
    (gates_dir / "_catalog.yaml").write_text(catalog_text)

    for gid in per_gate_ids:
        (gates_dir / f"{gid}.yaml").write_text(f"gate_id: {gid}\n")

    return repo


# ---------------------------------------------------------------------------
# 1. THE DEFECT -- structural: no size-driven total-count literal survives
#    in the two step files. RED now (the `== 60` pins exist); GREEN once
#    the fix retires them and replaces pin C with compute_catalog_coherence.
# ---------------------------------------------------------------------------

_STEPS_DIR = Path(__file__).parent / "catalog_steps"
_STEPS_CATALOG_PY = _STEPS_DIR / "steps_catalog.py"
_STEPS_SLICE_02_PY = _STEPS_DIR / "steps_slice_02.py"

# Scoped to the three known redundant pins only -- must NEVER also flag the
# `@regression-pin` semantic pins (language_neutral_contract count == 2,
# the carpaccio-slice-gate field-check), which are out of scope and stay.
_SIZE_DRIVEN_TOTAL_PIN_RE = re.compile(
    r"(?:len\(composition\.(?:catalog_gate_ids|registry_names)\)"
    r"|per_gate_comp\.file_count)\s*==\s*\d+"
)


def test_step_files_never_pin_a_size_driven_total_count_literal() -> None:
    """No `len(composition.catalog_gate_ids/registry_names) == N` or
    `per_gate_comp.file_count == N` literal survives in the two step files.

    RED now: steps_catalog.py:124,127 and steps_slice_02.py:171 each still
    carry one such pin (`== 60`) -- the exact operator-cost defect from the
    RCA. GREEN once the fix retires them (replaced by the scale-invariant
    subset checks + compute_catalog_coherence's named drift sets).
    """
    offenders: dict[str, list[str]] = {}
    for path in (_STEPS_CATALOG_PY, _STEPS_SLICE_02_PY):
        found = _SIZE_DRIVEN_TOTAL_PIN_RE.findall(path.read_text(encoding="utf-8"))
        if found:
            offenders[str(path)] = found

    assert offenders == {}, (
        f"size-driven total-count literal(s) still hand-pinned: {offenders} "
        "-- retire the `== <catalog_size>` assertion, keep the scale-invariant "
        "subset checks, and replace the per-gate-file count pin with "
        "compute_catalog_coherence's named drift sets."
    )


# ---------------------------------------------------------------------------
# 2a. Coverage that must survive -- positive: a well-formed, in-sync fixture
#     set at any scale is coherent with empty drift sets. Already GREEN
#     today (compute_catalog_coherence is already shipped) -- this pins the
#     behaviour the retirement in (1) depends on, so it can never regress.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry_count", [1, 3, 10, 50])
def test_well_formed_in_sync_catalog_is_coherent_with_empty_drift_sets(
    tmp_path: Path, entry_count: int
) -> None:
    """A maintainer adding N well-formed, 1:1-wired gates never trips a count
    pin -- coherent at ANY scale, no total literal anywhere in this path."""
    ids = tuple(f"gate-{i}" for i in range(entry_count))
    repo = _write_fixture_repo(
        tmp_path, registry_ids=ids, catalog_ids=ids, per_gate_ids=ids
    )

    comp = CoherenceComposition(repo)
    comp.compute()

    assert comp.malformed_error is None
    result = comp.result
    assert result is not None
    assert result.coherent is True
    assert result.registry_not_in_catalog == ()
    assert result.catalog_not_in_registry == ()
    assert result.catalog_without_per_gate_file == ()
    assert result.per_gate_without_catalog_entry == ()


# ---------------------------------------------------------------------------
# 2b. Coverage that must survive -- negative oracle: a real drift (one id
#     out of sync in exactly one of the three surfaces) is caught and NAMED
#     by id, never swallowed just because no count literal needed editing.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "drift_kind",
    [
        "catalog_without_per_gate_file",
        "per_gate_without_catalog_entry",
        "registry_not_in_catalog",
        "catalog_not_in_registry",
    ],
)
def test_injected_drift_is_named_by_id_never_silently_swallowed(
    tmp_path: Path, drift_kind: str
) -> None:
    """One id out of sync in exactly one surface -> caught, named, never
    hidden by an unrelated total-count literal happening to still match."""
    base = ("gate-a", "gate-b", "gate-c")
    drifted = "gate-drifted"

    registry_ids = base
    catalog_ids = base
    per_gate_ids = base

    if drift_kind == "catalog_without_per_gate_file":
        # Catalog row exists, its per-gate file was forgotten.
        registry_ids = (*base, drifted)
        catalog_ids = (*base, drifted)
    elif drift_kind == "per_gate_without_catalog_entry":
        # Per-gate file exists, no catalog row references it.
        per_gate_ids = (*base, drifted)
    elif drift_kind == "registry_not_in_catalog":
        # Wired in the CLI registry, never reconciled into the catalog.
        registry_ids = (*base, drifted)
    elif drift_kind == "catalog_not_in_registry":
        # Catalog row exists, no CLI registry entry backs it.
        catalog_ids = (*base, drifted)
        per_gate_ids = (*base, drifted)

    repo = _write_fixture_repo(
        tmp_path,
        registry_ids=registry_ids,
        catalog_ids=catalog_ids,
        per_gate_ids=per_gate_ids,
    )

    comp = CoherenceComposition(repo)
    comp.compute()

    assert comp.malformed_error is None
    result = comp.result
    assert result is not None
    assert result.coherent is False
    assert drifted in getattr(result, drift_kind), (
        f"expected {drifted!r} named in {drift_kind}, got "
        f"{getattr(result, drift_kind)!r}"
    )
    # The other three drift dimensions must stay empty -- the oracle names
    # the SPECIFIC drift, it does not turn every set red.
    all_drift_fields = (
        "registry_not_in_catalog",
        "catalog_not_in_registry",
        "catalog_without_per_gate_file",
        "per_gate_without_catalog_entry",
    )
    for field in all_drift_fields:
        if field == drift_kind:
            continue
        assert getattr(result, field) == (), (
            f"unrelated drift field {field} unexpectedly non-empty: "
            f"{getattr(result, field)!r}"
        )


# ---------------------------------------------------------------------------
# 3. Degrade-LOUD floor -- a malformed catalog is never a false green.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "malformed_catalog_text",
    [
        pytest.param("gate_catalog_has_no_gates_key: true\n", id="no-gates-block"),
        pytest.param("gates:\n  - name: not-a-gate-id-field\n", id="zero-gate-ids"),
        pytest.param("", id="empty-file"),
    ],
)
def test_malformed_catalog_never_degrades_silently(
    tmp_path: Path, malformed_catalog_text: str
) -> None:
    """A structurally malformed `_catalog.yaml` raises `CatalogMalformedError`
    -- it is never quietly skipped/ignored to produce a false green."""
    repo = _write_fixture_repo(
        tmp_path,
        registry_ids=("gate-a",),
        catalog_text=malformed_catalog_text,
        per_gate_ids=("gate-a",),
    )

    comp = CoherenceComposition(repo)
    comp.compute()

    assert comp.result is None
    assert comp.malformed_error is not None
    assert isinstance(comp.malformed_error, CatalogMalformedError)
