"""Unit tests for UpdateCheckService - version comparison.

Tests the service through its public API (check_for_updates), verifying
observable outcomes at driven port boundaries (HTTP endpoint injection).

Test Budget: 5 behaviors x 2 = 10 max unit tests. Actual: 6 tests (1 parametrized).

Behaviors:
1. Returns UP_TO_DATE when local version equals latest PyPI version
2. Returns UPDATE_AVAILABLE when newer version exists on PyPI
3. Returns SKIP on network timeout (no exception propagated)
4. Returns SKIP on HTTP or JSON error (no exception propagated)
5. Returns UP_TO_DATE (safe fallback) when PyPI returns a pre-release version string
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

from des.application.update_check_service import (
    UpdateCheckService,
    UpdateStatus,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_pypi_response(version: str) -> bytes:
    """Return a minimal PyPI JSON response bytes for the given version."""
    payload: dict[str, Any] = {"info": {"version": version}}
    return json.dumps(payload).encode("utf-8")


class _PyPIHandlerFactory:
    """Creates request handler classes with configurable behavior."""

    @staticmethod
    def ok(version: str) -> type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = make_pypi_response(version)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: Any) -> None:  # suppress server logs
                pass

        return Handler

    @staticmethod
    def http_error(status: int) -> type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(status)
                self.end_headers()

            def log_message(self, *_: Any) -> None:
                pass

        return Handler

    @staticmethod
    def bad_json() -> type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = b"not-valid-json"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: Any) -> None:
                pass

        return Handler


def _start_server(
    handler_class: type[BaseHTTPRequestHandler],
) -> tuple[HTTPServer, str]:
    """Start a local HTTP server and return (server, base_url)."""
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


class TestUpdateCheckServiceVersionComparison:
    """Acceptance tests: UpdateCheckService returns correct status from PyPI."""

    def test_returns_up_to_date_when_versions_match(self) -> None:
        """Service returns UP_TO_DATE when local version equals the PyPI latest."""
        server, base_url = _start_server(_PyPIHandlerFactory.ok("1.2.3"))
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                local_version="1.2.3",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UP_TO_DATE
            assert result.latest is None or result.latest == "1.2.3"
        finally:
            server.shutdown()

    def test_returns_update_available_when_newer_version_exists(self) -> None:
        """Service returns UPDATE_AVAILABLE with latest version from PyPI."""
        server, base_url = _start_server(_PyPIHandlerFactory.ok("2.0.0"))
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UPDATE_AVAILABLE
            assert result.latest == "2.0.0"
        finally:
            server.shutdown()

    def test_returns_skip_on_timeout(self) -> None:
        """Service returns SKIP when the network request times out."""
        # Use a port that refuses connections immediately (no server)
        service = UpdateCheckService(
            pypi_url="http://127.0.0.1:19999/pypi/nwave-ai/json",
            local_version="1.0.0",
            timeout=0.001,  # near-zero timeout forces failure
        )
        result = service.check_for_updates()
        assert result.status == UpdateStatus.SKIP

    def test_returns_skip_on_http_error(self) -> None:
        """Service returns SKIP on non-200 HTTP response."""
        server, base_url = _start_server(_PyPIHandlerFactory.http_error(500))
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.SKIP
        finally:
            server.shutdown()

    def test_returns_skip_on_invalid_json(self) -> None:
        """Service returns SKIP when PyPI response is not valid JSON."""
        server, base_url = _start_server(_PyPIHandlerFactory.bad_json())
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.SKIP
        finally:
            server.shutdown()

    def test_pre_release_version_on_pypi_treated_as_up_to_date(self) -> None:
        """When PyPI returns a pre-release version string, treat as UP_TO_DATE (safe fallback).

        _parse_version raises ValueError on pre-release strings like '2.0.0rc1'
        (which contain non-integer parts). _is_newer catches the error and returns
        False, so the service reports UP_TO_DATE. This is a known limitation —
        documented here to ensure the silent-false behavior remains intentional
        and is not accidentally removed.
        """
        server, base_url = _start_server(_PyPIHandlerFactory.ok("2.0.0rc1"))
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            # Pre-release version cannot be parsed → _is_newer returns False safely
            assert result.status == UpdateStatus.UP_TO_DATE
        finally:
            server.shutdown()
