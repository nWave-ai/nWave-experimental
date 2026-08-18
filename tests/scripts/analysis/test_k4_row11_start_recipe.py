"""K4 matrix row 11 -- missing executable start recipe.

First divergence: the value authority lacked a public start recipe, so the
Examiner correctly returned INDETERMINATE rather than PASS/FAIL.
`prepare_examiner_fixture.py`'s `_render` (lines ~182-197) already carries a
real recipe -- CLI argv, localhost Base URL, and HTTP journeys -- and
`integration_probe_argv` already builds a runnable probe against it. But
`test_k4_examiner_fixture.py` only ever asserts the recipe's TEXT
(`test_rendered_doc_is_a_public_only_user_environment_recipe`) and the
probe's ARGV SHAPE (`test_integration_probe_contract_authenticates_get_list_
against_a_real_clone`, deliberately "no clone, no network, no server").
Nothing has ever actually started a server and fired the probe at it.

ADMISSION: the start recipe is present in the value authority AND
executable. This is the executability half.

The real Django subject (healthchecks) is NOT checked out in this
worktree, is not a project dependency, and cloning + migrating it for a
unit test would make the suite depend on network access and a full Django
install -- outside this harness's Python-only-tooling portability
constraint. A minimal stdlib `http.server` stands in for `manage.py
runserver` instead, serving exactly the ONE journey `integration_probe_
argv` actually targets today: authenticated `GET {base}/api/v3/checks/`
(the List journey). `integration_probe_argv` has no parameter for journey
choice, so it does not exercise the doc's separately-listed Readback
(`GET {base}/api/v3/checks/<uuid>`), Create, Update, or Invalid-input
journeys -- those have no executable probe function today; extending
`integration_probe_argv` to cover them is future scope, not claimed here.

Discriminating power comes first, inside the same test: the SAME argv
constructor fed a wrong API key, and fed a port nothing listens on, must
both FAIL -- proving the probe genuinely observes the server rather than
passing unconditionally. Only then does the real rendered recipe, run
VERBATIM and unmodified through `integration_probe_argv`, get asserted to
succeed against the live fake server.
"""

from __future__ import annotations

import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.analysis.k4 import prepare_examiner_fixture as pef


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _make_checks_list_handler(expected_api_key: str):
    """A stand-in for healthchecks' `GET /api/v3/checks/` -- 200 with a
    non-empty JSON body when `X-Api-Key` matches, 403 otherwise. This is
    the ONE journey `integration_probe_argv` targets; see module docstring
    for what it does NOT cover."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/v3/checks/" and (
                self.headers.get("X-Api-Key") == expected_api_key
            ):
                body = b'{"checks": []}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(403)
                self.end_headers()

        def log_message(self, *_args: object) -> None:
            pass  # keep test output quiet; failures are asserted, not printed

    return _Handler


def test_the_rendered_start_recipe_is_executable_against_a_running_server():
    port = _free_port()
    api_key = "k4-fixture-recipe-9c31"
    base_url = f"http://127.0.0.1:{port}"

    server = ThreadingHTTPServer(
        ("127.0.0.1", port), _make_checks_list_handler(api_key)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Negative control 1: wrong API key -- the recipe's own doc renders
        # the credential the probe must present; a probe that succeeds
        # without it would prove nothing about the recipe being correct.
        wrong_key_argv = pef.integration_probe_argv(base_url, "not-the-real-key")
        wrong_key = subprocess.run(
            wrong_key_argv, capture_output=True, text=True, timeout=10
        )
        assert wrong_key.returncode != 0, (
            "the probe must FAIL with the wrong API key -- a probe that "
            "passes regardless of credential proves nothing about the "
            "recipe's start-and-authenticate chain"
        )

        # Negative control 2: nothing is listening on this port -- the
        # recipe's Base URL is load-bearing, not decorative.
        dead_port = _free_port()
        assert dead_port != port
        wrong_port_argv = pef.integration_probe_argv(
            f"http://127.0.0.1:{dead_port}", api_key
        )
        wrong_port = subprocess.run(
            wrong_port_argv, capture_output=True, text=True, timeout=10
        )
        assert wrong_port.returncode != 0, (
            "the probe must FAIL against a port nothing is listening on"
        )

        # Positive: the real rendered doc's recipe, run VERBATIM through
        # integration_probe_argv unmodified, against a real running server.
        rendered = pef._render(port, api_key)
        assert base_url in rendered
        assert f"API key: {api_key}" in rendered

        argv = pef.integration_probe_argv(base_url, api_key)
        done = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        assert done.returncode == 0, (
            "the rendered start recipe's probe must succeed against a real "
            f"running server: stdout={done.stdout!r} stderr={done.stderr!r}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
