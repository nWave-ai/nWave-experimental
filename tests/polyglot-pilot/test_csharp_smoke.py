"""Pytest wrapper around the C# polyglot smoke script.

Marked ``polyglot_smoke`` (custom marker, registered in ``pyproject.toml``).
Behaviour:

- If no .NET SDK is available (the smoke script's own toolchain probe):
  SKIPPED (no toolchain).
- Otherwise: subprocess-invokes ``scripts/polyglot/smoke_csharp_pilot.py``
  and asserts exit 0.

The smoke script itself fails-open on missing toolchain (exit 0 with
WARNING). The test here additionally SKIPs so the test report is honest
about the fact that no actual .NET suite ran.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.polyglot.smoke_csharp_pilot import _toolchain_present


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "polyglot" / "smoke_csharp_pilot.py"


@pytest.mark.polyglot_smoke
@pytest.mark.slow
def test_csharp_polyglot_pilot_runs_green() -> None:
    """The C# pilot's xUnit suite must run GREEN end-to-end."""
    if not _toolchain_present():
        pytest.skip("no .NET SDK available — polyglot C# smoke deferred")

    assert SMOKE_SCRIPT.is_file(), f"missing smoke script: {SMOKE_SCRIPT}"

    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        pytest.fail(
            "polyglot C# smoke FAILED\n"
            f"exit={result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )


@pytest.mark.parametrize("probe_exit, expected_exit", [(0, 0), (7, 2)])
def test_empty_sdk_probe_distinguishes_absence_from_failure(
    tmp_path, monkeypatch, probe_exit, expected_exit
) -> None:
    from scripts.polyglot import smoke_csharp_pilot as smoke

    dotnet = tmp_path / "dotnet"
    dotnet.write_text(f"#!{sys.executable}\nimport sys\nsys.exit({probe_exit})\n")
    dotnet.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(smoke, "PILOT_DIR", tmp_path)

    assert smoke.main() == expected_exit


@pytest.mark.parametrize(
    "probe_error",
    [OSError("cannot execute SDK host"), subprocess.TimeoutExpired("dotnet", 60)],
)
def test_unexecutable_sdk_probe_is_broken_not_absent(
    tmp_path, monkeypatch, probe_error
) -> None:
    from scripts.polyglot import smoke_csharp_pilot as smoke

    monkeypatch.setattr(smoke, "PILOT_DIR", tmp_path)
    monkeypatch.setattr(smoke.shutil, "which", lambda _: "/broken/dotnet")

    def cannot_execute(*args, **kwargs):
        raise probe_error

    monkeypatch.setattr(smoke.subprocess, "run", cannot_execute)

    assert smoke.main() == smoke.EXIT_TOOLCHAIN_BROKEN
