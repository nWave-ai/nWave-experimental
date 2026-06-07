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
from des.cli.run_contract_gate import (
    _committed_scope_digest_value,
    _CommittedScopeDigest,
    extract_gate_scope,
)


# The placeholder digest stamped on the FIRST (pre-amend) commit. 64 zero-hex
# matches the ``Gate-Scope:`` trailer shape (``[0-9a-f]{64}``) so the commit is
# well-formed, yet is unmistakably a placeholder. It is replaced in step 4 by
# the real committed-scope digest of the resulting HEAD.
_PLACEHOLDER_DIGEST = "0" * 64

# Matches a ``Gate-Scope:`` trailer line (anchored, full-line) for replacement
# during the amend. Mirrors run_contract_gate._GATE_SCOPE_TRAILER_RE but is
# multiline-anchored for an in-place message rewrite.
_GATE_SCOPE_LINE_RE = re.compile(r"^Gate-Scope:.*$", re.MULTILINE)


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


def _amend_trailer(repo: Path, digest: str, no_verify: bool) -> None:
    """Amend HEAD's message, replacing the placeholder with the real digest.

    Reads HEAD's full message, substitutes the ``Gate-Scope:`` line with the
    committed-scope ``digest``, and amends. Because the digest is over the
    committed TREE (NOT the message), this message-only amend leaves the
    committed-scope digest STABLE -- the post-amend verify re-derives a
    byte-identical digest (the fixed point).
    """
    current = _git(repo, "log", "-1", "--format=%B", "HEAD")
    rewritten = _GATE_SCOPE_LINE_RE.sub(f"Gate-Scope: {digest}", current, count=1)
    args = ["commit", "--amend", "--file", "-"]
    if no_verify:
        args.append("--no-verify")
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
        _commit_with_placeholder(repo, args.message, args.no_verify_commit)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "CommitFailed", "error": f"git commit failed: {exc}"})
        return 2

    # Step 3: the committed-scope digest of the RESULTING HEAD. This now
    # includes the slice's previously-untracked AT files -- the whole point.
    # git absent / not a work-tree emits the LOUD INDETERMINATE event (exit 2
    # propagated as 1 -- the commit landed but is un-verifiable).
    digest_result = _committed_scope_digest_value(repo, "HEAD")
    if not isinstance(digest_result, _CommittedScopeDigest):
        # The committed-scope machinery already emitted its LOUD event.
        return 1
    digest = digest_result.digest

    # Step 4: amend the message-only trailer to the committed-scope digest.
    try:
        _amend_trailer(repo, digest, args.no_verify_commit)
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
