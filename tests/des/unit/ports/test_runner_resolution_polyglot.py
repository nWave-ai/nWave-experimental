"""Regression: target-aware runner resolution on POLYGLOT repos (BUG B, ADR-FLOW-008).

`resolve(target_root)` used first-lockfile-wins -- on a polyglot repo (Rust
Cargo.toml + JS package.json) `package.json` shadowed `Cargo.toml` -> vitest,
so a Rust feature's cargo gate never fired. The fix makes resolution
feature/target-aware: single-lockfile fast-path unchanged; multi-lockfile
disambiguated via signal cascade (runner.json override -> cargo-target-presence);
un-disambiguable -> Indeterminate (degrade-LOUD, names the competing lockfiles),
NEVER a silent first-row pick.
"""

from __future__ import annotations

from pathlib import Path

from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.test_runner_port import (
    RunnerAdapter,
    RunnerResolutionContext,
    resolve,
)


def _write(root: Path, name: str, content: str = "") -> None:
    (root / name).write_text(content, encoding="utf-8")


def test_polyglot_rust_plus_js_resolves_cargo_not_vitest(tmp_path):
    """THE BUG: Cargo.toml + package.json(vitest) + a feature context -> cargo-test."""
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "package.json", '{"devDependencies":{"vitest":"^1"}}')
    ctx = RunnerResolutionContext(feature_id="my-rust-feature", repo=tmp_path)
    result = resolve(tmp_path, ctx)
    assert isinstance(result, RunnerAdapter)
    assert result.name == "cargo-test"


def test_single_lockfile_python_unchanged_without_context(tmp_path):
    """Fast-path: a pure-Python repo resolves pytest exactly as before (no ctx)."""
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    result = resolve(tmp_path)
    assert isinstance(result, RunnerAdapter)
    assert result.name == "pytest"


def test_single_lockfile_python_unchanged_with_context(tmp_path):
    """Fast-path is signal-agnostic: one match ignores the feature context."""
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    ctx = RunnerResolutionContext(feature_id="f", repo=tmp_path)
    result = resolve(tmp_path, ctx)
    assert isinstance(result, RunnerAdapter)
    assert result.name == "pytest"


def test_undisambiguable_polyglot_degrades_loud_indeterminate(tmp_path):
    """2+ lockfiles, no cargo + no runner.json -> Indeterminate naming BOTH."""
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    _write(tmp_path, "go.mod", "module x\n")
    ctx = RunnerResolutionContext(feature_id="f", repo=tmp_path)
    result = resolve(tmp_path, ctx)
    assert isinstance(result, Indeterminate)
    assert "pyproject.toml" in result.reason and "go.mod" in result.reason


def test_polyglot_no_context_is_indeterminate_not_silent_pick(tmp_path):
    """Multi-lockfile with NO feature context -> Indeterminate, never a silent row-0 pick."""
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "package.json", '{"devDependencies":{"vitest":"^1"}}')
    result = resolve(tmp_path)
    assert isinstance(result, Indeterminate)


def test_runner_json_override_beats_cargo(tmp_path):
    """Signal (c): a runner.json declaring a runner overrides cargo-presence."""
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "package.json", '{"devDependencies":{"vitest":"^1"}}')
    feat_dir = tmp_path / "docs" / "feature" / "f"
    feat_dir.mkdir(parents=True)
    (feat_dir / "runner.json").write_text(
        '{"feature_id":"f","runner":"vitest"}', encoding="utf-8"
    )
    ctx = RunnerResolutionContext(feature_id="f", repo=tmp_path)
    result = resolve(tmp_path, ctx)
    assert isinstance(result, RunnerAdapter)
    assert result.name == "vitest"


def test_polyglot_repo_runner_json_declares_cargo_whole_tree(tmp_path):
    """.nwave/runner.json whole-tree override resolves cargo on a polyglot root.

    FIX-1 (#73, D8): resolve(repo, None) on a polyglot root (Cargo.toml +
    package.json) normally returns Indeterminate (2 lockfiles, no feature context
    to disambiguate). A repo-level .nwave/runner.json declaring "cargo-test"
    BYPASSES the lockfile-scan and returns RunnerAdapter("cargo-test"). This is the
    escape hatch for polyglot repos where the whole-tree runner is unambiguous to
    the operator but not to the lockfile registry.
    """
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "package.json", '{"devDependencies":{"vitest":"^1"}}')
    nwave_dir = tmp_path / ".nwave"
    nwave_dir.mkdir(parents=True)
    (nwave_dir / "runner.json").write_text('{"runner": "cargo-test"}', encoding="utf-8")
    result = resolve(tmp_path)  # feature=None -> whole-tree path
    assert isinstance(result, RunnerAdapter), (
        f'polyglot root with .nwave/runner.json {{"runner": "cargo-test"}} must '
        f"resolve RunnerAdapter(name='cargo-test'), got {result!r}"
    )
    assert result.name == "cargo-test"


def test_polyglot_absent_repo_runner_json_still_indeterminate(tmp_path):
    """Without .nwave/runner.json a polyglot whole-tree root stays Indeterminate.

    FIX-1 (#73, D8) no-regression witness: the override pre-check only fires
    when the file IS present; absent -> fall through to the unchanged lockfile-scan
    -> Indeterminate (degrade-LOUD). The existing D2 refusal is byte-unchanged.
    """
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "package.json", '{"devDependencies":{"vitest":"^1"}}')
    result = resolve(tmp_path)  # feature=None, no .nwave/runner.json
    assert isinstance(result, Indeterminate), (
        f"polyglot root WITHOUT .nwave/runner.json must return Indeterminate "
        f"(degrade-LOUD), not {result!r}"
    )
