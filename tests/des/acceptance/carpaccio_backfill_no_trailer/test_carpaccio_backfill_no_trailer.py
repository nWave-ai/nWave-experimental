"""Regression: the carpaccio predecessor-backfill must find a predecessor
commit that predates the `Slice-Id:` trailer convention.

RCA (bugfix-carpaccio-backfill-no-trailer, blocking des-refactor-fixer-swarm
slice-02): `_predecessor_commit_sha` (carpaccio_intercept.py) ONLY searches
`git log --grep '^Slice-Id: *<predecessor>$'` for the predecessor's commit.
`_attempt_predecessor_backfill` is otherwise fail-closed-correct (E1
AT-files-present + E2 verify-gate-scope digest) -- but it can never even START
verifying a predecessor committed before the trailer convention shipped,
because no candidate SHA is ever found. Confirmed empirically: the real
slice-01 commit `1ad46e416` ("...des refactor drains a tech-debt pile item in
an isolated worktree (slice-01)") carries NO `Slice-Id:` line -- only the
legacy `(slice-NN)` parenthetical subject suffix.

FIX: `_predecessor_commit_sha` gains a SECOND lookup strategy -- a
subject-line search for the legacy `(slice-NN)` / `[slice-NN]` parenthetical
suffix -- used ONLY when the trailer-grep strategy finds nothing. Both
strategies feed the SAME unmodified E1 + E2 verification; this widens HOW the
candidate commit is found, never weakens what is verified.

GIT SAFETY: every git call below targets the DISPOSABLE `tmp_path` fixture
only (`cwd=repo`, never a bare git config against the real project repo).

Driving surface (Mandate-13 driving-port-only): the REAL U1 carpaccio
PreToolUse intercept driving port (`intercept_atdd_pure_dispatch`), the same
production entry `des-refactor-fixer-swarm` slice-02 dispatches through. The
carpaccio + readiness sub-gates are pre-cleared closures (as the shipped
`fix-slicecommitverified-emission` composition does) so the sole observable
under test is the M8 order-check's backfill-then-allow decision.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    intercept_atdd_pure_dispatch,
)
from des.cli import run_contract_gate


_FEATURE_ID = "carpaccio-backfill-no-trailer-demo"
_PREDECESSOR = "slice-01"
_SUCCESSOR = "slice-02"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: seed")


def _write_predecessor_feature_file(repo: Path) -> Path:
    slice_dir = repo / "tests" / "des" / "acceptance" / _FEATURE_ID / "acceptance"
    slice_dir.mkdir(parents=True, exist_ok=True)
    feature_file = slice_dir / f"{_PREDECESSOR}.feature"
    feature_file.write_text(
        f"@feature-{_FEATURE_ID} @{_PREDECESSOR}\n"
        "Feature: predecessor slice\n  Scenario: x\n    Given y\n",
        encoding="utf-8",
    )
    return feature_file


def _fresh_gate_scope_digest(repo: Path) -> str:
    """The verifiable Gate-Scope digest the in-gate `--verify-gate-scope`
    recomputes -- via the PRODUCTION `run_contract_gate --collect-only
    --print-digest`, driven in-process (mirrors
    `fix-slicecommitverified-emission/steps/composition.py`).
    """
    exit_code, stdout, stderr = run_cli_in_process(
        ["--collect-only", "--print-digest", "--repo", str(repo)],
        cwd=repo,
        main=run_contract_gate.main,
    )
    if exit_code != 0:
        raise RuntimeError(
            f"run_contract_gate --collect-only --print-digest exited "
            f"{exit_code} for repo {repo}: {stderr.strip()}"
        )
    return stdout.strip().splitlines()[-1].strip()


def _seed_predecessor_commit_pre_trailer_era(repo: Path, *, with_at_file: bool) -> None:
    """A predecessor commit using ONLY the legacy `(slice-NN)` subject suffix
    -- no `Slice-Id:` trailer anywhere in the message (the pre-trailer-era
    convention `1ad46e416` actually used).

    ``with_at_file=True``: the `.feature` file is part of the SAME commit the
    subject-marker strategy finds -- E1 must pass, the backfill happy path.

    ``with_at_file=False`` reproduces the RCA Branch-A defect exactly: the
    `.feature` file is written to the WORKING TREE (so `feature_files_for_slice`
    discovers it) AFTER the marker commit, never committed anywhere -- an AT
    file authored but never persisted into the commit the backfill verifies
    against, so E1 must find it missing. Omitting the file entirely would make
    E1 vacuously pass (nothing expected -> nothing missing), which would not
    exercise the refusal path at all.
    """
    if with_at_file:
        feature_file = _write_predecessor_feature_file(repo)
        _git(repo, "add", str(feature_file.relative_to(repo)))
    else:
        (repo / "NOTES.md").write_text("no unrelated content here\n", encoding="utf-8")
        _git(repo, "add", "NOTES.md")
    _git(
        repo,
        "commit",
        "-m",
        f"feat(des): predecessor work in an isolated worktree ({_PREDECESSOR})",
    )
    digest = _fresh_gate_scope_digest(repo)
    _git(
        repo,
        "commit",
        "--amend",
        "-m",
        f"feat(des): predecessor work in an isolated worktree ({_PREDECESSOR})"
        f"\n\nGate-Scope: {digest}",
    )
    if not with_at_file:
        # RCA Branch-A: authored on disk, never committed anywhere.
        _write_predecessor_feature_file(repo)


def _seed_predecessor_commit_with_trailer(repo: Path) -> None:
    """A predecessor commit using the MODERN `Slice-Id:` trailer -- the
    regression pin: this path must keep working identically.
    """
    feature_file = _write_predecessor_feature_file(repo)
    _git(repo, "add", str(feature_file.relative_to(repo)))
    _git(repo, "commit", "-m", f"feat: predecessor work\n\nSlice-Id: {_PREDECESSOR}")
    digest = _fresh_gate_scope_digest(repo)
    _git(
        repo,
        "commit",
        "--amend",
        "-m",
        f"feat: predecessor work\n\nSlice-Id: {_PREDECESSOR}\nGate-Scope: {digest}",
    )


def _evaluate_entry_gate(repo: Path):
    return intercept_atdd_pure_dispatch(
        prompt=(
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : A_GREEN_ATS -->\n"
            f"<!-- DES-SLICE : {_SUCCESSOR} -->\n"
            "\natdd_pure dispatch body.\n"
        ),
        feature_id=_FEATURE_ID,
        project_root=repo,
        carpaccio_runner=lambda _f, _s: (
            0,
            json.dumps({"event": "SliceCleared", "slice_id": _s}),
        ),
        readiness_runner=lambda _f, _s: (0, ""),
    )


def _predecessor_verified(repo: Path) -> bool:
    return _PREDECESSOR in AtCompletionLedger(_FEATURE_ID, repo).verified_slices()


# ---------------------------------------------------------------------------
# Scenario (a): pre-trailer-era subject pattern, AT files present -- backfill
# must now succeed via the new subject-marker lookup strategy.
# ---------------------------------------------------------------------------


def test_predecessor_backfill_finds_pre_trailer_commit_via_content_signature(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _seed_predecessor_commit_pre_trailer_era(tmp_path, with_at_file=True)

    decision = _evaluate_entry_gate(tmp_path)

    assert not decision.is_block, (
        "a predecessor commit carrying ONLY the legacy '(slice-NN)' subject "
        "suffix (no Slice-Id trailer) -- with its AT files genuinely "
        "committed and a verifiable Gate-Scope digest -- must be found by "
        f"the backfill and the successor allowed in. decision={decision!r}"
    )
    assert _predecessor_verified(tmp_path), (
        "the predecessor must carry a SliceCommitVerified ledger record "
        "after a successful pre-trailer-era backfill."
    )


# ---------------------------------------------------------------------------
# Scenario (b): pre-trailer-era subject pattern found, but E1 (AT files) does
# NOT match -- the backfill must still refuse; no false-allow.
# ---------------------------------------------------------------------------


def test_predecessor_backfill_still_refuses_when_at_files_missing_even_with_subject_match(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _seed_predecessor_commit_pre_trailer_era(tmp_path, with_at_file=False)

    decision = _evaluate_entry_gate(tmp_path)

    assert decision.is_block, (
        "a pre-trailer-era predecessor commit found by subject-marker but "
        "missing its AT files (E1 deficient) must still be BLOCKED -- the "
        "new lookup strategy must never weaken E1/E2 verification. "
        f"decision={decision!r}"
    )
    assert not _predecessor_verified(tmp_path), (
        "no SliceCommitVerified record may be appended when E1 fails, "
        "regardless of which lookup strategy found the candidate commit."
    )


# ---------------------------------------------------------------------------
# Scenario (c): regression pin -- a proper Slice-Id trailer commit must keep
# working exactly as before (the trailer-grep path is unchanged).
# ---------------------------------------------------------------------------


def test_predecessor_backfill_trailer_path_unchanged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _seed_predecessor_commit_with_trailer(tmp_path)

    decision = _evaluate_entry_gate(tmp_path)

    assert not decision.is_block, (
        "the modern Slice-Id trailer lookup path must keep working "
        f"unchanged (no regression from adding the fallback). decision={decision!r}"
    )
    assert _predecessor_verified(tmp_path)


# ---------------------------------------------------------------------------
# Scenario (d): RCA fix-carpaccio-e1-vacuous-taxonomy-gap -- a candidate
# commit found by the trailer scan for a feature/slice whose AT layout
# matches NEITHER the .feature nor the pytest-tagged taxonomy (zero
# candidates anywhere -- taxonomy-blind, e.g. the real des-refactor-fixer-
# swarm shape of tests/des/refactor/*.py before it was tagged) must be
# REFUSED, never silently accepted as "E1 satisfied". This reproduces the
# real incident (backlog.md:347): `missing_at_files` returns `[]` both when
# genuinely verified-complete AND when it found ZERO AT candidates to check
# in the first place -- the trailer-scan loop in `_predecessor_commit_sha`
# reads either `[]` as "this candidate satisfies E1" and accepts the FIRST
# trailer-matching commit with zero real discrimination, even though the
# commit itself carries no relation whatsoever to this feature's slice-01.
# ---------------------------------------------------------------------------


def _seed_predecessor_commit_taxonomy_blind(repo: Path) -> None:
    """A predecessor commit carrying a genuine `Slice-Id:` trailer AND a
    verifiable Gate-Scope digest (E2 would clear), but the feature owns
    ZERO `.feature`/pytest-tagged AT candidates anywhere on the tree --
    taxonomy-blind. E1 has nothing to check this candidate against; the fix
    must refuse rather than read that absence as "nothing missing".
    """
    (repo / "UNRELATED.md").write_text("unrelated content\n", encoding="utf-8")
    _git(repo, "add", "UNRELATED.md")
    _git(repo, "commit", "-m", f"feat: unrelated work\n\nSlice-Id: {_PREDECESSOR}")
    digest = _fresh_gate_scope_digest(repo)
    _git(
        repo,
        "commit",
        "--amend",
        "-m",
        f"feat: unrelated work\n\nSlice-Id: {_PREDECESSOR}\nGate-Scope: {digest}",
    )


def test_predecessor_backfill_refuses_when_taxonomy_finds_zero_candidates(
    tmp_path: Path,
) -> None:
    """RED (fix-carpaccio-e1-vacuous-taxonomy-gap): a taxonomy-blind
    feature/slice (zero .feature/pytest-tagged AT candidates anywhere) must
    cause the backfill to REFUSE, never silently accept a trailer-matching
    commit as a verified predecessor -- regardless of that commit's Gate-
    Scope digest being genuinely fresh. Today `missing_at_files` returns
    `[]` for "found nothing to check" identically to "checked everything,
    nothing missing", so this candidate is wrongly accepted as E1-satisfied.
    """
    _init_repo(tmp_path)
    _seed_predecessor_commit_taxonomy_blind(tmp_path)

    decision = _evaluate_entry_gate(tmp_path)

    assert decision.is_block, (
        "a predecessor commit whose feature/slice AT layout matches NEITHER "
        "the .feature nor the pytest-tagged taxonomy (zero candidates "
        "anywhere) must be REFUSED -- E1 found nothing to verify, which is "
        "not the same as verifying nothing is missing. Silently accepting "
        "it is exactly the incident this fix closes: a commit belonging to "
        "an unrelated feature was accepted as the true predecessor because "
        f"E1 vacuously reported [] regardless of input. decision={decision!r}"
    )
    assert not _predecessor_verified(tmp_path), (
        "no SliceCommitVerified record may be minted for a taxonomy-blind "
        "predecessor candidate -- doing so mints a false-positive ledger "
        "record for a commit that was never actually verified."
    )
