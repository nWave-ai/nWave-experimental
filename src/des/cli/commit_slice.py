"""des commit-slice -- the mechanical correct-by-construction slice commit.

Closes the recurring gate-scope-timing defect (#67 facet-4 / AD-23 adjacent):
a slice commit's ``Gate-Scope:`` trailer must carry the COMMITTED-scope digest
the G_COMMIT exit gate (``run_contract_gate --verify-gate-scope``) re-derives,
NOT the working-tree digest computed before the commit -- when the slice's new
AT files are still untracked.

THE DIVERGENCE this command removes
-----------------------------------
``run_contract_gate``'s default (producer) mode digests the committed scope of
the *current* HEAD. At terminating-run time HEAD is still the slice's PARENT,
so the new ``test_*.py`` / ``.feature`` files (untracked) are absent from the
digest input -> the producer stamps the PARENT's committed-scope digest. After
``git commit`` HEAD's committed tree NOW includes those files, so the exit
gate's fresh committed-scope digest of HEAD differs -> ``GateScopeUnverified``
(mismatch) -> a manual ``git commit --amend`` of the trailer was required to
ship. That amend was prose discipline, inconsistently applied (some crafters
stamped the working-tree digest, others did the amend) -- a discipline-gap.

THE MECHANICAL FLOW (correct by construction)
---------------------------------------------
The committed-scope digest is over the committed TREE, NOT the commit message,
so amending the *message* leaves the digest STABLE -- a fixed point reached in
ONE amend:

  1. stage the named paths (or ``--all``)
  2. commit with a PLACEHOLDER ``Gate-Scope:`` trailer (HEAD now carries the
     slice's tree)
  3. compute the COMMITTED-scope digest of the resulting HEAD via the existing
     ``run_contract_gate`` committed-scope seam
  4. ``--amend`` the message, replacing the placeholder with the real digest
  5. (default) verify clean via ``run_contract_gate --verify-gate-scope`` --
     the acceptance proof: a verified commit with NO human amend.

The crafter calls ONE command; the digest is ALWAYS committed-scope. git is a
test-harness / driven-port dependency confined to ``git_mutate.git_run`` +
``git_subprocess.git_text`` (AD-21 git-free mandate -- the gate logic itself
stays Python+filesystem).

Exit codes:
    0 = a verified slice commit was produced.
    1 = the committed-scope digest could not be established (LOUD
        INDETERMINATE -- e.g. not a git work-tree) OR the post-amend verify
        refused the commit.
    2 = malformed input (nothing staged, empty message, repo unreadable).

Reference: docs/feature/des-spine-control-plane-ssot (committed-scope trailer),
           #67 facet-4 / MEMORY control-plane SSOT (digest-timing facet).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.git.git_mutate import git_run
from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.cli.run_contract_gate import (
    _committed_scope_digest_value,
    _CommittedScopeDigest,
    extract_gate_scope,
)
from des.cli.verify_slice_commit_completeness import _append_slice_commit_indeterminate
from des.domain.slice_id_trailer import extract_slice_ids


# The honest free-text degrade reason the committed-scope-digest step records
# when no pytest interpreter resolves on this machine (a non-Python target). The
# first value the carpaccio-honest AT pins; degrade-LOUD keeps the taxonomy open.
_DEGRADE_REASON_INTERPRETER_UNAVAILABLE = "gate_scope_interpreter_unavailable"


# The placeholder digest stamped on the FIRST (pre-amend) commit. 64 zero-hex
# matches the ``Gate-Scope:`` trailer shape (``[0-9a-f]{64}``) so the commit is
# well-formed, yet is unmistakably a placeholder. It is replaced in step 4 by
# the real committed-scope digest of the resulting HEAD.
_PLACEHOLDER_DIGEST = "0" * 64

# Matches a ``Gate-Scope:`` trailer line (anchored, full-line) for replacement
# during the amend. Mirrors run_contract_gate._GATE_SCOPE_TRAILER_RE but is
# multiline-anchored for an in-place message rewrite.
_GATE_SCOPE_LINE_RE = re.compile(r"^Gate-Scope:.*$", re.MULTILINE)

# Matches a ``Reviewed-by:`` trailer line (multiline-anchored). Presence in the
# operator-supplied ``--message`` means the operator hand-stamped the trailer --
# it is then preserved verbatim and the mechanical ledger lookup is skipped.
_REVIEWED_BY_LINE_RE = re.compile(r"^Reviewed-by:.*$", re.MULTILINE)

# The ATReviewVerdict ledger event name + the APPROVED verdict literal. The
# ``Reviewed-by:`` trailer carries the APPROVED ATReviewVerdict record's
# tamper-evident ``record_hash`` -- the SAME value the M7 ledger seals when
# ``des record-at-review-verdict`` records the acceptance-designer's approval.
_AT_REVIEW_VERDICT_EVENT = "ATReviewVerdict"
_VERDICT_APPROVED = "APPROVED"


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object."""
    print(json.dumps(payload))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des commit-slice",
        description=(
            "Produce a slice commit whose Gate-Scope: trailer ALWAYS carries the "
            "committed-scope digest the G_COMMIT exit gate verifies -- correct by "
            "construction, no manual amend."
        ),
    )
    parser.add_argument(
        "--repo", required=True, help="Path to the git repository / project root."
    )
    parser.add_argument(
        "--message",
        required=True,
        help="The commit message BODY (conventional-commit subject + body). The "
        "Gate-Scope: trailer is appended mechanically -- do NOT include one.",
    )
    parser.add_argument(
        "--slice-id",
        default=None,
        help="The carpaccio slice identity (slice-NN). Stamped mechanically as a "
        "Slice-Id: trailer (idempotent -- skipped if the message already carries "
        "one). Required unless the --message already carries a Slice-Id: trailer.",
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help="The feature the slice commit belongs to (kebab-case). The "
        "AT-completion ledger is feature-scoped, so it is required to MINT the "
        "honest SliceCommitIndeterminate record when the committed-scope digest "
        "degrades LOUD on a non-Python target (interpreter unavailable). On the "
        "non-degraded path it is unused.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        dest="paths",
        help="A path to stage (repeatable). Omit with --all to stage everything.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Stage all tracked+untracked changes (git add -A) instead of --path.",
    )
    parser.add_argument(
        "--no-verify-commit",
        action="store_true",
        help="Pass --no-verify to the underlying git commit/amend (skip git hooks). "
        "The committed-scope verify still runs unless --skip-verify is given.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-amend run_contract_gate --verify-gate-scope check "
        "(produce + amend only). The verify is the acceptance proof; skipping it "
        "is for callers that verify separately.",
    )
    return parser


def _stage(repo: Path, paths: list[str], stage_all: bool) -> dict[str, object] | None:
    """Stage the requested paths; return a MalformedInput payload or None.

    ``--all`` stages everything (``git add -A``); otherwise each ``--path`` is
    staged. After staging, refuse (MalformedInput) when the index carries no
    change -- an empty commit is never a slice commit.
    """
    if stage_all:
        git_run(repo, "add", "-A")
    elif paths:
        git_run(repo, "add", "--", *paths)
    else:
        return {
            "event": "MalformedInput",
            "error": "no paths to stage: pass --path (repeatable) or --all",
        }

    # `git diff --cached --quiet` exits 1 when the index differs from HEAD.
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if staged.returncode == 0:
        return {
            "event": "MalformedInput",
            "error": "nothing staged -- the index matches HEAD; refusing an "
            "empty slice commit",
        }
    return None


def _commit_with_placeholder(repo: Path, message: str, no_verify: bool) -> None:
    """Create the first commit carrying a PLACEHOLDER Gate-Scope: trailer.

    HEAD now carries the slice's committed tree -- the prerequisite for a
    committed-scope digest that includes the slice's new (previously untracked)
    AT files. Written via ``--file`` (never a shell-interpolated ``-m``) so a
    multi-line body with special characters commits verbatim.
    """
    full_message = f"{message.rstrip()}\n\nGate-Scope: {_PLACEHOLDER_DIGEST}\n"
    args = ["commit", "--file", "-"]
    if no_verify:
        args.append("--no-verify")
    subprocess.run(
        ["git", *args],
        cwd=repo,
        input=full_message,
        text=True,
        capture_output=True,
        check=True,
    )


def _amend_trailer(repo: Path, digest: str) -> None:
    """Amend HEAD's message, replacing the placeholder with the real digest.

    Reads HEAD's full message, substitutes the ``Gate-Scope:`` line with the
    committed-scope ``digest``, and amends. Because the digest is over the
    committed TREE (NOT the message), this message-only amend leaves the
    committed-scope digest STABLE -- the post-amend verify re-derives a
    byte-identical digest (the fixed point).

    The amend ALWAYS passes ``--no-verify``, unconditionally. The amend mutates
    only the commit MESSAGE on an already-validated tree: the slice's tree was
    already validated by the pre-commit hook on the FIRST commit
    (``_commit_with_placeholder``), and content validity is re-proven end-to-end
    by the final ``_verify`` (``run_contract_gate --verify-gate-scope``). Re-running
    the pre-commit hook here would re-execute the full suite a SECOND time against
    a byte-identical tree -- redundant by construction. The user ``--no-verify-commit``
    flag governs ONLY the first commit (``_commit_with_placeholder``); it does not
    reach this amend, because the amend never warrants the hook either way.
    """
    current = _git(repo, "log", "-1", "--format=%B", "HEAD")
    rewritten = _GATE_SCOPE_LINE_RE.sub(f"Gate-Scope: {digest}", current, count=1)
    args = ["commit", "--amend", "--file", "-", "--no-verify"]
    subprocess.run(
        ["git", *args],
        cwd=repo,
        input=rewritten,
        text=True,
        capture_output=True,
        check=True,
    )


def _verify(repo: Path) -> int:
    """Run ``run_contract_gate --verify-gate-scope --commit HEAD``; return exit.

    Invoked in-process (the SAME definition the G_COMMIT exit gate runs -- no
    stub, no reimplementation). A clean exit 0 here is the acceptance proof: the
    produced commit verifies with NO manual amend.
    """
    from des.cli.run_contract_gate import main as run_contract_gate_main

    return run_contract_gate_main(
        ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    )


def _review_verdict_hash(
    repo: Path, slice_id: str, feature_id: str | None
) -> str | None:
    """The latest APPROVED ATReviewVerdict ``record_hash`` for ``slice_id``, or None.

    The ``Reviewed-by:`` trailer carries the ATReviewVerdict ledger record's
    ``record_hash`` -- the M7 tamper-evident seal ``des record-at-review-verdict``
    minted when the acceptance-designer reviewer APPROVED the slice's AT set. The
    READ here is aligned with that WRITE: same ledger
    (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``), same record keyed by
    ``slice_id``, the LATEST (highest ``seq``) APPROVED record selected.

    Resolves the owning feature from ``--feature-id`` when supplied; otherwise
    discovers it by scanning the per-feature ledger directory for the file whose
    records carry ``slice_id`` (the SAME discovery the ``verify-commit-trailers``
    auditor performs). Returns ``None`` when no APPROVED verdict exists for the
    slice OR the ledger is unreadable (the degrade-LOUD caller warns) -- a hash
    is NEVER fabricated.
    """
    if feature_id is not None:
        candidates = [feature_id]
    else:
        ledger_dir = repo / ".nwave" / "telemetry" / "atdd-pure"
        candidates = (
            sorted(path.stem for path in ledger_dir.glob("*.jsonl"))
            if ledger_dir.is_dir()
            else []
        )

    for candidate in candidates:
        ledger = AtCompletionLedger(feature_id=candidate, project_root=repo)
        try:
            records = ledger.read_records(
                slice_id=slice_id, event_type=_AT_REVIEW_VERDICT_EVENT
            )
        except LedgerIntegrityViolation:
            # A corrupt ledger is surfaced as "no verdict found" (the caller
            # warns LOUD); the M7 fail-closed read already refused to undercount.
            continue
        approved = [r for r in records if r.get("verdict") == _VERDICT_APPROVED]
        if not approved:
            continue
        latest = max(approved, key=lambda r: int(r.get("seq", 0)))
        record_hash = latest.get("record_hash")
        if record_hash:
            return str(record_hash)
    return None


def _ensure_reviewed_by(
    repo: Path, message: str, slice_ids: list[str], feature_id: str | None
) -> str:
    """Mechanically stamp the ``Reviewed-by:`` trailer from the AT-review ledger.

    Closes the recurring records-of-truth omission (class-#56): the
    ``Reviewed-by:`` trailer was historically hand-typed into ``--message`` by the
    crafter, so when the agent forgot it the trailer was SILENTLY omitted (no
    error, ``verified:true``) -- the SAME discipline-gap class ``commit-slice``
    already mechanized away for ``Gate-Scope:`` and ``Slice-Id:``. This looks the
    verdict up from the ledger and stamps it, so the trailer no longer depends on
    the agent remembering.

    Idempotent: a ``--message`` already carrying a ``Reviewed-by:`` trailer is
    preserved verbatim (no duplicate, no override of an operator hand-stamp).

    Degrade-LOUD (no-silent-pass): a slice with NO recorded APPROVED verdict
    emits a what/why/how WARNING on stderr and the trailer is omitted for that
    slice -- never a silent omission, never a fabricated hash. The trailer
    requirement itself is NOT weakened: ``verify-commit-trailers`` (exit 45) and
    the carpaccio/readiness gate remain the enforcing authority on presence.
    """
    if _REVIEWED_BY_LINE_RE.search(message):
        return message

    trailers: list[str] = []
    for slice_id in slice_ids:
        record_hash = _review_verdict_hash(repo, slice_id, feature_id)
        if record_hash is None:
            sys.stderr.write(
                f"WARNING: des commit-slice found NO APPROVED ATReviewVerdict "
                f"record for {slice_id} -- the Reviewed-by: trailer is OMITTED "
                f"for this slice (records-of-truth omission, not a silent pass). "
                f"WHY: no `des record-at-review-verdict ... --verdict APPROVED` "
                f"record is keyed to this slice in "
                f".nwave/telemetry/atdd-pure/ (the AT-review was never recorded, "
                f"or the ledger is unreadable). HOW: after the acceptance-designer "
                f"reviewer APPROVES, run `des record-at-review-verdict "
                f"--feature-id <feature> --slice-id {slice_id} --verdict APPROVED "
                f"--reviewer-agent-id <id>`, then re-run des commit-slice.\n"
            )
            continue
        trailers.append(f"Reviewed-by: {record_hash} ({_VERDICT_APPROVED})")

    if not trailers:
        return message
    return f"{message.rstrip()}\n\n" + "\n".join(trailers)


def main(argv: list[str] | None = None) -> int:
    """Produce a correct-by-construction slice commit (stage->commit->amend->verify)."""
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

    if not args.message.strip():
        _emit({"event": "MalformedInput", "error": "--message must be non-empty"})
        return 2
    if extract_gate_scope(args.message) is not None:
        _emit(
            {
                "event": "MalformedInput",
                "error": "--message must NOT contain a Gate-Scope: trailer -- it "
                "is appended mechanically",
            }
        )
        return 2

    # Resolve the Slice-Id trailer mechanically (the SAME discipline the
    # Gate-Scope amend already closes). The message must end carrying a Slice-Id:
    # trailer; it arrives via --slice-id or is already inlined. Refuse up-front
    # when NEITHER is present -- no Slice-Id-less commit is ever produced.
    if not extract_slice_ids(args.message):
        if args.slice_id is None:
            _emit(
                {
                    "event": "MalformedInput",
                    "error": "missing Slice-Id: pass --slice-id or include a "
                    "Slice-Id: trailer",
                }
            )
            return 2
        # Idempotent stamp: append only when the message carries no Slice-Id (the
        # presence check above already excluded a message-carried one).
        message = f"{args.message.rstrip()}\n\nSlice-Id: {args.slice_id}"
    else:
        # The message already carries a Slice-Id -- preserve it verbatim, no
        # duplicate stamp even if --slice-id was also passed.
        message = args.message

    # Mechanically stamp the Reviewed-by: trailer from the AT-review ledger (the
    # SAME discipline the Gate-Scope + Slice-Id stamps already close). When the
    # operator already hand-stamped it the message is preserved verbatim; when a
    # slice has no recorded APPROVED verdict the omission is WARNED LOUD on stderr
    # (never silent), never fabricated.
    message = _ensure_reviewed_by(
        repo, message, extract_slice_ids(message), args.feature_id
    )

    try:
        malformed = _stage(repo, args.paths, args.all)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "MalformedInput", "error": f"git staging failed: {exc}"})
        return 2
    if malformed is not None:
        _emit(malformed)
        return 2

    # Step 2: commit with the placeholder trailer. HEAD now carries the slice.
    try:
        _commit_with_placeholder(repo, message, args.no_verify_commit)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "CommitFailed", "error": f"git commit failed: {exc}"})
        return 2

    # Step 3: the committed-scope digest of the RESULTING HEAD. This now
    # includes the slice's previously-untracked AT files -- the whole point.
    # git absent / not a work-tree emits the LOUD INDETERMINATE event (exit 2
    # propagated as 1 -- the commit landed but is un-verifiable).
    digest_result = _committed_scope_digest_value(repo, "HEAD")
    if not isinstance(digest_result, _CommittedScopeDigest):
        # The committed-scope machinery already emitted its LOUD event. The
        # commit LANDED at step 2 carrying its Slice-Id trailer, but the digest
        # could not be pinned (a non-Python target with no resolvable pytest
        # interpreter). DDD-6: instead of returning record-less -- which wedges
        # the successor slice ("predecessor has no honest record") -- route the
        # degrade to MINT the honest SliceCommitIndeterminate record (the SAME
        # SSOT mint `des verify-slice-commit`'s E2 degrade uses). The in-order
        # gate accepts an INDETERMINATE predecessor, so the chain progresses; a
        # fabricated SliceCommitVerified is NEVER written (the honesty invariant).
        if args.feature_id is not None:
            slice_ids = extract_slice_ids(message)
            _append_slice_commit_indeterminate(
                repo,
                args.feature_id,
                slice_ids,
                reason=_DEGRADE_REASON_INTERPRETER_UNAVAILABLE,
            )
            _emit(
                {
                    "event": "SliceCommitIndeterminate",
                    "commit": _git(repo, "rev-parse", "HEAD").strip(),
                    "feature_id": args.feature_id,
                    "slice_ids": slice_ids,
                    "reason": _DEGRADE_REASON_INTERPRETER_UNAVAILABLE,
                    "error": "the committed-scope digest could not be established "
                    "on this machine (no resolvable interpreter) -- recorded an "
                    "honest SliceCommitIndeterminate (unverified here), never a "
                    "fabricated pass",
                }
            )
        return 1
    digest = digest_result.digest

    # Step 4: amend the message-only trailer to the committed-scope digest.
    try:
        _amend_trailer(repo, digest)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "CommitFailed", "error": f"git amend failed: {exc}"})
        return 2

    head = _git(repo, "rev-parse", "HEAD").strip()

    # Step 5: the acceptance proof -- verify clean with NO human amend.
    if not args.skip_verify:
        verify_code = _verify(repo)
        if verify_code != 0:
            _emit(
                {
                    "event": "SliceCommitUnverified",
                    "commit": head,
                    "gate_scope_digest": digest,
                    "error": "the committed-scope digest did not verify after "
                    "amend -- run_contract_gate --verify-gate-scope refused HEAD",
                }
            )
            return 1

    _emit(
        {
            "event": "SliceCommitted",
            "commit": head,
            "gate_scope_digest": digest,
            "verified": not args.skip_verify,
        }
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
