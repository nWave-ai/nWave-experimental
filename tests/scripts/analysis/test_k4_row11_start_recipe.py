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

import subprocess
import threading
from http.server import ThreadingHTTPServer

from scripts.analysis.k4 import prepare_examiner_fixture as pef


def test_the_rendered_start_recipe_is_executable_against_a_running_server():
    port = pef.free_port()
    api_key = "k4-fixture-recipe-9c31"
    base_url = f"http://127.0.0.1:{port}"

    server = ThreadingHTTPServer(
        ("127.0.0.1", port), pef.make_checks_list_handler(api_key)
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
        dead_port = pef.free_port()
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


def _install_fake_runserver_venv_python(workspace, *, api_key: str) -> None:
    """A fake clone-local interpreter that answers ONLY `manage.py
    runserver <host>:<port>` (the ONE command
    `preflight.probe_examiner_start_recipe` actually executes) by binding
    a real stdlib HTTP server that plays healthchecks' `GET
    /api/v3/checks/` -- the SAME response shape
    `pef.make_checks_list_handler` produces, reimplemented here as a
    standalone subprocess script since it must run in its OWN
    interpreter, not import this test's process."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    script = f"""#!/usr/bin/env python3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

argv = sys.argv[1:]
if len(argv) >= 3 and argv[0] == "manage.py" and argv[1] == "runserver":
    host, _, port_s = argv[2].partition(":")
    port = int(port_s)
    expected_api_key = {api_key!r}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/v3/checks/" and (
                self.headers.get("X-Api-Key") == expected_api_key
            ):
                body = b'{{"checks": []}}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(403)
                self.end_headers()

        def log_message(self, *_args):
            pass

    ThreadingHTTPServer((host, port), Handler).serve_forever()
sys.exit(0)
"""
    venv_python.write_text(script, encoding="utf-8")
    venv_python.chmod(0o755)


class TestExaminerStartRecipeProvenUnderTheArmEnv:
    """Run 8 (K4 matrix): the examiner burned 40 calls trying to stand up
    a Django dev server and never got evidence. `preflight.
    probe_examiner_start_recipe` proves the examiner's ACTUAL rendered
    recipe (`pef.DOC_NAME`, API key included) starts and answers under
    the SAME rendered env every arm's setup/delivery subprocess already
    runs under -- deterministically, with NO model call, before a single
    expensive turn is spent. One source: the same doc, the same port, the
    same key `nw-user-examiner` would later read."""

    def test_the_mechanism_is_proven_against_the_real_rendered_recipe(self, tmp_path):
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        port = pef.free_port()
        api_key = "k4-row11-arm-env-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )

        problems = preflight.probe_examiner_start_recipe(workspace, port=port)

        assert problems == []

    def test_a_missing_recipe_doc_is_reported_not_silently_passed(self, tmp_path):
        """Negative control: row 11's own gap -- no `pef.DOC_NAME` in the
        workspace at all (exactly what every arm's setup produced before
        `fixture_setup_step` was wired in) -- must be REPORTED, never
        silently treated as proven."""
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        problems = preflight.probe_examiner_start_recipe(
            workspace, port=pef.free_port()
        )

        assert problems, (
            "a workspace with no examiner recipe doc must be reported, "
            "not silently treated as proven"
        )

    def test_a_server_that_never_binds_is_reported_not_silently_passed(self, tmp_path):
        """Negative control: the recipe's own server-start command runs
        but never actually binds the port (a broken/hung interpreter) --
        must be REPORTED, proving the canary genuinely observes the
        server rather than passing unconditionally once a doc exists."""
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        port = pef.free_port()
        api_key = "k4-row11-arm-env-broken"
        venv_python = workspace / pef.VENV_PYTHON
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text(
            "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n",
            encoding="utf-8",
        )
        venv_python.chmod(0o755)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )

        problems = preflight.probe_examiner_start_recipe(workspace, port=port)

        assert problems, (
            "a server that never binds its port must be reported, not "
            "silently treated as proven"
        )

    def test_probe_genuinely_executes_start_and_wait_block_one_source(
        self, tmp_path, monkeypatch
    ):
        """One source, proven by dependency, not coincidence: the probe
        must genuinely EXECUTE `pef.start_and_wait_block`'s own output --
        swapping it for a broken block must change the probe's result,
        proving the probe does not carry an independent reimplementation
        that merely happens to behave the same as a working recipe."""
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        port = pef.free_port()
        api_key = "k4-row11-one-source-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )

        def _broken_block(_port: int, _api_key: str) -> str:
            return "exit 1\n"

        monkeypatch.setattr(pef, "start_and_wait_block", _broken_block)

        problems = preflight.probe_examiner_start_recipe(workspace, port=port)

        assert problems, (
            "swapping start_and_wait_block for a broken one must change "
            "the probe's result -- the probe must genuinely execute it, "
            "not carry an independent copy of the same logic"
        )

    def test_survives_across_two_separate_subprocess_calls(self, tmp_path):
        """Run 9's exact defect, reproduced directly: a server started by
        one subprocess call must still answer from a SECOND, separate
        subprocess call -- not merely respond while the starting process
        is still the one being awaited."""
        import re
        import subprocess

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        port = pef.free_port()
        api_key = "k4-row11-survives-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        block = pef.start_and_wait_block(port, api_key)

        first = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert first.returncode == 0, first.stderr or first.stdout
        pid_match = re.search(r"Server PID: (\d+)", first.stdout)
        assert pid_match, f"no PID printed: {first.stdout!r}"
        pid = pid_match.group(1)

        try:
            second = subprocess.run(
                pef.integration_probe_argv(f"http://127.0.0.1:{port}", api_key),
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert second.returncode == 0, (
                "a SEPARATE subprocess call must still reach the server "
                f"the first call started: {second.stdout!r} {second.stderr!r}"
            )
        finally:
            subprocess.run(["kill", pid], capture_output=True)
