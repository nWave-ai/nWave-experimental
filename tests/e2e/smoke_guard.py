"""Guard seam for the Windows smoke test.

Two pure, side-effect-free functions used by ``smoke_test_windows.py`` to
keep it from ever touching the developer's real home directory (see that
module's docstring / RCA for the full context):

- ``require_windows(platform)`` -- refuses to proceed on any platform other
  than Windows, naming the offending platform and explaining why.
- ``sandbox_home(root)`` -- derives a throwaway install target from a
  caller-supplied root, never from the machine's real home.

Neither function performs I/O. Importing this module has zero side effects.
"""

from __future__ import annotations

from pathlib import Path


def require_windows(platform: str) -> str | None:
    """Refuse to proceed unless ``platform`` is Windows (``"win32"``).

    Returns a human-readable refusal message naming the detected platform
    and explaining that this smoke test only runs on Windows, or ``None``
    when ``platform`` is ``"win32"`` (proceed).
    """
    if platform == "win32":
        return None
    return (
        "This smoke test only runs on Windows -- it validates the "
        f"Windows-specific install path, and the detected platform is "
        f"{platform!r}, not Windows. Stopping here before any setup, "
        "network call, or installation step runs. Run it on a Windows "
        "host instead (for example, GitHub Actions windows-latest)."
    )


def sandbox_home(root: Path) -> Path:
    """Derive a throwaway home directory from ``root``.

    Pure -- performs no I/O; the caller is responsible for creating the
    directory. The result always descends from ``root`` and is never the
    machine's real home directory.
    """
    return Path(root) / "sandbox-home"
