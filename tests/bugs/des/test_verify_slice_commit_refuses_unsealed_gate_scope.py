"""Regression: `des verify-slice-commit` -- the G_COMMIT verify-then-record
exit gate -- must REFUSE a slice commit whose `Gate-Scope:` trailer attests
nothing, instead of laundering it into a `SliceCommitVerified` ledger record.

RCA: ``docs/feature/fix-null-gate-scope-exit-gate/rca.md``.
Charter: ``docs/product/expectations/fix-null-gate-scope-exit-gate/
the-exit-gate-refuses-an-empty-attestation.md``.

Found in ``src/des/cli/verify_slice_commit_completeness.py``: the module's
three legs -- E1 (`.feature`/regression AT-file completeness), E2 (the
feature-scoped contract-gate run, or a behavioral regression-file run), E3
(the examine verdict) -- NEVER read the commit's `Gate-Scope:` trailer at
all. ``extract_gate_scope`` (``run_contract_gate.py``) has zero call sites in
this module. So a commit whose trailer is the 64-zero placeholder (or any
other not-a-real-fingerprint value) clears E1+E2(+E3) exactly like a commit
sealed with a real digest, and earns the identical `SliceCommitVerified`
ledger record -- "I checked nothing" and "everything is fine" produce the
same output. Measured prevalence in this repo's own history: 26/914
slice-attesting commits (2.8%) carry the all-zero placeholder.

The fix direction (RCA, NOT implemented here -- test-authoring only, zero
``src/`` edits): add a seal-integrity leg that decides on the PROPERTY, never
the DESIGNATION -- the trailer must be present AND a well-formed 64-hex
digest that is not the all-zero placeholder; anything else refuses via the
EXISTING named third state ``SliceCommitIndeterminate``
(``_GATE_INDETERMINATE_EXIT_CODE``), never a fabricated
``SliceCommitVerified``. The refusal must carry a ``how`` naming a `des`
producing command (`commit-slice` / `reverify-slice-commit`), never a manual
`git` amend instruction.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_slice_commit_completeness.main()`` CLI driver,
called via ``run_cli_in_process`` (no interpreter fork) -- the SAME entry
point `des commit-slice`'s own step-5 verify and the U2 hook invoke.

Fixtures: real tmp git repos (raw `git` subprocess, no mocking of git). Every
scenario shares the IDENTICAL Given (a slice commit that would otherwise
clear E1 -- a real, committed, tagged `.feature` AT file for the slice -- and
E2, monkeypatched to an unconditional clear so the seal-integrity leg under
test is isolated and E2 stays cheap on a heavily contended box, mirroring the
proven GREEN `ADDITIVITY guard` precedent in
`test_verify_slice_commit_pytest_regression_behavioral_attestation.py`); the
ONLY variable across scenarios is the commit's `Gate-Scope:` trailer value
(Pillar 2, chained narrative). The one genuine, non-mocked pytest subprocess
this file spawns is the single `--committed-scope-digest` collection call the
negative-AT fixture needs to derive a REAL digest (never fabricated) -- the
`_write_committed_contract` shape mirrored from the proven GREEN precedent
`test_run_contract_gate_scope_unverified_names_how.py`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc
from des.cli.run_contract_gate import main as _run_contract_gate_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "fix-null-gate-scope-exit-gate"
_SLICE_ID = "slice-01"

_ALL_ZERO_PLACEHOLDER = "0" * 64


# ---------------------------------------------------------------------------
# Shared fixture builders
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


def _write_feature_file(repo: Path, feature_id: str, slice_id: str) -> None:
    """A real, tracked, tagged `.feature` AT file for the slice -- clears E1
    exactly like the proven GREEN `ADDITIVITY guard` precedent's fixture in
    `test_verify_slice_commit_pytest_regression_behavioral_attestation.py`.
    """
    feat_path = repo / "tests" / "acceptance" / "fixture_slice.feature"
    feat_path.parent.mkdir(parents=True, exist_ok=True)
    feat_path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: fixture feature\n\n"
        f"  @{slice_id}\n"
        "  Scenario: fixture scenario\n"
        "    Given a fixture precondition\n"
        "    When the fixture action occurs\n"
        "    Then the fixture outcome holds\n",
        encoding="utf-8",
    )


def _write_committed_pytest_module(repo: Path) -> None:
    """A tiny real pytest module -- gives `--committed-scope-digest` genuine,
    non-empty collected content to fingerprint. Mirrors the proven GREEN
    precedent `_write_committed_contract` in
    `test_run_contract_gate_scope_unverified_names_how.py`.
    """
    (repo / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["unit"]\n', encoding="utf-8"
    )
    (repo / "test_committed_contract.py").write_text(
        "import pytest\n\n@pytest.mark.unit\ndef test_a():\n    assert True\n",
        encoding="utf-8",
    )


def _amend_with_gate_scope_trailer(repo: Path, gate_scope_value: str) -> None:
    """Amend HEAD so its message carries the `Gate-Scope:` trailer, mirroring
    the proven GREEN precedent `_amend_with_trailer` in
    `test_run_contract_gate_scope_unverified_names_how.py`. Kept alongside the
    real `Slice-Id:` trailer already on HEAD's message.
    """
    original = _git(repo, "log", "-1", "--format=%B", "HEAD").strip()
    _git(
        repo,
        "commit",
        "-q",
        "--amend",
        "-m",
        f"{original}\n\nGate-Scope: {gate_scope_value}",
    )


def _build_repo_with_gate_scope(
    tmp_path: Path, feature_id: str, slice_id: str, gate_scope_value: str | None
) -> Path:
    """Given: a slice commit that would clear E1 (a real, tracked `.feature`
    AT file for the slice) -- the ONLY variable across every scenario in this
    file is the commit's `Gate-Scope:` trailer. `gate_scope_value=None` means
    the trailer is entirely absent (no amend).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_feature_file(repo, feature_id, slice_id)
    _write_committed_pytest_module(repo)
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): fixture delivery\n\nSlice-Id: {slice_id}",
    )
    if gate_scope_value is not None:
        _amend_with_gate_scope_trailer(repo, gate_scope_value)
    return repo


def _committed_scope_digest(repo: Path) -> str:
    """Return the REAL, correctly-computed committed-scope digest of `repo`
    at HEAD -- derived through the shipped CLI (`--committed-scope-digest`),
    never fabricated. Mirrors the proven GREEN precedent
    `_committed_scope_digest` in
    `test_run_contract_gate_scope_unverified_names_how.py`.
    """
    exit_code, stdout, _stderr = run_cli_in_process(
        ["--repo", str(repo), "--committed-scope-digest"],
        cwd=repo,
        main=_run_contract_gate_main,
    )
    for line in (ln.strip() for ln in stdout.splitlines()):
        if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
            return line
    raise AssertionError(
        "could not derive a committed-scope digest to build the trailer "
        f"(exit {exit_code}); stdout={stdout!r}"
    )


def _run_verify_slice_commit(
    repo: Path, feature_id: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI in-process (`main()`, no
    interpreter fork), with the E2 contract-gate subprocess monkeypatched to
    an unconditional clear -- mirrors the proven GREEN `ADDITIVITY guard`
    precedent: the seal-integrity leg under test is independent of E2 (RCA:
    "one `git log -1 --format=%B` read, no extra collection"), so E2 is kept
    cheap rather than spawning a real feature-scoped contract-gate subprocess
    on a heavily contended box.

    Returns `(exit_code, payload)` -- `payload` is the LAST single-line JSON
    verdict emitted (the CLI dual-emits every verdict on stdout AND stderr,
    plus a non-JSON human-readable line).
    """
    monkeypatch.setattr(vscc, "_run_contract_gate", lambda *a, **k: 0)
    exit_code, stdout, stderr = run_cli_in_process(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id],
        cwd=repo,
        main=vscc.main,
    )
    combined = stdout + stderr
    json_lines = [
        ln.strip() for ln in combined.splitlines() if ln.strip().startswith("{")
    ]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


def _assert_names_unsealed_gate_scope(payload: dict[str, object]) -> None:
    """WHY: the refusal must name the Gate-Scope receipt as the problem, in
    plain language distinguishing "the receipt is wrong" from "the code is
    wrong" -- never a generic, reason-less refusal.
    """
    error = str(payload.get("error", "")).lower()
    assert "gate" in error and "scope" in error, (
        "the refusal must name the Gate-Scope trailer as the problem, not a "
        f"generic/unrelated cause -- payload={payload!r}"
    )
    unsealed_markers = (
        "unsealed",
        "not sealed",
        "no seal",
        "invalid",
        "malformed",
        "blank",
        "placeholder",
        "not a real",
        "unverified",
        "not verified",
        "well-formed",
        "well formed",
        "zero",
    )
    assert any(marker in error for marker in unsealed_markers), (
        "the refusal must explain WHY the receipt is a problem (unsealed / "
        "invalid / blank / placeholder), a blank receipt means nothing was "
        f"actually checked -- payload={payload!r}"
    )


def _assert_how_names_a_des_producing_command(payload: dict[str, object]) -> None:
    """HOW: the refusal must route to a `des` producing command -- never a
    manual `git` amend of the commit trailer.
    """
    how = payload.get("how")
    assert how, (
        "the refusal must carry a `how` field routing to the producing tool "
        f"that reseals the Gate-Scope trailer -- payload carries no `how`: "
        f"{payload!r}"
    )
    how_l = str(how).lower()
    assert ("commit-slice" in how_l) or ("reverify-slice-commit" in how_l), (
        "the `how` must name a concrete `des` command that produces a real "
        f"receipt (`des commit-slice` or `des reverify-slice-commit`) -- got "
        f"how={how!r}"
    )
    assert "git commit --amend" not in how_l and "git commit -amend" not in how_l, (
        "the `how` must NEVER instruct a manual `git` amend of the commit "
        f"trailer -- got how={how!r}"
    )


# ===========================================================================
# POSITIVE -- active-RED today: the exit gate currently PASSES these commits
# ===========================================================================


@pytest.mark.parametrize(
    "gate_scope_value",
    [
        pytest.param(_ALL_ZERO_PLACEHOLDER, id="all_zero_placeholder"),
        pytest.param("deadbeef" * 5, id="short_hex_digest"),  # 40 hex chars
        pytest.param("not-a-real-gate-scope-digest", id="non_hex_value"),
        pytest.param(None, id="absent_trailer"),
    ],
)
def test_unsealed_gate_scope_trailer_refuses_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate_scope_value: str | None,
) -> None:
    """A commit whose `Gate-Scope:` trailer is not a real, well-formed 64-hex
    committed-scope digest -- whether the all-zero placeholder, a short/non-
    hex value, or entirely absent -- must be REFUSED by the SAME named third
    state `SliceCommitIndeterminate`, never `SliceCommitVerified`. This
    decides on the PROPERTY ("does this trailer attest real coverage"), never
    the DESIGNATION (a literal-64-zeros special case) -- RCA finding #2: "A
    zero-only sentinel would be too narrow".

    RED for the right reason today: the exit gate never reads the
    `Gate-Scope:` trailer at all (`extract_gate_scope` has zero call sites in
    `verify_slice_commit_completeness.py`), so E1+E2 clearing is the WHOLE
    verdict -- every one of these malformed/absent trailers earns
    `SliceCommitVerified` today, identically to a genuine digest.
    """
    repo = _build_repo_with_gate_scope(
        tmp_path, _FEATURE_ID, _SLICE_ID, gate_scope_value
    )

    exit_code, payload = _run_verify_slice_commit(repo, _FEATURE_ID, monkeypatch)

    assert exit_code == vscc._GATE_INDETERMINATE_EXIT_CODE, (
        f"a Gate-Scope trailer of {gate_scope_value!r} attests nothing and "
        "must refuse via the gate's dedicated INDETERMINATE exit code, not "
        f"silently pass -- got exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitIndeterminate", (
        "the refusal must name a THIRD state, distinct from both "
        "'verified' and a generic code-failure refusal, so the operator can "
        "tell from the label alone this is a receipt problem, not a claim "
        f"their code is broken -- payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", (
        "the exact false-green this regression pins: a blank/unreadable "
        f"receipt must never earn SliceCommitVerified -- payload={payload!r}"
    )
    _assert_names_unsealed_gate_scope(payload)
    _assert_how_names_a_des_producing_command(payload)

    verified = AtCompletionLedger(_FEATURE_ID, repo).verified_slices()
    assert _SLICE_ID not in verified, (
        f"a Gate-Scope trailer of {gate_scope_value!r} must never leave a "
        "SliceCommitVerified ledger record behind -- observed "
        f"verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# NEGATIVE -- control, must be green BEFORE and AFTER the fix
# ===========================================================================


@pytest.fixture()
def _verified_commit_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, dict[str, object], Path]:
    """Given: a slice commit whose `Gate-Scope:` trailer is a REAL,
    well-formed committed-scope digest -- derived through the shipped CLI,
    never fabricated. When: `des verify-slice-commit` runs against it.

    Shared Given+When for the two negative-AT oracles below (Pillar 2,
    chained narrative) -- the anti-over-refusal control: the fix must not
    overcorrect into false refusals on valid receipts (charter negative
    oracle 1), the single most important negative AT in this file.
    """
    repo = _build_repo_with_gate_scope(tmp_path, _FEATURE_ID, _SLICE_ID, None)
    digest = _committed_scope_digest(repo)
    _amend_with_gate_scope_trailer(repo, digest)

    exit_code, payload = _run_verify_slice_commit(repo, _FEATURE_ID, monkeypatch)
    return exit_code, payload, repo


@pytest.mark.negative_at
def test_genuine_well_formed_gate_scope_digest_still_verifies_cleanly(
    _verified_commit_result: tuple[int, dict[str, object], Path],
) -> None:
    """A slice commit whose `Gate-Scope:` trailer is a REAL, correctly-
    computed digest continues to verify cleanly exactly as before -- the new
    seal-integrity leg must not start refusing commits it used to correctly
    pass. Must hold BEFORE and AFTER the fix.
    """
    exit_code, payload, repo = _verified_commit_result

    assert exit_code == 0, (
        "a commit sealed with a REAL, well-formed Gate-Scope digest must "
        f"still clear -- got exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", (
        f"a genuinely-sealed commit must still earn SliceCommitVerified -- "
        f"payload={payload!r}"
    )

    verified = AtCompletionLedger(_FEATURE_ID, repo).verified_slices()
    assert _SLICE_ID in verified, (
        "a genuinely-sealed commit must still leave a SliceCommitVerified "
        f"ledger record -- observed verified_slices={sorted(verified)!r}"
    )


@pytest.mark.negative_at
def test_verified_path_never_emits_indeterminate_or_a_spurious_how(
    _verified_commit_result: tuple[int, dict[str, object], Path],
) -> None:
    """The verified path must NOT emit `SliceCommitIndeterminate` and must
    NOT carry a spurious `how` field -- the `how` field belongs only to the
    refusal path, never leaking into a passing verdict. Must hold BEFORE and
    AFTER the fix.
    """
    _exit_code, payload, _repo = _verified_commit_result

    assert payload.get("event") != "SliceCommitIndeterminate", (
        f"a genuinely-sealed commit must never be misclassified as "
        f"unsealed -- payload={payload!r}"
    )
    assert "how" not in payload, (
        f"a VERIFIED verdict must never carry a spurious `how` field: {payload!r}"
    )
