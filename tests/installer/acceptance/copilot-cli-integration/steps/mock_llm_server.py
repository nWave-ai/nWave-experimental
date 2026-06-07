"""Minimal OpenAI-compatible SSE mock server for the Copilot CLI e2e harness.

slice-02 e2e firing proof. Recreated from the spike artifact
``/tmp/copilot-probe/mock-llm-tool.py`` (cleaned up after the spike, see
docs/analysis/copilot-cli-prereq-spike-2026-05-28.md §6). The real ``copilot``
binary, when pointed at this server via ``COPILOT_PROVIDER_BASE_URL`` +
``COPILOT_OFFLINE=true``, will run a full session lifecycle against it without a
GitHub account or a real model — which lets the e2e prove that an installed hook
FIRES end-to-end.

This server answers the single OpenAI Chat Completions streaming endpoint
(``POST /chat/completions``, also tolerant of the ``/v1/`` prefix) with a tiny
SSE stream that emits one short assistant text delta then ``[DONE]``. It
deliberately does NOT emit a tool_call — the spike established that mock
tool-dispatch is NOT exercisable within the session-bootstrap timeout (the
reason slice-02 pins the firing proof to ``sessionStart``, which fires reliably,
rather than ``preToolUse``).

Determinism contract (flake mitigation):
  - The server binds to an EPHEMERAL port (``127.0.0.1:0``) chosen by the OS, so
    parallel test runs never collide on a fixed port.
  - ``base_url`` is only published AFTER the listening socket is bound, and the
    harness performs an explicit readiness probe before invoking ``copilot``
    (see ``e2e_composition.CopilotE2EFixture._await_server_ready``).
  - All request handling is synchronous and side-effect-free; the server keeps no
    state between requests.

Pure-stdlib (``http.server`` + ``threading``) — no extra dependency. Layer 4+
(real-binary e2e); traditional assertions, no state-delta universe guard
(Mandate 8 applies to layers 1-3 only).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

# A single short assistant message, streamed as one delta then [DONE]. Enough for
# the Copilot session loop to complete a -p turn; no tool_call (see module docs).
_REPLY_TEXT = "ok"


def _chat_completion_chunk(
    content: str | None, finish: str | None, role: str | None = None
) -> str:
    """Render one OpenAI-style streaming chunk as an SSE ``data:`` line."""
    delta: dict = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    chunk = {
        "id": "mock-cmpl-0",
        "object": "chat.completion.chunk",
        "model": "probe-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(chunk)}\n\n"


class _MockLLMHandler(BaseHTTPRequestHandler):
    """Answers chat-completions with a tiny deterministic SSE stream.

    HTTP/1.1 with an explicit Content-Length per response. The default HTTP/1.0
    signals body-end by closing the connection, which empirically produced an
    EMPTY body for the streaming reader (copilot's OpenAI client saw no chunks
    and retried into "server error"); HTTP/1.1 + a fully-built body + a
    Content-Length is deterministic.
    """

    protocol_version = "HTTP/1.1"

    # Silence the default stderr request logging (keeps the test output clean).
    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _is_chat_path(self) -> bool:
        return self.path.rstrip("/").endswith("chat/completions")

    def _send_body(self, status: int, ctype: str, body: bytes) -> None:
        """Send a complete response with an explicit Content-Length (HTTP/1.1)."""
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self) -> None:
        # Readiness probe endpoint — any GET returns 200 so the harness can
        # confirm the listener is up before launching copilot.
        self._send_body(200, "application/json", b'{"status":"ready"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length:
            self.rfile.read(length)  # drain body; content is irrelevant to the mock

        if not self._is_chat_path():
            self._send_body(404, "application/json", b'{"error":"not found"}')
            return

        # First delta carries role (OpenAI clients expect it), then content, then
        # the stop chunk and the [DONE] sentinel — the full SSE body built up front.
        body = (
            _chat_completion_chunk(_REPLY_TEXT, None, role="assistant")
            + _chat_completion_chunk(None, "stop")
            + "data: [DONE]\n\n"
        ).encode("utf-8")
        self._send_body(200, "text/event-stream", body)


class MockLLMServer:
    """A context-managed, ephemeral-port, OpenAI-compatible SSE mock server.

    Usage:
        with MockLLMServer() as server:
            base_url = server.base_url   # e.g. "http://127.0.0.1:54321"
            ...

    The server runs on a daemon thread and is torn down on context exit.
    """

    def __init__(self) -> None:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _MockLLMHandler)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> MockLLMServer:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="mock-llm-server", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> MockLLMServer:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()
