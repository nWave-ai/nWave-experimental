"""Shared reverify/attest core -- the precondition/gate/record machinery.

`F-ATTEST-BUNDLED-SLICE` slice-01. This module is the SINGLE shared core
extracted VERBATIM from ``des.cli.reverify_slice_commit`` so that BOTH the
existing ``des reverify-slice-commit`` CLI AND the new ``des
attest-bundled-slice`` CLI import the very same precondition (P1-P6), gate
composition (E1+E2), and ledger-record helpers -- no parallel attestation
path (the `F-DES-LEDGER-BYPASS-GATE` failure class).

The extraction is BEHAVIOUR-PRESERVING: ``reverify_slice_commit`` re-imports
every symbol below and binds them at module scope, so its public helper
surface is byte-identical in behaviour and OBJECT-IDENTICAL to this core
(``reverify_slice_commit._compose_gates is _reverify_core._compose_gates``).

stdlib-only at import time (no ``import yaml``) per the DES-bundle contract,
mirroring the two gate CLIs it composes. Single-line JSON events to stdout
follow the gate CLIs' ``_emit`` convention.

Reference: docs/feature/f-attest-bundled-slice/feature-delta.md sec.3 (reuse
mandate) + ADR-ABS-001 sec.4.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.adapters.driven.runner.pytest_runner import run_timeout_seconds
from des.adapters.drivers.hooks.carpaccio_intercept import (
    _predecessor_slice,
    _slice_number,
)
from des.cli.verify_slice_commit_completeness import (
    _SLICE_ID_TRAILER_RE,
    files_in_commit,
)
from des.runtime.interpreter import des_spawn


if TYPE_CHECKING:
    from pathlib import Path


# A slice-id is `slice-` followed by one or more decimal digits.
_SLICE_ID_RE = re.compile(
    r"^slice-\d+(?:[a-z])?$"
)  # canonical + letter-suffix (friction #10)

# The feature-scoped E1 gate module ``_compose_gates`` invokes. Named as a
# module constant so the feature-scoped-E1 marker (the W5-collision arch-test
# self-coverage) resolves through the SSOT both CLIs share.
_FEATURE_SCOPED_E1_GATE = "des.cli.check_slice_at_completeness"


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object."""
    print(json.dumps(payload))


def _malformed_input(repo: Path, slice_id: str, commit: str) -> dict[str, str] | None:
    """Return a MalformedInput payload for bad inputs, else None.

    Three malformed-input conditions are checked, in order:
      1. ``slice_id`` does not match the ``slice-NN`` shape.
      2. ``repo`` is not a readable git repository.
      3. ``commit`` cannot be resolved inside ``repo``.
    """
    if not _SLICE_ID_RE.match(slice_id):
        return {
            "event": "MalformedInput",
            "error": f"--slice-id {slice_id!r} does not match slice-NN",
        }
    try:
        _git(repo, "rev-parse", "--is-inside-work-tree")
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        NotADirectoryError,
    ) as exc:
        return {
            "event": "MalformedInput",
            "error": f"--repo {str(repo)!r} is not a readable git repository: {exc}",
        }
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {
            "event": "MalformedInput",
            "error": f"--commit {commit!r} cannot be resolved in the repository: {exc}",
        }
    return None


def _refused(error: str) -> dict[str, str]:
    """Build a `SliceReverifyRefused` payload (a fail-closed precondition refusal)."""
    return {"event": "SliceReverifyRefused", "error": error}


def _trailer_slice_ids_case_insensitive(commit_message: str) -> list[str]:
    """Case-insensitive companion to ``extract_slice_ids``, scoped to P2 only.

    ``extract_slice_ids`` (the shared domain SSOT, consumed by 7+ other
    gates -- see ``des.domain.slice_id_trailer``) requires the trailer VALUE
    to already be lowercase ``slice-NN`` form; a commit carrying
    ``Slice-Id: Slice-02`` (mixed-case value) fails that regex entirely and
    ``extract_slice_ids`` reports an EMPTY set -- which P2 then prints
    verbatim, making a present-but-differently-cased trailer look absent
    (reverify-slice-commit-trailer-match-still-case-sensitive).

    Recompiles the SAME shared pattern text (``_SLICE_ID_TRAILER_RE.pattern``
    -- no duplicated regex literal, no drift risk) with ``re.IGNORECASE``,
    local to this module only, so the wider-consuming shared regex/gates are
    untouched. Matches follow are normalized to lowercase canonical form.
    """
    case_insensitive_re = re.compile(_SLICE_ID_TRAILER_RE.pattern, re.IGNORECASE)
    ordered: list[str] = []
    for line in commit_message.splitlines():
        match = case_insensitive_re.match(line.strip())
        if match:
            found = match.group(1).lower()
            if found not in ordered:
                ordered.append(found)
    return ordered


def _preconditions(
    repo: Path, feature_id: str, slice_id: str, commit: str
) -> dict[str, str] | None:
    """Run preconditions P1-P3, in order; return a refusal payload or None.

    P1 -- ancestor: ``commit`` must be an ancestor of HEAD.
    P2 -- trailer match: ``commit``'s `Slice-Id:`/`Step-Id:` trailer set must
          contain ``slice_id`` (set-membership, not whole-set equality).
    P3 -- not-already-verified: ``slice_id`` must not already carry a
          `SliceCommitVerified` ledger record. A corrupt ledger
          (`LedgerIntegrityViolation`) is surfaced structurally -- the run
          never proceeds onto an unreadable chain.
    P4 -- in-commit AT presence: ``commit`` must itself carry at least one
          `@slice-NN` `.feature` file for ``slice_id``. This closes the
          vacuous-E1-pass on a slice whose ATs were deleted from the tree
          after the commit -- E1 walks the working tree, so a removed AT
          would be silently skipped; P4 reads the commit tree directly.
    P5 -- orphan-state: ``commit`` must be a STRICT ancestor of HEAD, NOT
          equal to HEAD, with at least one commit between it and HEAD
          (``git rev-list <commit>..HEAD`` non-empty). This confines
          reverify to a genuinely-orphaned (buried) slice and closes the
          reverify-as-bypass-vector gap -- a still-HEAD slice is owned by
          the U2 G_COMMIT exit gate, not reverify, so the two own disjoint
          mechanically-enforced domains.

    P6 -- predecessor-verified: reverify of ``slice-N`` (N > 1) is refused
          when ``slice-(N-1)`` carries no `SliceCommitVerified` ledger
          record. ``slice-01`` passes vacuously (no predecessor). P6
          mirrors the U1 M8 carpaccio-order check -- immediate predecessor
          only, zero-padding-preserving -- and reuses the `verified_slices()`
          map already read for P3. Without P6 a reverify could mint an
          out-of-order `SliceCommitVerified` record, leaving a permanent
          M8-invisible hole in the carpaccio order.

    All six fail closed with `SliceReverifyRefused` (exit 1). A refusal
    appends nothing to the ledger -- preconditions run before any gate.
    """
    # P1 -- the commit must already live on the current branch's history.
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        return _refused(
            f"--commit {commit!r} is not an ancestor of HEAD; "
            "reverify is bounded to commits already on the branch's history"
        )

    # P2 -- the commit must bind to the slice via a Slice-Id:/Step-Id: trailer.
    # Case-insensitive: a mixed-case trailer VALUE (e.g. `Slice-Id: Slice-02`)
    # must be recognized, not silently dropped into an empty set (fix
    # reverify-slice-commit-trailer-match-still-case-sensitive).
    commit_message = _git(repo, "log", "-1", "--format=%B", commit)
    trailer_slices = _trailer_slice_ids_case_insensitive(commit_message)
    if slice_id not in trailer_slices:
        return _refused(
            f"--slice-id {slice_id!r} is not in the commit's trailer set "
            f"{trailer_slices!r}; reverify of a non-slice commit is refused"
        )

    # P3 -- an already-verified slice is an idempotent no-op refusal. The
    # verified-slices map read here is reused by P6 below (one ledger read).
    try:
        verified = AtCompletionLedger(feature_id, repo).verified_slices()
    except LedgerIntegrityViolation as exc:
        return {
            "event": "LedgerIntegrityViolation",
            "detail": exc.detail,
            "error": f"AT-completion ledger is corrupt ({exc.detail}): {exc}",
        }
    if slice_id in verified:
        return _refused(
            f"--slice-id {slice_id!r} is already verified "
            "(carries a SliceCommitVerified ledger record); "
            "a repeat reverify is an idempotent no-op"
        )

    # P4 -- the commit itself must carry at least one slice AT .feature file.
    at_refusal = _in_commit_at_presence(repo, slice_id, commit)
    if at_refusal is not None:
        return at_refusal

    # P5 -- the commit must be a genuinely-buried (orphaned) slice.
    orphan_refusal = _orphan_state(repo, commit)
    if orphan_refusal is not None:
        return orphan_refusal

    # P6 -- the immediate predecessor slice must already be verified.
    return _predecessor_verified(slice_id, verified)


def _predecessor_verified(
    slice_id: str, verified: frozenset[str]
) -> dict[str, str] | None:
    """P6: refuse `slice-N` (N > 1) whose `slice-(N-1)` is not yet verified.

    Mirrors the U1 M8 carpaccio-order check -- immediate predecessor only,
    zero-padding-preserving via ``_predecessor_slice``. ``slice-01`` is the
    base case and passes vacuously. ``verified`` is the `SliceCommitVerified`
    set already read for P3, so P6 adds no extra ledger read.
    """
    if _slice_number(slice_id) <= 1:
        return None
    predecessor = _predecessor_slice(slice_id)
    if predecessor in verified:
        return None
    return _refused(
        f"reverify of {slice_id!r} is refused: its predecessor "
        f"{predecessor!r} carries no SliceCommitVerified ledger record -- "
        "reverify cannot mint an out-of-order carpaccio slice"
    )


def _orphan_state(repo: Path, commit: str) -> dict[str, str] | None:
    """P5: refuse a commit that is not a strictly-buried ancestor of HEAD.

    The commit must be a STRICT ancestor of HEAD -- at least one commit
    must lie between it and HEAD (``git rev-list <commit>..HEAD`` non-empty).
    A commit equal to HEAD, or with zero commits burying it, is refused:
    a still-HEAD slice is owned by the U2 G_COMMIT exit gate, not reverify.
    """
    buried = _git(repo, "rev-list", f"{commit}..HEAD")
    if buried.strip():
        return None
    return _refused(
        f"--commit {commit!r} is not a buried slice -- zero commits lie "
        "between it and HEAD; a still-HEAD slice is owned by the U2 "
        "G_COMMIT exit gate, not reverify"
    )


def _path_in_commit_tree(repo: Path, commit: str, rel_path: str) -> bool:
    """True iff ``rel_path`` resolves to a blob in ``commit``'s tree.

    ``files_in_commit`` returns every path *touched* by the commit -- which
    includes paths the commit DELETES (`git show --name-only` lists deletions).
    A deleted path is touched-by but absent-from the commit's tree, so
    `git show {commit}:{path}` exits 128. `git cat-file -e` is the purpose-built
    existence probe: it exits 0 when the path resolves to a blob in the tree,
    non-zero (without raising) when it does not. An absent-from-commit path is
    a normal not-in-commit result, never an error.
    """
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{rel_path}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _in_commit_at_presence(
    repo: Path, slice_id: str, commit: str
) -> dict[str, str] | None:
    """P4: refuse a commit with no recoverable `@slice-NN` `.feature` AT.

    Reads the COMMIT TREE -- not the working tree -- so a slice whose `.feature`
    AT was deleted from the tree after the commit is still refused. A `.feature`
    file touched by ``commit`` belongs to the slice when its commit-tree content
    carries the `@slice_id` tag.

    When no in-commit AT matches, P4 falls through to
    ``_tracked_before_at_presence``: an AT committed in an EARLIER commit and
    unmodified by ``commit`` (the canonical carpaccio-split orphan) is still
    recoverable and still owned by the slice. Only when neither path finds an
    owned AT is the commit refused.

    A `.feature` path the commit only DELETES is touched-by but absent-from the
    commit tree -- it is skipped gracefully (not-in-commit), never raising.
    """
    slice_tag = re.compile(rf"@{re.escape(slice_id)}\b")
    for rel_path in sorted(files_in_commit(repo, commit)):
        if not rel_path.endswith(".feature"):
            continue
        if not _path_in_commit_tree(repo, commit, rel_path):
            continue
        content = _git(repo, "show", f"{commit}:{rel_path}")
        if slice_tag.search(content):
            return None
    if _tracked_before_at_presence(repo, slice_id, commit):
        return None
    return _refused(
        f"--commit {commit!r} carries no @{slice_id} .feature AT file; "
        f"reverify of {slice_id!r} is refused -- the slice's acceptance "
        "tests must live in the commit itself"
    )


def _tracked_before_at_presence(repo: Path, slice_id: str, commit: str) -> bool:
    """True iff a `@slice-NN .feature` AT is recoverable from ``commit~1``.

    The carpaccio-split-orphan fallback for P4. Accepts iff some `.feature`
    satisfies ALL THREE clauses:

      1. **Tracked-before existence** -- the path existed as a tracked blob in
         ``commit~1`` (candidates enumerated from ``commit~1``'s tree via
         `git ls-tree`, NOT from `files_in_commit` -- the orphan AT is, by
         definition, NOT touched by ``commit``).
      2. **Slice-tag present in pre-commit content** -- the ``commit~1`` blob
         carries the `@slice_id` tag (a `.feature` tracked-before for a
         *different* slice must not satisfy P4).
      3. **Unmodified by ``commit``** -- ``rel_path not in files_in_commit``.
         This makes the helper STRICTER than a naive `commit~1` probe: a commit
         that modified the `.feature` to drop the `@slice_id` tag still has the
         tag in ``commit~1``, so clauses 1+2 alone would accept it -- clause 3
         refuses it, because the tag-drop is a deliberate disownership signal.

    ``commit~1`` is resolved via `git rev-parse`; a commit with no parent (a
    root commit) has no tracked-before history, so the helper returns False.
    """
    try:
        parent = _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}~1")
    except subprocess.CalledProcessError:
        return False
    parent = parent.strip()
    if not parent:
        return False

    touched = files_in_commit(repo, commit)
    slice_tag = re.compile(rf"@{re.escape(slice_id)}\b")
    tree = _git(repo, "ls-tree", "-r", "--name-only", parent)
    for rel_path in sorted(line for line in tree.splitlines() if line):
        if not rel_path.endswith(".feature"):
            continue
        if rel_path in touched:
            continue
        content = _git(repo, "show", f"{parent}:{rel_path}")
        if slice_tag.search(content):
            return True
    return False


def _run_gate(repo: Path, *args: str) -> int:
    """Run a gate CLI as a subprocess; return its exit code.

    The gate is invoked as the *exact same* gate module the U2 exit gate
    invokes -- there is no stub, no reimplementation, no `--mock`
    path (invariant I-2 / feature-delta sec.6 no-fabrication).

    The interpreter is resolved through `python_for(None)` -- the canonical
    S1 runtime boundary -- never a raw `sys.executable` reference. The gate
    subprocess only needs *a* Python (the gates are `des.cli` modules already
    visible on the running interpreter), so `capability=None` applies.

    ``timeout=run_timeout_seconds()`` bounds the child (RCA Branch B item
    b.2, defense-in-depth): the child itself may route into an unbounded
    grandchild (e.g. a mis-routed cargo subprocess) -- this outer bound keeps
    a blocked reverify from hanging silently even if an inner bound is ever
    missing. Anchored on the same SSOT ceiling (``NWAVE_GATE_RUN_TIMEOUT``,
    default 45 min) the pytest run-facet and the arch-run subprocess use.
    """
    completed = des_spawn(
        None,
        *args,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=run_timeout_seconds(),
    )
    return completed.returncode


def _compose_gates(
    repo: Path,
    commit: str,
    feature_id: str,
    slice_id: str,
    *,
    at_kind: str | None = None,
) -> str | None:
    """Run gates E1 and E2 for real; return the failing gate name or None.

    E1 -- `check_slice_at_completeness` -- invoked feature-scoped via the thin
    SSOT wrapper shipped in slice-01 of fix-reverify-e1-via-scoped-wrapper.
    The wrapper requires ``--feature-id`` (DDD-2) so E1 walks ONLY the named
    feature's `.feature` files, closing the W5 cross-feature-collision defect
    (R4 of the decision table). The wrapper is pure-read (no ledger writes --
    arch-test enforced), matching the legacy `verify_slice_commit_completeness`
    no-mutate semantics this composition has always relied on.

    E2 -- `run_contract_gate` -- invoked in its default contract-gate mode (no
    `--verify-gate-scope`, no `--commit`): it runs the whole-tree contract
    suite against HEAD's working tree and asserts it passes green. This is the
    reverify-against-HEAD-suite relaxation that resolves R-3 -- a buried slice
    whose suite grew since the commit still reverifies green.

    Returns the name of the first gate that exits non-zero, or None when both
    gates pass.
    """
    e1_code = _run_gate(
        repo,
        _FEATURE_SCOPED_E1_GATE,
        "--repo",
        str(repo),
        "--commit",
        commit,
        "--slice-id",
        slice_id,
        "--feature-id",
        feature_id,
    )
    if e1_code != 0:
        return "check_slice_at_completeness"

    e2_args = ["des.cli.run_contract_gate", "--repo", str(repo)]
    if at_kind is not None:
        e2_args += ["--at-kind", at_kind]
    e2_code = _run_gate(repo, *e2_args)
    if e2_code != 0:
        return "run_contract_gate"

    return None


def _record_outcome(
    feature_id: str,
    repo: Path,
    slice_id: str,
    ledger_events: tuple[str, ...],
    payload: dict[str, object],
) -> None:
    """Append ``ledger_events`` for ``slice_id`` then emit ``payload``.

    The single ledger-mutation point shared by the gate-fail and success
    paths: both construct one `AtCompletionLedger`, append their genuine
    gate event(s) in order, then emit one terminal JSON event. Centralising
    it keeps the two recovery outcomes structurally identical.
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for event in ledger_events:
        ledger.append_gate_event(event=event, slice_id=slice_id)
    _emit(payload)
