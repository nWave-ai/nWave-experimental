"""Smoke command — run the polyglot C# pilot end-to-end.

Invocation::

    pipenv run python scripts/polyglot/smoke_csharp_pilot.py

Behaviour:

1. ``cd tests/polyglot-pilot/csharp/``.
2. If no .NET SDK is available (``dotnet`` absent on PATH, or a runtime-only
   ``dotnet`` host whose ``--list-sdks`` lists none): log ``[polyglot-smoke]
   .NET SDK absent — skipped`` and exit 0 with WARNING. (Fail-open robustness —
   CI without .NET should not break unrelated test suites.)
3. ``dotnet restore`` (only if ``obj/`` absent).
4. ``dotnet test``.
5. Exit 0 on success; non-zero on failure.

The script is the single contract Python-side callers depend on. Both
manual human runs and the pytest wrapper at
``tests/polyglot-pilot/test_csharp_smoke.py`` go through it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_DIR = REPO_ROOT / "tests" / "polyglot-pilot" / "csharp"

EXIT_OK = 0
EXIT_TEST_FAILED = 1
EXIT_TOOLCHAIN_BROKEN = 2


def _log(message: str) -> None:
    print(f"[polyglot-smoke] {message}", flush=True)


def _toolchain_present() -> bool:
    """Return True iff a `dotnet` host on PATH lists at least one SDK.

    A runtime-only host resolves on PATH yet cannot restore or build anything,
    so the host binary alone is not the C# toolchain.
    """
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        return False
    listed = subprocess.run(
        [dotnet, "--list-sdks"],
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    return bool(listed.stdout.strip())


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=False,
    )


def main() -> int:
    if not PILOT_DIR.is_dir():
        _log(f"pilot directory missing: {PILOT_DIR}")
        return EXIT_TOOLCHAIN_BROKEN

    try:
        toolchain_present = _toolchain_present()
    except (OSError, subprocess.SubprocessError) as exc:
        _log(f".NET SDK probe failed: {exc}")
        return EXIT_TOOLCHAIN_BROKEN
    if not toolchain_present:
        _log(".NET SDK absent — skipped (no SDK listed by a dotnet on PATH)")
        return EXIT_OK

    obj_dir = PILOT_DIR / "obj"
    if not obj_dir.is_dir():
        _log("restoring NuGet packages (one-time per checkout)")
        result = _run(["dotnet", "restore"], cwd=PILOT_DIR)
        if result.returncode != 0:
            _log(f"dotnet restore failed (exit {result.returncode})")
            return EXIT_TOOLCHAIN_BROKEN

    _log("running dotnet test")
    result = _run(
        ["dotnet", "test", "--nologo", "--verbosity", "minimal"],
        cwd=PILOT_DIR,
    )
    if result.returncode != 0:
        _log(f"dotnet test reported failures (exit {result.returncode})")
        return EXIT_TEST_FAILED

    _log("OK — polyglot C# pilot GREEN end-to-end")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
