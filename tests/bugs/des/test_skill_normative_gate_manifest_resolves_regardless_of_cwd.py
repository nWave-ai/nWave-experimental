"""Regression: a bare `des skill-normative-gate` must never validate a tree
the operator is not in -- neither by resolving against an accidental CWD, nor
by silently answering from the installed copy.

Two defects, one after the other, on the same line of code. This file pins
both, because the second was introduced by the fix for the first.

ROUND 1 (original): `_DEFAULT_MANIFEST = Path("nWave/data/skill-normative-
clauses.json")` was a bare RELATIVE path, resolved lazily against `Path.cwd()`
at read time. The gate found its manifest only when the caller's CWD happened
to be the checkout root -- true in CI and in a maintainer's habitual shell,
false from a sibling worktree or a packaged install.

ROUND 2 (introduced by round 1's fix): the fix anchored the default to the
PACKAGE -- `Path(__file__).resolve().parents[3] / "nWave" / ...`. That is
CWD-independent, which was the point, but under the installed shim
`Path(__file__)` is the INSTALLED package, so the gate read the installed
manifest (9 clauses on this machine) while `--root` defaulted to the operator's
repo (12 clauses). A clause that exists only in the repo was not checked at
all: perturbing its marker with a string absent from every skill still printed
`PASS: 0 failing clauses`. The gate announced `developer checkout detected via
.git adjacency at '<the worktree>'` on the very same run -- it had the
information and read elsewhere anyway.

ROUND 3 (current): which tree to read is DECIDED at run time by
`des.runtime.packaged_asset.resolve_packaged_asset`, and the decision is
printed. When a developer checkout carries its own copy that DIFFERS from the
installed one, the gate refuses INDETERMINATE naming both paths instead of
picking one. When the two agree, or only one exists, there is no ambiguity and
it resolves silently -- refusing there would be ceremony charged for nothing.

These tests therefore pin the PROPERTY (a bare invocation from a hostile CWD
still finds the shipped manifest, anchored to the package and never to the
accidental CWD) rather than the SHAPE (`_DEFAULT_MANIFEST` being an absolute
module-level constant) -- pinning the shape is what let round 2 land while the
suite stayed green.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from des.cli import skill_normative_gate as gate_module
from des.runtime.packaged_asset import (
    AssetOrigin,
    installed_package_root,
    resolve_packaged_asset,
)


_MANIFEST_RELATIVE = "nWave/data/skill-normative-clauses.json"


def _real_shipped_manifest() -> Path:
    """The manifest the gate MUST find, independent of CWD -- resolved here
    via the test file's OWN package position (`tests/bugs/des/` sits at the
    same `parents[3]`-to-repo-root depth as `src/des/cli/`), never by asking
    the module under test to name its own expectation."""
    return (
        Path(__file__).resolve().parents[3]
        / "nWave"
        / "data"
        / "skill-normative-clauses.json"
    )


@pytest.mark.negative_at
def test_bare_invocation_resolves_the_shipped_manifest_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 1 pinned: from a CWD with no `nWave/` tree, the gate still finds
    its own shipped manifest -- by PACKAGE location, never by accidental CWD."""
    monkeypatch.chdir(tmp_path)  # a CWD with no `nWave/` tree at all
    importlib.reload(gate_module)

    resolution = resolve_packaged_asset(_MANIFEST_RELATIVE, start=tmp_path)

    assert resolution.installed.is_absolute(), (
        f"the shipped-asset anchor is {resolution.installed!r} -- a relative "
        "path resolved lazily against whatever CWD happens to be active, "
        "instead of being anchored to the package location"
    )
    assert resolution.is_usable, (
        f"from CWD={tmp_path}, a directory with no `nWave/` tree at all, the "
        f"gate could not resolve its own shipped manifest: {resolution.detail}"
    )
    assert resolution.path == _real_shipped_manifest(), (
        f"resolved to {resolution.path!r}, expected the shipped asset at "
        f"{_real_shipped_manifest()!r}"
    )


@pytest.mark.negative_at
def test_shipped_anchor_matches_sibling_consumer_of_the_same_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin parity with the CWD-independent sibling: the gate's shipped-asset
    anchor and `coverage_map_verify_service`'s own default must land in the
    SAME `nWave/data/` directory from the SAME hostile CWD -- they ship next to
    the same package, so an outlier resolving differently is the defect."""
    monkeypatch.chdir(tmp_path)
    importlib.reload(gate_module)

    from des.application import coverage_map_verify_service as sibling_module

    sibling_default = sibling_module._default_omission_classes_path()
    anchored = installed_package_root() / _MANIFEST_RELATIVE

    assert anchored.parent == sibling_default.parent, (
        f"the gate's shipped anchor resolved to {anchored!r}, but the sibling "
        f"consumer of the SAME shipped tree resolved to {sibling_default!r} -- "
        "both should agree on the `nWave/data/` directory regardless of CWD"
    )


@pytest.mark.negative_at
def test_two_disagreeing_copies_are_refused_instead_of_silently_picked(
    tmp_path: Path,
) -> None:
    """Round 2 pinned: the exact state that printed `PASS: 0 failing clauses`.

    A developer checkout whose copy DIFFERS from the installed one must yield
    AMBIGUOUS -- the gate names both paths and validates neither.
    """
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    asset = checkout / _MANIFEST_RELATIVE
    asset.parent.mkdir(parents=True)
    asset.write_text('{"clauses": []}', encoding="utf-8")

    resolution = resolve_packaged_asset(_MANIFEST_RELATIVE, start=checkout)

    assert resolution.origin is AssetOrigin.AMBIGUOUS, (
        "a checkout copy that differs from the installed copy resolved to "
        f"{resolution.origin} instead of being refused: {resolution.detail}"
    )
    assert resolution.path is None, "an ambiguous resolution must name no path"


def test_identical_copies_resolve_without_ceremony(tmp_path: Path) -> None:
    """The `differs` test is load-bearing: when the two copies agree there is
    no ambiguity, and refusing would charge the operator for nothing."""
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    asset = checkout / _MANIFEST_RELATIVE
    asset.parent.mkdir(parents=True)
    asset.write_bytes(_real_shipped_manifest().read_bytes())

    resolution = resolve_packaged_asset(_MANIFEST_RELATIVE, start=checkout)

    assert resolution.origin is AssetOrigin.REPO
    assert resolution.is_usable


def test_explicit_manifest_argument_still_overrides_default_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sibling-branch pin (never flatten a fix into the wrong branch): an
    explicit `--manifest PATH` must keep overriding the default correctly
    from a hostile CWD -- fixing the default must not disturb this already-
    correct, unrelated branch of the same parser."""
    monkeypatch.chdir(tmp_path)
    importlib.reload(gate_module)

    explicit = tmp_path / "custom-manifest.json"
    explicit.write_text("{}", encoding="utf-8")

    parser = gate_module._build_parser()
    args = parser.parse_args(["--manifest", str(explicit)])

    assert args.manifest == explicit, (
        f"explicit --manifest override resolved to {args.manifest!r}, "
        f"expected the literal path passed on the command line {explicit!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
