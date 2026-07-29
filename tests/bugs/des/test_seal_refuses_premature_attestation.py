"""Regression: a `SliceCommitVerified` seal whose AT postdates the very
commit it attests must be CAUGHT, not silently trusted.

RCA (this feature's dispatch, `lane-seal-refuses-premature`, part B of the
two-lane `fix-slice-seal-carries-commit-sha` chain -- part A: commit
`61231e5dd`, threading `commit_sha` into `SliceCommitVerified`): in the real
`des-spine-control-plane-ssot` ledger, slice-03's seal carries timestamp
`2026-06-02T07:35:49Z`, while the `.feature`/pytest AT tagged `@slice-03`
was authored by a LATER commit (`3033d4f9a`, `08:30` the same day) -- the
seal fired 55 minutes before its own acceptance test existed, and stayed
invisible for two months because the record carried no `commit_sha` to join
against. Part A made the join key EXIST; this test proves the CONSUMER
(`des verify-seal-provenance`, `des.application.seal_provenance`) actually
USES it: once a seal carries a `commit_sha`, an AT that postdates it is a
provable, reported `PREMATURE` verdict -- and a historical record with NO
`commit_sha` (every pre-fix record, including the real slice-03 one as it
stands on trunk today) is `INDETERMINATE`, never silently trusted and never
a retroactive FAIL (GDP-8).

Driving surface: the REAL `des.cli.verify_seal_provenance.main()` CLI
driver (`des verify-seal-provenance`), over a REAL git repository and a REAL
`AtCompletionLedger` -- this is what a real audit run does end to end,
folding in `audit_seal_provenance` + `GitCommitTreePathAdapter` (git behind
the `CommitTreePathPort` boundary, AD-21) itself.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_seal_provenance import main as verify_seal_provenance_main


_FEATURE_ID = "seal-refuses-premature-at"
_SLICE_ID = "slice-03"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")


def _commit_the_at(repo: Path, feature_id: str, slice_id: str) -> str:
    """Author + commit the `@slice-03`-tagged `.feature` AT -- the commit
    the real `3033d4f9a` plays in the RCA. Returns its sha."""
    at_dir = repo / "tests" / "acceptance" / feature_id.replace("-", "_")
    at_dir.mkdir(parents=True, exist_ok=True)
    (at_dir / f"{slice_id}.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: mode resolution\n\n"
        f"  @{slice_id}\n"
        "  Scenario: the slice's observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"feat(slice): {slice_id} AT")
    return _git(repo, "rev-parse", "HEAD").strip()


def _pre_at_commit_sha(repo: Path) -> str:
    """HEAD BEFORE the AT-adding commit -- what a premature seal would (had
    it carried the join key) have attested: a real commit whose tree
    genuinely lacks the AT."""
    return _git(repo, "rev-parse", "HEAD").strip()


def _seal(
    repo: Path, feature_id: str, slice_id: str, *, commit_sha: str | None
) -> None:
    AtCompletionLedger(feature_id, repo).append_gate_event(
        "SliceCommitVerified", slice_id, commit_sha=commit_sha
    )


def _run_audit(repo: Path, feature_id: str) -> tuple[int, dict[str, object]]:
    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", feature_id]
    )
    return exit_code, None  # payload read separately via capsys in callers


# ===========================================================================
# POSITIVE -- the exact slice-03 shape: premature seal is caught
# ===========================================================================


def test_seal_attesting_a_commit_before_its_own_at_is_caught_premature(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reproduces the RCA precisely: the seal's `commit_sha` names a real
    commit whose tree does not yet contain the AT the seal claims to verify
    -- because that AT was authored by a LATER commit. Must surface
    `PREMATURE`, exit code 1 -- never a silent PASS."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    premature_commit_sha = _pre_at_commit_sha(repo)  # HEAD before the AT exists
    _commit_the_at(repo, _FEATURE_ID, _SLICE_ID)  # AT lands LATER

    # The seal claims the EARLIER commit -- exactly slice-03's 55-minutes-
    # premature shape, now made checkable because commit_sha is present.
    _seal(repo, _FEATURE_ID, _SLICE_ID, commit_sha=premature_commit_sha)

    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", _FEATURE_ID]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.splitlines()[0])

    assert exit_code == 1, (
        f"WHAT: expected exit_code=1 (a proven PREMATURE seal exists). WHY: "
        f"the seal's commit_sha={premature_commit_sha!r} predates the AT's "
        f"own commit -- the AT genuinely did not exist in that commit's "
        f"tree. HOW: audit_seal_provenance must resolve this via "
        f"CommitTreePathPort.path_exists_at_commit returning False and "
        f"classify it PREMATURE. observed exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload["verdict"] == "FAIL"
    assert payload["premature_count"] == 1
    finding = payload["findings"][0]
    assert finding["verdict"] == "PREMATURE"
    assert finding["slice_id"] == _SLICE_ID
    assert finding["commit_sha"] == premature_commit_sha


def test_honest_seal_after_its_own_at_is_verified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The non-regression companion: a seal whose commit_sha is the AT's OWN
    commit (or later) must clear as VERIFIED, exit 0 -- the fix must not
    turn honest seals into false positives."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    honest_commit_sha = _commit_the_at(repo, _FEATURE_ID, _SLICE_ID)
    _seal(repo, _FEATURE_ID, _SLICE_ID, commit_sha=honest_commit_sha)

    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", _FEATURE_ID]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.splitlines()[0])

    assert exit_code == 0
    assert payload["verdict"] == "PASS"
    assert payload["findings"][0]["verdict"] == "VERIFIED"


# ===========================================================================
# NEGATIVE AT -- historical records without commit_sha (the real slice-03
# record AS IT STANDS on trunk today) must never be silently trusted NOR
# retroactively failed
# ===========================================================================


@pytest.mark.negative_at
def test_historical_record_without_commit_sha_is_indeterminate_never_pass_never_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A record written the OLD way (no commit_sha ever threaded -- every
    record on trunk today, INCLUDING the real slice-03 one) must surface
    INDETERMINATE, exit code 3 -- distinct from both the green PASS/exit-0
    face and the FAIL/exit-1 face. Collapsing this into either face is
    exactly the invisibility the RCA describes."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_the_at(repo, _FEATURE_ID, _SLICE_ID)
    _seal(repo, _FEATURE_ID, _SLICE_ID, commit_sha=None)

    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", _FEATURE_ID]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.splitlines()[0])

    assert exit_code == 3, (
        f"WHAT: a commit_sha-less historical record must exit 3 "
        f"(INDETERMINATE), neither 0 (PASS -- would be a silent trust) nor "
        f"1 (FAIL -- would be a retroactive, evidence-free reject). "
        f"observed exit_code={exit_code!r}"
    )
    assert payload["verdict"] == "INDETERMINATE"
    assert payload["premature_count"] == 0
    assert payload["findings"][0]["verdict"] == "INDETERMINATE"


@pytest.mark.negative_at
def test_zero_population_is_indeterminate_never_a_bare_pass_absent_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Residual found the night this feature landed (main's own re-check):
    a `--repo`/`--feature-id` combination whose ledger FILE does not exist at
    all -- the exact shape of pointing the audit at a worktree that never
    saw the real, gitignored `.nwave/telemetry/atdd-pure/` file -- reported
    `PASS - 0 audited` instead of INDETERMINATE. A green face on zero checked
    records is the identical defect class one layer up: "I audited nothing"
    is not "I audited N things and they were all fine." Must never be exit 0.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    # No feature-delta, no AT, no seal -- and critically, no ledger file at
    # all is ever created for _FEATURE_ID.

    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", _FEATURE_ID]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.splitlines()[0])

    assert exit_code == 3, (
        f"WHAT: an absent ledger file must exit 3 (INDETERMINATE), never 0 "
        f"(PASS -- a green face on a population of zero). WHY: 0 audited "
        f"records is not evidence of a clean seal history -- it may mean the "
        f"ledger genuinely does not exist yet, or --repo points at the wrong "
        f"checkout. HOW: the verdict function must check audited==0 BEFORE "
        f"the per-finding tallies, since an empty premature/indeterminate "
        f"list is indistinguishable from 'nothing to check' by tally alone. "
        f"observed exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload["verdict"] == "INDETERMINATE"
    assert payload["audited"] == 0
    assert payload["reason"] == "zero_population"
    assert payload["ledger_exists"] is False


@pytest.mark.negative_at
def test_zero_population_is_indeterminate_never_a_bare_pass_empty_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The companion shape: the ledger FILE exists (some other gate already
    wrote to it) but carries zero `SliceCommitVerified` records for this
    feature -- must ALSO be INDETERMINATE, not PASS, distinguished from the
    absent-file case only by `ledger_exists: true` in the payload."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    AtCompletionLedger(_FEATURE_ID, repo).append_gate_event(
        event="SomeOtherGateEvent", slice_id="slice-01"
    )

    exit_code = verify_seal_provenance_main(
        ["--repo", str(repo), "--feature-id", _FEATURE_ID]
    )
    out = capsys.readouterr().out
    payload = json.loads(out.splitlines()[0])

    assert exit_code == 3
    assert payload["verdict"] == "INDETERMINATE"
    assert payload["audited"] == 0
    assert payload["reason"] == "zero_population"
    assert payload["ledger_exists"] is True
