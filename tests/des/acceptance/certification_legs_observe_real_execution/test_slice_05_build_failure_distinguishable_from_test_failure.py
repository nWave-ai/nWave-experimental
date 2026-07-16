"""Feature `certification-legs-observe-real-execution`, slice-05 (DDD-CERT-6).

Value statement (feature-delta.md [REF] Slice Plan, slice-05): a crafter
running ``des run-contract-gate`` against an import-broken tree gets
``kind=build-failure``; against a red-assertion tree gets
``kind=test-failure`` -- both distinguishable end-to-end through E2's
``refused_half`` payload. Folds backlog #196 (build-vs-test-failure
conflation).

Found in TWO components, both slice-05 per the Component decomposition table:

* C8 -- ``src/des/cli/run_contract_gate.py::_mode_feature_scoped`` /
  ``_feature_scope_malformed`` (:2287-2301, :2820-2965). A genuine pytest
  COLLECTION failure (``_CollectionError`` -- the tree does not compile/
  import, reason ``"collection-failed"``, :2878-2884) and a genuine RUN
  failure (a real arch-invariant-tier assertion FAILS at run-time, reason
  ``"arch-invariant-failed"``, :2944-2952 -- "the run-failure branches of the
  same function" DDD-CERT-6 names, the pytest-native sibling of the cargo
  ``verdict.passed is False`` example the design decision cites) both flow
  into ``_feature_scope_malformed`` with NO discriminator: today's payload is
  ``{event, cause, feature_id, reason, error, ...}``, no ``kind`` key at all.
  A crafter reading the raw contract-gate stdout cannot tell "your code does
  not compile" from "your tests are red" -- two different problems with two
  different fixes.

* C9 -- ``src/des/cli/verify_slice_commit_completeness.py::_run_contract_gate``
  (:431-463) spawns ``run_contract_gate`` as a subprocess and returns ONLY
  ``completed.returncode`` -- the child's JSON stdout (including any future
  ``kind`` field) is discarded outright. The E2 ``SliceCommitRefused`` verdict
  (:986-1004, ``refused_half="E2"``) therefore carries no ``kind`` either,
  even once C8 lands -- DDD-CERT-6 requires E2 to THREAD the SAME field
  through so a crafter reading the SLICE-COMMIT verdict (not just the raw
  contract-gate stdout) sees the same distinction.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default for C8; the SAME in-process convention slice-03/slice-04's
ATs use): the REAL ``des.cli.run_contract_gate.main(...)`` CLI driver via
``run_cli_in_process``. C9's ATs additionally drive the REAL
``des.cli.verify_slice_commit_completeness.main(...)`` CLI end-to-end against
a genuine tmp git repo (mirrors
``tests/bugs/des/test_slice_commit_refused_names_how.py``'s fixture idiom) --
``_run_contract_gate`` (vscc.py) spawns the REAL ``run_contract_gate`` as an
actual OS subprocess (``des_spawn``), so this exercises the genuine C8-then-C9
pipeline, not a mocked boundary. Both fixtures are pure Python/pytest (no
``cargo``/external toolchain dependency -- ``cargo`` is absent on this box,
per slice-04's precedent docstring), so the real subprocess chain runs
end-to-end with zero spying/mocking on either driving surface.

Active-RED today (real assertion failures, never an import/collection
error): ``_feature_scope_malformed`` carries no ``kind`` field at all, so
every assertion below that reads ``payload.get("kind")`` observes ``None`` --
a genuine ``AssertionError`` against the expected string, never a crash.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process

from des.cli import run_contract_gate as gate_cli
from des.cli import verify_slice_commit_completeness as vscc


_FEATURE_ID = "fixture-build-vs-test-failure"
_ENTERING_SLICE = "slice-05"

# The EXISTING `_feature_scope_malformed` exit (run_contract_gate.py:2301) --
# unchanged by this slice's fix; only the payload's `kind` field is net-new.
_EXPECTED_MALFORMED_EXIT = 2
_MALFORMED_EVENT = "FeatureScopeMalformed"
_CLEARED_EVENT = "FeatureScopeCleared"


# ===========================================================================
# Fixture builders -- real, minimal, top-level-manifest trees (shared across
# both driving surfaces: the direct C8 tests stage them under a bare
# `tmp_path`; the C9 tests stage the SAME content under a real git repo).
# ===========================================================================


def _write_pyproject(root: Path) -> None:
    """The minimal pytest config every fixture tree carries -- a real
    top-level manifest file, as every real repo has (task mandate)."""
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["unit", "integration", "acceptance"]\n',
        encoding="utf-8",
    )


def _write_feature_file(root: Path) -> Path:
    """A real `.feature` file self-identifying `_FEATURE_ID` (the
    `@feature-` tag `_feature_tag_files` resolves on) carrying the entering
    slice's `@slice-05` tag -- the M-8 non-vacuity floor `_mode_feature_scoped`
    checks before ever reaching either failure branch. Placed under `tests/`
    so `_walk_feature_files` discovers it."""
    feature_dir = root / "tests" / "features" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / f"{_FEATURE_ID}.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: fixture build-vs-test-failure coverage\n\n"
        f"  @{_ENTERING_SLICE}\n"
        "  Scenario: entering slice ships one scenario\n"
        "    Given the entering slice has exactly one scenario\n",
        encoding="utf-8",
    )
    return feature_dir


def _make_import_broken_repo(root: Path) -> Path:
    """Fixture A -- IMPORT-BROKEN tree: the code does NOT import/compile at
    all. A real Python test module under the feature-scope dir importing a
    module that does not exist -- pytest's own collection genuinely fails
    (`_CollectionError`, `run_contract_gate.py:403-406`), the M-1 floor's
    real mechanism, never a fabricated failure."""
    root.mkdir(parents=True, exist_ok=True)
    _write_pyproject(root)
    feature_dir = _write_feature_file(root)
    (feature_dir / "test_import_broken.py").write_text(
        "import this_module_does_not_exist_anywhere_xyz42  # noqa: F401\n",
        encoding="utf-8",
    )
    return root


def _make_red_assertion_repo(root: Path) -> Path:
    """Fixture B -- RED-ASSERTION tree: the code imports fine, the suite
    runs, an assertion fails. The feature scope itself is CLEAN (a real
    passing pytest test -- `_mode_feature_scoped`'s own M-1 collection is
    collect-only, so a feature-scope assertion can never surface there); the
    `tests/build/` architecture-invariant tier -- the ONE genuine pytest RUN
    `_mode_feature_scoped` performs (`_run_arch_invariant_set`) -- collects
    cleanly (imports only `pytest`) and FAILS AT RUN-TIME. This is
    DDD-CERT-6's "run-failure branches of the same function", the pytest-
    native sibling of the cited cargo `verdict.passed is False` case."""
    root.mkdir(parents=True, exist_ok=True)
    _write_pyproject(root)
    feature_dir = _write_feature_file(root)
    (feature_dir / "test_probe.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.acceptance\n"
        "def test_clean_feature_scope():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    build_dir = root / "tests" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "test_arch_seeded_invariant.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.unit\n"
        "def test_seeded_arch_invariant():\n"
        "    # collects cleanly (imports only pytest); FAILS when RUN -- the\n"
        "    # red-assertion shape this slice's `test-failure` kind pins.\n"
        "    assert False, 'seeded run-time architecture invariant failure'\n",
        encoding="utf-8",
    )
    return root


def _make_clean_repo(root: Path) -> Path:
    """POSITIVE CONTROL -- a genuinely clean tree: imports fine, every test
    passes, no arch violation. Proves the oracle CAN say NO -- neither
    `build-failure` nor `test-failure` fires -- before any YES is trusted."""
    root.mkdir(parents=True, exist_ok=True)
    _write_pyproject(root)
    feature_dir = _write_feature_file(root)
    (feature_dir / "test_probe.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.acceptance\n"
        "def test_clean_feature_scope():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    build_dir = root / "tests" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "test_arch_clean.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.unit\n"
        "def test_arch_invariant_holds():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return root


# ===========================================================================
# C8 driving surface -- the real `des run-contract-gate` CLI, in-process.
# ===========================================================================


def _drive_run_contract_gate(repo_root: Path) -> tuple[int, str, str]:
    """Drive the REAL `des run-contract-gate --feature-id ... --entering-slice
    ...` CLI in-process (Layer 3 composition), returning
    `(exit_code, stdout, stderr)` -- the command's real observables."""
    return run_cli_in_process(
        [
            "--repo",
            str(repo_root),
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE,
        ],
        cwd=repo_root,
        main=gate_cli.main,
    )


def _events(stdout: str, stderr: str) -> list[dict[str, object]]:
    """Every single-line JSON event the gate emitted, across both channels."""
    records: list[dict[str, object]] = []
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def _malformed_payload(stdout: str, stderr: str) -> dict[str, object]:
    """The single `FeatureScopeMalformed` verdict event, or `{}` if absent."""
    for event in _events(stdout, stderr):
        if event.get("event") == _MALFORMED_EVENT:
            return event
    return {}


# ===========================================================================
# C8 -- POSITIVE ATs (active-RED today)
# ===========================================================================


_KIND_CASES = [
    pytest.param(
        _make_import_broken_repo,
        "collection-failed",
        "build-failure",
        id="import-broken",
    ),
    pytest.param(
        _make_red_assertion_repo,
        "arch-invariant-failed",
        "test-failure",
        id="red-assertion",
    ),
]


@pytest.mark.parametrize("fixture_builder, expected_reason, expected_kind", _KIND_CASES)
def test_run_contract_gate_reports_kind_discriminator(
    fixture_builder,
    expected_reason: str,
    expected_kind: str,
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today, C8): `des run-contract-gate` against an
    import-broken tree names `kind=build-failure`; against a red-assertion
    tree names `kind=test-failure` (DDD-CERT-6). Today
    `_feature_scope_malformed` carries NO `kind` field at all -- the final
    assertion below is what fails.
    """
    repo_root = tmp_path / "target-repo"
    fixture_builder(repo_root)

    exit_code, stdout, stderr = _drive_run_contract_gate(repo_root)
    payload = _malformed_payload(stdout, stderr)

    assert exit_code == _EXPECTED_MALFORMED_EXIT, (
        f"expected the M-1/arch-invariant refusal at exit "
        f"{_EXPECTED_MALFORMED_EXIT}; got exit {exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}"
    )
    assert payload.get("event") == _MALFORMED_EVENT, payload
    assert payload.get("reason") == expected_reason, (
        f"expected the EXISTING reason discriminator {expected_reason!r}, "
        f"got payload={payload!r}"
    )
    assert payload.get("kind") == expected_kind, (
        f"the {expected_reason!r} refusal must name kind={expected_kind!r} "
        "(DDD-CERT-6, the build-vs-test-failure discriminator) so a crafter "
        "can tell 'your code does not compile' from 'your tests are red' -- "
        f"got payload={payload!r}"
    )


# ===========================================================================
# C8 -- NEGATIVE AT (anti-recurrence, active-RED today)
# ===========================================================================


@pytest.mark.negative_at
def test_import_broken_and_red_assertion_never_collapse_to_the_same_kind(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): the two runs must
    produce DIFFERENT, machine-readable `kind` values -- an import-broken
    tree and a red-assertion tree must NEVER be indistinguishable through the
    refusal payload. Today NEITHER refusal carries a `kind` field at all, so
    both collapse to the SAME (absent) discriminator -- `None == None` --
    this assertion is what fails.
    """
    build_repo = tmp_path / "build-broken"
    test_repo = tmp_path / "test-red"
    _make_import_broken_repo(build_repo)
    _make_red_assertion_repo(test_repo)

    _, build_stdout, build_stderr = _drive_run_contract_gate(build_repo)
    _, test_stdout, test_stderr = _drive_run_contract_gate(test_repo)

    build_kind = _malformed_payload(build_stdout, build_stderr).get("kind")
    test_kind = _malformed_payload(test_stdout, test_stderr).get("kind")

    assert build_kind is not None and test_kind is not None, (
        "both refusals must carry a kind discriminator -- got "
        f"build_kind={build_kind!r}, test_kind={test_kind!r}"
    )
    assert build_kind != test_kind, (
        "an import-broken tree and a red-assertion tree must NEVER report "
        f"the SAME kind -- got build_kind={build_kind!r} == "
        f"test_kind={test_kind!r} (today both collapse to the same "
        "undifferentiated refusal -- this assertion is what fails)"
    )


# ===========================================================================
# C8 -- POSITIVE CONTROL / fault-injection (REGRESSION-GUARD, already green)
# ===========================================================================


def test_clean_tree_reports_no_kind_and_clears_regression(tmp_path: Path) -> None:
    """REGRESSION-GUARD / positive control: a genuinely clean tree (imports
    fine, every test passes, no arch violation) must still CLEAR -- exit 0,
    `FeatureScopeCleared`, neither refusal `kind` fires. Proves the oracle
    CAN say NO before any YES (`build-failure`/`test-failure`) is trusted.
    Already green today -- pins the unchanged pass-through path this slice's
    fix must preserve.
    """
    repo_root = tmp_path / "target-repo"
    _make_clean_repo(repo_root)

    exit_code, stdout, stderr = _drive_run_contract_gate(repo_root)
    events = _events(stdout, stderr)
    event_names = {str(event.get("event", "")) for event in events}

    assert exit_code == 0, (
        f"a genuinely clean tree must clear: got exit {exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    assert _CLEARED_EVENT in event_names, events
    assert _MALFORMED_EVENT not in event_names, events


# ===========================================================================
# C9 driving surface -- the real `des verify-slice-commit` CLI (E2), against
# a genuine tmp git repo, end-to-end through the real `run_contract_gate`
# subprocess `_run_contract_gate` (vscc.py) spawns.
# ===========================================================================


def _git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _make_committed_repo(root: Path, fixture_builder) -> tuple[Path, str]:
    """A REAL git repo whose HEAD commit carries the fixture content AND the
    slice's `Slice-Id:` trailer -- E1 (completeness) genuinely clears (the
    `.feature` file is committed), so the run reaches E2 (the feature-scoped
    contract gate) for real, exercising the genuine C8-then-C9 pipeline."""
    _git_init(root)
    fixture_builder(root)
    _git(root, "add", "-A")
    _git(
        root,
        "commit",
        "-qm",
        f"feat(slice): behaviour\n\nSlice-Id: {_ENTERING_SLICE}",
    )
    commit = _git(root, "rev-parse", "HEAD").strip()
    return root, commit


def _run_verify_slice_commit(
    repo: Path, commit: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI (`main()`) in-process
    with `--feature-id` (the verify-then-record exit gate: E1 then E2),
    capturing its single-line JSON payload via `capsys`."""
    exit_code = vscc.main(
        [
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--feature-id",
            _FEATURE_ID,
        ]
    )
    stdout = capsys.readouterr().out
    lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    payload: dict[str, object] = json.loads(lines[-1])
    return exit_code, payload


# ===========================================================================
# C9 -- POSITIVE ATs (active-RED today)
# ===========================================================================


_E2_KIND_CASES = [
    pytest.param(_make_import_broken_repo, "build-failure", id="import-broken"),
    pytest.param(_make_red_assertion_repo, "test-failure", id="red-assertion"),
]


@pytest.mark.parametrize("fixture_builder, expected_kind", _E2_KIND_CASES)
def test_e2_refused_half_threads_kind_discriminator(
    fixture_builder,
    expected_kind: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """POSITIVE AT (active-RED today, C9): E2's `SliceCommitRefused` payload
    (`refused_half='E2'`) must thread the SAME `kind` discriminator C8 names
    at the raw `run_contract_gate` level -- a crafter reading the SLICE-
    COMMIT verdict (not only the raw contract-gate stdout) must ALSO see
    build-vs-test-failure distinguishably. Today `_run_contract_gate`
    (`verify_slice_commit_completeness.py:431-463`) discards the contract
    gate's stdout entirely, returning only the bare exit code -- no `kind`
    ever reaches this payload. This assertion is what fails.
    """
    repo, commit = _make_committed_repo(tmp_path / "e2-repo", fixture_builder)

    exit_code, payload = _run_verify_slice_commit(repo, commit, capsys)

    assert exit_code == 1, (
        "a slice whose feature-scoped contract gate refused must be REFUSED "
        f"(exit 1) at E2: got exit_code={exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitRefused", payload
    assert payload.get("refused_half") == "E2", payload
    assert payload.get("kind") == expected_kind, (
        f"the E2 SliceCommitRefused payload must thread kind={expected_kind!r} "
        "through from the underlying contract-gate refusal (DDD-CERT-6, C9) "
        f"so a crafter reading the slice-commit verdict alone can still tell "
        f"build-failure from test-failure -- got payload={payload!r}"
    )


# ===========================================================================
# C9 -- NEGATIVE AT (anti-recurrence, active-RED today)
# ===========================================================================


@pytest.mark.negative_at
def test_e2_never_collapses_build_and_test_failure_to_the_same_kind(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): the SAME
    distinguishability floor as the C8 negative AT, observed at the E2
    `SliceCommitRefused` payload -- an import-broken slice commit and a
    red-assertion slice commit must NEVER report the SAME `kind` (or no
    `kind` at all). Today `_run_contract_gate` threads nothing through, so
    both payloads carry `kind=None` -- `None == None` -- this assertion is
    what fails.
    """
    build_repo, build_commit = _make_committed_repo(
        tmp_path / "build-broken", _make_import_broken_repo
    )
    _, build_payload = _run_verify_slice_commit(build_repo, build_commit, capsys)

    test_repo, test_commit = _make_committed_repo(
        tmp_path / "test-red", _make_red_assertion_repo
    )
    _, test_payload = _run_verify_slice_commit(test_repo, test_commit, capsys)

    build_kind = build_payload.get("kind")
    test_kind = test_payload.get("kind")

    assert build_kind is not None and test_kind is not None, (
        "both E2 refusals must carry a kind discriminator -- got "
        f"build_kind={build_kind!r}, test_kind={test_kind!r}"
    )
    assert build_kind != test_kind, (
        "an import-broken slice commit and a red-assertion slice commit must "
        f"NEVER report the SAME E2 kind -- got build_kind={build_kind!r} == "
        f"test_kind={test_kind!r} (today both collapse to the same "
        "undifferentiated E2 refusal -- this assertion is what fails)"
    )
