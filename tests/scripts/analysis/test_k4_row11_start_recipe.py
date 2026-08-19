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

import pytest

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
    host, _, port_s = argv[-1].partition(":")
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


def _install_fake_runserver_venv_python_keyed_on_db_content(
    workspace, *, api_key: str, required_db_content: str
) -> None:
    """Like `_install_fake_runserver_venv_python`, but additionally
    requires the WORKING db file (`pef.DB_FILE_NAME`) to hold
    `required_db_content` at request time -- standing in for the real
    subject's actual defect shape (Run 11: a corrupted API key ROW
    inside the working sqlite file, not a corrupted config value). Lets
    a test prove the restore-precedes-serve ordering the same way the
    real bug was proven: a GET must observe whatever
    `start_and_wait_block` put in the working db file immediately
    before starting the server, never whatever an earlier dispatch left
    there."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    db_path = workspace / pef.DB_FILE_NAME
    script = f"""#!/usr/bin/env python3
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

argv = sys.argv[1:]
if len(argv) >= 3 and argv[0] == "manage.py" and argv[1] == "runserver":
    host, _, port_s = argv[-1].partition(":")
    port = int(port_s)
    expected_api_key = {api_key!r}
    required_db_content = {required_db_content!r}
    db_path = Path({str(db_path)!r})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            db_ok = (
                db_path.exists()
                and db_path.read_text(encoding="utf-8") == required_db_content
            )
            if self.path == "/api/v3/checks/" and (
                self.headers.get("X-Api-Key") == expected_api_key
            ) and db_ok:
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


def _install_pristine_db_snapshot(workspace) -> None:
    """The pristine-DB restore is a precondition `start_and_wait_block`
    now enforces before ANY server start (see
    `test_k4_examiner_fixture.py`'s
    `TestExaminerWalksAPristineSeededDatabase`); these fake-server tests
    stand in for `manage.py runserver`, not for the real seed/migrate
    step, so they provision the snapshot directly -- content is
    irrelevant here, only its PRESENCE is under test by this file."""
    (workspace / "hc.sqlite.pristine").write_text("fake-pristine", encoding="utf-8")


def _install_fake_venv_python_with_failing_migrate(workspace, *, api_key: str) -> None:
    """Like `_install_fake_runserver_venv_python`, but its `manage.py
    migrate --noinput` invocation exits nonzero and logs one line to
    `migrate.log` -- standing in for a real migration that cannot apply
    against the just-restored pristine snapshot (Run 13: the delivery
    adds migrations the pristine snapshot predates). Proves TWO things
    at once: the migrate step is genuinely EXECUTED (the log line exists
    at all) as part of `start_and_wait_block`, and its failure refuses
    LOUD -- the block must never fall through to `runserver` on a
    schema it could not bring current."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    migrate_log = workspace / "migrate.log"
    script = f"""#!/usr/bin/env python3
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

argv = sys.argv[1:]
if len(argv) >= 2 and argv[0] == "manage.py" and argv[1] == "migrate":
    Path({str(migrate_log)!r}).write_text("migrate invoked\\n", encoding="utf-8")
    sys.exit(1)
if len(argv) >= 3 and argv[0] == "manage.py" and argv[1] == "runserver":
    host, _, port_s = argv[-1].partition(":")
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


def _kill_leaked_server(workspace) -> None:
    """The ONE cleanup the `workspace` fixture's own teardown performs --
    factored out so a test can invoke it directly and assert on ITS
    effect (Run 14's `test_no_server_survives_teardown_...`), not merely
    trust the fixture ran. Reads `SERVER_PID_FILE_NAME` (the SAME file
    `start_and_wait_block` itself writes the REAL server's PID into,
    verified empirically to be `$!`'s exact PID, not a setsid wrapper's),
    never a re-derived or guessed PID."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    pid_file = workspace / pef.SERVER_PID_FILE_NAME
    if pid_file.exists():
        pid = pid_file.read_text(encoding="utf-8").strip()
        if pid:
            subprocess.run(["kill", pid], capture_output=True)


@pytest.fixture
def workspace(tmp_path):
    """Run 14 (K4 matrix): `setsid` (Run 12) makes a server started by
    `start_and_wait_block` survive every ancestor's process-group
    teardown BY DESIGN -- exactly the property that makes it useful
    against a real Bash tool call boundary, and exactly what turns a
    forgotten per-test cleanup into a server that outlives its own
    (deleted) `tmp_path` forever, occupying its port for every LATER run
    too. Centralizing teardown HERE, in a fixture's own teardown that
    pytest runs even if the test body raises, makes "a test forgot to
    kill its server" unrepresentable -- no test below needs its own
    try/finally to be correct."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    yield ws
    _kill_leaked_server(ws)


class TestExaminerStartRecipeProvenUnderTheArmEnv:
    """Run 8 (K4 matrix): the examiner burned 40 calls trying to stand up
    a Django dev server and never got evidence. `preflight.
    probe_examiner_start_recipe` proves the examiner's ACTUAL rendered
    recipe (`pef.DOC_NAME`, API key included) starts and answers under
    the SAME rendered env every arm's setup/delivery subprocess already
    runs under -- deterministically, with NO model call, before a single
    expensive turn is spent. One source: the same doc, the same port, the
    same key `nw-user-examiner` would later read."""

    def test_the_mechanism_is_proven_against_the_real_rendered_recipe(self, workspace):
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row11-arm-env-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)

        problems = preflight.probe_examiner_start_recipe(workspace)

        assert problems == []

    def test_a_missing_recipe_doc_is_reported_not_silently_passed(self, workspace):
        """Negative control: row 11's own gap -- no `pef.DOC_NAME` in the
        workspace at all (exactly what every arm's setup produced before
        `fixture_setup_step` was wired in) -- must be REPORTED, never
        silently treated as proven."""
        from scripts.analysis.k4 import preflight

        problems = preflight.probe_examiner_start_recipe(workspace)

        assert problems, (
            "a workspace with no examiner recipe doc must be reported, "
            "not silently treated as proven"
        )

    def test_a_server_that_never_binds_is_reported_not_silently_passed(self, workspace):
        """Negative control: the recipe's own server-start command runs
        but never actually binds the port (a broken/hung interpreter) --
        must be REPORTED, proving the canary genuinely observes the
        server rather than passing unconditionally once a doc exists."""
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

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
        _install_pristine_db_snapshot(workspace)

        problems = preflight.probe_examiner_start_recipe(workspace)

        assert problems, (
            "a server that never binds its port must be reported, not "
            "silently treated as proven"
        )

    def test_probe_genuinely_executes_start_and_wait_block_one_source(
        self, workspace, monkeypatch
    ):
        """One source, proven by dependency, not coincidence: the probe
        must genuinely EXECUTE `pef.start_and_wait_block`'s own output --
        swapping it for a broken block must change the probe's result,
        proving the probe does not carry an independent reimplementation
        that merely happens to behave the same as a working recipe."""
        from scripts.analysis.k4 import preflight
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row11-one-source-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )

        def _broken_block(_port: int, _api_key: str) -> str:
            return "exit 1\n"

        monkeypatch.setattr(pef, "start_and_wait_block", _broken_block)

        problems = preflight.probe_examiner_start_recipe(workspace)

        assert problems, (
            "swapping start_and_wait_block for a broken one must change "
            "the probe's result -- the probe must genuinely execute it, "
            "not carry an independent copy of the same logic"
        )

    def test_survives_across_two_separate_subprocess_calls(self, workspace):
        """Run 9's exact defect, reproduced directly: a server started by
        one subprocess call must still answer from a SECOND, separate
        subprocess call -- not merely respond while the starting process
        is still the one being awaited."""
        import re
        import subprocess

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row11-survives-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)
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

        # Cleanup is the `workspace` fixture's own job now (Run 14) -- it
        # reads the SAME `server.pid` file this block just wrote.
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

    def test_a_corrupted_working_db_is_restored_before_the_first_authenticated_get(
        self, workspace
    ):
        """Run 11 (next incident, same matrix row): an earlier dispatch
        (crafter/troubleshooter/tests) may mutate the working db between
        setup and the examiner's turn -- exactly what an ad-hoc
        troubleshooter script did to a real Project's api_key row,
        undetected across three examiner dispatches. The examiner must
        never observe that mutation: `start_and_wait_block` restores the
        working db from the pristine snapshot BEFORE the server starts,
        so the FIRST authenticated GET a fresh, SEPARATE subprocess call
        makes must already be 200 -- proving restore precedes serve, not
        merely that a restore eventually happens somewhere."""
        import re

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row11-pristine-9c31"
        pristine_content = "pristine-seeded-state"

        _install_fake_runserver_venv_python_keyed_on_db_content(
            workspace, api_key=api_key, required_db_content=pristine_content
        )
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        (workspace / pef.DB_PRISTINE_SNAPSHOT_NAME).write_text(
            pristine_content, encoding="utf-8"
        )
        # The corruption: a later dispatch overwrote the WORKING db with
        # something else entirely, harmlessly, per the real incident.
        (workspace / pef.DB_FILE_NAME).write_text(
            "corrupted-by-an-unrelated-troubleshooter-dispatch", encoding="utf-8"
        )

        block = pef.start_and_wait_block(port, api_key)
        started = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert started.returncode == 0, started.stderr or started.stdout
        assert (workspace / pef.DB_FILE_NAME).read_text(
            encoding="utf-8"
        ) == pristine_content, (
            "the working db must be byte-for-byte restored from the "
            "pristine snapshot before the server was allowed to start"
        )

        pid_match = re.search(r"Server PID: (\d+)", started.stdout)
        assert pid_match, f"no PID printed: {started.stdout!r}"

        # Cleanup is the `workspace` fixture's own job now (Run 14).
        probe = subprocess.run(
            pef.integration_probe_argv(f"http://127.0.0.1:{port}", api_key),
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert probe.returncode == 0, (
            "the examiner's FIRST authenticated GET, from a SEPARATE "
            "subprocess call, must already succeed -- the working db "
            "was restored from the pristine snapshot before serving: "
            f"{probe.stdout!r} {probe.stderr!r}"
        )

    def test_a_missing_pristine_snapshot_refuses_loud_instead_of_serving_the_working_db_as_is(
        self, workspace
    ):
        """Negative control: without a pristine snapshot to restore from,
        the block must refuse LOUD -- never silently start against
        whatever the working db currently holds. Silently serving is
        exactly how the real corruption incident went undetected across
        three examiner dispatches."""
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row11-missing-snapshot-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        # Deliberately NO pristine snapshot installed.

        block = pef.start_and_wait_block(port, api_key)
        result = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode != 0, (
            "a missing pristine snapshot must refuse LOUD, never silently "
            "start the server against whatever the working db holds"
        )
        assert pef.DB_PRISTINE_SNAPSHOT_NAME in (result.stderr or ""), (
            "the refusal must name the missing snapshot file"
        )

    def test_migrate_runs_after_the_pristine_restore_and_before_the_server_starts(
        self, workspace
    ):
        """Run 13 (K4 matrix): a delivery adds migrations the pristine
        snapshot -- taken once, right after the ORIGINAL seed -- predates.
        `start_and_wait_block` must genuinely EXECUTE `manage.py migrate
        --noinput` against the just-restored working db, and refuse LOUD
        rather than ever starting `runserver` on a schema it could not
        bring current."""
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row13-migrate-9c31"
        _install_fake_venv_python_with_failing_migrate(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)

        block = pef.start_and_wait_block(port, api_key)
        result = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert (workspace / "migrate.log").exists(), (
            "the block must genuinely EXECUTE the migrate step against "
            "the restored working db, not merely quote it in the rendered "
            "doc -- the fake migrate never ran"
        )
        assert result.returncode != 0, (
            "a migrate failure against the just-restored working db must "
            "refuse LOUD, never silently fall through to starting the "
            "server on a schema it could not bring current"
        )
        assert not (workspace / pef.SERVER_PID_FILE_NAME).exists(), (
            "the server must never start when the migrate step ahead of it failed"
        )

    def test_starting_the_block_twice_in_a_row_does_not_fail(self, workspace):
        """Run 14 (K4 matrix): the block's own stale-server-kill guard
        (`if -f server.pid && kill -0 ...; then kill ...; fi`) must make
        a SECOND run against the SAME workspace/port succeed too --
        proving restart is idempotent, not merely that a fresh start
        works once. A block that failed on the second run would be
        exactly the shape a retried/re-dispatched examiner turn hits."""
        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row14-restart-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)
        block = pef.start_and_wait_block(port, api_key)

        first = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert first.returncode == 0, first.stderr or first.stdout

        second = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert second.returncode == 0, (
            "running the block a SECOND time against the same "
            f"workspace/port must succeed too: {second.stderr or second.stdout}"
        )

        probe = subprocess.run(
            pef.integration_probe_argv(f"http://127.0.0.1:{port}", api_key),
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert probe.returncode == 0, (
            "the server the SECOND run started must genuinely be "
            f"reachable: {probe.stdout!r} {probe.stderr!r}"
        )

    def test_no_server_survives_teardown_even_when_the_test_never_cleaned_up(
        self, workspace
    ):
        """Run 14 (K4 matrix): prove the teardown MECHANISM itself, not
        merely that `_kill_leaked_server` exists -- start a real
        `setsid`'d server and do NOTHING to clean it up (no try/finally,
        exactly the omission that leaked Run 14's servers), confirm it
        is genuinely alive, then confirm `_kill_leaked_server` -- the
        SAME function the `workspace` fixture's own teardown calls --
        leaves no such process running."""
        import os
        import time

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row14-teardown-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)
        block = pef.start_and_wait_block(port, api_key)

        # Deliberately NO try/finally here.
        started = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert started.returncode == 0, started.stderr or started.stdout
        pid = int(
            (workspace / pef.SERVER_PID_FILE_NAME).read_text(encoding="utf-8").strip()
        )

        # Confirm it is genuinely alive first -- a teardown that
        # "succeeds" against an already-dead PID proves nothing.
        os.kill(pid, 0)

        _kill_leaked_server(workspace)
        for _ in range(10):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.5)
        else:
            raise AssertionError(
                f"PID {pid} was still alive 5s after _kill_leaked_server ran"
            )

    def test_restore_verify_migrate_window_is_lock_serialized_against_concurrent_writers(
        self, workspace
    ):
        """Stable-design report 2026-08-19 Sec.1.4: the SAME single-writer
        discipline `des commit` uses (`fcntl.flock`) now guards the
        restore + hash-verify + migrate window -- an external holder of
        the SAME lock file (`pef.DB_LOCK_FILE_NAME`) must genuinely
        BLOCK the block's own restore step, not merely coexist with it
        by luck. Proven via real `flock` blocking (timing + a mid-hold
        liveness check), never a grep for the word `flock` in the
        rendered text."""
        import time

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row14-lock-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)
        block = pef.start_and_wait_block(port, api_key)

        lock_path = workspace / pef.DB_LOCK_FILE_NAME
        holder = subprocess.Popen(["flock", "-x", str(lock_path), "-c", "sleep 3"])
        time.sleep(0.5)  # give the holder a real head start acquiring it

        started_at = time.monotonic()
        blocked_proc = subprocess.Popen(
            ["bash", "-c", block],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(1.0)
        assert not (workspace / pef.SERVER_PID_FILE_NAME).exists(), (
            "the block must genuinely BLOCK on the held lock, not proceed "
            "past the restore window while a concurrent writer holds it"
        )

        holder.wait(timeout=5)
        stdout, stderr = blocked_proc.communicate(timeout=40)
        elapsed = time.monotonic() - started_at

        assert blocked_proc.returncode == 0, stderr or stdout
        assert elapsed >= 2.0, (
            f"the block returned after only {elapsed:.2f}s -- it must have "
            "waited for the external holder to release the lock, not "
            "raced past it"
        )

    def test_a_restored_db_that_does_not_match_the_pristine_hash_refuses_loud(
        self, workspace
    ):
        """Stable-design report 2026-08-19 Sec.1.4: the working db is
        hash-verified against the pristine snapshot immediately after
        the restore -- a `cp` that (for whatever reason) does not
        produce a byte-identical copy must refuse LOUD before ever
        reaching migrate or runserver, never silently serve from an
        unverified copy. The examiner's server now starts ONLY from a
        copy PROVEN identical to the pristine snapshot, by construction."""
        import os

        from scripts.analysis.k4 import prepare_examiner_fixture as pef

        port = pef.free_port()
        api_key = "k4-row14-hash-9c31"
        _install_fake_runserver_venv_python(workspace, api_key=api_key)
        (workspace / pef.DOC_NAME).write_text(
            pef._render(port, api_key), encoding="utf-8"
        )
        _install_pristine_db_snapshot(workspace)

        # A fake `cp` that always writes garbage regardless of its real
        # arguments -- simulates a restore that silently did NOT
        # actually copy the pristine bytes (disk issue, truncated
        # write, a future refactor that breaks the copy step).
        fake_bin = workspace / "fake-bin"
        fake_bin.mkdir()
        fake_cp = fake_bin / "cp"
        fake_cp.write_text(
            '#!/bin/sh\necho garbage-not-the-pristine-content > "$2"\n',
            encoding="utf-8",
        )
        fake_cp.chmod(0o755)

        block = pef.start_and_wait_block(port, api_key)
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
        result = subprocess.run(
            ["bash", "-c", block],
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode != 0, (
            "a restored db that does not match the pristine hash must "
            "refuse LOUD, never silently proceed to migrate/serve"
        )
        assert "hash" in (result.stderr or "").lower(), (
            "the refusal must name the hash mismatch"
        )
        assert not (workspace / pef.SERVER_PID_FILE_NAME).exists(), (
            "the server must never start when the restored db failed hash verification"
        )
