"""Regression: `--manifest`'s default resolves against the invoking process's
CWD, not against the shipped package tree -- the one outlier among the several
consumers of the same `nWave/data/` asset directory.

OBSERVED: `_DEFAULT_MANIFEST = Path("nWave/data/skill-normative-clauses.json")`
(`src/des/cli/skill_normative_gate.py:42`) is a bare relative `Path`, used
directly as the `--manifest` argparse default (line 50). A relative `Path` is
never resolved at construction time -- it is resolved lazily, against
`Path.cwd()`, the moment something calls `.exists()` / `.read_text()` on it
(here: `SkillCorpusReader.read_manifest`, `manifest_path.read_text(...)`). So
`des skill-normative-gate` (with no explicit `--manifest`) finds its own
manifest only when the caller's CWD happens to already be the checkout root --
true in CI and in a maintainer's habitual shell, false for a sibling worktree,
a packaged install, or any other invoker.

Every OTHER consumer of the SAME shipped `nWave/data/` tree resolves relative
to the PACKAGE instead, via `Path(__file__).resolve().parents[N]`:
  - `coverage_map_verify_service._default_omission_classes_path`
    (`parents[3]` from `src/des/application/...`)
  - `session_start_handler.py` / `carpaccio_intercept.py` (`parents[5]`)
This file is the one outlier -- CWD-dependent where every sibling is
CWD-independent by construction.

THE FIX (not yet applied -- this test pins the pre-fix RED and the post-fix
GREEN in one assertion set):
    _DEFAULT_MANIFEST = (
        Path(__file__).resolve().parents[3]
        / "nWave" / "data" / "skill-normative-clauses.json"
    )

DRIVING SURFACE (Mandate 16, no direct domain testing): the defect lives in a
module-level constant consumed by the real `_build_parser()` / `main()`
composition root of `des skill-normative-gate` -- the same driving port the
CLI dispatcher invokes. This test exercises that constant + parser exactly as
`main()` does, from a hostile CWD, rather than re-deriving the resolution
logic by hand.

RED-for-right-reason: `test_default_manifest_resolves_to_shipped_asset_regardless_of_cwd`
fails with a plain `AssertionError` -- `resolved.is_absolute()` is `False` (a
relative `Path` object) and `resolved.exists()` is `False` (nothing at that
relative path under a CWD with no `nWave/` tree). Neither fails on
import/collection.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from des.cli import skill_normative_gate as gate_module


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
def test_default_manifest_resolves_to_shipped_asset_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_DEFAULT_MANIFEST` must name the shipped manifest by PACKAGE location,
    never by a path relative to the invoking process's CWD."""
    monkeypatch.chdir(tmp_path)  # a CWD with no `nWave/` tree at all
    importlib.reload(gate_module)

    resolved = gate_module._DEFAULT_MANIFEST

    assert resolved.is_absolute(), (
        f"_DEFAULT_MANIFEST is {resolved!r} -- a bare relative Path that is "
        "resolved lazily against whatever CWD happens to be active when it "
        "is later read (argparse default -> SkillCorpusReader.read_manifest "
        "-> .read_text()), instead of being anchored to the package location "
        "the way every sibling consumer of nWave/data/ is"
    )
    assert resolved.exists(), (
        f"_DEFAULT_MANIFEST resolved to {resolved!r} from CWD={tmp_path}, a "
        "directory with no `nWave/` tree at all -- `des skill-normative-gate` "
        "invoked without an explicit --manifest cannot find its own shipped "
        "manifest unless the caller's CWD happens to already be the checkout "
        "root"
    )
    assert resolved == _real_shipped_manifest(), (
        f"_DEFAULT_MANIFEST resolved to {resolved!r}, expected the shipped "
        f"asset at {_real_shipped_manifest()!r}"
    )


@pytest.mark.negative_at
def test_default_manifest_matches_sibling_consumer_of_the_same_shipped_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin parity with the CWD-independent sibling: both `_DEFAULT_MANIFEST`
    and `coverage_map_verify_service`'s own shipped-asset default must resolve
    into the SAME `nWave/data/` directory, from the SAME hostile CWD -- they
    ship next to the same package, so an outlier resolving differently is
    exactly the defect this AT pins."""
    monkeypatch.chdir(tmp_path)
    importlib.reload(gate_module)

    from des.application import coverage_map_verify_service as sibling_module

    sibling_default = sibling_module._default_omission_classes_path()

    assert gate_module._DEFAULT_MANIFEST.parent == sibling_default.parent, (
        f"_DEFAULT_MANIFEST resolved to {gate_module._DEFAULT_MANIFEST!r}, "
        f"but the sibling consumer of the SAME shipped tree resolved its own "
        f"default to {sibling_default!r} -- both should agree on the "
        "`nWave/data/` directory regardless of CWD, since both ship next to "
        "the same package"
    )


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
