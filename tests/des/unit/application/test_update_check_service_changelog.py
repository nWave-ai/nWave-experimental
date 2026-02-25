"""Unit tests for UpdateCheckService - changelog fetch.

Tests the changelog fetch behavior through the public API (check_for_updates),
verifying observable outcomes at the driven port boundary (GitHub API injection).

Test Budget: 4 behaviors x 2 = 8 max unit tests. Actual: 4 tests.

Behaviors:
1. Returns release notes when GitHub API responds with matching tag
2. Returns version-only result when GitHub API times out or fails
3. Returns version-only result when no release tag matches the latest version
4. Changelog is capped at 2000 chars to protect additionalContext token budget
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import urlparse

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


def make_github_release_response(tag: str, body: str) -> bytes:
    """Return a minimal GitHub release JSON response bytes."""
    payload: dict[str, Any] = {"tag_name": tag, "body": body}
    return json.dumps(payload).encode("utf-8")


class _DualEndpointHandler(BaseHTTPRequestHandler):
    """Request handler serving both PyPI and GitHub release endpoints."""

    pypi_version: str = "2.0.0"
    github_tag: str = "v2.0.0"
    github_body: str = "## What's New\n- Feature A\n- Bug fix B"
    github_status: int = 200

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if "/pypi/" in path:
            self._serve_pypi()
        elif "/releases/latest" in path or "/releases/tags/" in path:
            self._serve_github()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_pypi(self) -> None:
        body = make_pypi_response(self.__class__.pypi_version)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_github(self) -> None:
        if self.__class__.github_status != 200:
            self.send_response(self.__class__.github_status)
            self.end_headers()
            return
        body = make_github_release_response(
            self.__class__.github_tag, self.__class__.github_body
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: Any) -> None:  # suppress server logs
        pass


class _NoTagMatchHandler(BaseHTTPRequestHandler):
    """Handler that returns a release with a non-matching tag."""

    pypi_version: str = "2.0.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if "/pypi/" in path:
            body = make_pypi_response(self.__class__.pypi_version)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif "/releases/" in path:
            # Return release with a different tag (no match)
            payload = {"tag_name": "v99.0.0", "body": "unrelated release"}
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_: Any) -> None:
        pass


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
# Tests
# ---------------------------------------------------------------------------


class TestUpdateCheckServiceChangelog:
    """Tests: UpdateCheckService returns changelog when GitHub API responds."""

    def test_returns_release_notes_when_github_responds_with_matching_tag(
        self,
    ) -> None:
        """Service returns changelog when GitHub API has a release for the latest tag."""

        class Handler(_DualEndpointHandler):
            pypi_version = "2.0.0"
            github_tag = "v2.0.0"
            github_body = "## What's New\n- Feature A"
            github_status = 200

        server, base_url = _start_server(Handler)
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                github_releases_url=f"{base_url}/repos/nwave/releases/latest",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UPDATE_AVAILABLE
            assert result.latest == "2.0.0"
            assert result.changelog == "## What's New\n- Feature A"
        finally:
            server.shutdown()

    def test_returns_version_only_when_github_api_fails(self) -> None:
        """Service returns version-only result when GitHub API returns an error."""

        class Handler(_DualEndpointHandler):
            pypi_version = "2.0.0"
            github_tag = "v2.0.0"
            github_body = ""
            github_status = 500

        server, base_url = _start_server(Handler)
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                github_releases_url=f"{base_url}/repos/nwave/releases/latest",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UPDATE_AVAILABLE
            assert result.latest == "2.0.0"
            assert result.changelog is None
        finally:
            server.shutdown()

    def test_returns_version_only_when_no_release_tag_matches(self) -> None:
        """Service returns version-only result when GitHub tag does not match latest."""
        server, base_url = _start_server(_NoTagMatchHandler)
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                github_releases_url=f"{base_url}/repos/nwave/releases/latest",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UPDATE_AVAILABLE
            assert result.latest == "2.0.0"
            assert result.changelog is None
        finally:
            server.shutdown()

    def test_changelog_is_capped_at_2000_chars(self) -> None:
        """Changelog injected into additionalContext is capped at 2000 characters.

        A GitHub release body longer than 2000 chars must be truncated before
        being returned, protecting the additionalContext token budget.
        """
        long_body = "A" * 3000  # 3000 chars — exceeds cap

        class LongBodyHandler(_DualEndpointHandler):
            pypi_version = "2.0.0"
            github_tag = "v2.0.0"
            github_body = long_body
            github_status = 200

        server, base_url = _start_server(LongBodyHandler)
        try:
            service = UpdateCheckService(
                pypi_url=f"{base_url}/pypi/nwave-ai/json",
                github_releases_url=f"{base_url}/repos/nwave/releases/latest",
                local_version="1.0.0",
            )
            result = service.check_for_updates()
            assert result.status == UpdateStatus.UPDATE_AVAILABLE
            assert result.changelog is not None
            assert len(result.changelog) <= 2000, (
                f"Changelog exceeds 2000 chars: {len(result.changelog)}"
            )
        finally:
            server.shutdown()
