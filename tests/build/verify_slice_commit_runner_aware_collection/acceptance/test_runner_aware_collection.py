"""Active-RED acceptance: ``des verify-slice-commit``'s regression-test-file
COLLECTION must be RUNNER-AWARE, never pytest-native-only.

Feature: verify-slice-commit-runner-aware-collection (slice-01).

DEFECT (sister dogfooding nWave on a real cargo repo, repro commit 3de10740,
feature fix-focus-cross-file-tier-regression): ``des verify-slice-commit
--at-kind pytest-regression --regression-test-file X.rs`` mints an honest-
LOOKING ``SliceCommitIndeterminate`` "the declared --regression-test-file
could not be run on the committed tree (missing or uncollectible)" -- but the
completeness check never actually consulted the cargo runner. It COLLECTS the
declared file with a pytest-native collector unconditionally, which is
meaningless on a ``.rs`` file, even when a committed feature-dir
``runner.json`` declares ``{"test_command": "cargo nextest run ..."}`` (the
SAME override ``run_contract_gate._cargo_scope_command`` already consults for
the Gherkin/feature-scoped path). DISTINCT from the sibling fix
(gate-scope-digest-runner-agnostic, d15dc7cc8, which made the Gate-Scope
DIGEST step runner-aware) -- that fix alone still leaves every cargo
pytest-regression slice Indeterminate because THIS collection leg never
consults the runner port at all.

PINNED SEAM (tsunami atoms-in-file + read, binding-resolved):

  * The defect locus is ``_run_regression_gate`` (``src/des/cli/
    verify_slice_commit_completeness.py:357-397``): given a repo-relative
    ``regression_test_file`` it (a) refuses only on ``Path.is_file()``
    absence, then (b) unconditionally spawns ``pytest <file> -q`` via
    ``des_spawn`` -- no extension check, no ``runner.json`` consultation, no
    ``des.ports.test_runner_port.resolve`` call. Its caller,
    ``_run_verify_then_record`` (``:687-749``), maps the returned code back
    to ``SliceCommitVerified`` (0), a refusal (any other non-zero), or --
    ONLY when the code equals the dedicated
    ``_GATE_INDETERMINATE_EXIT_CODE`` sentinel (3) -- the honest
    ``SliceCommitIndeterminate`` lane via ``_record_indeterminate_outcome``
    (reason ``"pytest_regression_file_unrunnable"``, the exact literal
    diagnostic quoted in the DEFECT above).
  * The runner-port seam this collection leg must compose ALREADY EXISTS and
    is proven elsewhere: ``des.ports.test_runner_port.resolve(repo,
    RunnerResolutionContext(feature_id, repo))`` resolves a ``RunnerAdapter``
    from the target's lockfile (``Cargo.toml`` -> ``"cargo-test"``, single-
    lockfile fast path -- ``test_runner_port.py:239-278``);
    ``des.adapters.driven.runner.runner_json.read_runner_json`` reads the
    OPTIONAL ``docs/feature/{feature_id}/runner.json`` override
    (``{"test_command": ...}``); ``RunnerAdapter.run`` dispatches by name to
    the registered run-facet (``cargo_runner.run_cargo_scope``,
    ``cargo_runner.py:84-132``), which shells the resolved ``cargo`` and maps
    exit 0 -> PASS, exit 4/94 (empty-scope) -> raise
    ``RunnerAdapterUnavailable``, any other non-zero -> FAIL -- NEVER a
    silent pass, NEVER a crash. ``run_contract_gate._maybe_route_through_
    cargo`` (``run_contract_gate.py:2253-2302``) is the PROVEN precedent
    composing this exact seam for the Gherkin/feature-scoped E2 path; this
    feature's fix composes the SAME seam for the ``--at-kind pytest-
    regression`` collection leg instead of the unconditional pytest spawn.

  PINNED CONTRACT (the fix these ATs make GREEN): when ``--regression-test-
  file`` is NON-Python (extension not ``.py``) OR the feature-dir declares a
  ``runner.json`` ``test_command``, the collection leg routes through the
  runner-port instead of the pytest-native spawn. A successful runner RUN
  (exit-0 PASS) earns ``SliceCommitVerified`` -- the file is "collectible/
  runnable", never the pytest-empty ``"missing or uncollectible"``
  Indeterminate. A ``RunnerAdapterUnavailable`` runner (cargo empty-scope, or
  no runner resolves at all) degrades LOUD to the EXISTING honest
  ``SliceCommitIndeterminate`` lane -- naming the RUNNER as the cause, never
  reusing the pytest-native ``"pytest_regression_file_unrunnable"`` literal
  for a target the pytest collector was never meant to touch, and never a
  fabricated pass. The ``.py`` path stays byte-identical (regression guard,
  mirrors the shipped ``tests/bugs/des/
  test_verify_slice_commit_pytest_regression_behavioral_attestation.py``
  fixture convention).

DRIVING SURFACE (Mandate-13, Layer-3 composition, IN-PROCESS default): the
REAL ``des.cli.verify_slice_commit_completeness.main()`` composition-root
entry, driven in-process and captured via ``capsys`` -- mirrors the PROVEN,
already-GREEN precedent
``test_verify_slice_commit_pytest_regression_behavioral_attestation.py``
(same CLI, same in-process pattern). A deterministic, REAL chmod+x fake
``cargo`` script is prepended onto ``PATH`` via ``monkeypatch.setenv`` so the
in-process call's internal ``subprocess.run(["cargo", ...])`` (inside
``cargo_runner.run_cargo_scope``) resolves the fake binary via
``shutil.which`` -- no real Rust toolchain required, deterministic on any
box. Fixtures are disposable ``tmp_path`` git repos; every git write targets
the fixture only.

Active-RED (atdd_pure, no @skip): every import here is stdlib + ``pytest`` +
the already-shipped ``des.cli.verify_slice_commit_completeness`` /
``des.adapters.driven.logging.at_completion_ledger`` modules, so the module
COLLECTS cleanly. The POSITIVE ATs fail with a semantic ``AssertionError``
(``SliceCommitVerified`` expected, something else observed) because at HEAD
the collection leg is pytest-native-only -- never a collection/import error.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc


_SLICE_ID = "slice-01"
_REGRESSION_REL = "tests/regression_check.rs"
_PY_REGRESSION_REL = "tests/regression_check.py"

_FEATURE_ID_POS_RUNNER_JSON = "vscc-runner-aware-pos-runner-json"
_FEATURE_ID_POS_NO_RUNNER_JSON = "vscc-runner-aware-pos-convention"
_FEATURE_ID_UNAVAILABLE = "vscc-runner-aware-unavailable"
_FEATURE_ID_PY_GUARD = "vscc-runner-aware-py-guard"
_FEATURE_ID_NO_RUNNER = "vscc-runner-aware-no-runner"

# The literal legacy pytest-native diagnostic (`_run_regression_gate` /
# `_record_indeterminate_outcome`'s default `pytest_regression_file_unrunnable`
# caller-supplied text, verify_slice_commit_completeness.py:742-746). Pinning
# it by name makes every "never THIS message" assertion self-documenting: a
# diagnostic that contains this literal on a genuinely cargo-collectible or
# cargo-unavailable target is provably still the pytest-blind pre-fix path.
_LEGACY_PYTEST_UNCOLLECTIBLE_TEXT = (
    "could not be run on the committed tree (missing or uncollectible)"
)


# ---------------------------------------------------------------------------
# fixtures: disposable git repos + a deterministic FAKE cargo on PATH
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
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


def _write_cargo_manifest(repo: Path) -> None:
    (repo / "Cargo.toml").write_text(
        '[package]\nname = "runner_aware_fixture"\nversion = "0.0.0"\n'
        'edition = "2021"\n',
        encoding="utf-8",
    )


def _write_rust_regression_file(repo: Path, rel: str = _REGRESSION_REL) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#[test]\nfn regression_stays_fixed() { assert_eq!(1 + 1, 2); }\n",
        encoding="utf-8",
    )
    return path


def _write_runner_json(repo: Path, feature_id: str) -> None:
    runner_json = repo / "docs" / "feature" / feature_id / "runner.json"
    runner_json.parent.mkdir(parents=True, exist_ok=True)
    runner_json.write_text(
        json.dumps(
            {
                "feature_id": feature_id,
                "test_command": "cargo nextest run --test regression_check",
            }
        ),
        encoding="utf-8",
    )


def _commit_all(repo: Path, slice_id: str = _SLICE_ID) -> None:
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"fix(slice): runner-aware regression collection\n\nSlice-Id: {slice_id}",
    )


def _plant_fake_cargo(bin_dir: Path, *, run_exit: int) -> None:
    """A REAL chmod+x fake ``cargo`` -- deterministic, no Rust toolchain needed.

    Prepending its dir to PATH makes ``shutil.which("cargo")`` (the
    ``resolve_tool`` rung-1, ``cargo_runner.py`` / ``tool_discovery.py``) win
    BEFORE any real cargo installed on the box. Responds to ``nextest list``
    with a well-formed non-empty listing (never blocking on an unrelated list
    call some implementation shape might make) and to ``nextest run`` with
    the configured ``run_exit`` -- the exit code this AT is pinning:

      * 0  -> PASS (the collectible/runnable positive case);
      * 4  -> cargo's "no tests to run" empty-scope refusal, mapped by the
              SHIPPED ``cargo_runner.run_cargo_scope`` to
              ``RunnerAdapterUnavailable`` (INDETERMINATE, never a red);
      * 94 -> nextest's "filterset matched no binary names" empty-scope
              refusal, mapped identically to ``RunnerAdapterUnavailable``.

    Any OTHER invocation (unmatched subcommand) exits 0 -- this fake never
    manufactures a spurious failure for a call shape this AT does not pin.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "#!/bin/sh\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "list" ]; then\n'
        '  echo "runner_aware_fixture:"\n'
        '  echo "    regression::regression_stays_fixed"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "run" ]; then\n'
        f"  exit {run_exit}\n"
        "fi\n"
        "exit 0\n"
    )
    cargo = bin_dir / "cargo"
    cargo.write_text(script, encoding="utf-8")
    cargo.chmod(cargo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _prepend_fake_cargo_to_path(
    monkeypatch: pytest.MonkeyPatch, fake_bin: Path
) -> None:
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))


# ---------------------------------------------------------------------------
# driving port (Layer-3 composition over the REAL CLI's main(), in-process)
# ---------------------------------------------------------------------------


def _drive_verify_slice_commit(
    repo: Path,
    feature_id: str,
    regression_test_file_rel: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des verify-slice-commit`` CLI (``main()``) in-process,
    capturing its single-line JSON payload -- the SAME pattern the shipped
    ``test_verify_slice_commit_pytest_regression_behavioral_attestation.py``
    proves for this exact CLI.
    """
    exit_code = vscc.main(
        [
            "--repo",
            str(repo),
            "--commit",
            "HEAD",
            "--feature-id",
            feature_id,
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            regression_test_file_rel,
        ]
    )
    captured = capsys.readouterr()
    stdout = captured.out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


def _diag(exit_code: int, payload: dict[str, object]) -> str:
    return f"\nexit_code={exit_code}\npayload={payload!r}"


# ===========================================================================
# 1. POSITIVE -- .rs + committed runner.json test_command (active-RED today)
# ===========================================================================


def test_cargo_rs_regression_file_with_runner_json_test_command_is_collected_through_the_runner_port(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``.rs`` regression-test-file + a committed feature-dir ``runner.json``
    declaring a cargo ``test_command`` must be COLLECTED through the
    runner-port -- a successful (fake) cargo run earns
    ``SliceCommitVerified``, the file is "collectible/runnable", NEVER the
    pytest-empty ``"...missing or uncollectible"`` Indeterminate a pytest
    collector would mint on a Rust file.

    Active-RED at HEAD: ``_run_regression_gate`` spawns pytest on the ``.rs``
    file unconditionally -- pytest cannot collect it, so the slice never
    earns ``SliceCommitVerified`` (this AT's semantic assertion fails: the
    observed exit_code/event is NOT the Verified-capable outcome).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_cargo_manifest(repo)
    _write_rust_regression_file(repo)
    _write_runner_json(repo, _FEATURE_ID_POS_RUNNER_JSON)
    _commit_all(repo)

    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, run_exit=0)
    _prepend_fake_cargo_to_path(monkeypatch, fake_bin)

    exit_code, payload = _drive_verify_slice_commit(
        repo, _FEATURE_ID_POS_RUNNER_JSON, _REGRESSION_REL, capsys
    )

    assert exit_code == 0 and payload.get("event") == "SliceCommitVerified", (
        "a .rs regression-test-file with a committed runner.json test_command "
        "and a genuinely PASSING (fake) cargo run must earn "
        "SliceCommitVerified via the runner-port collection leg -- the file "
        "is collectible/runnable, never pytest-uncollectible."
        + _diag(exit_code, payload)
    )
    assert payload.get("event") != "SliceCommitIndeterminate" and (
        _LEGACY_PYTEST_UNCOLLECTIBLE_TEXT not in json.dumps(payload)
    ), (
        "a cargo-collectible .rs file must never mint the pytest-native "
        f"'{_LEGACY_PYTEST_UNCOLLECTIBLE_TEXT}' Indeterminate -- that "
        "diagnostic means the pytest collector ran on a Rust file it was "
        "never meant to touch." + _diag(exit_code, payload)
    )

    verified = AtCompletionLedger(_FEATURE_ID_POS_RUNNER_JSON, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "the runner-aware collection leg must record a genuine "
        f"SliceCommitVerified ledger entry -- verified={sorted(verified)!r}"
        + _diag(exit_code, payload)
    )


# ===========================================================================
# 2. POSITIVE -- .rs, NO runner.json, convention-derived cargo command
# ===========================================================================


def test_cargo_rs_regression_file_without_runner_json_is_still_collected_through_the_runner_port(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OTHER routing trigger (DESIGN [REF] Architecture & Contract: 'NON-
    Python (extension not .py) OR a committed runner.json') -- a ``.rs``
    regression-test-file with NO ``runner.json`` at all must still route
    through the runner-port purely by extension, resolving cargo via the
    single-lockfile ``Cargo.toml`` fast path. A genuinely PASSING (fake)
    cargo run still earns ``SliceCommitVerified`` -- ``runner.json`` is an
    OPTIONAL command override, never a precondition for runner routing.

    Active-RED at HEAD: identical failure shape to AT-1 -- the pytest-native
    spawn is unconditional regardless of ``runner.json`` presence.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_cargo_manifest(repo)
    _write_rust_regression_file(repo)
    _commit_all(repo)

    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, run_exit=0)
    _prepend_fake_cargo_to_path(monkeypatch, fake_bin)

    exit_code, payload = _drive_verify_slice_commit(
        repo, _FEATURE_ID_POS_NO_RUNNER_JSON, _REGRESSION_REL, capsys
    )

    assert exit_code == 0 and payload.get("event") == "SliceCommitVerified", (
        "a .rs regression-test-file with NO runner.json must still route "
        "through the runner-port by extension alone (Cargo.toml single-"
        "lockfile fast path resolves cargo-test) and earn "
        "SliceCommitVerified on a genuinely passing (fake) cargo run."
        + _diag(exit_code, payload)
    )

    verified = AtCompletionLedger(
        _FEATURE_ID_POS_NO_RUNNER_JSON, repo
    ).verified_slices()
    assert _SLICE_ID in verified, (
        "extension-triggered runner routing (no runner.json) must record a "
        f"genuine SliceCommitVerified ledger entry -- "
        f"verified={sorted(verified)!r}" + _diag(exit_code, payload)
    )


# ===========================================================================
# 3. NEGATIVE -- runner UNAVAILABLE (cargo empty-scope) -> honest degrade
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("run_exit", "flavor"),
    [
        pytest.param(4, "no tests to run (exit 4)", id="run-exit-4"),
        pytest.param(94, "no binary matched (exit 94)", id="run-exit-94"),
    ],
)
def test_cargo_regression_file_with_runner_unavailable_still_degrades_to_honest_indeterminate_not_pytest_uncollectible(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    run_exit: int,
    flavor: str,
) -> None:
    """The false-green guard's mirror image, in the honesty direction: a
    ``.rs`` regression-test-file whose (fake) cargo run is UNTRUSTWORTHY
    (empty-scope exit 4 / 94 -- both mapped by the SHIPPED
    ``cargo_runner.run_cargo_scope`` to ``RunnerAdapterUnavailable``) must
    NEVER earn ``SliceCommitVerified``, and must degrade to the EXISTING
    honest ``SliceCommitIndeterminate`` lane naming the RUNNER as the cause
    -- NEVER the pytest-native ``'...missing or uncollectible'`` literal
    (that diagnostic is a LIE here: the file was never uncollectible, the
    RUNNER reported empty-scope).

    Active-RED at HEAD: the cargo runner is never consulted at all -- the
    pytest spawn either produces a DIFFERENT (pytest-native, misleading)
    Indeterminate or a bare refusal, never the runner-named honest lane this
    AT pins.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_cargo_manifest(repo)
    _write_rust_regression_file(repo)
    _write_runner_json(repo, _FEATURE_ID_UNAVAILABLE)
    _commit_all(repo)

    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, run_exit=run_exit)
    _prepend_fake_cargo_to_path(monkeypatch, fake_bin)

    exit_code, payload = _drive_verify_slice_commit(
        repo, _FEATURE_ID_UNAVAILABLE, _REGRESSION_REL, capsys
    )

    assert not (exit_code == 0 and payload.get("event") == "SliceCommitVerified"), (
        f"an untrustworthy (fake) cargo run ({flavor}) must NEVER clear "
        "verify-slice-commit as a clean SliceCommitVerified pass."
        + _diag(exit_code, payload)
    )

    ledger_records = AtCompletionLedger(_FEATURE_ID_UNAVAILABLE, repo).read_records(
        feature_id=_FEATURE_ID_UNAVAILABLE, event_type="SliceCommitIndeterminate"
    )
    honest = payload.get("event") == "SliceCommitIndeterminate" or bool(ledger_records)
    assert honest, (
        f"the {flavor} runner-unavailable degrade must surface as the "
        "honest SliceCommitIndeterminate lane (ledger record or driving-"
        "channel event), never a silent/bare refusal." + _diag(exit_code, payload)
    )

    diagnostic_blob = json.dumps(payload) + json.dumps(ledger_records)
    assert _LEGACY_PYTEST_UNCOLLECTIBLE_TEXT not in diagnostic_blob, (
        f"a runner-reported empty-scope ({flavor}) must be diagnosed as a "
        f"RUNNER problem, never disguised as the pytest-native "
        f"'{_LEGACY_PYTEST_UNCOLLECTIBLE_TEXT}' literal -- that message "
        "means 'the pytest collector could not import this file', which is "
        "not what happened here." + _diag(exit_code, payload)
    )


# ===========================================================================
# 4. NEGATIVE -- NO resolvable runner at all -> honest degrade, never fabricated
# ===========================================================================


@pytest.mark.negative_at
def test_rs_regression_file_with_no_resolvable_runner_degrades_to_honest_indeterminate_not_a_fabricated_pass(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``.rs`` regression-test-file in a target with NO recognized lockfile
    at all (no ``Cargo.toml``, no ``runner.json``) has no runner to route
    through -- ``des.ports.test_runner_port.resolve`` returns
    ``UnrecognizedRunner``. This can never be fabricated into a collectible
    pass; it must degrade to the honest ``SliceCommitIndeterminate`` lane
    (never a crash, never a silent refusal, never coerced through the
    pytest-native collector -- the file is not Python).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_rust_regression_file(repo)
    _commit_all(repo)

    exit_code, payload = _drive_verify_slice_commit(
        repo, _FEATURE_ID_NO_RUNNER, _REGRESSION_REL, capsys
    )

    assert not (exit_code == 0 and payload.get("event") == "SliceCommitVerified"), (
        "a .rs file with NO resolvable runner (no lockfile, no runner.json) "
        "must NEVER be fabricated into a clean SliceCommitVerified pass."
        + _diag(exit_code, payload)
    )

    ledger_records = AtCompletionLedger(_FEATURE_ID_NO_RUNNER, repo).read_records(
        feature_id=_FEATURE_ID_NO_RUNNER, event_type="SliceCommitIndeterminate"
    )
    honest = payload.get("event") == "SliceCommitIndeterminate" or bool(ledger_records)
    assert honest, (
        "an unroutable .rs regression-test-file (no recognized runner) must "
        "degrade to the honest SliceCommitIndeterminate lane -- can't "
        "fabricate 'collectible' out of nothing." + _diag(exit_code, payload)
    )


# ===========================================================================
# 5. REGRESSION GUARD -- .py collection path stays byte-identical
# ===========================================================================


def test_python_regression_test_file_collection_path_stays_unchanged(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The EXISTING pytest-native collection path for a ``.py``
    ``--regression-test-file`` must keep clearing unchanged -- guards the
    runner-aware routing fix against perturbing the shipped behavioral-
    attestation path proven in
    ``tests/bugs/des/test_verify_slice_commit_pytest_regression_behavioral_
    attestation.py::test_pytest_regression_slice_with_passing_regression_
    test_is_verified_behaviorally``. Must stay GREEN both BEFORE and AFTER
    the runner-aware fix -- a ``.py`` file never triggers runner routing.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    path = repo / _PY_REGRESSION_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def test_the_regression_stays_fixed():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    _commit_all(repo)

    exit_code, payload = _drive_verify_slice_commit(
        repo, _FEATURE_ID_PY_GUARD, _PY_REGRESSION_REL, capsys
    )

    assert exit_code == 0 and payload.get("event") == "SliceCommitVerified", (
        "the EXISTING pytest-native .py collection path must keep clearing "
        "unchanged after the runner-aware routing fix." + _diag(exit_code, payload)
    )

    verified = AtCompletionLedger(_FEATURE_ID_PY_GUARD, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "the .py regression-test-file path must stay byte-coherent -- "
        f"verified={sorted(verified)!r}" + _diag(exit_code, payload)
    )
