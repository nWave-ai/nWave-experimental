"""Regression (SOSTITUZIONE class, AUDIT-gate-cli.md S1): ``resolve_tool``'s
not-found remediation must never hardcode a SINGLE toolchain's install
instruction for every language.

Found in ``src/des/adapters/driven/runner/tool_discovery.py::resolve_tool``:
the not-found branch used to synthesize a FIXED template --
``f"install it (e.g. via rustup or 'cargo install {name}')"`` -- for EVERY
caller, cargo included. ``resolve_tool`` is the SHARED 3-rung discovery scale
every language-adapter runner calls (go/vitest/kotlin/java/csharp/npm, not
only cargo) -- ``known_locations`` already carries language identity per
caller, but the remediation ignored it. Propagated VERBATIM to 4 downstream
refusal sites (``run_contract_gate.py`` x3, ``verify_slice_commit_
completeness.py`` x1) via ``RunnerAdapterUnavailable(reason=resolution.
remediation)`` -> ``str(exc)``. A Go target's not-found message told the
operator to run ``cargo install go`` -- a command that does not exist.

Fix (already landed alongside this test, NOT re-derived here): ``resolve_tool``
gained an ``install_hint: str | None`` parameter. Every caller now passes its
OWN toolchain-specific hint (go's caller -> a go.dev hint, vitest's callers
-> an npm hint, etc.) instead of relying on a shared default. When a caller
omits the hint, ``resolve_tool`` degrades LOUD -- it says explicitly no hint
was supplied, rather than inventing one (GDP-6, never silently-wrong).

This test would FAIL for the right reason if a caller's install-hint
regressed back to the shared cargo template, or if a NEW caller were added
without wiring its own hint: each per-tool assertion below checks the hint
NAMES that tool's own handler and does NOT leak "cargo"/"rustup" wording
(cargo's own hint is the one EXPECTED exception, asserted separately).

Driving surface (Mandate-13 driving-port-only): ``resolve_tool`` IS the
driven-adapter primitive under regression (mirrors ``tests/bugs/des/
test_resolve_tool_repo_relative_locations.py``, the sibling regression for
this same function).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.runner.tool_discovery import resolve_tool


# --- unit: resolve_tool's own not-found remediation, in isolation ----------


def test_not_found_without_install_hint_names_no_toolchain_and_says_so() -> None:
    """No ``install_hint`` supplied -> the message says so explicitly, and
    never falls back to inventing a cargo-flavoured remediation for a tool
    it has no toolchain knowledge of."""
    resolution = resolve_tool("some-unknown-tool", ())

    assert resolution.rung == "not-found"
    assert resolution.remediation is not None
    assert "cargo" not in resolution.remediation.lower()
    assert "rustup" not in resolution.remediation.lower()
    assert "no toolchain-specific install hint" in resolution.remediation


def test_not_found_with_install_hint_uses_the_callers_own_hint() -> None:
    """A caller-supplied ``install_hint`` is used verbatim -- never
    overridden by a shared default."""
    resolution = resolve_tool("go", (), install_hint="install Go via https://go.dev/dl")

    assert resolution.rung == "not-found"
    assert resolution.remediation is not None
    assert "install Go via https://go.dev/dl" in resolution.remediation
    assert "cargo" not in resolution.remediation.lower()


# --- per-tool: each production caller's remediation names ITS OWN handler --


def test_go_runner_install_hint_names_go_not_cargo() -> None:
    from des.adapters.driven.runner.go_runner import GO_INSTALL_HINT

    hint = GO_INSTALL_HINT.lower()
    assert "go" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_java_runner_install_hint_names_jdk_maven_not_cargo() -> None:
    from des.adapters.driven.runner.java_runner import MAVEN_INSTALL_HINT

    hint = MAVEN_INSTALL_HINT.lower()
    assert "maven" in hint or "jdk" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_kotlin_runner_install_hint_names_gradle_not_cargo() -> None:
    from des.adapters.driven.runner.kotlin_runner import GRADLE_INSTALL_HINT

    hint = GRADLE_INSTALL_HINT.lower()
    assert "gradle" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_csharp_runner_install_hint_names_dotnet_not_cargo() -> None:
    from des.adapters.driven.runner.csharp_runner import DOTNET_INSTALL_HINT

    hint = DOTNET_INSTALL_HINT.lower()
    assert ".net" in hint or "dotnet" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_vitest_runner_install_hint_names_npm_not_cargo() -> None:
    from des.adapters.driven.runner.vitest_runner import VITEST_INSTALL_HINT

    hint = VITEST_INSTALL_HINT.lower()
    assert "npm" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_npm_shared_install_hint_names_node_not_cargo() -> None:
    """The ``npm``-resolving callers (staged installer, artifact builder) share
    ``NPM_INSTALL_HINT`` from ``vitest_runner`` (SSOT for the Node toolchain
    hint, mirroring ``VITEST_KNOWN_LOCATIONS`` reuse)."""
    from des.adapters.driven.runner.vitest_runner import NPM_INSTALL_HINT

    hint = NPM_INSTALL_HINT.lower()
    assert "node" in hint
    assert "cargo" not in hint
    assert "rustup" not in hint


def test_cargo_runner_install_hint_names_cargo_the_one_expected_exception() -> None:
    """Cargo's OWN hint is correct by construction -- this is the one place
    "cargo"/"rustup" wording belongs."""
    from des.adapters.driven.runner.cargo_runner import CARGO_INSTALL_HINT

    hint = CARGO_INSTALL_HINT.lower()
    assert "cargo" in hint
    assert "rustup" in hint


# --- end-to-end: a resolved-runner not-found message never leaks cargo -----


def test_go_runner_not_found_reason_does_not_mention_cargo_install(
    monkeypatch,
) -> None:
    """The actual ``RunnerAdapterUnavailable`` raised by ``run_go_scope`` for a
    not-found go binary must not tell the operator to run ``cargo install go``
    -- the concrete regression scenario from the audit (S1)."""
    import shutil

    from des.adapters.driven.runner import go_runner
    from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(go_runner, "GO_KNOWN_LOCATIONS", ())

    adapter = RunnerAdapter(name="go-test")
    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        go_runner.run_go_scope(adapter, Path("/fake/target"), ("go", "test", "./..."))

    reason = str(excinfo.value).lower()
    assert "cargo install go" not in reason
    assert "go.dev" in reason
