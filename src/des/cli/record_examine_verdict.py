"""``des record-examine-verdict`` -- the User-Examiner verdict PRODUCER (P1.2).

evolution-plan P1.2: ``nw-user-examiner`` ("Vera") walks a human-intent charter
through the REAL surface of a delivered slice and observes a verdict. This CLI
is what Vera runs (she has Bash) to record that verdict -- a signed,
tamper-evident ``ExamineVerdict`` record appended to
``.nwave/telemetry/examine/{feature_id}.jsonl``. ``des commit-slice`` is the
CONSUMER (the commit-time gate) that reads this record back before a slice may
commit -- see ``des.cli.commit_slice.check_examine_verdict``.

Mirrors ``des.cli.at_review_verdict`` (the ATReviewVerdict producer): stdlib
JSONL append, canonical timestamp, dual stdout+stderr JSON emission, and a
colored human-readable summary line (``des.cli.human_surface``).

Exit codes:
    0 -- the verdict was recorded.
    2 -- the charter file does not exist (nothing to seal); LOUD what/why/how,
         never a fabricated record.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary
from des.domain.examine_verdict_signing import EXAMINE_VERDICTS, charter_seal


__all__ = ["main", "record_examine_verdict"]

_SCHEMA_VERSION = "1.0.0"
_EVENT = "ExamineVerdictRecorded"

_HUMAN_VERDICT_BY_EXAMINE_VERDICT: dict[str, Verdict] = {
    "PASS": Verdict.PASS,
    "FAIL": Verdict.FAIL,
    "INDETERMINATE": Verdict.DEGRADED,
}


def examine_ledger_path(repo: Path, feature_id: str) -> Path:
    """The examine-verdict ledger path for ``feature_id`` under ``repo``."""
    return repo / ".nwave" / "telemetry" / "examine" / f"{feature_id}.jsonl"


def _repo_relative(path: Path, repo: Path) -> str:
    """Repo-relative string form of ``path`` when it resolves under ``repo``."""
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def record_examine_verdict(
    repo: Path,
    feature_id: str,
    slice_id: str,
    charter_path: Path,
    verdict: str,
    observations: str,
    examiner: str,
    timestamp: str,
) -> dict[str, object]:
    """Seal + append a signed ``ExamineVerdict`` record; return the record written.

    Reads ``charter_path``'s CURRENT bytes and seals them (SHA-256) as
    ``charter_seal`` -- the tamper-evidence the commit-time gate later
    recomputes and compares. Append-only: earlier records are never altered.
    """
    charter_bytes = charter_path.read_bytes()
    record: dict[str, object] = {
        "event": _EVENT,
        "schema_version": _SCHEMA_VERSION,
        "feature_id": feature_id,
        "slice_id": slice_id,
        "charter_path": _repo_relative(charter_path, repo),
        "verdict": verdict,
        "observations": observations,
        "charter_seal": charter_seal(charter_bytes),
        "examiner": examiner,
        "timestamp": timestamp,
    }
    ledger_path = examine_ledger_path(repo, feature_id)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des record-examine-verdict",
        description=(
            "Record a User-Examiner (nw-user-examiner) verdict for a delivered "
            "slice: charter walked through the real surface, verdict observed."
        ),
    )
    parser.add_argument("--repo", required=True, help="Path to the repository.")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--slice", required=True, dest="slice_id")
    parser.add_argument(
        "--charter", required=True, help="Path to the human-intent charter file."
    )
    parser.add_argument("--verdict", required=True, choices=list(EXAMINE_VERDICTS))
    parser.add_argument("--observations", required=True)
    parser.add_argument("--examiner", required=True)
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def _emit(payload: dict[str, object]) -> None:
    line = json.dumps(payload, sort_keys=True) + "\n"
    sys.stdout.write(line)
    sys.stderr.write(line)


def main(argv: list[str] | None = None) -> int:
    """Record an examine-verdict from the command line."""
    args = _parse_args(argv)
    repo = Path(args.repo).resolve()
    charter_path = Path(args.charter)
    if not charter_path.is_absolute():
        charter_path = repo / charter_path

    if not charter_path.is_file():
        what = f"charter file not found: {args.charter}"
        payload: dict[str, object] = {
            "event": "CharterNotFound",
            "what": what,
            "why": (
                "des record-examine-verdict seals the CURRENT charter bytes "
                "(charter_seal); there is nothing to seal without the file."
            ),
            "how": (
                f"create/commit the charter at {args.charter}, then re-run "
                "des record-examine-verdict."
            ),
        }
        _emit(payload)
        print_human_summary(Verdict.FAIL, what)
        return 2

    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    record = record_examine_verdict(
        repo=repo,
        feature_id=args.feature_id,
        slice_id=args.slice_id,
        charter_path=charter_path,
        verdict=args.verdict,
        observations=args.observations,
        examiner=args.examiner,
        timestamp=timestamp,
    )
    _emit(record)
    print_human_summary(
        _HUMAN_VERDICT_BY_EXAMINE_VERDICT[args.verdict],
        f"examine verdict {args.verdict} recorded for "
        f"{args.feature_id}/{args.slice_id}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
