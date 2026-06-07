"""Tests for simulate_build -- wheel build simulation (step 02-01).

Validates that simulate_build() builds a wheel, checks size threshold,
and reports PASS/FAIL via StepResult.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.release.simulate import (
    MINIMUM_WHEEL_SIZE_BYTES,
    Status,
    simulate_build,
)


# ---------------------------------------------------------------------------
# Acceptance: simulate_build returns PASS for valid wheel
# ---------------------------------------------------------------------------


class TestSimulateBuildAcceptance:
    """Acceptance: simulate_build produces a wheel and validates size."""

    def test_valid_wheel_returns_pass(self, monkeypatch, tmp_path):
        """Given subprocess builds a wheel > minimum size,
        simulate_build should return PASS with wheel name and size."""

        wheel_name = "nwave_ai-3.2.0-py3-none-any.whl"

        def fake_run(cmd, **kwargs):
            # Intercept the build command and create a fake wheel
            outdir = None
            cmd_list = list(cmd) if isinstance(cmd, (list, tuple)) else cmd.split()
            if "--outdir" in cmd_list:
                idx = cmd_list.index("--outdir")
                outdir = cmd_list[idx + 1]

            if outdir:
                Path(outdir).mkdir(parents=True, exist_ok=True)
                wheel_path = Path(outdir) / wheel_name
                # Write content larger than MINIMUM_WHEEL_SIZE_BYTES
                wheel_path.write_bytes(b"x" * (MINIMUM_WHEEL_SIZE_BYTES + 1024))

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_build("3.2.0")

        assert result.status == Status.PASS
        assert result.name == "Build distribution"
        assert wheel_name in result.message


# ---------------------------------------------------------------------------
# Unit: subprocess failure returns FAIL
# ---------------------------------------------------------------------------


class TestSimulateBuildSubprocessFailure:
    """Unit: build subprocess returns non-zero -> FAIL."""

    def test_build_failure_returns_fail(self, monkeypatch):
        """When the build subprocess exits non-zero, result is FAIL."""

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="build error: missing setup"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_build("3.2.0")

        assert result.status == Status.FAIL
        assert "failed" in result.message.lower() or "error" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: no wheel produced returns FAIL
# ---------------------------------------------------------------------------


class TestSimulateBuildNoWheel:
    """Unit: build succeeds but no .whl file produced -> FAIL."""

    def test_no_wheel_returns_fail(self, monkeypatch):
        """When build succeeds but no wheel is created, result is FAIL."""

        def fake_run(cmd, **kwargs):
            # Succeed but don't create any wheel file
            cmd_list = list(cmd) if isinstance(cmd, (list, tuple)) else cmd.split()
            if "--outdir" in cmd_list:
                idx = cmd_list.index("--outdir")
                outdir = cmd_list[idx + 1]
                Path(outdir).mkdir(parents=True, exist_ok=True)
                # Create a non-wheel file
                Path(outdir).joinpath("README.txt").write_text("not a wheel")

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_build("3.2.0")

        assert result.status == Status.FAIL
        assert "no wheel" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: wheel too small returns FAIL
# ---------------------------------------------------------------------------


class TestSimulateBuildWheelTooSmall:
    """Unit: wheel under MINIMUM_WHEEL_SIZE_BYTES -> FAIL."""

    def test_small_wheel_returns_fail(self, monkeypatch):
        """When wheel exists but is smaller than minimum, result is FAIL."""

        def fake_run(cmd, **kwargs):
            cmd_list = list(cmd) if isinstance(cmd, (list, tuple)) else cmd.split()
            if "--outdir" in cmd_list:
                idx = cmd_list.index("--outdir")
                outdir = cmd_list[idx + 1]
                Path(outdir).mkdir(parents=True, exist_ok=True)
                wheel_path = Path(outdir) / "nwave_ai-3.2.0-py3-none-any.whl"
                # Write tiny wheel (well under threshold)
                wheel_path.write_bytes(b"x" * 100)

            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = simulate_build("3.2.0")

        assert result.status == Status.FAIL
        assert "small" in result.message.lower() or "bytes" in result.message.lower()
