"""des-reverify-slice-commit -- recover an orphaned carpaccio slice.

`F-CARPACCIO-REVERIFY-ORPHANED-SLICE`. A thin orchestration CLI that
re-verifies a carpaccio slice whose commit landed but whose ledger entry
was never written -- an "orphaned" slice. It composes two existing pure
gates (`verify_slice_commit_completeness`, `run_contract_gate`) then
performs one ledger mutation, gated by six fail-closed preconditions.

The precondition (P1-P6), gate-composition (E1 ``des.cli.check_slice_at_completeness``
+ E2), and ledger-record helpers now live VERBATIM in the shared
``des.cli._reverify_core`` module, re-imported below so the ``des
reverify-slice-commit`` and ``des attest-bundled-slice`` CLIs share ONE
attestation core (no parallel path -- the `F-DES-LEDGER-BYPASS-GATE`
failure class). The re-import binds each helper at module scope, so
``reverify_slice_commit._compose_gates is _reverify_core._compose_gates``
-- behaviour-preserving, object-identical (f-attest-bundled-slice slice-01).

This module owns the argument parser (``_build_parser``) and the
orchestration entry point (``main``) -- the success/gate-fail recovery flow
over the shared core helpers.

stdlib-only (no `import yaml`) per the DES-bundle contract, mirroring the
two gate CLIs it composes. Single-line JSON events to stdout follow the
gate CLIs' `_emit` convention.

Exit codes:
    0 = success.
    1 = refused / blocked (a precondition or gate refused the slice).
    2 = malformed input -- a bad `--slice-id`, or an unreadable repo or
        commit. The JSON payload names the offending input.

Reference: docs/feature/fix-carpaccio-reverify-orphaned-slice/feature-delta.md
+ docs/feature/f-attest-bundled-slice/feature-delta.md sec.3 (shared core).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument

# The shared precondition/gate/record core -- extracted VERBATIM into
# des.cli._reverify_core (f-attest-bundled-slice slice-01). Re-importing the
# helpers binds them at THIS module's scope, so reverify's public helper
# surface is OBJECT-IDENTICAL to the shared core (the no-parallel-copy witness).
from des.cli._reverify_core import (
    _SLICE_ID_RE,
    _compose_gates,
    _emit,
    _in_commit_at_presence,
    _malformed_input,
    _orphan_state,
    _path_in_commit_tree,
    _preconditions,
    _predecessor_verified,
    _record_outcome,
    _refused,
    _run_gate,
    _tracked_before_at_presence,
)


__all__ = [
    "_SLICE_ID_RE",
    "_build_parser",
    "_compose_gates",
    "_emit",
    "_in_commit_at_presence",
    "_malformed_input",
    "_orphan_state",
    "_path_in_commit_tree",
    "_preconditions",
    "_predecessor_verified",
    "_record_outcome",
    "_refused",
    "_run_gate",
    "_tracked_before_at_presence",
    "main",
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des reverify-slice-commit",
        description="Re-verify and recover an orphaned carpaccio slice.",
    )
    add_repo_root_argument(
        parser, "--repo", required=True, help="Path to the git repository to inspect."
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="The feature whose slice is being re-verified.",
    )
    parser.add_argument(
        "--slice-id",
        required=True,
        help="The orphaned slice to re-verify (slice-NN).",
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="The commit-ish carrying the slice (e.g. HEAD).",
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        default=None,
        choices=(None, "gherkin", "pytest-regression"),
        help=(
            "The acceptance-test kind the slice's committed suite carries "
            "(fix-reverify-slice-commit-at-kind). 'pytest-regression' skips "
            "the whole-tree runner-routing seam in the composed E2 gate so a "
            "Python-only slice reverify never mis-routes through a "
            "Rust-primary repo's cargo lockfile. Omitted / 'gherkin' keeps "
            "the EXISTING runner-routed behavior byte-identical."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Re-verify an orphaned carpaccio slice (scaffold, P1-P6, gate composition)."""
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

    malformed = _malformed_input(repo, args.slice_id, args.commit)
    if malformed is not None:
        _emit(malformed)
        return 2

    refusal = _preconditions(repo, args.feature_id, args.slice_id, args.commit)
    if refusal is not None:
        _emit(refusal)
        return 1

    # Gate composition: the preconditions (P1-P6) have all passed.
    failing_gate = _compose_gates(
        repo, args.commit, args.feature_id, args.slice_id, at_kind=args.at_kind
    )
    if failing_gate is not None:
        # Gate-fail path (step 04). A non-zero gate fails closed: append a
        # genuine `SliceCommitBlocked` ledger record the identical way the U2
        # handler's block path does, then surface `SliceReverifyBlocked`
        # naming the failing gate. No `SliceReverified` provenance record is
        # appended here -- that is success-only.
        _record_outcome(
            args.feature_id,
            repo,
            args.slice_id,
            ledger_events=("SliceCommitBlocked",),
            payload={
                "event": "SliceReverifyBlocked",
                "slice_id": args.slice_id,
                "failing_gate": failing_gate,
                "error": f"gate {failing_gate} did not pass for {args.commit!r}",
            },
        )
        return 1

    # Both gates passed: append a genuine `SliceCommitVerified` record the
    # identical way `_emit_g_commit_ledger_event` does (subagent_stop_handler),
    # then an adjacent `SliceReverified` provenance record (I-6). The
    # provenance record makes the recovery path visible in the integrity log;
    # `verified_slices()` keys only on `SliceCommitVerified`, so M8 carpaccio
    # ordering is unaffected by the second record.
    _record_outcome(
        args.feature_id,
        repo,
        args.slice_id,
        ledger_events=("SliceCommitVerified", "SliceReverified"),
        payload={
            "event": "SliceReverified",
            "slice_id": args.slice_id,
            "commit": args.commit,
        },
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
