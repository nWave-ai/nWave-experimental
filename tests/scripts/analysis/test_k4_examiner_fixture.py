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
    db_path = workspace / pef.DB_FILE_NAME
    script = f"""#!/usr/bin/env python3
import sys
from pathlib import Path

log = Path({str(log_path)!r})
argv = sys.argv[1:]
with log.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(argv) + "\\n")

if "migrate" in argv:
    # Real `manage.py migrate --noinput` creates the sqlite file if it
    # doesn't exist yet; `_snapshot_pristine_db` requires it to be
    # present right after this fake migrate step runs, same as the
    # real subject.
    Path({str(db_path)!r}).write_text("fake-migrated-db", encoding="utf-8")

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


def test_delivery_prepare_migrates_without_seeding_or_rendering_a_key(tmp_path):
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    log_path = _install_fake_venv_python(workspace, seed_key="must-not-leak")

    returned = pef.prepare_delivery(workspace)

    assert returned == workspace / pef.VENV_PYTHON
    calls = log_path.read_text().splitlines()
    assert any("migrate" in call for call in calls)
    assert not any(pef.SEED_ARGV[0] in call for call in calls)
    assert not (workspace / pef.DOC_NAME).exists()


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
    assert (
        f"{pef.VENV_PYTHON} manage.py runserver --noreload 127.0.0.1:{port}" in rendered
    ), (
        "the doc must carry the exact public run recipe for the declared port, "
        "through the same clone-local interpreter -- --noreload (Run 11) "
        "removes the autoreloader's restart window"
    )
    assert "server.pid" in rendered, (
        "the block must persist the server PID to a file so a SEPARATE, "
        "later tool call can re-check liveness without depending on the "
        "first call's own captured output"
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


def _install_fake_pip_venv_python(workspace, *, freeze_lines: list[str]):
    """A tiny executable fake standing in for the fixture-owned interpreter,
    answering ONLY `<venv_python> -m pip list --format=freeze` -- the ONE
    invocation `_installed_dependency_names` makes -- with `freeze_lines`,
    one per line. Any other argv exits nonzero, so a test asserting on the
    fragment's derived deps can never pass by accident against an
    unrelated command."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(freeze_lines)
    script = f"""#!/usr/bin/env python3
import sys

if sys.argv[1:] == ["-m", "pip", "list", "--format=freeze"]:
    print({body!r})
    sys.exit(0)
sys.exit(1)
"""
    venv_python.write_text(script, encoding="utf-8")
    venv_python.chmod(0o755)
    return venv_python


def test_project_fragment_derives_every_fact_from_its_one_source(tmp_path):
    """Row 8 (K4 matrix): the arm's project fragment must carry sandbox
    facts DERIVED from the harness's own sources -- never a second
    hand-typed copy -- and stay within the declared 25-line budget."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef
    from scripts.analysis.k4 import subject as k4_subject

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    venv_python = _install_fake_pip_venv_python(
        workspace, freeze_lines=["Django==5.0", "time-machine==2.14.0"]
    )

    fragment = pef.render_project_fragment(venv_python, workspace)

    assert fragment.count("\n") <= 25, (
        f"fragment must stay <=25 lines, got {fragment.count(chr(10))}"
    )
    # Deps: read from THIS venv's own `pip list`, not hand-typed.
    assert "Django" in fragment
    assert "time-machine" in fragment
    # Network: the SAME constant `_render_sandbox_settings` enforces.
    for domain in k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS:
        assert domain in fragment
    # Run 9 (K4 matrix): the environment file must be named as the FIRST
    # file to open, GDP-9 form (names the lazy alternative directly).
    assert pef.DOC_NAME in fragment
    assert "FIRST" in fragment
    assert "did you open the environment file" in fragment.lower()
    # Subject test command: the SAME argv `_probe_subject_test_dependencies`
    # already runs at setup time.
    assert " ".join(pef._SUBJECT_DEPENDENCY_PROBE_ARGV) in fragment
    # API docs location.
    assert pef._API_DOCS_PATH in fragment


def test_project_fragment_survives_a_pip_list_failure(tmp_path):
    """`_installed_dependency_names` degrades to an empty list, never an
    exception, on a broken/missing pip -- the fragment must still render a
    true, shorter doc rather than block delivery setup."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    venv_python = workspace / pef.VENV_PYTHON
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    venv_python.chmod(0o755)

    fragment = pef.render_project_fragment(venv_python, workspace)

    assert "pip list failed" in fragment
    assert fragment.count("\n") <= 25


def test_project_fragment_is_written_once_and_never_duplicated(tmp_path):
    """`prepare_delivery` writes the fragment into a fresh `CLAUDE.md`;
    running it again (idempotency, the SAME discipline every other
    `prepare_delivery` step already carries) must not duplicate it."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    content = "## K4 sandbox facts\n\nsome fact\n"

    pef._write_project_fragment(workspace, content)
    pef._write_project_fragment(workspace, content)

    claude_md = (workspace / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude_md.count("## K4 sandbox facts") == 1


def test_project_fragment_preserves_pre_existing_claude_md_content(tmp_path):
    """A `CLAUDE.md` the subject (or `nwave-ai project enable`) already
    wrote must be preserved, never clobbered -- the same append-safe
    discipline `project enable`'s own managed-section injection follows."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "CLAUDE.md").write_text("# Existing project guidance\n")

    pef._write_project_fragment(workspace, "## K4 sandbox facts\n\nsome fact\n")

    claude_md = (workspace / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Existing project guidance" in claude_md
    assert "## K4 sandbox facts" in claude_md


def _run_step(step, *, cwd) -> None:
    subprocess.run(step, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.mark.parametrize(
    "arm_name,port_name", [("control", "CONTROL_PORT"), ("nwave", "NWAVE_PORT")]
)
def test_arm_setup_provisions_the_examiner_recipe_before_any_model_call(
    tmp_path, monkeypatch, arm_name, port_name
):
    """Row 11 (K4 matrix): the examiner burned 40 calls trying to stand up
    a Django dev server with no start recipe in view -- because
    `fixture_setup_step`/`pef.prepare` existed but no driver ever called
    it. RED on base: `delivery_setup_step` alone (which `prepare_delivery`
    actively unlinks `pef.DOC_NAME` at the end of, see
    `test_delivery_prepare_migrates_without_seeding_or_rendering_a_key`
    above) leaves the workspace WITHOUT the recipe. GREEN once the arm's
    full declared setup runs, which must ALSO run `fixture_setup_step`
    after it: the workspace ends up carrying `pef.DOC_NAME` with the SAME
    rendered recipe -- run commands, Base URL, a REAL seed-produced API
    key -- `nw-user-examiner` reads its `PublicStartRecipe` from.

    Runs the real git clone/detach steps against a local throwaway SUT (no
    network, `test_k4_arm_workspace_is_detached.py`'s own pattern) and a
    fake clone-local interpreter (`_install_fake_venv_python`, no real
    Django install) -- proving the WIRING, not just its declared shape.
    """
    from scripts.analysis.k4 import preflight
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    sut = tmp_path / "sut"
    sut.mkdir()
    _git("init", "-q", "-b", "master", cwd=sut)
    _git("config", "user.email", "k4@example.test", cwd=sut)
    _git("config", "user.name", "k4", cwd=sut)
    (sut / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=sut)
    _git("commit", "-q", "-m", "seed", cwd=sut)
    sut_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=sut,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(preflight, "_SUT", str(sut))
    monkeypatch.setattr(preflight, "_SUT_PINNED_REV", sut_head)

    port = getattr(pef, port_name)
    if arm_name == "control":
        steps = preflight.control_setup_steps(tmp_path / "auth-unused")
    else:
        steps = preflight.nwave_setup_steps(
            tmp_path / "venv-unused", tmp_path / "auth-unused"
        )

    workspace = tmp_path / arm_name
    workspace.mkdir()
    doc_path = workspace / pef.DOC_NAME

    # Only the git/fixture steps are exercised here -- `seed_step`/install/
    # `project enable` need a real auth profile and a real nWave venv,
    # orthogonal to whether the examiner recipe lands (the SAME scoping
    # `test_k4_arm_workspace_is_detached.py`'s own tests already use).
    for step in (s for s in steps if s[0] == "git"):
        _run_step(step, cwd=workspace)

    _install_fake_venv_python(workspace, seed_key="k4-arm-setup-fixture-key")

    delivery_step = pef.delivery_setup_step()
    _run_step(delivery_step, cwd=workspace)
    assert not doc_path.exists(), (
        "delivery_setup_step alone must NOT leave the examiner recipe "
        "behind -- prepare_delivery unlinks it deliberately"
    )

    fixture_step = pef.fixture_setup_step(port)
    assert fixture_step in steps, (
        f"{arm_name}_setup_steps must itself include fixture_setup_step "
        f"at {port_name}, not just happen to work when run by hand"
    )
    _run_step(fixture_step, cwd=workspace)

    assert doc_path.exists(), (
        f"{arm_name} arm's full declared setup must provision {pef.DOC_NAME} "
        "-- fixture_setup_step must run in this arm's step list"
    )
    rendered = doc_path.read_text(encoding="utf-8")
    assert f"127.0.0.1:{port}" in rendered
    assert "k4-arm-setup-fixture-key" in rendered
    assert "manage.py migrate --noinput" in rendered
    assert "manage.py runserver" in rendered


def test_seed_step_executes_seed_code_verbatim_one_source(tmp_path):
    """K4 matrix (Run 11): 'fake-subject seed argv capture' -- the seed
    step must invoke exactly `pef._SEED_CODE`, byte-for-byte, as the `-c`
    argument -- never a second, drifted copy of the seeding logic. The
    fake interpreter logs the FULL argv it receives (including the
    multi-line code string), so this test proves WIRING (what actually
    got executed), not merely that `_SEED_CODE`'s source text exists
    somewhere in the module.
    """
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    workspace = _make_workspace(tmp_path)
    port = _free_port()
    log_path = _install_fake_venv_python(workspace, seed_key="k4-fake-83jd92kx")

    pef.prepare(workspace, port=port)

    log_text = log_path.read_text(encoding="utf-8")
    assert pef._SEED_CODE in log_text, (
        "the seed step must execute pef._SEED_CODE verbatim -- found a "
        "different script logged instead"
    )


def test_seed_code_self_verifies_through_the_subjects_own_code_path(tmp_path):
    """Run 11 (K4 matrix): the DB's ONE Project row held a literal 32-`Y`
    placeholder, structurally incapable of ever matching
    `compare_api_key`'s stored-hash format -- root cause (see
    `prepare_examiner_fixture`'s own module docstring for the full RCA,
    reproduced live against the real Run 11 checkout): NOT this seed
    step, which was and remains correct, but a LATER, unrelated
    troubleshooter dispatch overwriting the shared fixture DB directly.

    `_SEED_CODE`'s STRUCTURE is asserted statically here (healthchecks'
    `hc.accounts.models` is not a project dependency and is not
    importable in this test suite -- see
    `test_seed_code_hashing_roundtrip_against_the_real_subject_model`
    immediately below for the real, executable roundtrip, skipped unless
    that dependency happens to be importable). What is asserted here:
    the seed step calls the SUBJECT's OWN `Project.set_api_key()` (never
    a hand-rolled hash), then immediately self-verifies via
    `refresh_from_db()` + `compare_api_key()` before ever printing/
    documenting the key, exiting nonzero (LOUD) rather than silently
    trusting an unproven write.
    """
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    code = pef._SEED_CODE
    assert "project.set_api_key()" in code, (
        "must seed through the subject's OWN Project.set_api_key(), "
        "never a hand-rolled hash"
    )
    assert "project.save()" in code
    assert "project.refresh_from_db()" in code, (
        "must re-read from the DB after saving -- proving the write "
        "actually persisted, not merely that Python's in-memory object "
        "holds the expected value"
    )
    assert "project.compare_api_key(raw)" in code, (
        "must verify the freshly-read row authenticates against the "
        "SAME raw key about to be printed/documented"
    )
    assert "sys.exit(1)" in code, (
        "a failed self-verification must exit nonzero (LOUD) -- never "
        "silently print/document an unproven key"
    )
    # The failure branch must come before the ONLY print(raw) in the
    # else-branch, so a verification failure genuinely prevents the key
    # from ever being printed/documented.
    exit_at = code.index("sys.exit(1)")
    print_raw_at = code.index("print(raw)")
    assert exit_at < print_raw_at, (
        "the verification-failure exit must be reachable BEFORE the key "
        "is ever printed, not merely present somewhere in the script"
    )


def test_seed_code_hashing_roundtrip_against_the_real_subject_model():
    """The real, executable roundtrip for the assertions in
    `test_seed_code_self_verifies_through_the_subjects_own_code_path`
    above -- run for real ONLY if healthchecks' `hc.accounts.models` is
    importable (it is not a project dependency of this repo, and is not
    installed in this test suite's own venv by design -- portability,
    same reasoning `test_k4_row11_start_recipe.py`'s own module
    docstring gives for why it never clones/imports the real subject
    either).

    How this is ACTUALLY verified when that dependency is unavailable
    here: (1) reproduced live, by hand, against the real Run 11 checkout
    while diagnosing this defect -- `set_api_key()` + `save()` +
    `refresh_from_db()` + `compare_api_key(raw)` returned `True`,
    documented in `prepare_examiner_fixture`'s own module docstring; (2)
    every real campaign run: `preflight.probe_examiner_start_recipe`
    authenticates the documented key against the REAL running Django
    server before any model call, hard-refusing the whole campaign
    (Run 11) if it does not -- see `test_k4_row11_start_recipe.py`.
    """
    django_models = pytest.importorskip(
        "hc.accounts.models",
        reason=(
            "healthchecks is not a project dependency of nwave-dev; the "
            "real hashing roundtrip only runs inside an actual K4 arm "
            "workspace, never in this repo's own test suite"
        ),
    )
    Project = django_models.Project

    project = Project()
    raw = project.set_api_key()
    assert project.compare_api_key(raw)
