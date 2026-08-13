"""`.k4-user-environment.md` is the ONE doc a blind K4 examiner reads about a
delivery workspace, framed as a plain user-facing environment doc rather than
an examiner-labelled artifact.

`scripts.analysis.k4.prepare_examiner_fixture` (`pef`) exists on disk, but
today it only renders prose that ASSERTS a key is preprovisioned -- it never
migrates the isolated clone, never seeds the clone-local database, and never
proves the rendered key is the one a seed boundary actually produced. That is
a false green: it would ship the exact 210-second discovery failure the
design at `/tmp/k4-examiner-fixture-design.md` exists to remove. Every test
below therefore targets the approved state transition
`Unprovisioned -> Migrated -> Seeded(key) -> documented`, not the prose
alone. Expect failures via AttributeError/FileNotFoundError/assertion, not
ModuleNotFoundError -- the module is present, the lifecycle is not.

The public seam under test is `pef.prepare(workspace, port=...)`, the
`pef.DOC_NAME` constant, and the migrate/seed lifecycle it must drive through
a fixture-owned clone-local Python environment (`pef.VENV_PYTHON`, a
`workspace`-relative interpreter path) invoking `manage.py migrate --noinput`
before any seed command. There is no doc-source/doc-target filtering API to
invent -- production owns the whole template.

1. A port already occupied is refused with a WHAT/WHY/HOW message, and the
   refusal happens BEFORE migrate, seed, or the doc are touched -- a
   half-migrated clone or half-written doc left behind by a failed prepare
   would be worse than none at all.
2. Migration precedes seeding on every prepare call, repeated preparation is
   idempotent (same order, same rendered doc, no drift), and the API key
   rendered in the doc is exactly the one the seed boundary produced -- not
   a hardcoded literal the render step invented independently.
3. The rendered doc is public-only: exact public run recipe through the
   fixture-owned clone-local Python environment, noninteractive migration
   before runserver, a localhost base URL, a non-secret preprovisioned
   read/write API key, and concise list/create/update/readback/invalid-input
   HTTP journeys -- while never leaking source paths, model/storage symbols,
   expected verdicts, hidden-acceptance facts, or INTERNAL calibration
   content. The port stays a parameter, never hardcoded.
4. Generated fixture files are excluded CLONE-LOCALLY (`.git/info/exclude`,
   never a committed `.gitignore`) so `git status` cannot see them, while
   the files themselves stay fully readable on disk.
5. A separate, explicit integration-probe command contract exists for a
   later installed pilot to run against a REAL healthchecks clone and prove
   GET list authenticates with the rendered key -- this test asserts the
   contract's shape only; it never clones or touches the network itself.

Run: uv run pytest -q tests/scripts/analysis/test_k4_examiner_fixture.py
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys

import pytest


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _git("init", "-q", "-b", "master", cwd=workspace)
    _git("config", "user.email", "k4@example.test", cwd=workspace)
    _git("config", "user.name", "k4", cwd=workspace)
    (workspace / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=workspace)
    _git("commit", "-q", "-m", "seed", cwd=workspace)
    return workspace


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _install_fake_venv_python(workspace, *, seed_key: str):
    """A tiny executable fake standing in for the fixture-owned clone-local
    interpreter: it is invoked as `<venv_python> manage.py <subcommand>
    [args...]`, and logs the FULL argv it receives -- one line per
    invocation -- so a test can find the real subcommand by membership
    rather than by assuming a fixed position. On the actual seed invocation
    (its argv contains `pef.SEED_ARGV`'s subcommand marker) it prints
    `seed_key` to stdout -- the only channel production has for learning
    what the seed boundary produced."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    log_path = workspace / "manage.log"
    seed_marker = pef.SEED_ARGV[0]
    script = f"""#!/usr/bin/env python3
import sys
from pathlib import Path

log = Path({str(log_path)!r})
argv = sys.argv[1:]
with log.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(argv) + "\\n")

if {seed_marker!r} in argv:
    print({seed_key!r})
sys.exit(0)
"""
    venv_python.write_text(script, encoding="utf-8")
    venv_python.chmod(0o755)
    return log_path


def test_occupied_port_is_refused_before_migrate_seed_or_doc(tmp_path):
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    doc_target = workspace / pef.DOC_NAME
    # Deliberately no fake venv python installed: if production tried to
    # migrate/seed before checking the port, it would blow up on a missing
    # interpreter instead of returning the WHAT/WHY/HOW refusal below.
    log_path = workspace / "manage.log"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    occupied_port = sock.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as excinfo:
            pef.prepare(workspace, port=occupied_port)
        message = str(excinfo.value)
        assert "WHAT:" in message
        assert "WHY:" in message
        assert "HOW:" in message
        assert not doc_target.exists(), "refusal must happen before the doc is rendered"
        assert not log_path.exists(), (
            "refusal must happen before migrate or seed ever ran"
        )
    finally:
        sock.close()


def test_migrate_precedes_seed_repeated_prepare_is_idempotent_and_renders_the_seed_key(
    tmp_path,
):
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    port = _free_port()
    distinct_key = "k4-distinct-not-a-literal-9f31"
    log_path = _install_fake_venv_python(workspace, seed_key=distinct_key)

    # "migrate" is Django's own built-in subcommand name, not a private
    # implementation detail -- stable regardless of how pef.MIGRATE_ARGV
    # is shaped.
    migrate_marker = "migrate"
    seed_marker = pef.SEED_ARGV[0]

    def _first_index(lines, marker):
        for i, line in enumerate(lines):
            if marker in line:
                return i
        return None

    pef.prepare(workspace, port=port)
    first_log = log_path.read_text().splitlines()
    first_doc = (workspace / pef.DOC_NAME).read_text()

    pef.prepare(workspace, port=port)
    second_log = log_path.read_text().splitlines()
    second_doc = (workspace / pef.DOC_NAME).read_text()

    first_migrate_at = _first_index(first_log, migrate_marker)
    first_seed_at = _first_index(first_log, seed_marker)
    assert first_migrate_at is not None and first_seed_at is not None, (
        "both migrate and seed must have run on the first prepare"
    )
    assert first_migrate_at < first_seed_at, (
        "migration must precede seeding on the first prepare"
    )

    second_migrate_at = _first_index(second_log, migrate_marker)
    second_seed_at = _first_index(second_log, seed_marker)
    assert second_migrate_at is not None and second_seed_at is not None, (
        "both migrate and seed must run again on a repeated prepare too"
    )
    assert second_migrate_at < second_seed_at, (
        "migration must precede seeding on a repeated prepare too"
    )

    assert first_doc == second_doc, "repeated preparation must be idempotent"
    assert distinct_key in first_doc, (
        "the doc must render exactly the key the seed boundary produced, "
        "not a value the render step invented independently"
    )


def test_rendered_doc_is_a_public_only_user_environment_recipe(tmp_path):
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    doc_target = workspace / pef.DOC_NAME
    port = _free_port()
    _install_fake_venv_python(workspace, seed_key="k4-fake-83jd92kx")

    pef.prepare(workspace, port=port)
    rendered = doc_target.read_text()

    assert f"{pef.VENV_PYTHON} manage.py migrate --noinput" in rendered, (
        "the doc must show noninteractive migration through the "
        "fixture-owned clone-local Python environment, before runserver"
    )
    assert f"{pef.VENV_PYTHON} manage.py runserver 127.0.0.1:{port}" in rendered, (
        "the doc must carry the exact public run recipe for the declared port, "
        "through the same clone-local interpreter"
    )
    assert "ALLOWED_HOSTS=localhost,127.0.0.1" in rendered, (
        "the recipe must declare ALLOWED_HOSTS=localhost,127.0.0.1 -- both the "
        "configured SITE_ROOT hostname and the bound/request host are public "
        "runtime preconditions, without which the server refuses startup "
        "(hc.api.E002) or answers with DisallowedHost"
    )
    assert f"http://127.0.0.1:{port}" in rendered, (
        "base URL must be localhost, parameterised by port"
    )

    assert re.search(r"API key:\s*\S+", rendered, re.IGNORECASE), (
        "a preprovisioned read/write API key value must be present"
    )
    assert "read/write" in rendered.lower(), (
        "the API key's scope must be stated as read/write"
    )
    assert "secret" not in rendered.lower(), (
        "a preprovisioned test key must never be framed as a secret"
    )

    lowered = rendered.lower()
    for journey in ("list", "create", "update", "readback", "invalid"):
        assert journey in lowered, f"missing the {journey!r} public HTTP journey"

    for leak in (
        "scripts/analysis/k4",
        "prepare_examiner_fixture",
        "models.py",
        "database",
        "PASS",
        "FAIL",
        "expected verdict",
        "hidden",
        "INTERNAL",
    ):
        assert leak not in rendered, (
            f"{leak!r} leaked into the public user-environment doc"
        )


def test_fixture_files_are_excluded_clone_locally_yet_stay_readable(tmp_path):
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    doc_target = workspace / pef.DOC_NAME
    port = _free_port()
    _install_fake_venv_python(workspace, seed_key="k4-fake-83jd92kx")

    pef.prepare(workspace, port=port)

    exclude_file = workspace / ".git" / "info" / "exclude"
    assert exclude_file.exists()
    assert pef.DOC_NAME in exclude_file.read_text()

    gitignore = workspace / ".gitignore"
    assert not gitignore.exists(), (
        "exclusion must be clone-local (.git/info/exclude), never a committed "
        ".gitignore that a delivery diff could reveal"
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    assert pef.DOC_NAME not in status.stdout, (
        "fixture doc must be invisible to git status"
    )

    assert doc_target.exists()
    assert doc_target.read_text() != "", (
        "fixture doc must still be fully readable on disk"
    )


def test_integration_probe_contract_authenticates_get_list_against_a_real_clone(
    tmp_path,
):
    """Contract only -- no clone, no network, no server. `pef.integration_probe_argv`
    is the seam a later installed pilot runs, unmodified, against a real
    healthchecks clone to prove GET list authenticates with the rendered
    key. This test proves the contract's shape and that it is parameterised
    by base_url/api_key, never that it succeeds over a live server."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    api_key = "k4-fake-83jd92kx"

    argv = pef.integration_probe_argv(base_url, api_key)

    assert isinstance(argv, list) and argv, (
        "must be a runnable argv, not a template string"
    )
    assert argv[0] == sys.executable or argv[0].endswith("python"), (
        "the probe must run through a Python interpreter -- portability: "
        "Python is the only runtime dependency"
    )
    joined = " ".join(argv)
    assert base_url in joined
    assert api_key in joined
    assert "checks" in joined.lower(), (
        "the probe must target the checks list endpoint the doc documents"
    )
