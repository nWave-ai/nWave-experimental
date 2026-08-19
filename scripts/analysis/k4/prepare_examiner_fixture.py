#!/usr/bin/env python3
"""Render the ONE public-facing user-environment doc a K4 examiner reads.

Drives the state transition `Unprovisioned -> Migrated -> Seeded(key) ->
documented` through a fixture-owned, clone-local Python environment: migrate
the isolated clone, idempotently seed a user/project with one deterministic
read/write API key, then render a plain user onboarding doc carrying only
the public run recipe, localhost base URL, the SEED-PRODUCED key, and
concise HTTP journeys -- never a source path, model/storage symbol, expected
verdict, or hidden-acceptance fact. The port stays a parameter.

Run 11 (K4 matrix): the examiner's documented key rejected every request --
the DB's ONE Project row held a literal 32-`Y` placeholder, structurally
incapable of matching `compare_api_key`'s stored-hash format for ANY input.
Root cause: NOT this seed step (`project.set_api_key()` -- the subject's own
code path, `hc/accounts/models.py`'s `_make_api_key`/`set_api_key` -- was and
remains correct, reproduced live against the real Run 11 checkout while
diagnosing this). An UNRELATED troubleshooter dispatch, debugging a
different PUT-crash defect much later in the same run, ran its own ad-hoc
`p.api_key = 'Y' * 32; p.save()` directly against the shared fixture DB --
overwriting the correctly-seeded row for its own reproduction convenience,
permanently corrupting the fixture state three later examiner dispatches
then inherited. `_SEED_CODE` now self-verifies immediately after writing:
`refresh_from_db()` then `compare_api_key(raw)` must hold, or the seed step
itself exits nonzero rather than ever printing/documenting an unproven key.
This closes the "seed step lies" class of defect.

CLOSED (same matrix row, next incident): "a later dispatch corrupts shared
fixture state after a correct seed" -- a troubleshooter, debugging an
UNRELATED bug, ran `p.api_key = 'Y' * 32; p.save()` directly against the
shared working DB, and three later examiner dispatches inherited the
corruption. `prepare()` now snapshots the just-seeded, just-verified DB to
a READ-ONLY pristine copy (`DB_PRISTINE_SNAPSHOT_NAME`) right after
`_seed()` succeeds; `start_and_wait_block` (quoted in the rendered doc AND
executed by `preflight.probe_examiner_start_recipe`, one source either
way) restores the WORKING db from that pristine copy -- refusing LOUD if
the snapshot is missing -- before every server start. Any earlier
dispatch (crafter/troubleshooter/tests) may still mutate the working DB;
it no longer matters, because the examiner never walks against it -- only
ever against a byte-for-byte restore of the pristine, self-verified seed.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from scripts.analysis.k4 import subject as k4_subject


#: The doc a blind examiner reads, framed as user-facing, not examiner-labelled.
DOC_NAME = ".k4-user-environment.md"

#: Declared, arm-specific high ports so control and nwave fixtures can run
#: side by side without colliding on one port.
CONTROL_PORT = 18771
NWAVE_PORT = 18772

#: healthchecks' own default sqlite path (`hc/settings.py`:
#: `BASE_DIR / "hc.sqlite"`, `BASE_DIR` == this workspace root) -- the ONE
#: working DB every dispatch (crafter, troubleshooter, tests, the
#: examiner) reads/writes through `manage.py`.
DB_FILE_NAME = "hc.sqlite"

#: A read-only copy of `DB_FILE_NAME`, taken right after `_seed()`
#: succeeds -- the ONE known-good state `start_and_wait_block` restores
#: the working DB from before every server start, so any earlier
#: dispatch's mutation to the working DB (Run 11: a troubleshooter
#: overwrote the seeded Project's api_key directly, debugging an
#: unrelated bug) never reaches the examiner.
DB_PRISTINE_SNAPSHOT_NAME = "hc.sqlite.pristine"

#: Fixture-owned clone-local venv, workspace-relative. Never the operator's
#: own environment -- migrate/seed/runserver all run through this.
_VENV_DIR_NAME = "k4-fixture-venv"
VENV_PYTHON = f"{_VENV_DIR_NAME}/bin/python"

MIGRATE_ARGV = ["migrate", "--noinput"]

_SEED_CODE = (
    "import os\n"
    "import sys\n"
    "from django.contrib.auth import get_user_model\n"
    "from hc.accounts.models import Project\n"
    "User = get_user_model()\n"
    "user, _ = User.objects.get_or_create(\n"
    "    username='k4', defaults={'email': 'k4@example.test'}\n"
    ")\n"
    "project, _ = Project.objects.get_or_create(owner=user)\n"
    "existing = os.environ.get('K4_EXISTING_API_KEY')\n"
    "if existing and project.compare_api_key(existing):\n"
    "    print(existing)\n"
    "else:\n"
    "    raw = project.set_api_key()\n"
    "    project.save()\n"
    "    project.refresh_from_db()\n"
    "    if not project.compare_api_key(raw):\n"
    "        sys.stderr.write(\n"
    "            'SEED VERIFICATION FAILED: the just-written api_key does '\n"
    "            'not authenticate against its own just-generated raw key, '\n"
    "            'even immediately after refresh_from_db()\\n'\n"
    "        )\n"
    "        sys.exit(1)\n"
    "    print(raw)\n"
)

#: Final element is the complete shell code argument, per the test fake's
#: contract: it logs the full argv it receives and treats the LAST SEED_ARGV
#: element as the marker to search that log for.
SEED_ARGV = ["shell", "-c", _SEED_CODE]


#: `_run` owns dependency install/migrate, both of which can legitimately
#: take a while; `_seed` is one Django shell invocation and gets a much
#: tighter bound.
_SETUP_TIMEOUT = 1800
_SEED_TIMEOUT = 300


def make_checks_list_handler(expected_api_key: str) -> type[BaseHTTPRequestHandler]:
    """A stdlib stand-in for healthchecks' `GET /api/v3/checks/` -- 200
    with a non-empty JSON body when `X-Api-Key` matches, 403 otherwise.

    The ONE handler both `test_k4_row11_start_recipe.py` (the recipe's own
    executability proof, no arm env involved) and
    `preflight.probe_examiner_start_recipe` (the SAME proof run through the
    arm's rendered env, before any model call) build their fake server
    from -- never a second hand-typed copy of the same 15 lines.
    """

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
            pass  # keep runs quiet; failures are asserted/reported, not printed

    return _Handler


def _run(argv: list[str], cwd: Path, timeout: int = _SETUP_TIMEOUT) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    return done.returncode, (done.stderr or done.stdout)[-800:]


#: Packages `requirements-dev.txt` names that this fixture never installs --
#: see `_ensure_venv`'s inline note for the measured incident (a real
#: install attempt failed building `mysqlclient` for lack of MySQL client
#: headers) and the verification that nothing in the subject's own package
#: or test suite imports it. A named, single-item exclusion, not a policy:
#: if the pinned revision ever adds a genuinely-needed unbuildable package,
#: this set is the wrong tool -- that needs a real fix (a system package, or
#: dropping the pin), not a silent addition here.
_DEV_REQUIREMENTS_SKIP = frozenset({"mysqlclient"})

_REQUIREMENT_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+")


def _dev_requirement_lines_excluding_unbuildable(text: str) -> list[str]:
    """`requirements-dev.txt`'s own lines, verbatim, minus any whose package
    name is in `_DEV_REQUIREMENTS_SKIP`. Comments and blank lines are
    dropped; every other line (an exact pin, an extras marker, a hash) is
    preserved byte-for-byte -- this never rewrites a requirement, only
    omits whole lines."""
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQUIREMENT_NAME_RE.match(line)
        name = match.group(0) if match else line
        if name in _DEV_REQUIREMENTS_SKIP:
            continue
        kept.append(line)
    return kept


def _port_is_occupied(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return True
    finally:
        sock.close()
    return False


def free_port() -> int:
    """One OS-assigned free port on 127.0.0.1 -- the ONE source
    `test_k4_row11_start_recipe.py` and `preflight.probe_examiner_start_
    recipe` both use to stand up their fake server, never a second
    hand-typed bind-and-release copy."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _ensure_venv(workspace: Path) -> Path:
    """Return the fixture-owned interpreter, creating+installing it only if
    it does not already exist -- a test-provided fake is never replaced."""
    venv_python = workspace / VENV_PYTHON
    if venv_python.exists():
        return venv_python
    venv_dir = workspace / _VENV_DIR_NAME
    code, tail = _run([sys.executable, "-m", "venv", str(venv_dir)], workspace)
    if code != 0:
        raise SystemExit(
            f"WHAT: could not create the fixture-owned clone-local venv at {venv_dir}.\n"
            "WHY:  migrate/seed/runserver must run through an isolated interpreter, "
            "never the operator's own environment.\n"
            f"HOW:  reproduce `{sys.executable} -m venv {venv_dir}` and read the "
            f"error below.\n{tail}"
        )
    pip = venv_dir / "bin" / "pip"
    req = "requirements.txt"
    code, tail = _run([str(pip), "install", "-q", "-r", req], workspace)
    if code != 0:
        raise SystemExit(
            f"WHAT: could not install {req} into the fixture venv.\n"
            "WHY:  migrate/seed need the subject's own declared dependencies, "
            "installed symmetrically outside timed delivery.\n"
            f"HOW:  reproduce `{pip} install -r {req}` in {workspace} and read "
            f"the error below.\n{tail}"
        )
    # Row 4 (K4 matrix): a real BASELINE run hit `ModuleNotFoundError: No
    # module named 'time_machine'` importing the SUBJECT's own pre-existing
    # `hc/api/tests/test_sendalerts.py` -- declared in requirements-dev.txt
    # (test-only deps), never installed here. BASELINE runs network-
    # sandboxed (see `_render_sandbox_settings`'s allowedDomains), so a gap
    # discovered mid-delivery cannot be repaired there; installing it HERE,
    # once, at setup time (network available, workspace still the pristine
    # pinned-revision clone -- no delivery-added drift possible yet), closes
    # it before a single model call is spent. Unlike `run_acceptance.py`'s
    # POST-delivery `_dev_requirements_delta` (which deliberately installs
    # only what a delivery itself ADDED, to avoid a pre-existing dev dep
    # needing an unavailable system package failing a snapshot that has
    # nothing to do with the delivery under test), there is no delivery yet
    # to isolate from here -- but the SAME class of hazard still applies to
    # the whole file at setup time: a real attempt to install the pinned
    # revision's requirements-dev.txt verbatim failed building
    # `mysqlclient` ("Can not find valid pkg-config name ... Specify
    # MYSQLCLIENT_CFLAGS and MYSQLCLIENT_LDFLAGS env vars manually" -- no
    # MySQL client headers in this sandbox). `grep -rln "MySQLdb|mysqlclient"
    # hc/` returns zero hits (2026-08-18): nothing in the subject's own
    # package or test suite ever imports it: it is a dev-only alternate-
    # backend convenience for a human running a real MySQL locally, never
    # exercised by `manage.py test`. Excluded by name, not by a blanket
    # best-effort/catch-and-skip policy that could silently drop a package
    # a future pin genuinely needs.
    dev_req = workspace / "requirements-dev.txt"
    if dev_req.is_file():
        install_lines = _dev_requirement_lines_excluding_unbuildable(
            dev_req.read_text(encoding="utf-8")
        )
        if install_lines:
            filtered_req = venv_dir / "requirements-dev-filtered.txt"
            filtered_req.write_text("\n".join(install_lines) + "\n", encoding="utf-8")
            code, tail = _run(
                [str(pip), "install", "-q", "-r", str(filtered_req)], workspace
            )
            if code != 0:
                raise SystemExit(
                    "WHAT: could not install requirements-dev.txt (minus "
                    f"{sorted(_DEV_REQUIREMENTS_SKIP)}) into the fixture "
                    "venv.\n"
                    "WHY:  the subject's own pre-existing test suite "
                    "declares its test-only dependencies there (e.g. "
                    "time-machine, imported by "
                    "hc/api/tests/test_sendalerts.py), and BASELINE runs "
                    "with no network access to install one mid-delivery.\n"
                    f"HOW:  reproduce `{pip} install -r {filtered_req}` in "
                    f"{workspace} and read the error below.\n{tail}"
                )
    return venv_python


def _migrate(venv_python: Path, workspace: Path) -> None:
    code, tail = _run([str(venv_python), "manage.py", *MIGRATE_ARGV], workspace)
    if code != 0:
        raise SystemExit(
            "WHAT: clone-local `manage.py migrate --noinput` failed.\n"
            "WHY:  the isolated fixture database must be migrated before it can "
            "be seeded.\n"
            f"HOW:  reproduce `{venv_python} manage.py migrate --noinput` in "
            f"{workspace} and read the error below.\n{tail}"
        )


#: Scoped small, per row 4 (K4 matrix): exercises the SAME Django test
#: import/collection machinery a real BASELINE run uses, over the one app
#: both crafter BASELINE and the hidden acceptance suite exercise -- without
#: running the whole subject suite.
_SUBJECT_DEPENDENCY_PROBE_ARGV = ("manage.py", "test", "hc.api", "--noinput")

_MODULE_NOT_FOUND_MARKER = "ModuleNotFoundError"


def _probe_subject_test_dependencies(venv_python: Path, workspace: Path) -> None:
    """Run the subject's own `hc.api` test command for real, once, refusing
    LOUD on `ModuleNotFoundError` -- the causal reproduction of row 4's
    first divergence: a real BASELINE run hit `ModuleNotFoundError: No
    module named 'time_machine'` importing `hc/api/tests/test_sendalerts.py`
    mid-delivery, with no network access there to install it (see
    `_render_sandbox_settings`'s `network.allowedDomains`). Catching the
    SAME failure class HERE, at setup time (network available, before a
    single model call is spent), means a missing test dependency refuses
    the campaign loud and early instead of surfacing as an opaque
    INDETERMINATE mid-delivery.

    Runs on the PRISTINE pinned-revision checkout, before ATD/crafter ever
    touch it -- this proves the SUBJECT's own pre-existing test suite
    imports cleanly; it says nothing about dependencies a not-yet-authored
    acceptance test might need (out of scope: that gap belongs to the
    delivery contract's own obligations, not this fixture).
    """
    _code, tail = _run([str(venv_python), *_SUBJECT_DEPENDENCY_PROBE_ARGV], workspace)
    if _MODULE_NOT_FOUND_MARKER in tail:
        raise SystemExit(
            "WHAT: the subject's own test command (`"
            f"{venv_python.name} {' '.join(_SUBJECT_DEPENDENCY_PROBE_ARGV)}"
            f"`) hit {_MODULE_NOT_FOUND_MARKER} in the fixture venv.\n"
            "WHY:  row 4 (K4 matrix) -- BASELINE runs network-sandboxed; a "
            "test dependency missing from the fixture venv cannot be "
            "installed mid-delivery, and every K4 subject execution built "
            "on this fixture is non-reproducible until it is.\n"
            f"HOW:  reproduce `{venv_python} {' '.join(_SUBJECT_DEPENDENCY_PROBE_ARGV)}` "
            f"in {workspace}, find the missing import, and add it to "
            "requirements-dev.txt (or requirements.txt, if it belongs to "
            "the subject's runtime rather than its tests) before rerunning."
            f"\n{tail}"
        )


def _existing_api_key(workspace: Path) -> str | None:
    doc = workspace / DOC_NAME
    if not doc.exists():
        return None
    match = re.search(
        r"API key:\s*(\S+)", doc.read_text(encoding="utf-8"), re.IGNORECASE
    )
    return match.group(1) if match else None


def _seed(venv_python: Path, workspace: Path, existing_api_key: str | None) -> str:
    env = dict(os.environ)
    if existing_api_key:
        env["K4_EXISTING_API_KEY"] = existing_api_key
    try:
        done = subprocess.run(
            [str(venv_python), "manage.py", *SEED_ARGV],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=env,
            timeout=_SEED_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            "WHAT: the clone-local seed step did not produce an API key.\n"
            "WHY:  the doc must never claim a preprovisioned key the seed "
            "boundary did not actually produce.\n"
            f"HOW:  reproduce the seed command in {workspace} and read the "
            f"error below.\nTIMEOUT after {_SEED_TIMEOUT}s"
        ) from None
    stdout = done.stdout.strip()
    key = stdout.splitlines()[-1].strip() if stdout else ""
    if done.returncode != 0 or not key:
        raise SystemExit(
            "WHAT: the clone-local seed step did not produce an API key.\n"
            "WHY:  the doc must never claim a preprovisioned key the seed "
            "boundary did not actually produce.\n"
            f"HOW:  reproduce the seed command in {workspace} and read the "
            f"error below.\n{(done.stderr or done.stdout)[-800:]}"
        )
    return key


#: Written by `start_and_wait_block` right after backgrounding the server;
#: a SEPARATE, later tool call can re-check liveness (`kill -0 $(cat
#: server.pid)`) without depending on having captured the first call's
#: own printed text.
SERVER_PID_FILE_NAME = "server.pid"


def _runserver_argv_and_env(port: int) -> tuple[list[str], dict[str, str]]:
    """The ONE structured source for the runserver command: its directly
    executable argv + env-var overrides. `start_and_wait_block`'s
    rendered/executed Bash block derives its command line from this --
    never a second hand-typed copy of the same command.

    `--noreload` (Run 11, K4 matrix): Django's default StatReloader forks
    a watcher/worker pair and restarts the worker on any file-system
    change it observes under the workspace -- `server.log`'s own growth
    lives inside that same tree. An examiner dispatch (attempt #2)
    documented the server going unresponsive across several later tool
    calls despite a clean `nohup ... & disown` start; her own later,
    independent empirical fix in the SAME transcript was exactly
    `--noreload`. A single-process, non-reloading server has no restart
    window to be caught mid-cycle by a later, separate request.
    """
    return (
        [VENV_PYTHON, "manage.py", "runserver", "--noreload", f"127.0.0.1:{port}"],
        {"ALLOWED_HOSTS": "localhost,127.0.0.1"},
    )


def _migrate_command() -> str:
    """The ONE migrate command line every consumer quotes."""
    return f"{VENV_PYTHON} manage.py migrate --noinput"


def start_and_wait_block(port: int, api_key: str) -> str:
    """The ONE copy-paste Bash block every consumer of the examiner
    recipe uses to start the server: `_render`'s rendered doc quotes it
    verbatim, and `preflight.probe_examiner_start_recipe` EXECUTES it
    verbatim under the arm's rendered env -- one source, never a second
    hand-typed copy that could drift from what a real examiner runs.

    Run 9 (K4 matrix): the examiner's server died between separate Bash
    tool calls -- a bare `cmd &` only backgrounds for the CURRENT shell,
    which this harness's tool-call boundary tears down -- and she burned
    25 calls restarting it before falling back to the project's own test
    suite. `nohup ... & disown` detaches the process from that shell so
    it survives the tool-call boundary; the bounded `until curl ...; do
    sleep 1; done` loop (exits 1 past 30s, never silently proceeds) waits
    for real readiness inside this SAME call, so the very next tool call
    can act on a server already confirmed reachable -- never a second,
    separate "is it up yet" round trip.

    Run 11: `--noreload` (see `_runserver_argv_and_env`) removes the
    autoreloader restart window; `SERVER_PID_FILE_NAME` gives a LATER,
    separate tool call a persistent liveness check
    (`kill -0 $(cat server.pid)`) that does not depend on that call
    having captured THIS call's own printed "Server PID:" line.

    Run 11 (next incident, same matrix row): the examiner must never
    walk against a mutated working DB -- an earlier troubleshooter
    dispatch, debugging an unrelated bug, overwrote the seeded Project's
    api_key directly, and three later examiner dispatches inherited the
    corruption. Before touching the server at all, this block: (1) stops
    any server ALREADY running under `SERVER_PID_FILE_NAME` (a stale
    process from a prior attempt would otherwise hold the working DB
    open while step 3 overwrites it underneath it); (2) refuses LOUD if
    `DB_PRISTINE_SNAPSHOT_NAME` is missing -- never silently starts
    against whatever the working DB currently holds; (3) restores the
    working DB from that snapshot, byte-for-byte. Only then does it
    start the server.

    Run 12: readiness answered 200 INSIDE the call that started the
    server, then the server died silently the instant that Bash tool
    call returned -- `nohup ... & disown` detaches the process from the
    shell's JOB TABLE, but a background child launched without `setsid`
    still shares the calling shell's process GROUP, and the tool kills
    that whole group when the call ends. `setsid` gives the server its
    own session/process group before `nohup` even execs it, so it
    survives the group teardown, not merely the shell's own job
    control; `< /dev/null` detaches stdin too, so the child never blocks
    waiting on a pipe the dying call closes.
    """
    base_url = f"http://127.0.0.1:{port}"
    argv, env_overrides = _runserver_argv_and_env(port)
    env_prefix = " ".join(f"{name}={value}" for name, value in env_overrides.items())
    runserver = (
        f"{env_prefix} setsid nohup {' '.join(argv)} > server.log 2>&1 < /dev/null &"
    )
    return (
        f"if [ -f {SERVER_PID_FILE_NAME} ] && "
        f'kill -0 "$(cat {SERVER_PID_FILE_NAME})" 2>/dev/null; then\n'
        f'    kill "$(cat {SERVER_PID_FILE_NAME})" 2>/dev/null\n'
        "    sleep 1\n"
        "fi\n"
        f"if [ ! -f {DB_PRISTINE_SNAPSHOT_NAME} ]; then\n"
        '    echo "pristine seed snapshot missing: '
        f'{DB_PRISTINE_SNAPSHOT_NAME}" >&2\n'
        "    exit 1\n"
        "fi\n"
        f"cp {DB_PRISTINE_SNAPSHOT_NAME} {DB_FILE_NAME}\n"
        f"{runserver}\n"
        "SERVER_PID=$!\n"
        "disown\n"
        f"echo $SERVER_PID > {SERVER_PID_FILE_NAME}\n"
        "i=0\n"
        f"until curl -fsS {base_url}/api/v3/checks/ "
        f'-H "X-Api-Key: {api_key}" > /dev/null 2>&1; do\n'
        "    i=$((i+1))\n"
        '    if [ "$i" -ge 30 ]; then\n'
        '        echo "server did not become ready within 30s" >&2\n'
        "        exit 1\n"
        "    fi\n"
        "    sleep 1\n"
        "done\n"
        f'echo "Server PID: $SERVER_PID (stop with: kill $SERVER_PID, or: '
        f'kill \\$(cat {SERVER_PID_FILE_NAME}))"\n'
    )


def _render(port: int, api_key: str) -> str:
    base = f"http://127.0.0.1:{port}"
    block = start_and_wait_block(port, api_key)
    return (
        "# User environment\n\n"
        "Run once first:\n\n"
        f"    {_migrate_command()}\n\n"
        "Then run this ONE block to start the server and wait until it "
        "is ready -- copy/paste it verbatim; it survives across "
        "separate tool calls:\n\n"
        "```\n"
        f"{block}"
        "```\n\n"
        f"Base URL: {base}\n\n"
        f"API key: {api_key} (read/write, preprovisioned for this environment)\n\n"
        "## HTTP journeys\n\n"
        f"- List: GET {base}/api/v3/checks/\n"
        f"- Create: POST {base}/api/v3/checks/\n"
        f"- Update: POST {base}/api/v3/checks/<uuid>\n"
        f"- Readback: GET {base}/api/v3/checks/<uuid>\n"
        "- Invalid input: POST a malformed body, expect a 400 response\n"
    )


#: Run 8 (K4 matrix): the architect had Read access to this the whole
#: time and never used it before hand-deriving an API shape from prompt
#: text alone. Fixed for the pinned subject revision -- verified present
#: at `SUT_PINNED_REV` (`healthchecks/templates/docs/api.md`, the v3 API
#: reference the recipe's own HTTP journeys target).
_API_DOCS_PATH = "templates/docs/api.md"


def _installed_dependency_names(venv_python: Path, workspace: Path) -> list[str]:
    """Top-level installed package names in the fixture's clone-local venv
    -- the SAME venv every subject/migrate/test command already runs
    through, read via `pip list`, never a second hand-typed dependency
    list. Empty on any failure -- the fragment degrades to a shorter,
    still-true doc rather than block delivery setup over a diagnostic
    extra."""
    try:
        done = subprocess.run(
            [str(venv_python), "-m", "pip", "list", "--format=freeze"],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if done.returncode != 0:
        return []
    names = []
    for line in done.stdout.splitlines():
        name = line.split("==", 1)[0].strip()
        if name:
            names.append(name)
    return names


def render_project_fragment(
    venv_python: Path,
    workspace: Path,
    *,
    network_allowed_domains: tuple[str, ...] = (
        k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS
    ),
) -> str:
    """The arm's project-level sandbox-facts fragment (<=25 lines) --
    written into BOTH arms' workspaces (`prepare_delivery`, shared by
    `control_setup_steps` and `nwave_setup_steps`) so every agent that
    explores the workspace -- architect, crafter, examiner alike -- reads
    these facts instead of re-discovering them by trial and error.

    Every fact is DERIVED, never hand-typed: installed deps come from
    THIS venv's own `pip list` (`_installed_dependency_names`); the
    environment-file pointer names the SAME `DOC_NAME` `_render` writes
    to; the network fact is the SAME `SANDBOX_ALLOWED_NETWORK_DOMAINS`
    `preflight._render_sandbox_settings` enforces. Run 8 (K4 matrix): the
    architect spent a round trip on `pip install hypothesis` (no outbound
    network here). Run 9: the examiner never opened `DOC_NAME` (present
    the whole time) and instead hand-derived a start sequence that died
    between separate Bash calls, burning 25 calls before falling back to
    the project's own test suite -- both a missing fact at the point of
    use, not missing capability, and (Run 9 specifically) a fact that
    EXISTED but was never the first thing read. The GDP-9 form of the
    first bullet below names that lazy alternative directly.
    """
    deps = ", ".join(_installed_dependency_names(venv_python, workspace)) or (
        "(pip list failed; treat the venv as fixed regardless)"
    )
    domains = ", ".join(network_allowed_domains)
    test_command = f"{VENV_PYTHON} {' '.join(_SUBJECT_DEPENDENCY_PROBE_ARGV)}"
    return (
        "## K4 sandbox facts\n\n"
        f"- Open `{DOC_NAME}` FIRST: did you open the environment file "
        "this workspace provides before trying to start anything "
        "yourself? It has the exact Base URL, API key, and the ONE "
        "copy-paste block that starts the service and survives across "
        "tool calls -- open it now if you have not.\n"
        f"- Outbound network: NONE reachable except {domains}. `pip install` "
        "or any other package fetch will fail (no proxy egress) -- use only "
        "what this venv already has:\n"
        f"  {deps}\n"
        f"- Run the subject's own tests: `{test_command}`\n"
        f"- API documentation: `{_API_DOCS_PATH}`\n"
    )


def _write_project_fragment(workspace: Path, content: str) -> None:
    """Create-or-append, never clobber: `nwave-ai project enable` (nwave
    arm only, later in `nwave_setup_steps`) itself appends its own managed
    section to an existing `CLAUDE.md` rather than overwriting one, and
    this write must be equally safe run twice (idempotent `prepare_delivery`)
    or ahead of a subject that ships its own `CLAUDE.md` one day."""
    claude_md = workspace / "CLAUDE.md"
    existing = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    if content.strip() in existing:
        return
    joined = f"{existing.rstrip(chr(10))}\n\n{content}" if existing else content
    claude_md.write_text(joined, encoding="utf-8")


def _add_exclude_entries(workspace: Path) -> None:
    exclude = workspace / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = existing.splitlines()
    to_add = [
        entry
        for entry in (DOC_NAME, f"{_VENV_DIR_NAME}/", DB_PRISTINE_SNAPSHOT_NAME)
        if entry not in lines
    ]
    if not to_add:
        return
    with exclude.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n".join(to_add) + "\n")


def _snapshot_pristine_db(workspace: Path) -> None:
    """Copy the just-seeded, just-self-verified working DB to a read-only
    pristine snapshot -- the ONE known-good state `start_and_wait_block`
    restores from before every server start (Run 11: closes "a later
    dispatch corrupts shared fixture state after a correct seed", see
    this module's own docstring for the full incident).

    Runs immediately after `_seed()` returns, so the snapshot captures
    the database at the earliest point it is provably correct (migrated,
    seeded, and the seed step's own `refresh_from_db()` +
    `compare_api_key()` already held) -- before any model dispatch has
    had a chance to touch it.
    """
    db_path = workspace / DB_FILE_NAME
    if not db_path.exists():
        raise SystemExit(
            "WHAT: cannot snapshot the pristine seeded database -- "
            f"{db_path} does not exist.\n"
            "WHY:  `start_and_wait_block` restores the working DB from "
            "this snapshot before every server start; without it, a "
            "later dispatch's mutation to the working DB would reach "
            "the examiner undetected -- exactly the Run 11 incident.\n"
            f"HOW:  reproduce migrate+seed in {workspace} and confirm "
            f"{DB_FILE_NAME} exists before this snapshot step runs."
        )
    snapshot_path = workspace / DB_PRISTINE_SNAPSHOT_NAME
    if snapshot_path.exists():
        snapshot_path.chmod(0o644)
    shutil.copy2(db_path, snapshot_path)
    snapshot_path.chmod(0o444)


def prepare(workspace: Path, *, port: int) -> Path:
    """Refuse an occupied port before any mutation; else migrate, seed,
    snapshot the pristine seeded DB, and (re)render the public
    user-environment doc with the seed-produced key, idempotently,
    confined to `workspace`."""
    workspace = Path(workspace)
    if _port_is_occupied(port):
        raise SystemExit(
            f"WHAT: port {port} is already occupied on 127.0.0.1.\n"
            "WHY:  the examiner fixture must bind this exact declared port; a "
            "half-migrated clone or half-written doc left behind by a failed "
            "prepare would be worse than none at all.\n"
            "HOW:  free the port or declare a different one, then retry."
        )
    venv_python = _ensure_venv(workspace)
    _migrate(venv_python, workspace)
    api_key = _seed(venv_python, workspace, _existing_api_key(workspace))
    _snapshot_pristine_db(workspace)
    _add_exclude_entries(workspace)
    doc_target = workspace / DOC_NAME
    doc_target.write_text(_render(port, api_key), encoding="utf-8")
    return doc_target


def prepare_delivery(workspace: Path) -> Path:
    """Prepare the clone-local runtime without creating any credential.

    Delivery agents need the subject interpreter and migrated database, not an
    examiner API key.  Keeping seed+documentation behind ``prepare`` prevents
    a transient credential from entering the external model's readable
    workspace during timed delivery.
    """
    workspace = Path(workspace)
    venv_python = _ensure_venv(workspace)
    _migrate(venv_python, workspace)
    _probe_subject_test_dependencies(venv_python, workspace)
    _write_project_fragment(workspace, render_project_fragment(venv_python, workspace))
    _add_exclude_entries(workspace)
    (workspace / DOC_NAME).unlink(missing_ok=True)
    return venv_python


def delivery_setup_step() -> list[str]:
    """Stable, credential-free setup argv shared verbatim by both arms."""
    return [sys.executable, str(Path(__file__).resolve()), "--delivery-only"]


def fixture_setup_step(port: int) -> list[str]:
    """One stable argv shape shared by both arms; only the trailing port differs."""
    return [sys.executable, str(Path(__file__).resolve()), str(port)]


def integration_probe_argv(base_url: str, api_key: str) -> list[str]:
    """Portable stdlib-only probe: authenticated GET of the checks list,
    nonzero on any HTTP/auth failure. Run only by a later installed pilot
    against a real healthchecks clone -- never invoked here."""
    url = f"{base_url}/api/v3/checks/"
    code = (
        "import urllib.request as u\n"
        f"req = u.Request({url!r}, headers={{'X-Api-Key': {api_key!r}}})\n"
        "with u.urlopen(req, timeout=10) as resp:\n"
        "    assert 200 <= resp.status < 300, resp.status\n"
        "    assert len(resp.read(1)) == 1, 'empty body'\n"
    )
    return [sys.executable, "-c", code]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--delivery-only"]:
        prepare_delivery(Path.cwd())
        return 0
    port = int(argv[0])
    prepare(Path.cwd(), port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
