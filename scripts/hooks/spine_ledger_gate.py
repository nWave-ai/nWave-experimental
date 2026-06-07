"""Spine-ledger gate -- slices 00+01 of atdd-spine-ledger-enforcement-gate-v2.

The gate inspects a candidate commit message + target machine state and emits a
single-line JSON verdict to stdout. Two decision branches co-exist:

  Slice-00 KILL-SWITCH contract: operator-driven bypass mechanisms (env var +
  repo-local file) and a fail-open dormant-mode when the target machine has not
  adopted the spine.

  Slice-01 LEDGER-EVIDENCE BLOCK contract: when a candidate commit carries a
  `Slice-Id:` trailer, the spine telemetry directory exists, and no bypass
  fires, the gate verifies that EVERY listed slice carries a matching
  `SliceCommitVerified` record in some per-feature ledger under the telemetry
  root. Absent -> exit 1, `commit-refused`, cause `block-ledger-evidence-missing`.
  Present -> exit 0, `commit-allowed`, cause `ledger-evidence-present`. Phase 0
  audit Gap B fix option 2: a malformed legacy ledger (raising
  `LedgerIntegrityViolation`) does NOT abort the union-scan -- the gate skips
  the offending file, emits one `LedgerSkipped` audit event per skipped file,
  and continues scanning the healthy siblings.

Substrate (Ale 2026-05-28 framing-shift): Claude Code hook lifecycle. NOT git.
This script is invocable as `python -m scripts.hooks.spine_ledger_gate` from the
PreToolUse hook (slice-02 wiring) on Bash commands matching `^git commit`.

Stdlib-only (no PyYAML, no third-party deps). Mirrors the pattern of
`scripts/hooks/subagent_stop_robustness_gate.py` (shipped 2026-05-27): single
`main()` returning an exit code, JSON payload on stdout, env + filesystem reads
isolated to small helpers.

Mandate-12 SSOT: the ledger-evidence path consumes the SINGLE source of truth
`AtCompletionLedger.verified_slices()` (in
`src/des/adapters/driven/logging/at_completion_ledger.py`). No duplicated
ledger reader -- the existing `verify_slice_ledger_record.py:_verified_slices`
helper logic is mirrored here as a partial-failure-tolerant union-scan over
per-feature ledger files, but the actual record reading goes through
`AtCompletionLedger` exclusively.

Exit codes:
    0 = commit-allowed -- env bypass, file bypass, dormant-mode, no slice
        trailer, or every listed slice has a matching ledger record
    1 = commit-refused -- the candidate commit carries a `Slice-Id:` trailer
        for a slice that has no matching `SliceCommitVerified` ledger record

Audit events:
    SpineBypassUsed -- emitted on env or file bypass; carries bypass_source +
    candidate_slice. Written JSONL to `.nwave/des/logs/audit-{today}.log`.
    Dormant-mode emits ZERO audit events (silent default for non-adopters).

    LedgerSkipped -- emitted once per per-feature ledger file that raises
    `LedgerIntegrityViolation` during the union-scan; carries ledger_path +
    cause + ts. Slice-01 Phase 0 Gap B partial-failure tolerance.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


# Make the `des` package importable when the gate runs as a standalone
# subprocess (the hook does not put `src/` on `sys.path`). The script lives at
# `scripts/hooks/`, so the repo root is two parents up and `src/` sits beneath
# it. Mirrors `verify_slice_ledger_record.py` -- target-machine-neutral self-
# bootstrap, no dependency on pytest config or installed-artifact layout.
_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from des.adapters.driven.logging.at_completion_ledger import (  # noqa: E402
    AtCompletionLedger,
    LedgerIntegrityViolation,
)


_BYPASS_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"
_GATE_NAME = "spine-ledger-gate"
_BYPASS_EVENT = "SpineBypassUsed"
_LEDGER_SKIPPED_EVENT = "LedgerSkipped"
_DISABLED_GATES_RELPATH = Path(".nwave") / "disabled-gates"
_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"

# Audit-event bypass_source attribution values. Distinct from `_BYPASS_ENV`
# (which is the env-var NAME); these are the values the audit log carries to
# distinguish env vs file as the bypass origin.
_BYPASS_SOURCE_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"
_BYPASS_SOURCE_FILE = ".nwave/disabled-gates"

# Verdict literals carried in the stdout JSON contract.
_VERDICT_ALLOWED = "commit-allowed"
_VERDICT_REFUSED = "commit-refused"


class BypassCause(StrEnum):
    """Cause vocabulary carried by the spine-ledger gate stdout verdict + audit events.

    Pista 1 v2 Phase 2.25 L4 Abstraction Refinement: eliminates Primitive
    Obsession on the seven `_CAUSE_*` string constants. Each member's
    `.value` is byte-identical to the predecessor constant it replaced — the
    predecessor feature's 15 ATs pin the wire-level vocabulary, and the L4
    refactor preserves that wire format exactly (AT-1 5-row parity outline +
    AT-3 regression-zero guard).

    StrEnum (PEP 663, Python 3.11+) means each member IS a `str` subclass:
    `BypassCause.OPERATOR_ENV_BYPASS == "operator-env-bypass"` evaluates
    True, and `json.dumps({"cause": BypassCause.OPERATOR_ENV_BYPASS})`
    serialises the bare string value, NOT a tagged enum representation.
    The producer-side migration is therefore transparent to every existing
    consumer of the gate's stdout contract.

    Type-safety benefit: future cause additions are caught at lint/mypy
    time (a typo on a `BypassCause.<MEMBER>` reference is an
    AttributeError, not a silently-misspelled audit event). Closes the
    Primitive Obsession smell on cause vocabulary (RPP L4 timing clause).
    """

    OPERATOR_ENV_BYPASS = "operator-env-bypass"
    OPERATOR_FILE_BYPASS = "operator-file-bypass"
    SPINE_TELEMETRY_ABSENT = "spine-telemetry-absent"
    NO_SLICE_TRAILER = "no-slice-trailer"
    BLOCK_LEDGER_EVIDENCE_MISSING = "block-ledger-evidence-missing"
    LEDGER_EVIDENCE_PRESENT = "ledger-evidence-present"
    LEDGER_INTEGRITY_VIOLATION = "ledger-integrity-violation"


# Falsy env-var spellings that DO NOT activate the bypass, mirroring
# standard shell conventions for boolean flags.
_FALSY_ENV_VALUES = frozenset({"0", "false", "no", "off"})

# The trailer-extraction surface tolerates both `Slice-Id:` (the ADR-025
# lowercase-d canonical form, slice-01 contract) and `Step-Id:` (legacy
# intra-slice TDD turn marker, kept for migration window). Multiple trailers
# in one commit message collapse to ordered-unique list (mirrors the
# `verify_slice_ledger_record.py` extractor). Single SSOT regex; the slice-00
# `_SLICE_ID_TRAILER_RE` alias is retired -- `_extract_candidate_slice`
# delegates to `_extract_slice_ids` for the first-trailer convenience.
_TRAILER_MULTI_RE = re.compile(r"^(?:Slice-Id|Step-Id):\s*(\S+)\s*$")


def _extract_slice_ids(commit_message: str) -> list[str]:
    """Return every slice id carried by a Slice-Id/Step-Id trailer (ordered, deduped).

    The slice-01 block path consumes ALL listed slices, not only the first
    (mirrors `verify_slice_ledger_record._extract_slice_ids`). An empty list
    means the commit is not a slice commit -- the gate abstains.
    """
    ordered: list[str] = []
    for line in commit_message.splitlines():
        match = _TRAILER_MULTI_RE.match(line.strip())
        if match:
            slice_id = match.group(1)
            if slice_id not in ordered:
                ordered.append(slice_id)
    return ordered


def _collect_ledger_evidence(
    ledger_root: Path,
) -> tuple[frozenset[str], list[Path]]:
    """Union-scan per-feature ledgers under `ledger_root` for verified slices.

    Mandate-12 SSOT: the actual record reading goes through
    `AtCompletionLedger.verified_slices()` -- the M7 fail-closed integrity
    contract -- so a hand-edited or pre-M7 legacy ledger surfaces as a
    `LedgerIntegrityViolation` here, NOT a silent undercount.

    Phase 0 audit Gap B fix option 2: a per-file `LedgerIntegrityViolation`
    does NOT abort the union-scan. The offending file is recorded as a
    skipped path (caller emits one `LedgerSkipped` audit event per entry)
    and the loop continues to the next sibling. A healthy sibling ledger
    carrying the slice's `SliceCommitVerified` record still satisfies the
    ledger-evidence contract.

    Returns the (verified_slices, skipped_files) pair. `skipped_files` is
    empty on the common all-ledgers-healthy path; the caller decides whether
    to surface a `ledger_skipped` field on the stdout verdict.
    """
    verified: set[str] = set()
    skipped: list[Path] = []
    # The legacy-shape `AtCompletionLedger(feature_id, project_root)` resolves
    # `ledger_dir() == project_root / .nwave / telemetry / atdd-pure`, so the
    # `project_root` we hand the ledger is the parent of `.nwave/`. The
    # `ledger_root` argument here points at `.nwave/telemetry/atdd-pure/` --
    # three parents up reaches the project root.
    project_root = ledger_root.parent.parent.parent
    for ledger_file in sorted(ledger_root.glob("*.jsonl")):
        feature_id = ledger_file.stem
        try:
            verified |= AtCompletionLedger(feature_id, project_root).verified_slices()
        except LedgerIntegrityViolation:
            skipped.append(ledger_file)
    return frozenset(verified), skipped


def _emit_ledger_skipped_event(target_root: Path, ledger_path: Path) -> None:
    """Append one LedgerSkipped event to today's audit log (JSONL format).

    Phase 0 audit Gap B fix option 2: a malformed legacy ledger surfaced
    during the union-scan is named in the audit log so the operator sees the
    diagnostic without parsing stdout. The directory is created on demand --
    mirrors `_emit_bypass_event`.
    """
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": _LEDGER_SKIPPED_EVENT,
        "ts": datetime.now(timezone.utc).isoformat(),
        "ledger_path": str(ledger_path),
        "cause": BypassCause.LEDGER_INTEGRITY_VIOLATION,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _extract_candidate_slice(commit_message: str) -> str | None:
    """Return the first slice id carried by a Slice-Id/Step-Id trailer, or None.

    The audit event names the candidate slice the operator was attempting to
    commit when the bypass fired. A commit message without any trailer still
    produces a valid bypass event -- the field is simply None.

    L1 cleanup: delegates to `_extract_slice_ids` so a single regex
    `_TRAILER_MULTI_RE` is the source of truth for trailer extraction (the
    slice-00-only `_SLICE_ID_TRAILER_RE` is retired as redundant).
    """
    ids = _extract_slice_ids(commit_message)
    return ids[0] if ids else None


def _read_commit_message(path: Path) -> str:
    """Read the candidate commit message; return its text.

    The composition fixture always writes the file before invoking the gate
    (the test's `write_candidate_commit_message_with_slice_trailer` step). No
    AT exercises an unreadable file; slice-01 will introduce the
    malformed-input error contract when the ledger-evidence path lands.
    """
    return path.read_text(encoding="utf-8")


def _bypass_env_active() -> bool:
    """True when NWAVE_SPINE_LEDGER_GATE_BYPASS is set to a truthy value.

    Truthy = any non-empty string that is not one of `_FALSY_ENV_VALUES`
    (case-insensitive). Mirrors the standard shell convention for env-var
    flags so an operator who exports the var with any non-zero value gets
    the bypass.
    """
    raw = os.environ.get(_BYPASS_ENV, "")
    if not raw:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def _disabled_gates_file_lists_gate(target_root: Path) -> bool:
    """True when `<target>/.nwave/disabled-gates` lists `spine-ledger-gate`.

    The file format is one gate name per line. Blank lines + leading/trailing
    whitespace are tolerated. A missing file returns False (no bypass) -- the
    common case on a target that has not opted out of any gate.
    """
    path = target_root / _DISABLED_GATES_RELPATH
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == _GATE_NAME:
            return True
    return False


def _telemetry_dir_present(ledger_root: Path) -> bool:
    """True when the spine telemetry directory exists on the target machine.

    Dormant-mode precondition: customers who have not adopted the spine have
    no telemetry dir; the gate MUST NOT block them.
    """
    return ledger_root.exists() and ledger_root.is_dir()


def _audit_log_path(target_root: Path) -> Path:
    """Return today's UTC-dated audit log path under the target root."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def _emit_bypass_event(
    target_root: Path,
    bypass_source: str,
    candidate_slice: str | None,
) -> None:
    """Append one SpineBypassUsed event to today's audit log (JSONL format).

    The directory is created on demand so the first bypass on a clean target
    succeeds. The event carries the bypass-source attribution (env vs file)
    and the candidate slice the operator was committing.
    """
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": _BYPASS_EVENT,
        "ts": datetime.now(timezone.utc).isoformat(),
        "bypass_source": bypass_source,
        "candidate_slice": candidate_slice,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _emit_verdict(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON verdict object on stdout."""
    print(json.dumps(payload, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spine_ledger_gate",
        description=(
            "Spine-ledger enforcement gate. Operator bypass (env var or "
            "repo-local file) emits an audited SpineBypassUsed event; absent "
            "spine telemetry yields fail-open dormant-mode. With telemetry "
            "present and no bypass, a candidate commit carrying a Slice-Id "
            "trailer is refused (exit 1) unless every listed slice carries a "
            "matching SliceCommitVerified ledger record. A malformed legacy "
            "ledger is skipped with an audited LedgerSkipped event rather "
            "than fail-stuck-refusing every slice commit."
        ),
    )
    parser.add_argument(
        "--commit-msg-file",
        required=True,
        help="Path to the candidate commit message file.",
    )
    parser.add_argument(
        "--ledger-root",
        required=True,
        help=(
            "The spine telemetry directory "
            "(typically `<target>/.nwave/telemetry/atdd-pure`)."
        ),
    )
    parser.add_argument(
        "--target-root",
        required=True,
        help=(
            "The target machine root (the repo or installed-artifact tree) "
            "under which `.nwave/disabled-gates` and `.nwave/des/logs/` live."
        ),
    )
    return parser


def _emit_allowed(cause: BypassCause) -> None:
    """Emit the canonical `commit-allowed` verdict carrying the given cause.

    The `cause` is a `BypassCause` member; StrEnum members serialise to their
    bare string value via `json.dumps`, so the stdout wire format remains
    byte-identical to the pre-refactor `_CAUSE_*` constants.
    """
    _emit_verdict({"verdict": _VERDICT_ALLOWED, "cause": cause})


def _attach_skipped(
    payload: dict[str, object], skipped: list[Path]
) -> dict[str, object]:
    """Attach a `ledger_skipped` field to the payload when any file was skipped.

    L2 cleanup: the optional-field append pattern is shared between the
    refused-path and allowed-path verdicts; centralising it keeps both
    code paths to a single decision point.
    """
    if skipped:
        payload["ledger_skipped"] = [str(p) for p in skipped]
    return payload


def _dispatch_block_path(
    target_root: Path,
    ledger_root: Path,
    slice_ids: list[str],
) -> int:
    """Slice-01 ledger-evidence dispatcher.

    Runs a union-scan over per-feature ledgers, tolerating per-file
    `LedgerIntegrityViolation` (Phase 0 audit Gap B fix option 2). For each
    skipped file the gate emits one `LedgerSkipped` audit event so the
    operator sees the diagnostic without parsing stdout.

    Block path: any slice trailer with no matching `SliceCommitVerified`
    record across the healthy ledgers -> exit 1, `commit-refused`,
    `block-ledger-evidence-missing`. The verdict carries both an
    `unverified_slices` array AND a `slice_id` scalar (first unverified)
    so the AT's tolerant assertion accepts either shape.

    Allow path: every slice trailer has a matching record -> exit 0,
    `commit-allowed`, `ledger-evidence-present`. The verdict carries a
    `verified_slices` array AND a `slice_id` scalar (first verified). When
    any file was skipped, the verdict also carries a `ledger_skipped` array
    of skipped paths so the operator sees the partial-failure tolerance
    surface on stdout.
    """
    verified, skipped = _collect_ledger_evidence(ledger_root)
    for skipped_path in skipped:
        _emit_ledger_skipped_event(target_root, skipped_path)

    unverified = [sid for sid in slice_ids if sid not in verified]
    if unverified:
        _emit_verdict(
            _attach_skipped(
                {
                    "verdict": _VERDICT_REFUSED,
                    "cause": BypassCause.BLOCK_LEDGER_EVIDENCE_MISSING,
                    "unverified_slices": sorted(unverified),
                    "slice_id": unverified[0],
                },
                skipped,
            )
        )
        return 1

    verified_listed = [sid for sid in slice_ids if sid in verified]
    _emit_verdict(
        _attach_skipped(
            {
                "verdict": _VERDICT_ALLOWED,
                "cause": BypassCause.LEDGER_EVIDENCE_PRESENT,
                "verified_slices": sorted(verified_listed),
                "slice_id": verified_listed[0],
            },
            skipped,
        )
    )
    return 0


def _dispatch(
    target_root: Path,
    ledger_root: Path,
    commit_message: str,
) -> int:
    """Apply the full slice-00 + slice-01 decision order.

    Decision order:
        1. env-var bypass active  -> commit-allowed (audited SpineBypassUsed)
        2. disabled-gates file lists this gate -> commit-allowed (audited)
        3. spine telemetry dir absent -> commit-allowed (dormant, silent)
        4. commit has NO Slice-Id/Step-Id trailer -> commit-allowed (abstain)
        5. union-scan ledger evidence:
             - all listed slices verified -> commit-allowed
               (cause=ledger-evidence-present)
             - any slice unverified -> commit-refused
               (cause=block-ledger-evidence-missing, exit 1)
    """
    candidate_slice = _extract_candidate_slice(commit_message)
    if _bypass_env_active():
        _emit_bypass_event(target_root, _BYPASS_SOURCE_ENV, candidate_slice)
        _emit_allowed(BypassCause.OPERATOR_ENV_BYPASS)
        return 0

    if _disabled_gates_file_lists_gate(target_root):
        _emit_bypass_event(target_root, _BYPASS_SOURCE_FILE, candidate_slice)
        _emit_allowed(BypassCause.OPERATOR_FILE_BYPASS)
        return 0

    if not _telemetry_dir_present(ledger_root):
        _emit_allowed(BypassCause.SPINE_TELEMETRY_ABSENT)
        return 0

    slice_ids = _extract_slice_ids(commit_message)
    if not slice_ids:
        # Not a slice commit -- abstain. The kill-switch already cleared,
        # the telemetry dir is present, but the commit carries no Slice-Id
        # trailer so the ledger-evidence contract does not apply.
        _emit_allowed(BypassCause.NO_SLICE_TRAILER)
        return 0

    return _dispatch_block_path(target_root, ledger_root, slice_ids)


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args + delegate to the unified decision dispatcher."""
    args = _build_parser().parse_args(argv)
    commit_message = _read_commit_message(Path(args.commit_msg_file))
    return _dispatch(
        target_root=Path(args.target_root),
        ledger_root=Path(args.ledger_root),
        commit_message=commit_message,
    )


if __name__ == "__main__":
    sys.exit(main())
