"""Regression: the carpaccio predecessor-backfill lookup must be SCOPED to
the dispatching feature -- a `slice-01`/`slice-02` marker is REUSED across
every feature in the repo, so trusting the trailer strategy's first hit can
short-circuit the fallback strategy entirely and never even try the real
predecessor commit.

RCA (bugfix-carpaccio-feature-scoping, blocking des-refactor-fixer-swarm
slice-02 dispatch, found empirically by the prior bugfix's own crafter,
verified against a read-only clone of the real repo): `_predecessor_commit_sha`
(carpaccio_intercept.py) searched for the predecessor's identity WITHOUT
scoping by `feature_id`. Concretely, for des-refactor-fixer-swarm's slice-02
dispatch: `git log --grep '^Slice-Id: *slice-01$'` matched commit `53ce06c4`
(an UNRELATED feature's commit, carrying a genuine `Slice-Id: slice-01`
trailer) -- the OLD code returned that match UNCONDITIONALLY, without ever
trying the subject-marker fallback strategy, even though the REAL
predecessor commit `1ad46e416` (des-refactor-fixer-swarm's own slice-01)
predates the `Slice-Id:` trailer convention entirely and can therefore ONLY
be found via the subject-marker fallback. E1 (AT-files-present inside
`_attempt_predecessor_backfill`) correctly REJECTS `53ce06c4` (it does not
carry des-refactor-fixer-swarm's AT files) -- so this was never a
false-allow safety bug -- but because the trailer strategy's ONE wrong hit
starved the subject-marker fallback of ever running, the backfill could
never even REACH the right candidate commit, permanently blocking the
successor out of order.

FIX: `_predecessor_commit_sha` now walks ALL of the trailer strategy's
candidates (most recent first), checking E1 per candidate, and falls
through to the subject-marker strategy's candidates (same per-candidate E1
walk) ONLY when none of the trailer candidates satisfy E1 -- instead of
returning the trailer strategy's first hit unconditionally.

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


_FEATURE_WRONG = "carpaccio-predecessor-lookup-feature-scoped-wrong"
_FEATURE_RIGHT = "carpaccio-predecessor-lookup-feature-scoped-right"
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


def _write_predecessor_feature_file(repo: Path, feature_id: str) -> Path:
    slice_dir = repo / "tests" / "des" / "acceptance" / feature_id / "acceptance"
    slice_dir.mkdir(parents=True, exist_ok=True)
    feature_file = slice_dir / f"{_PREDECESSOR}.feature"
    feature_file.write_text(
        f"@feature-{feature_id} @{_PREDECESSOR}\n"
        "Feature: predecessor slice\n  Scenario: x\n    Given y\n",
        encoding="utf-8",
    )
    return feature_file


def _fresh_gate_scope_digest(repo: Path) -> str:
    """The verifiable Gate-Scope digest the in-gate `--verify-gate-scope`
    recomputes -- via the PRODUCTION `run_contract_gate --collect-only
    --print-digest`, driven in-process (mirrors
    `carpaccio_backfill_no_trailer/test_carpaccio_backfill_no_trailer.py`).
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


def _seed_wrong_feature_trailer_commit(repo: Path) -> None:
    """An UNRELATED feature's slice-01 commit -- modern `Slice-Id:` trailer,
    its OWN AT file, its OWN verifiable Gate-Scope digest. This is the
    commit `53ce06c4` plays in the real bug: a genuine trailer match for
    ``_PREDECESSOR`` that belongs to a completely different feature.
    """
    feature_file = _write_predecessor_feature_file(repo, _FEATURE_WRONG)
    _git(repo, "add", str(feature_file.relative_to(repo)))
    _git(
        repo,
        "commit",
        "-m",
        f"feat({_FEATURE_WRONG}): unrelated predecessor work\n\n"
        f"Slice-Id: {_PREDECESSOR}",
    )
    digest = _fresh_gate_scope_digest(repo)
    _git(
        repo,
        "commit",
        "--amend",
        "-m",
        f"feat({_FEATURE_WRONG}): unrelated predecessor work\n\n"
        f"Slice-Id: {_PREDECESSOR}\nGate-Scope: {digest}",
    )


def _seed_right_feature_pre_trailer_commit(repo: Path) -> None:
    """The REAL predecessor's commit -- pre-trailer-era convention ONLY (the
    legacy `(slice-NN)` subject suffix, no `Slice-Id:` trailer anywhere),
    committed AFTER the wrong feature's trailer commit. This is the commit
    `1ad46e416` plays in the real bug: findable ONLY via the subject-marker
    fallback strategy.
    """
    feature_file = _write_predecessor_feature_file(repo, _FEATURE_RIGHT)
    _git(repo, "add", str(feature_file.relative_to(repo)))
    _git(
        repo,
        "commit",
        "-m",
        f"feat({_FEATURE_RIGHT}): predecessor work ({_PREDECESSOR})",
    )
    digest = _fresh_gate_scope_digest(repo)
    _git(
        repo,
        "commit",
        "--amend",
        "-m",
        f"feat({_FEATURE_RIGHT}): predecessor work ({_PREDECESSOR})\n\n"
        f"Gate-Scope: {digest}",
    )


def _evaluate_entry_gate(repo: Path, feature_id: str):
    return intercept_atdd_pure_dispatch(
        prompt=(
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : A_GREEN_ATS -->\n"
            f"<!-- DES-SLICE : {_SUCCESSOR} -->\n"
            "\natdd_pure dispatch body.\n"
        ),
        feature_id=feature_id,
        project_root=repo,
        carpaccio_runner=lambda _f, _s: (
            0,
            json.dumps({"event": "SliceCleared", "slice_id": _s}),
        ),
        readiness_runner=lambda _f, _s: (0, ""),
    )


def _predecessor_verified(repo: Path, feature_id: str) -> bool:
    return _PREDECESSOR in AtCompletionLedger(feature_id, repo).verified_slices()


# ---------------------------------------------------------------------------
# Scenario (a): genuine cross-feature collision, reproducing the real
# blocker exactly -- an unrelated feature's Slice-Id-trailer commit for
# `slice-01` exists on trunk BEFORE the real predecessor's own pre-trailer-
# era commit. Dispatching the RIGHT feature's slice-02 must still resolve
# ITS OWN slice-01 commit via the subject-marker fallback, not give up
# after the wrong feature's trailer hit.
# ---------------------------------------------------------------------------


def test_predecessor_lookup_scoped_to_feature_id_not_cross_feature_collision(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _seed_wrong_feature_trailer_commit(tmp_path)
    _seed_right_feature_pre_trailer_commit(tmp_path)

    decision = _evaluate_entry_gate(tmp_path, _FEATURE_RIGHT)

    assert not decision.is_block, (
        "the right feature's slice-02 dispatch must find ITS OWN slice-01 "
        "commit via the subject-marker fallback, even though an unrelated "
        "feature's Slice-Id-trailer commit for the same slice marker exists "
        f"on trunk. decision={decision!r}"
    )
    assert _predecessor_verified(tmp_path, _FEATURE_RIGHT), (
        "the right feature's ledger must carry the SliceCommitVerified "
        "record for its own slice-01 after a correctly feature-scoped "
        "backfill."
    )
    assert not _predecessor_verified(tmp_path, _FEATURE_WRONG), (
        "the wrong feature's ledger must remain untouched -- the backfill "
        "for the right feature's dispatch must never cross-write the wrong "
        "feature's record."
    )


# ---------------------------------------------------------------------------
# Scenario (b): regression pin -- the original single-feature case (no
# collision, modern trailer commit only) must keep working identically.
# ---------------------------------------------------------------------------


def test_predecessor_lookup_single_feature_no_collision_unchanged(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _seed_wrong_feature_trailer_commit(tmp_path)

    decision = _evaluate_entry_gate(tmp_path, _FEATURE_WRONG)

    assert not decision.is_block, (
        "the single-feature case (no cross-feature collision) must keep "
        f"working unchanged. decision={decision!r}"
    )
    assert _predecessor_verified(tmp_path, _FEATURE_WRONG)
