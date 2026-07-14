"""Regression -- ``des run-slice-ats`` (wired at ``commit-msg``,
``.pre-commit-config.yaml:445-452``) must SEE a slice's pytest-only
acceptance test, not just Gherkin ``.feature`` files.

RCA: ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/deliver/rca.md``.
Feature-delta: ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/
feature-delta.md``.

This file pins Vector 1 ONLY (slice-01 of the Slice Plan). Vector 2 (the
``commit-slice --feature-id`` disarming) is a SEPARATE slice, deliberately
kept apart -- see ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/
feature-delta.md`` "Wave: DISCUSS / [REF] Slice Plan" for why the separation
is the point.

The defect: ``_slice_feature_dir`` (``run_contract_gate.py:2028-2036``) scans
ONLY ``*.feature`` files. On a pytest-only slice it finds nothing and returns
``NOT_APPLICABLE``/exit-0 -- a RED pytest AT and a GREEN pytest AT produce
BYTE-IDENTICAL output (measured, Repro A vs Repro B in the RCA). The gate
never inspects the pytest slice's content at all. The hardened, pytest-aware
SSOT oracle (``des.application.slice_at_completeness.feature_files_for_slice``)
already FINDS what ``_slice_feature_dir`` calls absent (Repro D).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.run_slice_ats.main()`` -- the ACTUAL ``commit-msg``-stage
executor, unchanged CLI signature (``--repo-root`` / ``--entering-slice``) --
invoked in-process, captured via ``capsys``. No monkeypatching: the runner
resolution (``TestRunnerPort.resolve``) and the pytest subprocess spawn
underneath run for REAL, mirroring the proven pattern in
``tests/bugs/des/test_contract_gate_scopes_shipped_plus_entering.py``.

Feature-id resolution: per the feature-delta's DESIGN reference, the fix
routes ``main()`` through ``spine_ledger_pre_commit_hook._active_feature_id``
(already ships, already runs in a commit-stage hook today,
``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``). This file seeds that
ledger via the SAME shipped ``AtCompletionLedger`` writer the reuse fixture
below uses, so exactly one ledger resolves unambiguously (or, for the
INDETERMINATE control, deliberately more than one). It never asserts on
WHICH function performs the resolution or how the SCOPE step is internally
wired -- only the CLI's observable exit code / JSON payload (Mandate: "pin
the BEHAVIOUR, not the internals").

Fixtures: real tmp git repos, own local ``user.name``/``user.email``
(git-safety rule #48), reusing the throwaway-repo + pytest head-comment-tag
idiom from ``test_contract_gate_scopes_shipped_plus_entering.py``
(``_write_regression_test``) rather than inventing a third builder.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import run_slice_ats


_FEATURE_ASYMMETRY = "fix-precommit-vacuous-scaffold-asymmetry"
_FEATURE_GREEN_PYTEST = "fix-precommit-vacuous-scaffold-green-pytest"
_FEATURE_GREEN_GHERKIN = "fix-precommit-vacuous-scaffold-green-gherkin"
_FEATURE_RED_GHERKIN = "fix-precommit-vacuous-scaffold-red-gherkin"
_FEATURE_INDETERMINATE_A = "fix-precommit-vacuous-scaffold-indeterminate-a"
_FEATURE_INDETERMINATE_B = "fix-precommit-vacuous-scaffold-indeterminate-b"
_FEATURE_HOLLOW = "fix-precommit-vacuous-scaffold-hollow-at"
_FEATURE_NO_AT_CONTROL = "fix-precommit-vacuous-scaffold-no-at-control"
_FEATURE_SKIPPED_ONLY = "fix-precommit-vacuous-scaffold-skipped-only"


# ---------------------------------------------------------------------------
# Shared fixture builders (mirrors
# test_contract_gate_scopes_shipped_plus_entering.py -- Test Reuse row 1).
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    """Isolated tmp repo with its OWN local git config (rule #48) -- the real
    project repo's ``user.name``/``user.email`` are never read or touched.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _write_pyproject(repo: Path) -> None:
    """The pytest lockfile -- resolves ``TestRunnerPort.resolve`` to pytest
    via the single-lockfile fast path (no polyglot ambiguity, no other
    recognized lockfile present).
    """
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
    )


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible slice AT, head-tagged for the pytest-aware
    SSOT oracle (``# @feature-{id}`` / ``# @{slice_id}``) -- mirrors
    ``test_contract_gate_scopes_shipped_plus_entering.py::_write_regression_test``.
    """
    rel_dir = Path("tests") / feature_id.replace("-", "_")
    path = repo / rel_dir / f"test_{slice_id.replace('-', '_')}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    name = f"test_{slice_id.replace('-', '_')}_behaviour"
    if passing:
        body = f"def {name}():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            f"def {name}():\n"
            f"    assert False, 'this AT is RED on purpose ({slice_id})'\n"
        )
    path.write_text(f"# @feature-{feature_id}\n# @{slice_id}\n{body}", encoding="utf-8")
    return path


def _write_at_file_with_body(
    repo: Path, feature_id: str, slice_id: str, body: str
) -> Path:
    """Like ``_write_regression_test`` but with a caller-supplied BODY -- lets
    the examiner-caught-defect tests below construct AT files that carry the
    real discovery head-tags (``# @feature-{id}`` / ``# @{slice_id}``) while
    controlling exactly HOW zero observed execution is produced (a hollow
    file, a module-level skip, a ``@pytest.mark.skip``, an
    ``@pytest.mark.xfail(run=False)``, an empty ``parametrize`` set, ...).
    """
    rel_dir = Path("tests") / feature_id.replace("-", "_")
    path = repo / rel_dir / f"test_{slice_id.replace('-', '_')}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# @feature-{feature_id}\n# @{slice_id}\n{body}", encoding="utf-8")
    return path


def _write_gherkin_slice_at(
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> None:
    """A tagged Gherkin scenario + its pytest-bdd binding -- the Repro-C
    control: the ALREADY-correct Gherkin path must not regress.
    """
    feature_dir = repo / "tests" / "acceptance"
    feature_dir.mkdir(parents=True, exist_ok=True)
    stem = feature_id.replace("-", "_")
    outcome_word = "passes" if passing else "fails"
    (feature_dir / f"{stem}.feature").write_text(
        f"@feature-{feature_id} @{slice_id}\n"
        "Feature: control case\n"
        "  Scenario: the control scenario\n"
        "    Given nothing\n"
        "    When nothing happens\n"
        f"    Then it {outcome_word} on purpose\n",
        encoding="utf-8",
    )
    then_assertion = "pass" if passing else "assert False, 'deliberately RED'"
    (feature_dir / f"test_{stem}.py").write_text(
        "from __future__ import annotations\n\n"
        "from pytest_bdd import given, scenarios, then, when\n\n"
        f'scenarios("{stem}.feature")\n\n'
        '@given("nothing")\n'
        "def _given() -> None:\n    pass\n\n"
        '@when("nothing happens")\n'
        "def _when() -> None:\n    pass\n\n"
        f'@then("it {outcome_word} on purpose")\n'
        f"def _then() -> None:\n    {then_assertion}\n",
        encoding="utf-8",
    )


def _commit_with_trailer(repo: Path, slice_id: str, subject: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{subject}\n\nSlice-Id: {slice_id}")


def _seed_ledger(repo: Path, feature_id: str) -> None:
    """Exactly ONE telemetry ledger resolves unambiguously (mirrors the
    SHIPPED resolver ``spine_ledger_pre_commit_hook._active_feature_id``,
    ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``). Reuses the shipped
    ``AtCompletionLedger`` writer (Reuse Analysis row 2) rather than
    hand-rolling the JSONL substrate.
    """
    AtCompletionLedger(feature_id, repo).append_workflow_phase_completed_distill()


def _run_slice_ats(
    repo: Path, entering_slice: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des run-slice-ats`` CLI (``main()``) in-process -- the
    ACTUAL ``commit-msg``-stage executor, unchanged signature
    (``--repo-root`` / ``--entering-slice``) -- capturing its single-line
    JSON payload via ``capsys``. Never passes a ``--feature-id`` flag: the
    fix resolves the feature internally (via the ledger), so the driving
    surface pinned here is the one ``run_slice_ats_precommit.py`` already
    invokes today -- pinning BEHAVIOUR, not which function performs the
    resolution.
    """
    argv = ["--repo-root", str(repo), "--entering-slice", entering_slice]
    exit_code = run_slice_ats.main(argv)
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


def _run_slice_ats_with_human_line(
    repo: Path, entering_slice: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object], str]:
    """Same driving surface as ``_run_slice_ats`` (the REAL ``main()``,
    in-process) but ADDITIONALLY captures the human-readable summary line
    (``human_surface.print_human_summary``, stderr by default) -- the exact
    surface a developer's terminal shows, and the surface the examiner's
    report quotes verbatim (``"✅ PASS — slice slice-01 acceptance
    tests passed"``). ``_run_slice_ats`` deliberately captures stdout (the
    JSON payload) only; this is an ADDITIVE variant, not a signature change,
    so the five already-green tests above are untouched.
    """
    argv = ["--repo-root", str(repo), "--entering-slice", entering_slice]
    exit_code = run_slice_ats.main(argv)
    captured = capsys.readouterr()
    json_lines = [ln for ln in captured.out.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    human_lines = [ln for ln in captured.err.splitlines() if ln.strip()]
    human_line = human_lines[-1] if human_lines else ""
    return exit_code, payload, human_line


# ===========================================================================
# THE ASYMMETRY -- item 1. Pin the DIFFERENCE, not just one arm. Active-RED
# today: both repos below produce the byte-identical NOT_APPLICABLE verdict.
# ===========================================================================


def test_red_pytest_only_at_refuses_and_differs_from_the_green_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A RED pytest-only slice AT must REFUSE the commit, and its outcome
    must DIFFER from the identically-shaped GREEN run.

    RED for the right reason today: ``_slice_feature_dir``
    (``run_contract_gate.py:2028-2036``) scans only ``*.feature`` files -- on
    a pytest-only slice it finds nothing regardless of content, so BOTH the
    RED and GREEN repos below emit the identical ``NOT_APPLICABLE``/exit-0
    payload (Repro A == Repro B in the RCA). A gate that merely refuses
    everything would satisfy "RED refuses" without ever proving it inspected
    the content -- the payload-equality assertion is what rules that out.
    """
    red_repo = tmp_path / "red_repo"
    _git_init(red_repo)
    _write_pyproject(red_repo)
    _seed_ledger(red_repo, _FEATURE_ASYMMETRY)
    _write_regression_test(red_repo, _FEATURE_ASYMMETRY, "slice-01", passing=False)
    _commit_with_trailer(red_repo, "slice-01", "feat(slice): red pytest-only AT")
    red_exit, red_payload = _run_slice_ats(red_repo, "slice-01", capsys)

    green_repo = tmp_path / "green_repo"
    _git_init(green_repo)
    _write_pyproject(green_repo)
    _seed_ledger(green_repo, _FEATURE_ASYMMETRY)
    _write_regression_test(green_repo, _FEATURE_ASYMMETRY, "slice-01", passing=True)
    _commit_with_trailer(green_repo, "slice-01", "feat(slice): green pytest-only AT")
    green_exit, green_payload = _run_slice_ats(green_repo, "slice-01", capsys)

    assert red_exit != 0, (
        "a RED pytest-only slice AT must REFUSE the commit -- today the gate "
        "is blind to pytest ATs and returns NOT_APPLICABLE/exit-0 regardless "
        f"of content. got exit_code={red_exit!r} payload={red_payload!r}"
    )
    assert red_payload.get("verdict") != "NOT_APPLICABLE", (
        "a RED pytest AT must not be waved through as NOT_APPLICABLE -- "
        f"payload={red_payload!r}"
    )
    assert green_exit == 0, (
        f"sanity: a GREEN pytest-only slice AT must pass. got "
        f"exit_code={green_exit!r} payload={green_payload!r}"
    )
    assert red_payload != green_payload, (
        "the RED and GREEN runs must produce DIFFERENT observable outcomes "
        "-- today they are BYTE-IDENTICAL (Repro A == Repro B in the RCA), "
        "proof the gate never inspects the pytest slice's content at all. "
        f"red_payload={red_payload!r} green_payload={green_payload!r}"
    )


# ===========================================================================
# THE ANTI-OVERCORRECTION CONTROLS -- item 2 (load-bearing, do NOT omit).
# A gate that starts refusing everything gets reverted within a day, which
# is worse than the bug. Before believing its NO, prove it can still say YES.
# ===========================================================================


@pytest.mark.negative_at
def test_green_pytest_only_at_is_never_refused_by_the_widened_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A genuinely GREEN pytest-only slice AT must still PASS -- not merely
    "not refused" (``NOT_APPLICABLE`` would also satisfy a bare exit==0
    check), but a genuine ``PASS`` verdict, proving the widened gate actually
    RAN the AT rather than continuing to silently no-op on it.

    RED for the right reason today: the gate is blind to pytest ATs, so this
    GREEN AT ALSO earns ``NOT_APPLICABLE`` today, not ``PASS`` -- the exact
    same blindness the asymmetry test above exposes, from the other side.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_GREEN_PYTEST)
    _write_regression_test(repo, _FEATURE_GREEN_PYTEST, "slice-01", passing=True)
    _commit_with_trailer(repo, "slice-01", "feat(slice): green pytest-only AT")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code == 0, (
        "a genuinely GREEN pytest-only slice AT must never be refused -- the "
        f"fix must not make everything refuse. got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("verdict") == "PASS", (
        "a genuinely GREEN pytest-only slice AT must earn a real PASS "
        "verdict (not a blind NOT_APPLICABLE no-op) -- proof the widened "
        f"gate actually ran it. payload={payload!r}"
    )


@pytest.mark.negative_at
def test_green_gherkin_at_is_never_refused_by_the_widened_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A genuinely GREEN Gherkin-authored slice AT must still PASS -- the
    fix must not disturb the already-correct Gherkin path. Green both BEFORE
    and AFTER the fix (untouched by either half of it).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_GREEN_GHERKIN)
    _write_gherkin_slice_at(repo, _FEATURE_GREEN_GHERKIN, "slice-01", passing=True)
    _commit_with_trailer(repo, "slice-01", "feat(slice): green gherkin AT")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code == 0, (
        "a genuinely GREEN Gherkin slice AT must never be refused by the "
        f"pytest-widening fix. got exit_code={exit_code!r} payload={payload!r}"
    )
    assert payload.get("verdict") == "PASS", payload


# ===========================================================================
# THE GHERKIN REGRESSION CONTROL -- item 3. Must not disturb what it already
# saw. Green both BEFORE and AFTER the fix (Repro C in the RCA).
# ===========================================================================


def test_gherkin_red_at_refusal_is_not_regressed_by_the_pytest_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A RED Gherkin-authored slice AT still refuses (exit 1) exactly as it
    does today (Repro C) -- the fix widens what the gate can SEE; it must
    not disturb what it already saw. Green both BEFORE and AFTER the fix.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_RED_GHERKIN)
    _write_gherkin_slice_at(repo, _FEATURE_RED_GHERKIN, "slice-01", passing=False)
    _commit_with_trailer(repo, "slice-01", "feat(slice): red gherkin AT")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code == 1, (
        "a RED Gherkin slice AT must still refuse the commit exactly as it "
        f"does today -- unregressed by the pytest-blindness fix. got "
        f"exit_code={exit_code!r} payload={payload!r}"
    )
    assert payload.get("verdict") == "FAIL", payload


# ===========================================================================
# CANNOT-RUN IS LOUD, NEVER A PASS -- item 4, THE negative AT on the CLASS.
# When the gate genuinely cannot resolve which feature is being committed,
# it degrades LOUD to INDETERMINATE (exit 4) -- never exit 0. A check that
# could not run must never be indistinguishable from a check that passed.
# ===========================================================================


@pytest.mark.negative_at
def test_ambiguous_feature_ledger_never_earns_a_pass_it_degrades_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When the repo carries TWO in-flight feature telemetry ledgers, the
    gate genuinely cannot resolve which feature the commit belongs to --
    the resolver (``_active_feature_id``-equivalent) cannot disambiguate.
    The gate MUST degrade LOUD to INDETERMINATE (exit 4, the code
    ``run_slice_ats.py:76`` already reserves) -- it must NEVER default to
    ``NOT_APPLICABLE``/exit-0, which would be indistinguishable from "I
    checked and there was nothing to check."

    RED for the right reason today: ``main()`` performs no feature-id
    resolution at all, so the ambiguous ledgers are invisible to it -- it
    falls straight through to the blind ``.feature``-only scan, finds
    nothing (this slice's real AT is pytest-only), and emits
    ``NOT_APPLICABLE``/exit-0 -- exit_code=0, not the expected 4.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_INDETERMINATE_A)
    _seed_ledger(repo, _FEATURE_INDETERMINATE_B)
    _write_regression_test(repo, _FEATURE_INDETERMINATE_A, "slice-01", passing=False)
    _commit_with_trailer(repo, "slice-01", "feat(slice): ambiguous feature ledger")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code == 4, (
        "when the gate genuinely cannot resolve which feature is being "
        "committed (two in-flight telemetry ledgers), it must degrade LOUD "
        "to INDETERMINATE (exit 4) -- a check that could not run must never "
        f"look like a check that passed. got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("verdict") == "INDETERMINATE", (
        f"expected an INDETERMINATE verdict -- payload={payload!r}"
    )
    assert exit_code not in (0, 1), (
        "INDETERMINATE must be distinguishable on the exit-code observable "
        f"from both PASS/NOT_APPLICABLE (0) and FAIL (1). payload={payload!r}"
    )

    reason = str(payload.get("reason", "")).lower()
    self_explains = any(
        marker in reason
        for marker in (
            "feature",
            "ambiguous",
            "ledger",
            "cannot resolve",
            "indeterminate",
            "multiple",
        )
    )
    assert self_explains, (
        "the INDETERMINATE verdict must NAME what could not be resolved "
        "(the feature id) and why (ambiguous/multiple telemetry ledgers) -- "
        f"a bare, unexplained refusal is not enough. payload={payload!r}"
    )


# ===========================================================================
# DEFECT 1 (examiner-caught, reproduced verbatim) -- a VACUOUS AT PASSES.
#
# A slice's declared AT file exists on disk, head-tagged for this slice, but
# contains ZERO test functions -- the vacuous scaffold this feature is NAMED
# after, surviving inside its own cure. Root cause: ``pytest_runner.py``'s
# ``_GREEN_EXIT_CODES = frozenset({0, 5})`` folds pytest's exit code 5 ("no
# tests were collected for the scope") into the SAME green bucket as exit 0
# ("all selected tests passed") -- so a hollow file and a real, green AT are
# byte-identical on both the JSON payload and the human-readable console
# line the examiner actually read.
# ===========================================================================


def test_hollow_at_scaffold_is_never_indistinguishable_from_a_genuine_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declared-but-empty AT file must not earn the SAME observable outcome
    as a genuinely GREEN AT -- on the exit code, the verdict field, AND the
    developer-visible console line (the examiner's whole complaint: the
    console output was identical for "my AT ran and passed" and "my AT file
    is empty").

    Note the distinction that matters (must NOT collapse): this is NOT the
    "no AT file at all" case (pinned separately, unchanged, as
    ``NOT_APPLICABLE`` below) -- a file EXISTS and CLAIMS to be this slice's
    acceptance test. Zero observed execution over a file that DECLARES
    itself an AT is a LOUD refusal, not a silent PASS and not a silent
    NOT_APPLICABLE (that would collapse it right back into "nothing
    declared").
    """
    hollow_repo = tmp_path / "hollow_repo"
    _git_init(hollow_repo)
    _write_pyproject(hollow_repo)
    _seed_ledger(hollow_repo, _FEATURE_HOLLOW)
    _write_at_file_with_body(
        hollow_repo,
        _FEATURE_HOLLOW,
        "slice-01",
        "# this AT file head-tags itself for slice-01 but authors ZERO test\n"
        "# functions -- the vacuous scaffold this feature exists to close.\n"
        "x = 1\n",
    )
    _commit_with_trailer(hollow_repo, "slice-01", "feat(slice): hollow AT scaffold")
    hollow_exit, hollow_payload, hollow_human = _run_slice_ats_with_human_line(
        hollow_repo, "slice-01", capsys
    )

    green_repo = tmp_path / "green_repo_for_hollow_comparison"
    _git_init(green_repo)
    _write_pyproject(green_repo)
    _seed_ledger(green_repo, _FEATURE_HOLLOW)
    _write_regression_test(green_repo, _FEATURE_HOLLOW, "slice-01", passing=True)
    _commit_with_trailer(green_repo, "slice-01", "feat(slice): real green AT")
    green_exit, green_payload, green_human = _run_slice_ats_with_human_line(
        green_repo, "slice-01", capsys
    )

    assert green_exit == 0 and green_payload.get("verdict") == "PASS", (
        "sanity: the comparison arm must be a genuine pass -- "
        f"exit_code={green_exit!r} payload={green_payload!r}"
    )
    assert hollow_exit != 0, (
        "a declared AT file that collects ZERO tests must NOT earn the same "
        "non-blocking exit code as a genuine pass -- got "
        f"exit_code={hollow_exit!r} payload={hollow_payload!r}"
    )
    assert hollow_payload.get("verdict") not in ("PASS", "NOT_APPLICABLE"), (
        "a hollow, declared-but-empty AT must be distinguishable from BOTH a "
        "genuine PASS and the genuinely-no-AT-at-all NOT_APPLICABLE case -- "
        f"payload={hollow_payload!r}"
    )
    assert hollow_human != green_human, (
        "the DEVELOPER-VISIBLE console line must differ between a hollow "
        "scaffold and a genuine pass -- today they are byte-identical "
        f"({hollow_human!r} == {green_human!r}), which is the exact bug the "
        "examiner caught: a developer sees the same green for 'my acceptance "
        "test ran and passed' and 'my acceptance test file is empty'."
    )


def test_no_at_file_at_all_still_returns_not_applicable_the_control(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The control for the hollow-AT fix (item 2, load-bearing -- do NOT
    omit): a slice with NO AT file whatsoever -- genuinely nothing declared
    -- must keep returning ``NOT_APPLICABLE``, non-blocking, EXACTLY as
    today. Pin it, or a fix that widens the hollow-AT refusal will overreach
    into this genuinely-no-AT-yet case and get reverted.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_NO_AT_CONTROL)
    _commit_with_trailer(repo, "slice-01", "feat(slice): no AT authored yet")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code == 0, (
        "a slice with genuinely NO AT file must stay non-blocking -- got "
        f"exit_code={exit_code!r} payload={payload!r}"
    )
    assert payload.get("verdict") == "NOT_APPLICABLE", (
        "a slice with genuinely NO AT file must stay NOT_APPLICABLE -- "
        f"payload={payload!r}"
    )


# ===========================================================================
# DEFECT 2 (examiner-caught, reproduced verbatim) -- a SKIPPED test is
# reported as one that RAN.
#
# The slice's only AT is decorated ``@pytest.mark.skip``. pytest collects it
# (it exists), never executes its body, and exits 0 ("1 skipped", no
# failures) -- the SAME ``_GREEN_EXIT_CODES`` bug maps that to PASS. Worse:
# ``ran_node_ids`` is populated by the SCOPE step (``_collect_node_ids``, a
# collection-only walk that happens BEFORE the RUN), not by anything the RUN
# actually executed -- so the one field whose entire job is to testify to
# what ran NAMES a test that was NEVER run.
# ===========================================================================


def test_skipped_only_at_never_earns_pass_and_ran_node_ids_never_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice whose ONLY AT is skipped has had ZERO observed execution: it
    must not earn PASS, and the skipped test's node id must never appear in
    ``ran_node_ids`` -- the field must testify ONLY to what actually
    executed, never to what was merely collected.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, _FEATURE_SKIPPED_ONLY)
    _write_at_file_with_body(
        repo,
        _FEATURE_SKIPPED_ONLY,
        "slice-01",
        "import pytest\n\n"
        "@pytest.mark.skip(reason='not implemented yet')\n"
        "def test_slice_01_behaviour():\n"
        "    assert False\n",
    )
    _commit_with_trailer(repo, "slice-01", "feat(slice): skipped-only AT")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code != 0, (
        "a slice whose ONLY AT is skipped has had ZERO observed execution -- "
        f"it must not earn a non-blocking exit. got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("verdict") != "PASS", (
        f"a skipped-only AT must not earn a PASS verdict -- payload={payload!r}"
    )
    ran_node_ids = payload.get("ran_node_ids", [])
    assert not any(
        str(node_id).endswith("test_slice_01_behaviour") for node_id in ran_node_ids
    ), (
        "``ran_node_ids`` must testify ONLY to what was actually EXECUTED -- "
        "it must never name a test that was SKIPPED (collected, never run). "
        f"got ran_node_ids={ran_node_ids!r}"
    )


# ===========================================================================
# THE NEGATIVE AT ON THE CLASS (item 4, THE durable one) -- no verdict may be
# earned over ZERO OBSERVED EXECUTION, however that zero is produced.
#
# Defect 1 (hollow file) and Defect 2 (skipped-only) are two INSTANCES of one
# bug class, not the full list of it -- pushed on further (per the dispatch),
# two MORE real pytest constructions independently zero out observed
# execution and STILL earn a green exit TODAY (verified empirically against
# the installed pytest interpreter before this test was authored):
#
#   * ``@pytest.mark.xfail(run=False)`` -- pytest deliberately never runs the
#     body, reports "1 xfailed", exits 0.
#   * an empty ``@pytest.mark.parametrize("x", [])`` set -- zero effective
#     cases, pytest reports "1 skipped", exits 0.
#
# A third real-but-differently-shaped construction (a module-level
# ``pytest.skip(allow_module_level=True)``) reproduces DEFECT 1's exit-5 root
# cause rather than DEFECT 2's exit-0 root cause -- included here to prove
# the invariant is genuinely root-cause-agnostic, not two special cases in a
# trenchcoat.
# ===========================================================================


_ZERO_EXECUTION_AT_BODIES: tuple[tuple[str, str], ...] = (
    (
        "hollow-file-zero-test-functions",
        "# head tags only -- no test function at all in this file\nx = 1\n",
    ),
    (
        "module-level-skip",
        "import pytest\n\n"
        "pytest.skip('module skipped', allow_module_level=True)\n\n"
        "def test_slice_01_behaviour():\n"
        "    assert False\n",
    ),
    (
        "skip-decorator",
        "import pytest\n\n"
        "@pytest.mark.skip(reason='not implemented yet')\n"
        "def test_slice_01_behaviour():\n"
        "    assert False\n",
    ),
    (
        "xfail-run-false",
        "import pytest\n\n"
        "@pytest.mark.xfail(run=False, reason='not implemented yet')\n"
        "def test_slice_01_behaviour():\n"
        "    assert False\n",
    ),
    (
        "empty-parametrize",
        "import pytest\n\n"
        "@pytest.mark.parametrize('x', [])\n"
        "def test_slice_01_behaviour(x):\n"
        "    assert x\n",
    ),
)


@pytest.mark.parametrize("case_id, body", _ZERO_EXECUTION_AT_BODIES)
def test_zero_observed_execution_never_earns_a_pass_the_class_invariant(
    case_id: str, body: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No verdict may be earned over zero observed execution -- the durable,
    root-cause-agnostic invariant, not an enumerated list of two cases. The
    NEXT way to produce a zero-execution PASS must be caught by this SAME
    assertion, not require a new test.
    """
    feature_id = f"fix-precommit-vacuous-scaffold-zero-exec-{case_id}"
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_pyproject(repo)
    _seed_ledger(repo, feature_id)
    _write_at_file_with_body(repo, feature_id, "slice-01", body)
    _commit_with_trailer(repo, "slice-01", f"feat(slice): zero-exec AT ({case_id})")

    exit_code, payload = _run_slice_ats(repo, "slice-01", capsys)

    assert exit_code != 0, (
        f"[{case_id}] zero observed execution must never earn the "
        f"non-blocking exit code -- got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("verdict") != "PASS", (
        f"[{case_id}] zero observed execution must never earn a PASS "
        f"verdict -- payload={payload!r}"
    )
