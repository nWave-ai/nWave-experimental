"""Regression (GDP-6 / language-agnosticism): a cargo feature-scope that matches
NO binary must be INDETERMINATE (empty-scope), never a false cargo-red.

Charter: ``docs/product/expectations/fix-cargo-scope-nomatch-not-red/
a-cargo-scope-matching-no-binary-is-indeterminate-not-red.md``.

Found in ``src/des/adapters/driven/runner/cargo_runner.py`` `run_cargo_scope`
(:73-111): the exit-code map is ``exit 0 -> PASS``, ``exit 4 (_NO_MATCH_EXIT)
-> raise RunnerAdapterUnavailable`` (INDETERMINATE empty-scope), and **any other
non-zero exit -> RunVerdict(passed=False)** (FAIL / cargo-red). EMPIRICALLY
(real cargo 1.95 + nextest 0.9.137): when the feature-scoped selector
``cargo nextest run -E 'binary(/<snake_feature_id>/)'`` matches NO cargo binary
(the ``binary(/<feature_id>/)`` convention does not match a real crate's
binaries, which are named after the crate), nextest exits **94** -- "filterset
matched no binary names". Exit 94 hits the "any other non-zero" arm and is
reported as cargo-red, so ``des verify-slice-commit`` E2 FALSELY REFUSES a
slice whose tests actually PASS.

The fix direction (charter, NOT implemented here): treat nextest exit 94 like
exit 4 -- raise ``RunnerAdapterUnavailable`` (empty-scope INDETERMINATE) naming
the ``runner.json`` remediation, NOT a false cargo-red. Exit 100 (a genuine
nextest test failure) stays FAIL; exit 0 stays PASS; exit 4 stays
INDETERMINATE -- none of the three genuine paths may regress.

CI-SAFE: no real cargo/nextest is invoked. ``subprocess.run`` and
``resolve_tool`` (both consumed by ``cargo_runner`` via direct-name imports,
mirrored from the proven ``tests/des/acceptance/rust_test_runner_adapter``
stubbing precedent) are monkeypatched so the exit-code map is exercised
deterministically without a Rust toolchain.

Driving surface (Mandate-13 driving-port-only): ``run_cargo_scope`` IS the
driven-runner adapter's own production entry point (the object under
regression) -- it is not domain/cli business logic, so this bugfix-class
regression AT drives it directly, mirroring the established
``tests/bugs/des/test_run_contract_gate_scope_unverified_names_how.py``
adapter-direct precedent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.runner import cargo_runner
from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.ports.test_runner_port import (
    RunnerAdapter,
    RunnerAdapterUnavailable,
    RunVerdict,
)


_ADAPTER = RunnerAdapter(name="cargo-test")
_TARGET_ROOT = Path("/fake/target-crate")
_SCOPED_COMMAND = ("cargo", "nextest", "run", "--test", "ws_driver")

# nextest's "filterset matched no binary names" exit -- empirically 94 on real
# cargo 1.95 + nextest 0.9.137 (the charter's evidence). Today falls into the
# cargo_runner "any other non-zero" arm -> false cargo-red (the defect).
_NEXTEST_NO_BINARY_MATCH_EXIT = 94

# A genuine nextest test-failure exit (tests EXECUTED, some failed). Must stay
# cargo-red (FAIL) -- the fix must not weaken this path.
_NEXTEST_GENUINE_FAILURE_EXIT = 100


def _stub_cargo_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """cargo "resolves" to a fake path -- no real cargo binary is touched."""
    monkeypatch.setattr(
        cargo_runner,
        "resolve_tool",
        lambda name, known_locations, **_kwargs: ToolResolution(
            rung="on-path", path="/fake/cargo"
        ),
    )


def _stub_subprocess_run(monkeypatch: pytest.MonkeyPatch, returncode: int) -> None:
    """The shelled cargo command "runs" and exits ``returncode`` -- no subprocess."""

    def _fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=argv, returncode=returncode, stdout="", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)


# --- POSITIVE (active-RED today) --------------------------------------------


def test_cargo_exit_94_no_binary_match_is_indeterminate_not_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """nextest exit 94 (filterset matched no binary) must raise
    ``RunnerAdapterUnavailable`` (empty-scope INDETERMINATE), NOT return
    ``RunVerdict(passed=False)`` (a false cargo-red).

    Active-RED at HEAD: ``run_cargo_scope`` only special-cases exit 4
    (``_NO_MATCH_EXIT``); exit 94 falls to
    ``RunVerdict(passed=completed.returncode == 0)`` -> ``passed=False`` --
    ``pytest.raises(RunnerAdapterUnavailable)`` below never fires the
    expected exception, so this test fails for the RIGHT business reason
    (the call returns a FAIL verdict instead of raising).
    """
    _stub_cargo_resolved(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=_NEXTEST_NO_BINARY_MATCH_EXIT)

    with pytest.raises(RunnerAdapterUnavailable) as exc_info:
        cargo_runner.run_cargo_scope(_ADAPTER, _TARGET_ROOT, _SCOPED_COMMAND)

    reason = str(exc_info.value).lower()
    assert any(token in reason for token in ("runner.json", "no", "scope", "binary")), (
        "the exit-94 no-binary-match INDETERMINATE must name the scope / "
        f"runner.json remediation (HOW to fix); got reason={reason!r}"
    )


# --- NEGATIVE (green now AND after -- the genuine paths must NOT regress) ---


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "returncode, expected_passed",
    [
        (0, True),  # exit 0 -> PASS, unchanged
        (_NEXTEST_GENUINE_FAILURE_EXIT, False),  # exit 100 -> still cargo-red (FAIL)
    ],
)
def test_cargo_genuine_pass_and_fail_exits_are_unaffected(
    monkeypatch: pytest.MonkeyPatch, returncode: int, expected_passed: bool
) -> None:
    """exit 0 stays PASS; a genuine test failure (exit 100) stays cargo-red
    (FAIL, does NOT raise). Neither genuine path may regress under the fix.
    """
    _stub_cargo_resolved(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=returncode)

    verdict = cargo_runner.run_cargo_scope(_ADAPTER, _TARGET_ROOT, _SCOPED_COMMAND)

    assert verdict == RunVerdict(passed=expected_passed, runner=_ADAPTER.name)


@pytest.mark.negative_at
def test_cargo_exit_4_empty_scope_stays_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """exit 4 (``_NO_MATCH_EXIT``, declared command ran zero tests) must keep
    raising ``RunnerAdapterUnavailable`` -- unchanged by the exit-94 fix.
    """
    _stub_cargo_resolved(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=cargo_runner._NO_MATCH_EXIT)

    with pytest.raises(RunnerAdapterUnavailable):
        cargo_runner.run_cargo_scope(_ADAPTER, _TARGET_ROOT, _SCOPED_COMMAND)
