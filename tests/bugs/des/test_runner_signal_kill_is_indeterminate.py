"""Regression (GDP-6 / degrade-LOUD): an OS signal-kill (SIGKILL/OOM, SIGTERM)
must surface as INDETERMINATE, never a false test-red.

RCA: ``docs/feature/fix-runverdict-sigkill-mislabel/deliver/rca.md``. Charter:
``docs/product/expectations/fix-runverdict-sigkill-mislabel/
operator-sees-os-kill-as-indeterminate-not-a-failure.md``.

Found in the 4 concrete ``RunnerAdapter.run`` leaf adapters
(``pytest_runner.run_pytest_scope``, ``cargo_runner.run_cargo_scope``,
``vitest_runner.run_vitest_scope``, ``go_runner.run_go_scope``): each maps a
subprocess exit code to ``RunVerdict.passed`` with a bare comparison
(``returncode in _GREEN_EXIT_CODES`` / ``returncode == 0``) that does NOT branch
on the host-OS signal-kill vocabulary (``returncode < 0`` on POSIX, or the
shell-convention ``128+signal`` = 137 SIGKILL / 143 SIGTERM). A subprocess killed
by earlyoom/OOM under memory pressure is therefore indistinguishable from a
genuine test failure to every downstream consumer -- an operator hunts for a bug
in code that is fine, because the box killed the run, not the code.

The fix direction (RCA S4, NOT implemented here): each leaf RAISES
``RunnerAdapterUnavailable`` with a signal-naming reason (mirroring
``run_contract_gate._describe_worker_kill``) when the returncode indicates a
signal-kill -- NOT ``RunVerdict(passed=False)``. ``RunVerdict`` stays binary
(``passed: bool`` + ``runner: str``, NO 3rd field, ADR-GV-001 D4(d)); the
already-established 3-state escape hatch is the ``RunnerAdapterUnavailable``
exception channel, already caught by all 4 call sites and routed to
``GateVerdict.INDETERMINATE``.

CI-SAFE: no real pytest/cargo/vitest/go subprocess is invoked. ``subprocess.run``
is monkeypatched globally (mirrored from the proven
``tests/bugs/des/test_cargo_scope_nomatch_is_indeterminate.py`` stubbing
precedent); each runner's own tool-discovery seam (``pytest_interpreter`` /
``resolve_tool``) is monkeypatched per-module so the exit-code map is exercised
deterministically without any real toolchain.

Driving surface (Mandate-13 driving-port-only): each ``run_*_scope`` function IS
the driven-runner adapter's own production entry point (the object under
regression) -- not domain/cli business logic -- so this bugfix-class regression
AT drives it directly, mirroring the established
``tests/bugs/des/test_cargo_scope_nomatch_is_indeterminate.py`` adapter-direct
precedent.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pytest

from des.adapters.driven.runner import (
    cargo_runner,
    go_runner,
    pytest_runner,
    vitest_runner,
)
from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.ports.test_runner_port import (
    RunnerAdapter,
    RunnerAdapterUnavailable,
    RunVerdict,
)


_TARGET_ROOT = Path("/fake/target-root")


class _RunFn(Protocol):
    def __call__(
        self,
        adapter: RunnerAdapter,
        target_root: Path,
        scoped_node_ids: tuple[str, ...],
    ) -> RunVerdict: ...


@dataclass(frozen=True)
class _RunnerCase:
    """One of the 4 leaf adapters the fix touches -- its run entry + stub setup."""

    name: str
    run_fn: _RunFn
    adapter: RunnerAdapter
    scoped_command: tuple[str, ...]
    setup: Callable[[pytest.MonkeyPatch], None]
    # A genuine non-zero, non-signal exit this runner treats as a REAL test
    # failure (must stay ``passed=False``, never swallowed into INDETERMINATE).
    genuine_fail_exit: int = 1


def _stub_subprocess_run(monkeypatch: pytest.MonkeyPatch, returncode: int) -> None:
    """The shelled subprocess "runs" and exits ``returncode`` -- no real process."""

    def _fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=argv, returncode=returncode, stdout="", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    # `run_pytest_scope` shells through the process-group-reaping helper
    # (`run_pytest_reaped`), not `subprocess.run` directly, so stub that seam too
    # -- it returns the same `CompletedProcess` shape, exercising the exit-code
    # map without a real process (the other 3 runners still call subprocess.run).
    monkeypatch.setattr(pytest_runner, "run_pytest_reaped", _fake_run)


def _setup_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    # `run_pytest_scope` forwards `repo_root=target_root` (defect #79) --
    # the stub accepts the (unused) kwarg so the call shape stays compatible;
    # every assertion in this file is unaffected (the stub's RETURN VALUE,
    # which the exit-code-mapping assertions depend on, is untouched).
    monkeypatch.setattr(
        pytest_runner, "pytest_interpreter", lambda repo_root=None: "/fake/python"
    )


def _setup_cargo(monkeypatch: pytest.MonkeyPatch) -> None:
    # `**_kwargs` swallows `install_hint` (and any future keyword
    # `resolve_tool` gains) so this stub stays compatible with the real
    # signature without needing a matching edit per new parameter.
    monkeypatch.setattr(
        cargo_runner,
        "resolve_tool",
        lambda name, known_locations, **_kwargs: ToolResolution(
            rung="on-path", path="/fake/cargo"
        ),
    )


def _setup_vitest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        vitest_runner,
        "resolve_tool",
        lambda name, known_locations, base_dir=None, **_kwargs: ToolResolution(
            rung="on-path", path="/fake/vitest"
        ),
    )


def _setup_go(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        go_runner,
        "resolve_tool",
        lambda name, known_locations, base_dir=None, **_kwargs: ToolResolution(
            rung="on-path", path="/fake/go"
        ),
    )


_RUNNER_CASES: tuple[_RunnerCase, ...] = (
    _RunnerCase(
        name="pytest",
        run_fn=pytest_runner.run_pytest_scope,
        adapter=RunnerAdapter(name="pytest"),
        scoped_command=("tests/fake_test.py::test_fake",),
        setup=_setup_pytest,
        genuine_fail_exit=1,  # a real pytest test-failure exit
    ),
    _RunnerCase(
        name="cargo",
        run_fn=cargo_runner.run_cargo_scope,
        adapter=RunnerAdapter(name="cargo-test"),
        scoped_command=("cargo", "nextest", "run", "--test", "ws_driver"),
        setup=_setup_cargo,
        genuine_fail_exit=1,  # a real cargo test-failure exit (not 4/94 empty-scope)
    ),
    _RunnerCase(
        name="vitest",
        run_fn=vitest_runner.run_vitest_scope,
        adapter=RunnerAdapter(name="vitest"),
        scoped_command=("vitest", "run"),
        setup=_setup_vitest,
        genuine_fail_exit=1,  # a real vitest test-failure exit
    ),
    _RunnerCase(
        name="go",
        run_fn=go_runner.run_go_scope,
        adapter=RunnerAdapter(name="go-test"),
        scoped_command=("go", "test", "./..."),
        setup=_setup_go,
        genuine_fail_exit=1,  # a real go test-failure exit
    ),
)


# The signal-kill domain the RCA's proposed ``_signal_kill_reason`` helper
# classifies (mirroring ``run_contract_gate._describe_worker_kill``):
# ``returncode < 0`` (POSIX negative-signal convention) and the ``128+signal``
# shell convention (137 SIGKILL, 143 SIGTERM). ``expected_tokens`` pins that the
# raised reason NAMES the signal (GDP-3 WHAT/WHY/HOW), tolerant of the exact
# wording as long as the signal identity is legible.
_SIGNAL_KILL_CASES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (-9, ("sigkill", "signal 9")),  # raw POSIX SIGKILL
    (137, ("137",)),  # shell-convention 128+9 (SIGKILL/OOM-kill)
    (143, ("143",)),  # shell-convention 128+15 (SIGTERM)
    (-15, ("sigterm", "signal 15")),  # raw POSIX SIGTERM
)


# --- POSITIVE (active-RED today): signal-kill must be INDETERMINATE --------


@pytest.mark.parametrize(
    "returncode, expected_tokens",
    _SIGNAL_KILL_CASES,
    ids=["sigkill_raw_-9", "sigkill_shell_137", "sigterm_shell_143", "sigterm_raw_-15"],
)
@pytest.mark.parametrize("case", _RUNNER_CASES, ids=lambda c: c.name)
def test_signal_kill_raises_runner_adapter_unavailable_not_false_red(
    case: _RunnerCase,
    returncode: int,
    expected_tokens: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subprocess killed by an OS signal must raise ``RunnerAdapterUnavailable``
    (INDETERMINATE) naming the signal -- NEVER ``RunVerdict(passed=False)`` (a
    false test-red that sends the operator hunting for a bug that isn't there).

    Active-RED at HEAD: none of the 4 leaves branch on ``returncode < 0`` or
    ``returncode in (137, 143)`` before constructing ``RunVerdict`` -- the bare
    ``returncode == 0`` / ``in _GREEN_EXIT_CODES`` comparison evaluates ``False``
    for every one of these signal-kill returncodes, so ``run_*_scope`` returns
    ``RunVerdict(passed=False, runner=...)`` instead of raising. This test drives
    ``pytest.raises(RunnerAdapterUnavailable)``, which the current bare-comparison
    code never satisfies -- it fails for the RIGHT business reason (a FAIL
    verdict returned where an INDETERMINATE exception was expected), not an
    import/collection error.
    """
    case.setup(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=returncode)

    with pytest.raises(RunnerAdapterUnavailable) as exc_info:
        case.run_fn(case.adapter, _TARGET_ROOT, case.scoped_command)

    reason = str(exc_info.value).lower()
    assert any(token in reason for token in expected_tokens), (
        f"{case.name}: the signal-kill INDETERMINATE reason must NAME the "
        f"signal (one of {expected_tokens!r}), mirroring "
        f"run_contract_gate._describe_worker_kill; got reason={reason!r}"
    )
    assert exc_info.value.runner == case.adapter.name


# --- NEGATIVE (green now AND after -- the genuine paths must NOT regress) --


@pytest.mark.negative_at
@pytest.mark.parametrize("case", _RUNNER_CASES, ids=lambda c: c.name)
def test_genuine_pass_stays_passed_true(
    case: _RunnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine PASS (exit 0) must stay ``RunVerdict(passed=True)`` -- the
    signal-kill fix must not swallow a real green run into INDETERMINATE.
    """
    case.setup(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=0)

    verdict = case.run_fn(case.adapter, _TARGET_ROOT, case.scoped_command)

    assert verdict == RunVerdict(passed=True, runner=case.adapter.name)


@pytest.mark.negative_at
@pytest.mark.parametrize("case", _RUNNER_CASES, ids=lambda c: c.name)
def test_genuine_fail_stays_passed_false_not_swallowed(
    case: _RunnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine test FAILURE (a real non-zero, non-signal exit) must stay
    ``RunVerdict(passed=False)`` -- the signal-kill fix must distinguish a
    signal-kill from a real regression, never swallow a real red into
    INDETERMINATE (that would hide an actual defect from the operator).
    """
    case.setup(monkeypatch)
    _stub_subprocess_run(monkeypatch, returncode=case.genuine_fail_exit)

    verdict = case.run_fn(case.adapter, _TARGET_ROOT, case.scoped_command)

    assert verdict == RunVerdict(passed=False, runner=case.adapter.name)


__all__: list[str] = []
