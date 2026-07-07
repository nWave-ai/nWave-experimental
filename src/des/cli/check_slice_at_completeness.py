"""des-check-slice-at-completeness -- feature-scoped E1-only completeness wrapper.

Closes F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION (PRR D2 blocker).

A thin read-only CLI wrapping the SSOT
``des.application.slice_at_completeness.missing_at_files``. It exists so
``reverify_slice_commit._compose_gates`` can run E1 feature-scoped via a
subprocess that does NOT mode-switch into the atomic verify-then-record
exit gate (the W5 defect: ``verify_slice_commit_completeness`` dispatches on
``--feature-id`` -- present ⇒ atomic gate + ledger mutation; absent ⇒ legacy
E1-only global-scope -- so reverify cannot get feature-scoped E1-only out of
the existing CLI).

Driving-port contract shape: pure-function (return-only). ZERO ledger writes,
ZERO filesystem mutation. Arch-test enforces no ``AtCompletionLedger`` import
(F4 self-application probe per residuality pass).

CLI surface:
    --repo        required: path to the git repo
    --commit      required: commit-ish to inspect
    --slice-id    required: the slice tag (e.g. slice-01)
    --feature-id  REQUIRED: the feature whose `.feature` files scope E1

Output: exactly one single-line JSON object on stdout:
    {"slice_id": "...", "missing": [...], "verdict": "complete" | "incomplete"}

Exit codes:
    0 = complete -- ``missing`` is empty.
    1 = incomplete -- ``missing`` lists the .feature files the slice commit
        fails to carry.
    2 = malformed input -- bad argv (missing ``--feature-id``), unreadable
        repo, or unresolvable commit. Argparse failures exit 2 by default,
        matching this contract.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from des.application.slice_at_completeness import missing_at_files


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des check-slice-at-completeness",
        description=(
            "Feature-scoped E1-only completeness verdict for one slice commit."
        ),
    )
    parser.add_argument(
        "--repo", required=True, help="Path to the git repository to inspect."
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="The commit-ish to inspect (e.g. HEAD).",
    )
    parser.add_argument(
        "--slice-id",
        required=True,
        help="The slice tag (e.g. slice-01) to scope the AT completeness check.",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help=(
            "The feature whose `.feature` files scope the AT search "
            "(wall W5 -- a global rglob collides @slice-NN tags across features)."
        ),
    )
    return parser


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object."""
    print(json.dumps(payload))


def main(argv: list[str] | None = None) -> int:
    """Feature-scoped E1-only completeness verdict.

    Returns 0 (complete), 1 (incomplete), or 2 (malformed). Argparse failures
    on the required ``--feature-id`` (and friends) exit 2 by default.
    """
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)
    try:
        missing = missing_at_files(repo, args.commit, args.slice_id, args.feature_id)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        _emit(
            {
                "event": "MalformedInput",
                "slice_id": args.slice_id,
                "feature_id": args.feature_id,
                "error": f"cannot inspect repository: {exc}",
                "how": (
                    "cannot inspect the repository/commit -- verify --repo "
                    f"({args.repo!r}) points at a real, readable git "
                    f"repository and --commit ({args.commit!r}) resolves to "
                    "an inspectable commit-ish in it, then re-run "
                    "`des check-slice-at-completeness`"
                ),
            }
        )
        return 2
    if missing:
        _emit(
            {
                "slice_id": args.slice_id,
                "feature_id": args.feature_id,
                "commit": args.commit,
                "missing": missing,
                "verdict": "incomplete",
                "how": (
                    "stage and land the missing .feature AT files "
                    f"({', '.join(missing)}) into the slice commit via "
                    "`des commit-slice` -- re-run it so the slice commit "
                    "carries every declared .feature file"
                ),
            }
        )
        return 1
    _emit(
        {
            "slice_id": args.slice_id,
            "feature_id": args.feature_id,
            "commit": args.commit,
            "missing": [],
            "verdict": "complete",
        }
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
