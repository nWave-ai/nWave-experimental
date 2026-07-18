# @feature-attest-legacy-commit-slice-id-override
# @slice-01
"""Regression AT (#51, bugfix lane): `des verify-slice-commit` can never attest
a bare legacy commit (no `Slice-Id:` trailer) even when its fix is real and its
regression test genuinely passes on the committed tree -- `_resolve_slice_ids`
(`src/des/cli/verify_slice_commit_completeness.py:453-461`) exits 2
unconditionally on a missing trailer, before the E2 behavioral leg ever runs.
Confirmed >=4 times across the DEV + sister trees; fabricating a trailer
post-hoc is audit-tampering (correctly classifier-blocked).

Charter: `docs/product/expectations/attest-legacy-commit-slice-id-override/`.

Design contract (feature-delta.md, `## Wave: DESIGN / [REF] Architecture &
Contract`, NOT implemented here -- test-authoring only, zero `src/` edits):
add an ADDITIVE `--slice-id SLICE` CLI flag to
`verify_slice_commit_completeness._build_parser()`. When `_resolve_slice_ids`
finds NO `Slice-Id:` trailer on the commit, `--slice-id` supplies the slice id
instead of failing -- attesting on the BEHAVIORAL proof (the E2
pytest-regression leg passing on the committed tree) rather than the trailer.
Honesty guards (fail-closed, GDP-6, never a fabricated attestation):
  (1) `--slice-id` REQUIRES `--at-kind pytest-regression` +
      `--regression-test-file <path>` -- missing either -> REFUSE (exit 2).
  (2) the declared regression test MUST PASS on the committed tree -- a
      failing/uncollectible test -> the existing refusal/indeterminate path,
      NEVER a fabricated `SliceCommitVerified`.
  (3) a `--slice-id` that CONFLICTS with a real `Slice-Id:` trailer on the
      commit -> REFUSE (an override must not silently contradict a trailer).
      A trailer that MATCHES `--slice-id` is fine (idempotent) -- untouched by
      this AT set; see the legacy-path regression guard below instead.
The `SliceCommitVerified` record written on success carries an added
transparent field `attested_via: "slice-id-override"` (absent/default on the
normal trailer path) -- the audit shows the trailer was bypassed while still
counting toward the scorecard.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.verify_slice_commit_completeness.main()` CLI driver,
captured via `capsys` -- mirrors every sibling regression AT in
`tests/bugs/des/` (e.g. `test_verify_slice_commit_pytest_regression_
behavioral_attestation.py`, the closest sibling: same E2 behavioral-
attestation mechanics, this AT set adds the trailer-override on top).

Fixtures: real tmp git repos (`git subprocess`, no mocking) -- each with its
OWN local `user.name`/`user.email` config (git-safety rule #48; the real
project repo's git config is never touched). The regression test file IS the
AT for E1 completeness discovery (pytest head-comment-tag convention,
`# @feature-{id}` / `# @{slice-NN}`), doubling as both the E1 delivered-AT
artifact and the E2 behavioral witness -- mirroring the sibling AT exactly.

RED for the right reason today: `--slice-id` is not a recognized flag on
`verify-slice-commit` yet, so driving it raises `SystemExit(2)` (argparse
"unrecognized arguments") BEFORE any repo/ledger access.
`_run_verify_slice_commit` below catches that `SystemExit` and folds its code
into the SAME `(exit_code, payload)` shape the post-fix call returns, so every
assertion is a genuine, semantic comparison against the verdict/ledger --
never an uncaught-exception "pass" and never a bare collection error. The
positive scenario (1) is the one that must observably FAIL today (a real
`AssertionError` on the expected post-fix verdict); the honesty-guard
scenarios (2-4) hold trivially both before and after the fix (nothing is
EVER verified while the flag does not exist, and must stay that way once it
does) -- the SAME "green both before and after" shape the sibling AT set
uses for its own honesty guards. Scenario 5 is a pure regression guard on the
UNCHANGED legacy path (no `--slice-id` involved) and is green today already.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc


_REGRESSION_FILE_REL = "tests/fixture/test_pytest_regression_fixture.py"

_FEATURE_ID_OVERRIDE_POS = "attest-legacy-override-pos"
_FEATURE_ID_OVERRIDE_FAIL = "attest-legacy-override-fail"
_FEATURE_ID_OVERRIDE_NO_PROOF = "attest-legacy-override-no-proof"
_FEATURE_ID_OVERRIDE_CONFLICT = "attest-legacy-override-conflict"
_FEATURE_ID_LEGACY_UNCHANGED = "attest-legacy-override-legacy-unchanged"


# ---------------------------------------------------------------------------
# Shared fixture builders (real git subprocess, isolated tmp repo, own config)
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
    """Isolated tmp repo with its OWN local git config (rule #48) -- the real
    project repo's `user.name`/`user.email` are never read or touched.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible regression test, head-tagged for E1
    discovery (`# @feature-{id}` / `# @{slice-NN}`) -- doubles as the E1
    delivered-AT artifact and the E2 behavioral witness, mirroring the
    sibling behavioral-attestation AT fixture exactly.
    """
    path = repo / _REGRESSION_FILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if passing:
        body = "def test_the_legacy_fix_stays_fixed():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            "def test_the_legacy_fix_is_still_broken():\n"
            "    assert 1 + 1 == 3, 'the legacy fix is NOT fixed'\n"
        )
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n{body}",
        encoding="utf-8",
    )
    return path


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _bare_commit_no_trailer(repo: Path, subject: str = "fix: bare legacy fix") -> None:
    """A commit carrying NO `Slice-Id:`/`Step-Id:` trailer -- the exact shape
    of a real, green, EXAMINE-passed fix committed without the trailer (the
    bug this whole feature exists to close).
    """
    _commit_all(repo, subject)


def _commit_with_trailer(repo: Path, slice_id: str, subject: str) -> None:
    _commit_all(repo, f"{subject}\n\nSlice-Id: {slice_id}")


def _run_verify_slice_commit(
    repo: Path,
    feature_id: str,
    capsys: pytest.CaptureFixture[str],
    *,
    slice_id: str | None = None,
    at_kind: str | None = None,
    regression_test_file: str | None = None,
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI (`main()`) in-process,
    capturing its single-line JSON payload via `capsys`.

    Today (pre-fix) `--slice-id` is unrecognized -- argparse raises
    `SystemExit(2)` before any repo access. That `SystemExit` is caught and
    folded into the SAME `(exit_code, payload)` return shape the post-fix
    call produces (`payload={}` when nothing was ever emitted), so every
    caller's assertion is a genuine comparison against the verdict, never a
    crash masquerading as a failing test.
    """
    argv = ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    if slice_id is not None:
        argv += ["--slice-id", slice_id]
    if at_kind is not None:
        argv += ["--at-kind", at_kind]
    if regression_test_file is not None:
        argv += ["--regression-test-file", regression_test_file]

    try:
        exit_code = vscc.main(argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


# ===========================================================================
# 1. POSITIVE -- override attests a bare legacy commit -- active-RED today
# ===========================================================================


def test_override_attests_a_bare_commit_via_behavioral_proof(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit with NO `Slice-Id:` trailer, whose declared regression test
    genuinely PASSES on the committed tree, must earn `SliceCommitVerified`
    when `--slice-id` supplies the slice the trailer cannot -- the honest
    fix for the "real, green fix that can never be attested" bug. The
    written ledger record (and the emitted verdict) must carry the
    transparent `attested_via: "slice-id-override"` marker so the audit
    shows the trailer was bypassed, never a silent loosening.

    RED for the right reason today: `--slice-id` does not exist on
    `verify-slice-commit` yet, so the call raises `SystemExit(2)` (folded to
    `exit_code=2`, `payload={}`) -- a semantic mismatch against the expected
    `exit_code == 0` / `SliceCommitVerified` / `attested_via` verdict, not a
    collection or import error.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(repo, _FEATURE_ID_OVERRIDE_POS, "slice-01", passing=True)
    _bare_commit_no_trailer(repo)

    exit_code, payload = _run_verify_slice_commit(
        repo,
        _FEATURE_ID_OVERRIDE_POS,
        capsys,
        slice_id="slice-01",
        at_kind="pytest-regression",
        regression_test_file=_REGRESSION_FILE_REL,
    )

    assert exit_code == 0, (
        "a bare legacy commit (no Slice-Id trailer) whose declared regression "
        "test genuinely PASSES on the committed tree must clear via the "
        "--slice-id override's behavioral proof -- got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload
    assert payload.get("attested_via") == "slice-id-override", (
        "the SliceCommitVerified verdict for a trailer-less commit attested "
        "via --slice-id must carry the transparent attested_via marker so "
        f"the audit shows the trailer was bypassed -- payload={payload!r}"
    )

    ledger = AtCompletionLedger(_FEATURE_ID_OVERRIDE_POS, repo)
    verified = ledger.verified_slices()
    assert "slice-01" in verified, (
        "the --slice-id override path must record a SliceCommitVerified "
        f"ledger entry for the supplied slice -- verified={sorted(verified)!r}"
    )
    records = [
        r
        for r in ledger.read_records()
        if r.get("event") == "SliceCommitVerified" and r.get("slice_id") == "slice-01"
    ]
    assert records and records[-1].get("attested_via") == "slice-id-override", (
        "the persisted SliceCommitVerified ledger record itself must carry "
        f"attested_via: slice-id-override (transparent audit trail) -- "
        f"records={records!r}"
    )


# ===========================================================================
# 2. HONESTY (negative, CRITICAL) -- behavioral proof is mandatory
# ===========================================================================


@pytest.mark.negative_at
def test_override_never_attests_when_the_regression_test_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The false-green guard: a bare legacy commit whose declared regression
    test genuinely FAILS on the committed tree must NEVER earn
    `SliceCommitVerified` via `--slice-id` -- neither today (the flag does
    not exist, so nothing can verify) nor after the fix (the behavioral run
    observes the failure and refuses/indeterminates). The override attests
    on the BEHAVIORAL proof only -- a failing test must never be laundered
    into a verified record just because a slice id was supplied.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(repo, _FEATURE_ID_OVERRIDE_FAIL, "slice-01", passing=False)
    _bare_commit_no_trailer(repo)

    exit_code, payload = _run_verify_slice_commit(
        repo,
        _FEATURE_ID_OVERRIDE_FAIL,
        capsys,
        slice_id="slice-01",
        at_kind="pytest-regression",
        regression_test_file=_REGRESSION_FILE_REL,
    )

    assert exit_code != 0, (
        "a --slice-id override whose declared regression test FAILS on the "
        f"committed tree must never clear -- got exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", (
        "a broken legacy commit earned SliceCommitVerified via --slice-id -- "
        f"the exact false-green the honesty invariant exists to prevent: "
        f"payload={payload!r}"
    )

    verified = AtCompletionLedger(_FEATURE_ID_OVERRIDE_FAIL, repo).verified_slices()
    assert "slice-01" not in verified, (
        "a --slice-id override on a genuinely failing regression test must "
        f"NEVER earn a fabricated SliceCommitVerified -- verified="
        f"{sorted(verified)!r}"
    )


# ===========================================================================
# 3. HONESTY (negative) -- no behavioral proof declared -> refuse
# ===========================================================================


@pytest.mark.negative_at
def test_override_refuses_without_a_declared_regression_test(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--slice-id` REQUIRES the behavioral proof pair (`--at-kind
    pytest-regression` + `--regression-test-file`) -- a bare structural
    attestation cannot be trusted without a trailer, so the override with
    neither flag supplied must REFUSE self-explainingly (exit 2, per the
    design contract's honesty-guard #1), never silently fall through to a
    verified record.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _bare_commit_no_trailer(repo)

    exit_code, payload = _run_verify_slice_commit(
        repo,
        _FEATURE_ID_OVERRIDE_NO_PROOF,
        capsys,
        slice_id="slice-01",
    )

    assert exit_code == 2, (
        "--slice-id without --at-kind pytest-regression + "
        "--regression-test-file must REFUSE with exit 2 (no behavioral proof "
        f"was declared) -- got exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", payload
    assert payload.get("error"), (
        "the refusal must be self-explaining (WHAT/WHY/HOW, GDP-3) -- a bare "
        f"exit code with no error text is itself a defect: payload={payload!r}"
    )

    verified = AtCompletionLedger(_FEATURE_ID_OVERRIDE_NO_PROOF, repo).verified_slices()
    assert "slice-01" not in verified, (
        "a --slice-id override declaring no behavioral proof must never "
        f"reach a SliceCommitVerified record -- verified={sorted(verified)!r}"
    )


# ===========================================================================
# 4. HONESTY (negative) -- --slice-id conflicting with a real trailer
# ===========================================================================


@pytest.mark.negative_at
def test_override_refuses_when_it_conflicts_with_the_commits_real_trailer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit that DOES carry a `Slice-Id:` trailer must not have that
    trailer silently overridden -- `--slice-id slice-01` on a commit whose
    real trailer says `Slice-Id: slice-02` must REFUSE (honesty guard #3):
    an override must never silently contradict a real, already-honest
    trailer. Neither the trailer's slice nor the override's slice may earn
    a SliceCommitVerified record out of this conflicting invocation.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(
        repo, _FEATURE_ID_OVERRIDE_CONFLICT, "slice-02", passing=True
    )
    _commit_with_trailer(repo, "slice-02", "fix: trailer-carrying legacy fix")

    exit_code, payload = _run_verify_slice_commit(
        repo,
        _FEATURE_ID_OVERRIDE_CONFLICT,
        capsys,
        slice_id="slice-01",
        at_kind="pytest-regression",
        regression_test_file=_REGRESSION_FILE_REL,
    )

    assert exit_code != 0, (
        "--slice-id slice-01 conflicting with a commit's real "
        "'Slice-Id: slice-02' trailer must REFUSE -- got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("event") != "SliceCommitVerified", (
        "a conflicting --slice-id must never silently win over (or be "
        f"silently ignored in favour of) the commit's real trailer -- "
        f"payload={payload!r}"
    )

    ledger = AtCompletionLedger(_FEATURE_ID_OVERRIDE_CONFLICT, repo)
    verified = ledger.verified_slices()
    assert "slice-01" not in verified and "slice-02" not in verified, (
        "neither the conflicting override slice nor the commit's real "
        "trailer slice may earn SliceCommitVerified out of a conflicting "
        f"invocation -- verified={sorted(verified)!r}"
    )


# ===========================================================================
# 5. REGRESSION GUARD -- the legacy (no --slice-id) path is byte-unchanged
# ===========================================================================


def test_legacy_trailer_path_is_unchanged_without_the_override_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A normal trailer-carrying commit attested with NO `--slice-id` must
    keep working exactly as today -- the override branch must not disturb
    the pre-existing pytest-regression E2 path in any way. Green both
    BEFORE and AFTER the fix (this scenario touches none of the new code).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    _write_regression_test(repo, _FEATURE_ID_LEGACY_UNCHANGED, "slice-01", passing=True)
    _commit_with_trailer(repo, "slice-01", "fix: trailer-carrying legacy fix")

    exit_code, payload = _run_verify_slice_commit(
        repo,
        _FEATURE_ID_LEGACY_UNCHANGED,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=_REGRESSION_FILE_REL,
    )

    assert exit_code == 0, (
        "a normal trailer-carrying commit with NO --slice-id must clear via "
        f"the pre-existing behavioral E2 path -- exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload
    assert not payload.get("attested_via"), (
        "the legacy trailer path must never carry the attested_via marker -- "
        f"that field is exclusive to the --slice-id override path: "
        f"payload={payload!r}"
    )

    ledger = AtCompletionLedger(_FEATURE_ID_LEGACY_UNCHANGED, repo)
    verified = ledger.verified_slices()
    assert "slice-01" in verified, (
        "the legacy trailer path must keep recording SliceCommitVerified "
        f"unchanged -- verified={sorted(verified)!r}"
    )
    records = [
        r
        for r in ledger.read_records()
        if r.get("event") == "SliceCommitVerified" and r.get("slice_id") == "slice-01"
    ]
    assert records and not records[-1].get("attested_via"), (
        "the legacy trailer path's persisted ledger record must never carry "
        f"attested_via -- records={records!r}"
    )
