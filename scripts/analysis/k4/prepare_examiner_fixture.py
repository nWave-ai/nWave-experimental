#!/usr/bin/env python3
"""Render the ONE public-facing user-environment doc a K4 examiner reads.

Drives the state transition `Unprovisioned -> Migrated -> Seeded(key) ->
documented` through a fixture-owned, clone-local Python environment: migrate
the isolated clone, idempotently seed a user/project with one deterministic
read/write API key, then render a plain user onboarding doc carrying only
the public run recipe, localhost base URL, the SEED-PRODUCED key, and
concise HTTP journeys -- never a source path, model/storage symbol, expected
verdict, or hidden-acceptance fact. The port stays a parameter.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from pathlib import Path


#: The doc a blind examiner reads, framed as user-facing, not examiner-labelled.
DOC_NAME = ".k4-user-environment.md"

#: Declared, arm-specific high ports so control and nwave fixtures can run
#: side by side without colliding on one port.
CONTROL_PORT = 18771
NWAVE_PORT = 18772

#: Fixture-owned clone-local venv, workspace-relative. Never the operator's
#: own environment -- migrate/seed/runserver all run through this.
_VENV_DIR_NAME = "k4-fixture-venv"
VENV_PYTHON = f"{_VENV_DIR_NAME}/bin/python"

MIGRATE_ARGV = ["migrate", "--noinput"]

_SEED_CODE = (
    "import os\n"
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


def _render(port: int, api_key: str) -> str:
    base = f"http://127.0.0.1:{port}"
    return (
        "# User environment\n\n"
        "Local run recipe:\n\n"
        f"    {VENV_PYTHON} manage.py migrate --noinput\n"
        f"    ALLOWED_HOSTS=localhost,127.0.0.1 {VENV_PYTHON} manage.py runserver 127.0.0.1:{port}\n\n"
        f"Base URL: {base}\n\n"
        f"API key: {api_key} (read/write, preprovisioned for this environment)\n\n"
        "## HTTP journeys\n\n"
        f"- List: GET {base}/api/v3/checks/\n"
        f"- Create: POST {base}/api/v3/checks/\n"
        f"- Update: POST {base}/api/v3/checks/<uuid>\n"
        f"- Readback: GET {base}/api/v3/checks/<uuid>\n"
        "- Invalid input: POST a malformed body, expect a 400 response\n"
    )


def _add_exclude_entries(workspace: Path) -> None:
    exclude = workspace / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = existing.splitlines()
    to_add = [entry for entry in (DOC_NAME, f"{_VENV_DIR_NAME}/") if entry not in lines]
    if not to_add:
        return
    with exclude.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n".join(to_add) + "\n")


def prepare(workspace: Path, *, port: int) -> Path:
    """Refuse an occupied port before any mutation; else migrate, seed, and
    (re)render the public user-environment doc with the seed-produced key,
    idempotently, confined to `workspace`."""
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
