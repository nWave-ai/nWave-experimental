"""UpdateCheckService - application service for version update checks.

Fetches the latest version from PyPI, compares to the local version via
importlib.metadata, and returns a structured result. On timeout or any
network/JSON error, returns a silent-skip result (no exception propagates).

Architecture: application layer service.
- Driving port: check_for_updates() public method
- Driven port boundaries: HTTP endpoint (injectable via constructor)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class UpdateStatus(Enum):
    """Status of an update check."""

    UP_TO_DATE = "UP_TO_DATE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    SKIP = "SKIP"


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of an update check.

    Attributes:
        status:    Outcome of the check (UP_TO_DATE, UPDATE_AVAILABLE, SKIP).
        latest:    Latest version string from PyPI (present when UPDATE_AVAILABLE).
        changelog: Release notes from GitHub (present when available).
    """

    status: UpdateStatus
    latest: str | None = field(default=None)
    changelog: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_DEFAULT_PYPI_URL = "https://pypi.org/pypi/nwave-ai/json"
_DEFAULT_TIMEOUT = 5  # seconds


class UpdateCheckService:
    """Checks for available updates by querying PyPI.

    Constructor accepts injectable URLs and local version to enable testing
    without real network calls.
    """

    def __init__(
        self,
        pypi_url: str = _DEFAULT_PYPI_URL,
        local_version: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the service.

        Args:
            pypi_url:      PyPI JSON endpoint (injectable for tests).
            local_version: Local package version string; auto-detected when None.
            timeout:       HTTP request timeout in seconds (default 5).
        """
        self._pypi_url = pypi_url
        self._local_version = local_version or _detect_local_version()
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API (driving port)
    # ------------------------------------------------------------------

    def check_for_updates(self) -> UpdateCheckResult:
        """Fetch latest version from PyPI and compare to local version.

        Returns:
            UpdateCheckResult with status UP_TO_DATE, UPDATE_AVAILABLE, or SKIP.
            Never raises an exception.
        """
        latest = self._fetch_latest_version()
        if latest is None:
            return UpdateCheckResult(status=UpdateStatus.SKIP)

        if _is_newer(latest, self._local_version):
            return UpdateCheckResult(
                status=UpdateStatus.UPDATE_AVAILABLE, latest=latest
            )

        return UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_latest_version(self) -> str | None:
        """Fetch latest version from PyPI. Returns None on any failure."""
        try:
            req = urllib.request.Request(self._pypi_url)
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                if response.status != 200:
                    return None
                raw = response.read()
        except Exception:
            return None

        try:
            data = json.loads(raw)
            return str(data["info"]["version"])
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _detect_local_version() -> str:
    """Return the installed nwave-ai version, or '0.0.0' when unavailable."""
    try:
        return pkg_version("nwave-ai")
    except PackageNotFoundError:
        return "0.0.0"


def _is_newer(candidate: str, current: str) -> bool:
    """Return True when candidate version is strictly newer than current.

    Uses simple tuple comparison on integer version parts.  Sufficient for
    PEP 440 epoch-free semantic versions (MAJOR.MINOR.PATCH).
    """
    try:
        return _parse_version(candidate) > _parse_version(current)
    except (ValueError, AttributeError):
        return False


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison."""
    return tuple(int(part) for part in v.split("."))
