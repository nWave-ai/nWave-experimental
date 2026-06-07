"""Unit tests for substrate_probe module.

Tests run_probe() through its public function signature (driving port),
monkeypatching run_doctor at the nwave_ai.doctor.runner driven port boundary.

After the P0-A fix, nwave_ai imports are deferred inside run_probe() with
try/except ImportError.  Monkeypatching therefore targets the source module
(nwave_ai.doctor.runner) rather than a module-level name on substrate_probe.

Test Budget: 4 behaviors x 2 = 8 max. Using 4 tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nwave_ai.doctor.runner as runner_module
from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    import pytest


def _make_results(passed_count: int, failed_count: int) -> list[CheckResult]:
    passed = [
        CheckResult(passed=True, error_code=None, message="ok", remediation=None)
        for _ in range(passed_count)
    ]
    failed = [
        CheckResult(
            passed=False,
            error_code="ERR",
            message="fail",
            remediation="fix it",
        )
        for _ in range(failed_count)
    ]
    return passed + failed


class TestRunProbe:
    """Tests for run_probe() driving port."""

    def test_returns_empty_string_when_all_checks_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Healthy install → silent empty string."""
        monkeypatch.setattr(
            runner_module, "run_doctor", lambda ctx: _make_results(7, 0)
        )

        from src.des.adapters.drivers.hooks.substrate_probe import run_probe

        result = run_probe()

        assert result == ""

    def test_returns_advisory_with_singular_issue_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """1 failing check → advisory containing '1 issue'."""
        monkeypatch.setattr(
            runner_module, "run_doctor", lambda ctx: _make_results(6, 1)
        )

        from src.des.adapters.drivers.hooks.substrate_probe import run_probe

        result = run_probe()

        assert "1 issue" in result
        assert "issues" not in result
        assert result.endswith("\n")

    def test_returns_advisory_with_plural_issue_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """3 failing checks → advisory containing '3 issues'."""
        monkeypatch.setattr(
            runner_module, "run_doctor", lambda ctx: _make_results(4, 3)
        )

        from src.des.adapters.drivers.hooks.substrate_probe import run_probe

        result = run_probe()

        assert "3 issues" in result
        assert result.endswith("\n")

    def test_returns_empty_string_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception during probe → fire-and-forget empty string."""

        def _raise(ctx: object) -> list[CheckResult]:
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(runner_module, "run_doctor", _raise)

        from src.des.adapters.drivers.hooks.substrate_probe import run_probe

        result = run_probe()

        assert result == ""
