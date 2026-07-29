"""des-verify-seal-provenance -- did a sealed slice's AT exist at its own seal?

`lane-seal-refuses-premature`, part B of the two-lane
`fix-slice-seal-carries-commit-sha` chain (part A: `commit_sha` threaded into
`SliceCommitVerified`, commit `61231e5dd`). Part A made the join key EXIST;
this CLI is the consumer that USES it -- an audit window over the
AT-completion ledger (mirrors `verify_commit_trailers.py`'s own framing: "an
audit window over the gate's verdict logic, never a second verifier"), never
a mutation.

For every `SliceCommitVerified` record of `--feature-id`, asks: did the AT
file(s) that slice owns exist as blobs in the commit `commit_sha` the record
attests? A record whose AT postdates its own seal is a PROVEN premature
attestation -- exactly the slice-03 defect (sealed at 07:35:49Z, its own
`.feature`/pytest AT authored 55 minutes later at 08:30). A record written
before `commit_sha` existed at all (every historical record predating the
part-A fix) is INDETERMINATE, never silently trusted and never a retroactive
FAIL (GDP-8).

Pure read: no ledger mutation. Composes `audit_seal_provenance`
(`des.application.seal_provenance`, git-free logic) with
`GitCommitTreePathAdapter` (the ONE place git enters, degrading LOUD to
Indeterminate on any git failure per AD-21).

Exit codes:
    0 = every record VERIFIED.
    1 = at least one record PREMATURE -- a proven premature seal exists.
    3 = zero PREMATURE, at least one INDETERMINATE -- mirrors
        `run_contract_gate._GATE_INDETERMINATE_EXIT_CODE`, the established
        "could not verify" exit code on this CLI surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.adapters.driven.git.git_commit_tree_path_adapter import (
    GitCommitTreePathAdapter,
)
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.seal_provenance import (
    SealProvenanceFinding,
    SealVerdict,
    audit_seal_provenance,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.run_contract_gate import _GATE_INDETERMINATE_EXIT_CODE


#: The exact defect class this feature exists to kill, one level up: an
#: empty AUDITED population (0 findings) must never present as a bare PASS.
#: "0 audited" collapses three genuinely different situations -- the ledger
#: is absent at this --repo (wrong path, or a separate worktree that never
#: saw the untracked telemetry file -- exactly how this residual was caught:
#: the real ledger is gitignored and does not travel between worktrees), the
#: ledger exists but is genuinely empty for this feature, or a filtering
#: defect silently dropped real records -- and a bare PASS cannot distinguish
#: any of them from "audited N records, all honest." GDP-8: the third state
#: must reach the aggregate, never silently disappear beneath it.
_ZERO_POPULATION_REASON = "zero_population"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-seal-provenance",
        description=(
            "Audit every SliceCommitVerified record for --feature-id: did "
            "the slice's AT file(s) exist at the commit_sha the seal "
            "attests? A record predating commit_sha (no join key) is "
            "reported INDETERMINATE, never silently passed."
        ),
        epilog=(
            "Exit codes: 0 all VERIFIED | "
            "1 at least one PREMATURE (proven premature seal) | "
            "3 zero PREMATURE, at least one INDETERMINATE (could not verify)."
        ),
    )
    add_repo_root_argument(parser, "--repo", default=".", help="target repository root")
    parser.add_argument(
        "--feature-id", required=True, help="feature whose ledger to audit"
    )
    return parser


def _finding_payload(finding: SealProvenanceFinding) -> dict[str, object]:
    return {
        "slice_id": finding.slice_id,
        "seq": finding.seq,
        "verdict": finding.verdict.value,
        "reason": finding.reason,
        "commit_sha": finding.commit_sha,
        "checked_paths": list(finding.checked_paths),
    }


def _human_verdict(
    premature: list[SealProvenanceFinding],
    indeterminate: list[SealProvenanceFinding],
    *,
    audited: int,
) -> tuple[Verdict, int]:
    """The aggregate verdict -- population floor first (GDP-8).

    ``audited == 0`` is checked BEFORE the per-finding tallies: an empty
    population is not "zero premature, zero indeterminate, therefore clean"
    -- it is "nothing was actually checked," which must never wear the same
    green face as "N records checked, all honest." Only a NON-EMPTY,
    all-clean population earns ``PASS``.
    """
    if audited == 0:
        return Verdict.INDETERMINATE, _GATE_INDETERMINATE_EXIT_CODE
    if premature:
        return Verdict.FAIL, 1
    if indeterminate:
        return Verdict.INDETERMINATE, _GATE_INDETERMINATE_EXIT_CODE
    return Verdict.PASS, 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    repo = Path(args.repo).resolve()

    findings = audit_seal_provenance(
        repo, args.feature_id, path_port=GitCommitTreePathAdapter()
    )

    premature = [f for f in findings if f.verdict is SealVerdict.PREMATURE]
    indeterminate = [f for f in findings if f.verdict is SealVerdict.INDETERMINATE]
    verdict, exit_code = _human_verdict(premature, indeterminate, audited=len(findings))

    payload: dict[str, object] = {
        "event": "SealProvenanceAudited",
        "feature_id": args.feature_id,
        "verdict": verdict.value,
        "audited": len(findings),
        "premature_count": len(premature),
        "indeterminate_count": len(indeterminate),
        "findings": [_finding_payload(f) for f in findings],
    }
    if not findings:
        ledger_path = AtCompletionLedger(args.feature_id, repo).ledger_path()
        payload["reason"] = _ZERO_POPULATION_REASON
        payload["ledger_path"] = str(ledger_path)
        payload["ledger_exists"] = ledger_path.is_file()
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")

    if not findings:
        ledger_exists = bool(payload["ledger_exists"])
        why = (
            f"0 SliceCommitVerified records were found for "
            f"{args.feature_id!r} at {payload['ledger_path']} -- "
            + (
                "the ledger file exists but carries none for this feature"
                if ledger_exists
                else "the ledger file does not exist at this path at all "
                "(commonly: a --repo pointed at the wrong checkout, or a "
                "separate git worktree that never saw this UNTRACKED "
                "telemetry file -- it does not travel between worktrees)"
            )
        )
        how = (
            "an empty audited population is NOT evidence of a clean seal "
            "history -- re-run with --repo pointed at the checkout that "
            "actually holds "
            f".nwave/telemetry/atdd-pure/{args.feature_id}.jsonl before "
            "trusting any verdict for this feature"
        )
    elif premature:
        why = "; ".join(f"{f.slice_id} (seq={f.seq}): {f.reason}" for f in premature)
        how = (
            "the AT for a PREMATURE slice postdates its own seal -- this is "
            "not mechanically auto-repairable (it may mean the seal is "
            "spurious, or the AT was legitimately re-authored later); "
            "reconcile by hand which is true, then if the seal is spurious "
            "re-verify via `des reverify-slice-commit --feature-id "
            f"{args.feature_id} --slice-id <slice-id> --commit <real-sha>`"
        )
    elif indeterminate:
        why = "; ".join(
            f"{f.slice_id} (seq={f.seq}): {f.reason}" for f in indeterminate
        )
        how = (
            "these records cannot be mechanically verified (no commit_sha, "
            "no discoverable AT, or git itself could not resolve the fact) "
            "-- this is a visibility gap to review manually, not an "
            "automatic failure"
        )
    else:
        why = f"every record's AT existed at its own attested commit_sha ({len(findings)} audited)"
        how = ""

    print_human_summary(
        verdict,
        f"seal-provenance audit of {args.feature_id!r}: "
        f"{len(findings)} audited, {len(premature)} premature, "
        f"{len(indeterminate)} indeterminate",
        why=why,
        how=how,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]
