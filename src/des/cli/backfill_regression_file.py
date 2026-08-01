"""``des backfill-regression-file`` -- historical regression-gap backfill producer.

Feature-delta ``fix-shipped-regression-file-backfill`` (Fixture A, the
historical-gap half). A shipped slice's regression-evidence bookkeeping can
predate the ``regression_test_file`` ledger field (#59,
``fix-commit-slice-reverify-uses-stored-file``) -- its
``SliceCommitVerified`` record carries no stored declaration, and when its
real file also happens to live outside the naming convention, later commits'
E2 re-check (``_shipped_and_entering_regression_files`` in
``verify_slice_commit_completeness.py``) can never resolve it, degrading the
whole commit to ``SliceCommitIndeterminate`` with no recovery path.

This subcommand attests, with a REAL commit + a REAL committed-tree
existence check, that a named SHIPPED slice's regression file genuinely
existed and passed at a genuine point in this branch's own history, and
records a ``RegressionFileHistoricalBackfill`` record on the SAME per-feature
``AtCompletionLedger`` ``des commit-slice`` writes to.
``_shipped_and_entering_regression_files`` reads this record back as its
SECOND resolution tier (after the slice's own stored declaration, before the
naming-convention glob).

CLI contract (pinned by ``tests/bugs/des/test_historical_regression_file_backfill.py``):

    des backfill-regression-file
        --repo <path>                 (required)
        --feature-id <id>             (required)
        --slice-id <id>               (required -- the SHIPPED slice being backfilled)
        --regression-test-file <path> (required, repo-relative)
        --at-kind {pytest-regression,native-regression,rust-regression}  (required;
                                        'rust-regression' normalizes to
                                        'native-regression', mirroring commit_slice.py)
        --commit <commit-ish>         (required -- where this file was genuinely shipped)
        --reason <text>               (required, non-empty human justification)
        --override                    (flag, default off)

Validation order, each refusal exit 1 with a single-line JSON payload on
stdout carrying ``"event": "RegressionFileBackfillRefused"`` and a DISTINCT,
named ``"reason"`` per cause:

    a. ``--reason`` empty/whitespace           -> reason ``reason_required``
    b. slice-id never SHIPPED (no SliceCommitVerified
       record for feature-id)                 -> reason ``slice_never_shipped``
    c. ``--commit`` is NOT an ancestor of (and
       not equal to) current HEAD             -> reason ``commit_not_ancestor_of_head``
    d. ``--regression-test-file`` does not
       exist in ``--commit``'s committed tree -> reason ``regression_test_file_missing_at_commit``
    e. a backfill record for this EXACT
       (feature-id, slice-id) already exists
       and ``--override`` was NOT passed      -> reason ``duplicate_backfill_without_override``

    f. otherwise: exit 0, ``"event": "RegressionFileBackfillRecorded"``,
       appends ONE ``RegressionFileHistoricalBackfill`` ledger record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.git.git_subprocess import is_ancestor
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli._identity_args import meaningful_identity
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.verify_deliver_integrity import _slice_commit_verified_slices
from des.runtime.spawn import GIT_TIMEOUT_ENV, git_timeout_seconds, spawn


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des backfill-regression-file",
        description=(
            "Attest that a SHIPPED slice's regression file genuinely existed "
            "and passed at a genuine point in this branch's own history -- "
            "recovering a shipped slice's regression-evidence bookkeeping "
            "when it predates the stored regression_test_file ledger field "
            "or was never declared."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo",
        required=True,
        type=meaningful_identity,
        help="Path to the git repository / project root.",
    )
    parser.add_argument(
        "--feature-id",
        dest="feature_id",
        required=True,
        type=meaningful_identity,
        help="The feature the backfilled slice belongs to (kebab-case).",
    )
    parser.add_argument(
        "--slice-id",
        dest="slice_id",
        required=True,
        type=meaningful_identity,
        help="The SHIPPED slice whose regression-file gap is being backfilled.",
    )
    parser.add_argument(
        "--regression-test-file",
        dest="regression_test_file",
        required=True,
        help="Repo-relative path to the regression file, as it existed at --commit.",
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        required=True,
        choices=("pytest-regression", "native-regression", "rust-regression"),
        help=(
            "The acceptance-test kind the backfilled file attests. "
            "'rust-regression' is an accepted ALIAS of 'native-regression', "
            "normalized right after parsing -- never a second code path."
        ),
    )
    parser.add_argument(
        "--commit",
        dest="commit",
        required=True,
        help="Commit-ish where --regression-test-file was genuinely shipped and passed.",
    )
    parser.add_argument(
        "--reason",
        dest="reason",
        required=True,
        help="Non-empty human justification for this historical backfill.",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Allow superseding an existing backfill record for this (feature-id, slice-id).",
    )
    return parser


def _refuse(reason: str, feature_id: str, slice_id: str, error: str, how: str) -> int:
    print(
        json.dumps(
            {
                "event": "RegressionFileBackfillRefused",
                "reason": reason,
                "feature_id": feature_id,
                "slice_id": slice_id,
                "error": error,
                "how": how,
            }
        )
    )
    return 1


def _committed_file_bytes(repo: Path, commit_sha: str, rel_path: str) -> bytes | None:
    """Raw bytes of ``rel_path`` as committed at ``commit_sha``, or ``None``.

    ``None`` covers both "path absent at this commit" and "commit itself
    unreadable" uniformly -- the caller degrades both to the SAME
    ``regression_test_file_missing_at_commit`` refusal (GDP-6: never a
    fabricated pass on an ambiguous git failure).
    """
    completed = spawn(
        ["git", "cat-file", "-p", f"{commit_sha}:{rel_path}"],
        cwd=repo,
        capture_output=True,
        check=False,
        timeout=git_timeout_seconds(),
        timeout_env=GIT_TIMEOUT_ENV,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)
    feature_id = args.feature_id
    slice_id = args.slice_id
    regression_test_file = args.regression_test_file
    commit = args.commit
    reason_text = args.reason
    override = bool(args.override)
    at_kind = "native-regression" if args.at_kind == "rust-regression" else args.at_kind

    if reason_text is None or not reason_text.strip():
        return _refuse(
            "reason_required",
            feature_id,
            slice_id,
            "--reason must be a non-empty human justification -- an "
            "unaudited backfill is unauditable.",
            're-run with --reason "<why this file genuinely shipped and passed>"',
        )

    if slice_id not in _slice_commit_verified_slices(repo, feature_id):
        return _refuse(
            "slice_never_shipped",
            feature_id,
            slice_id,
            f"slice {slice_id!r} has no SliceCommitVerified record for "
            f"feature {feature_id!r} -- only a genuinely SHIPPED slice's "
            "regression-evidence gap can be backfilled.",
            "confirm --feature-id/--slice-id name a slice that already "
            "shipped via `des commit-slice`, or ship it first",
        )

    if not is_ancestor(repo, commit, "HEAD"):
        return _refuse(
            "commit_not_ancestor_of_head",
            feature_id,
            slice_id,
            f"--commit {commit!r} is not an ancestor of (and not equal to) "
            "this repo's current HEAD.",
            "pass a --commit that is a real ancestor of (or equal to) HEAD "
            "on this branch's own history",
        )

    resolved_commit_sha = _git(repo, "rev-parse", commit).strip()
    raw_bytes = _committed_file_bytes(repo, resolved_commit_sha, regression_test_file)
    if raw_bytes is None:
        return _refuse(
            "regression_test_file_missing_at_commit",
            feature_id,
            slice_id,
            f"--regression-test-file {regression_test_file!r} does not "
            f"exist in --commit {commit!r}'s committed tree.",
            "confirm the file's repo-relative path and the commit where it "
            "genuinely shipped, e.g. `git show <commit>:<path>`",
        )

    ledger = AtCompletionLedger(feature_id, repo)
    existing = ledger.read_records(
        slice_id=slice_id, event_type="RegressionFileHistoricalBackfill"
    )
    if existing and not override:
        return _refuse(
            "duplicate_backfill_without_override",
            feature_id,
            slice_id,
            f"a RegressionFileHistoricalBackfill record for feature "
            f"{feature_id!r} slice {slice_id!r} already exists.",
            "pass --override to intentionally supersede the existing "
            "backfill record with this new one",
        )

    content_digest = hashlib.sha256(raw_bytes).hexdigest()
    ledger.append_gate_event(
        "RegressionFileHistoricalBackfill",
        slice_id,
        regression_test_file=regression_test_file,
        at_kind=at_kind,
        commit_sha=resolved_commit_sha,
        content_digest=content_digest,
        reason=reason_text,
        override=override,
    )
    print(
        json.dumps(
            {
                "event": "RegressionFileBackfillRecorded",
                "feature_id": feature_id,
                "slice_id": slice_id,
                "regression_test_file": regression_test_file,
                "at_kind": at_kind,
                "commit_sha": resolved_commit_sha,
                "content_digest": content_digest,
                "override": override,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
