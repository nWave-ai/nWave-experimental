"""M-2 involuntary commit-time backstop -- refuse an unverified slice commit.

simplify-atdd-pure-carpaccio-spine slice-03 (DDD-2 / M-2). The single
CREATE-NEW of the feature: a thin pre-commit hook that restores the
involuntariness the removed U1/U2/U4 sequencer hooks provided.

Relocating the spine's evidence-producing logic into CLIs the orchestrator
invokes makes non-vacuity rest on a fallible operator reliably running the
right CLI -- a memory rule, not a control. This hook is the control: it fires
on EVERY commit whether or not the orchestrator wants it to, and refuses any
commit carrying a `Slice-Id:` trailer unless a matching `SliceCommitVerified`
ledger record exists.

It adds NO new gate logic -- it composes the existing
`AtCompletionLedger.verified_slices()` read. A commit with no `Slice-Id:`
trailer is not a slice commit; the hook abstains (exit 0). A `Slice-Id:`
commit whose slice has a `SliceCommitVerified` record in any per-feature
ledger under `--ledger-root` is allowed (exit 0). A `Slice-Id:` commit with no
matching record is refused (exit 1) with a structured JSON verdict naming the
`missing-slice-commit-verified-record` cause.

Usage (pre-commit, commit-msg stage):
    python scripts/hooks/verify_slice_ledger_record.py \
        --commit-msg-file .git/COMMIT_EDITMSG \
        --ledger-root .nwave/telemetry/atdd-pure

Exit codes:
    0 = allowed -- not a slice commit, or every listed slice has a record
    1 = refused -- a Slice-Id slice has no SliceCommitVerified ledger record
    2 = malformed input -- the commit-msg file is unreadable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Make the `des` package importable when the hook runs as a standalone
# subprocess (pre-commit does not put `src/` on `sys.path`). The hook lives at
# `scripts/hooks/`, so the repo root is two parents up and `src/` sits beneath
# it. Target-machine-neutral self-bootstrap -- no dependency on pytest config.
_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from des.adapters.driven.logging.at_completion_ledger import (  # noqa: E402
    AtCompletionLedger,
    LedgerIntegrityViolation,
)


_SLICE_ID_TRAILER_RE = re.compile(r"^(?:Slice-Id|Step-Id):\s*(slice-\d+)\s*$")


def _extract_slice_ids(commit_message: str) -> list[str]:
    """Return every `slice-NN` carried by a `Slice-Id:`/`Step-Id:` trailer.

    Order of first appearance is preserved; duplicates collapse so a repeated
    trailer does not double-count. An empty list means the commit is not a
    slice commit -- the hook abstains.
    """
    ordered: list[str] = []
    for line in commit_message.splitlines():
        match = _SLICE_ID_TRAILER_RE.match(line.strip())
        if match:
            slice_id = match.group(1)
            if slice_id not in ordered:
                ordered.append(slice_id)
    return ordered


def _verified_slices(ledger_root: Path) -> frozenset[str]:
    """The union of slices carrying a `SliceCommitVerified` record.

    The commit message carries only a `Slice-Id:` trailer, not a feature id,
    so the backstop scans every per-feature `{feature_id}.jsonl` ledger under
    `ledger_root` and unions their `verified_slices()`. Reads through
    `AtCompletionLedger.verified_slices()` -- the exact M7 fail-closed seam the
    spine consumes -- so a wrong-substrate or integrity-free record does not
    count as verified.
    """
    verified: set[str] = set()
    # The ledger's project_root is the parent of `.nwave/telemetry/atdd-pure`.
    # `glob` on an absent directory yields no entries, so a missing ledger
    # root needs no separate guard -- the loop simply does not run.
    project_root = ledger_root.parent.parent.parent
    for ledger_file in sorted(ledger_root.glob("*.jsonl")):
        feature_id = ledger_file.stem
        verified |= AtCompletionLedger(feature_id, project_root).verified_slices()
    return frozenset(verified)


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON verdict object."""
    print(json.dumps(payload, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_slice_ledger_record",
        description=(
            "M-2 involuntary commit-time backstop: refuse a Slice-Id commit "
            "with no matching SliceCommitVerified ledger record."
        ),
    )
    parser.add_argument(
        "--commit-msg-file",
        required=True,
        help="Path to the commit message file (e.g. .git/COMMIT_EDITMSG).",
    )
    parser.add_argument(
        "--ledger-root",
        required=True,
        help="The .nwave/telemetry/atdd-pure directory holding the ledgers.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    msg_path = Path(args.commit_msg_file)
    try:
        commit_message = msg_path.read_text(encoding="utf-8")
    except OSError as exc:
        _emit(
            {
                "event": "MalformedInput",
                "cause": "unreadable-commit-msg-file",
                "error": f"cannot read commit message file {msg_path}: {exc}",
            }
        )
        return 2

    slice_ids = _extract_slice_ids(commit_message)
    if not slice_ids:
        # Not a slice commit -- the backstop abstains.
        _emit({"event": "NotASliceCommit", "verdict": "commit-allowed"})
        return 0

    try:
        verified = _verified_slices(Path(args.ledger_root))
    except LedgerIntegrityViolation as exc:
        _emit(
            {
                "event": "LedgerIntegrityViolation",
                "cause": "ledger-integrity-violation",
                "error": f"the AT-completion ledger failed its M7 contract: {exc}",
            }
        )
        return 1

    unverified = [sid for sid in slice_ids if sid not in verified]
    if unverified:
        _emit(
            {
                "event": "SliceCommitRefused",
                "verdict": "commit-refused",
                "cause": "missing-slice-commit-verified-record",
                "unverified_slices": unverified,
                "error": (
                    "the commit carries Slice-Id trailer(s) "
                    f"{unverified} with no matching SliceCommitVerified ledger "
                    "record -- run verify_slice_commit before committing"
                ),
            }
        )
        return 1

    _emit(
        {
            "event": "SliceCommitAllowed",
            "verdict": "commit-allowed",
            "verified_slices": sorted(slice_ids),
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
