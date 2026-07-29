"""``des record-review-verdict`` -- the general reviewer-verdict PRODUCER (#45).

WS-6 recovery gap: ad-hoc reviewers (``nw-agent-builder-reviewer`` and other
non-wave reviewers dispatched for skill/prose changes) have NO ledger to
persist their verdict -- it lives ONLY in the reviewer's final chat message,
so a reviewer that dies before delivering leaves the verdict UNRECOVERABLE.
The User-Examiner (``des record-examine-verdict``) and the wave reviewers
(``record-at/discuss/design/devops-review``) already have a recovery ledger;
this CLI closes the gap for every OTHER reviewer with a single general
producer: it appends a ``ReviewVerdictRecorded`` record to
``.nwave/telemetry/review/{feature_id}.jsonl`` so an orchestrator that lost a
reviewer mid-session can grep the record back.

Mirrors ``des.cli.record_examine_verdict`` (ledger shape: event / JSONL
append / canonical UTC timestamp) and ``des.cli.at_review_verdict`` (reviewer
/ slice / verdict fields, closed verdict set).

Exit codes:
    0 -- the verdict was recorded.
    2 -- an unknown ``--verdict`` value or an unwritable ledger path; LOUD
         what/why/how, nothing written.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from typing import TYPE_CHECKING

from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.repo_path_resolver import resolve_repo_root
from des.domain.telemetry_paths import LedgerFamily, ledger_path


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["main", "record_review_verdict"]

_EVENT = "ReviewVerdictRecorded"
_REVIEW_VERDICTS = ("APPROVED", "NEEDS_REVISION", "REJECTED")

_HUMAN_VERDICT_BY_REVIEW_VERDICT: dict[str, Verdict] = {
    "APPROVED": Verdict.PASS,
    "NEEDS_REVISION": Verdict.DEGRADED,
    "REJECTED": Verdict.FAIL,
}


def review_ledger_path(repo: Path, feature_id: str) -> Path:
    """The review-verdict ledger path for ``feature_id`` under ``repo``."""
    return ledger_path(repo, LedgerFamily.REVIEW, feature_id)


def record_review_verdict(
    repo: Path,
    feature_id: str,
    slice_id: str,
    reviewer_agent_id: str,
    verdict: str,
    artifact: str,
    timestamp: str,
) -> dict[str, object]:
    """Append a ``ReviewVerdictRecorded`` record; return the record written.

    Append-only: earlier records are never altered.
    """
    record: dict[str, object] = {
        "event": _EVENT,
        "feature_id": feature_id,
        "slice_id": slice_id,
        "reviewer_agent_id": reviewer_agent_id,
        "verdict": verdict,
        "artifact": artifact,
        "timestamp": timestamp,
    }
    ledger_path = review_ledger_path(repo, feature_id)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des record-review-verdict",
        description=(
            "Record a general reviewer verdict to the review ledger, so an "
            "orchestrator can recover it after a reviewer dies mid-session."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--reviewer-agent-id", required=True)
    parser.add_argument("--verdict", required=True, choices=list(_REVIEW_VERDICTS))
    parser.add_argument(
        "--artifact", required=True, help="Free text: what was reviewed."
    )
    add_repo_root_argument(parser, "--repo-root", default=None)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def _emit(payload: dict[str, object]) -> None:
    line = json.dumps(payload, sort_keys=True) + "\n"
    sys.stdout.write(line)
    sys.stderr.write(line)


def main(argv: list[str] | None = None) -> int:
    """Record a review-verdict from the command line."""
    args = _parse_args(argv)
    repo = resolve_repo_root(args.repo_root)

    try:
        timestamp = (
            datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        record = record_review_verdict(
            repo=repo,
            feature_id=args.feature_id,
            slice_id=args.slice_id,
            reviewer_agent_id=args.reviewer_agent_id,
            verdict=args.verdict,
            artifact=args.artifact,
            timestamp=timestamp,
        )
    except OSError as os_error:
        what = f"could not write the review ledger: {os_error}"
        payload: dict[str, object] = {
            "event": "ReviewLedgerWriteFailed",
            "what": what,
            "why": "the ledger path is unwritable or the repo root is invalid.",
            "how": (
                "verify --repo-root points at a writable repository, then "
                "re-run des record-review-verdict."
            ),
        }
        _emit(payload)
        print_human_summary(Verdict.FAIL, what)
        return 2

    _emit(record)
    print_human_summary(
        _HUMAN_VERDICT_BY_REVIEW_VERDICT[args.verdict],
        f"review verdict {args.verdict} recorded for {args.feature_id}/{args.slice_id}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
