"""AT-completion-ledger audit window for delivered slice commits.

Audits a commit's AT-review record by reading the same AT-completion ledger
record the carpaccio slice gate reads, and reaching the SAME verdict the gate
reaches. One check, one home. The CLI is an audit window over the gate's
verdict logic, never a second verifier.

Resolves the ``Slice-Id:`` trailer(s) in the commit body via the domain
helper ``extract_slice_ids`` (the blessed F-07 batched-commit shape), then
for each slice runs ``check_at_review`` -- the exact record-presence check
the carpaccio gate runs -- against the AT-completion ledger. A record the
gate refuses is refused here with the SAME ``ATReviewGateRejected`` reason.

Driving port: the ``CommitTrailerReadPort.commit_message`` seam (``git show``
behind the port); the ledger + feature-delta + ``.feature`` files are read
from the filesystem. Pure-read: no file is written.

Exit codes:
    0 = all slices carry a present-and-approved record
    7 = cannot-evaluate: git absent, SHA unresolvable, OR no Slice-Id trailer
        found in the commit body (A-absent-trailer: honest nothing-to-audit
        INDETERMINATE, never a silent clear, never a block)
   45 = AT_REVIEW_NOT_APPROVED: first refusing slice's ATReviewGateRejected
        reason surfaced (the gate's own closed vocabulary)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.adapters.driven.git.git_commit_diff_adapter import GitCommitDiffAdapter
from des.adapters.driven.git.git_commit_trailer_read_adapter import (
    GitCommitTrailerReadAdapter,
)
from des.cli.carpaccio_format import (
    GateError,
    SlicePlan,
    _at_review_rejection,
    read_feature_files,
)
from des.cli.carpaccio_slice_gate import (
    check_at_review,
    parse_scenarios,
    parse_slice_plan,
)
from des.domain.repo_path_resolver import feature_delta_path as _feature_delta_path
from des.domain.slice_id_trailer import extract_slice_ids
from des.ports.driven_ports.commit_trailer_read_port import (
    CommitTrailerReadPort,
    Indeterminate,
)


_NO_SLICE_ID_REASON = "no Slice-Id trailer -- nothing to audit"


def _feature_id_for_slice(repo: Path, slice_id: str) -> str | None:
    """Discover the feature that owns ``slice_id`` by scanning the ledger dir.

    Scans ``repo/.nwave/telemetry/atdd-pure/*.jsonl`` for an
    ``ATReviewVerdict`` record whose ``slice_id`` matches. The file stem is
    the feature id. Returns the FIRST matching feature id in filesystem order,
    or ``None`` if no record matches (the gate will then surface ``absent``).
    """
    ledger_dir = repo / ".nwave" / "telemetry" / "atdd-pure"
    if not ledger_dir.is_dir():
        return None
    for ledger_file in sorted(ledger_dir.glob("*.jsonl")):
        for line in ledger_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("event") != "ATReviewVerdict":
                continue
            if record.get("slice_id") == slice_id:
                return ledger_file.stem
    return None


def _read_commit_body(
    repo: Path, sha: str, port: CommitTrailerReadPort
) -> str | Indeterminate:
    """Read a single commit body via the port; return body string or Indeterminate."""
    result = port.commit_message(repo, sha)
    if isinstance(result, Indeterminate):
        return result
    return result.body


def _slice_plan_for_feature(repo: Path, feature_id: str) -> SlicePlan | None:
    """Parse the feature's Slice Plan for the green-to-green lane consult (D1.2).

    Returns ``None`` when the feature-delta is absent or its ``[REF] Slice
    Plan`` section cannot be parsed -- ``check_at_review`` then falls back to
    the legacy ledger-record check byte-identically (``plan=None`` is its
    existing default), so a feature predating the Slice Plan convention (or
    any malformed feature-delta) audits exactly as before this change.
    """
    delta_path = _feature_delta_path(repo, feature_id)
    if not delta_path.is_file():
        return None
    try:
        return parse_slice_plan(delta_path.read_text(encoding="utf-8"))
    except GateError:
        return None


def _audit_slice(repo: Path, slice_id: str, commit_sha: str) -> None:
    """Audit one slice's review record. Raises ``GateError`` exit 45 on refusal.

    Discovers the owning feature from the ledger dir, then reuses
    ``check_at_review`` -- the carpaccio gate's own record-presence logic --
    to verify the record. A record the gate refuses is refused here with the
    same ``ATReviewGateRejected`` reason (one check, one home).

    D1.2 (f-prefactoring-dispatch-clears-honestly slice-02, feature-end deep
    review): threads ``plan=``/``commit_sha=``/``commit_diff_port=`` through
    the SAME ``check_at_review`` seam ``carpaccio_slice_gate.main`` uses at
    ENTRY, so a COMMIT-time ``@prefactoring`` slice's green-to-green proof
    actually runs here too -- a real ``GitCommitDiffAdapter`` (git behind the
    ``CommitDiffPort`` boundary, AD-21) reads the audited commit's changed
    paths. ``commit_sha`` is the SAME commit identifier this module already
    audits (``--commit``, default ``HEAD``) -- the commit whose trailers were
    just resolved.
    """
    feature_id = _feature_id_for_slice(repo, slice_id)
    if feature_id is None:
        raise _at_review_rejection("absent", slice_id)
    scenarios = parse_scenarios(read_feature_files(repo, feature_id))
    plan = _slice_plan_for_feature(repo, feature_id)
    check_at_review(
        repo,
        feature_id,
        slice_id,
        scenarios,
        plan=plan,
        commit_sha=commit_sha,
        commit_diff_port=GitCommitDiffAdapter(),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-commit-trailers",
        description=(
            "AT-completion-ledger audit window. Resolves the commit's "
            "Slice-Id trailer(s) and audits each slice's review record "
            "against the AT-completion ledger, reusing the carpaccio "
            "gate's record-presence check."
        ),
        epilog=(
            "Exit codes: 0 all slices approved | "
            "7 cannot-evaluate (git absent / SHA unresolvable / no Slice-Id trailer) | "
            "45 AT-review not approved (gate's own reason surfaced)."
        ),
    )
    parser.add_argument("--commit", default="HEAD", help="target commit SHA or ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))

    port: CommitTrailerReadPort = GitCommitTrailerReadAdapter()
    repo = Path.cwd()

    body = _read_commit_body(repo, args.commit, port)
    if isinstance(body, Indeterminate):
        print(
            f"INDETERMINATE: cannot-evaluate git commit body -- {body.reason}",
            file=sys.stderr,
        )
        return 7

    slice_ids = extract_slice_ids(body)
    if not slice_ids:
        print(
            f"INDETERMINATE: {_NO_SLICE_ID_REASON}\n"
            "Fix: if this is meant to be a slice commit, re-commit through "
            "`des commit-slice` -- it stamps the Slice-Id trailer for you; "
            "otherwise a non-slice commit carrying no Slice-Id is expected "
            "and this INDETERMINATE is correct.",
            file=sys.stderr,
        )
        return 7

    for slice_id in slice_ids:
        try:
            _audit_slice(repo, slice_id, args.commit)
        except GateError as gate_error:
            payload = gate_error.payload
            line = json.dumps(payload, sort_keys=True) + "\n"
            sys.stdout.write(line)
            sys.stderr.write(line)
            return gate_error.exit_code

    # All slices approved.
    approved_payload: dict[str, object] = {
        "event": "SliceAuditCleared",
        "slice_id": slice_ids[0] if len(slice_ids) == 1 else slice_ids,
        "audited_slices": slice_ids,
    }
    line = json.dumps(approved_payload, sort_keys=True) + "\n"
    sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
