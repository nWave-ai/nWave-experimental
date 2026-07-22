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

THE PRINTED-REMEDIATION RULE (read this before writing any HOW here)
--------------------------------------------------------------------
Every refusal in this module states WHAT failed, WHY, and HOW to fix it. The
HOW is where a specific, recurring trap lives, so the rule is stated once,
here, and obeyed at every emission site:

  * A printed remediation MAY name a FLAG the operator must supply
    ("pass ``--feature-id``", "substitute ``<id>`` with the reviewer's agent
    id"). That is HONEST: the operator can see they are being asked for
    something, and knows they are the only one who can answer.

  * A printed COMMAND must be runnable **AS PRINTED**. If the tool knows the
    value, it INTERPOLATES it (shell-quoted). If it genuinely cannot know the
    value, it prints **no command at all** and says why.

  * **Never print a token that LOOKS like a value and is not one.**

A ``<placeholder>`` inside something shaped like a runnable command is not an
instruction -- it is a trap with instructions attached. Empirically (2026-07-13,
twice in one night): an examiner was handed a command carrying a placeholder,
substituted something plausible, aimed a gate at the WRONG repository, and
produced a verdict that had to be thrown away. Both times the tool already HELD
the value it was asking for -- the cost of assembling the invocation fell on the
operator for no reason (GDP-5: the cost belongs on the SYSTEM).

The three emission sites in this module that obey the rule, as worked examples:
  * ``_missing_feature_id_refusal`` -- resolves the id via ``active_feature_id``
    and emits the complete command; when it CANNOT resolve (zero or several
    ledgers) it emits NO ``command`` key and names the ambiguity instead.
  * ``_extraneous_staged_content_refusal`` -- interpolates the actual staged
    paths it already knows into a runnable ``git restore --staged`` command.
  * ``_ensure_reviewed_by`` -- interpolates the known ``feature_id``; its
    ``<id>`` is an honest flag-slot (a value only the operator holds), in prose.

COROLLARY -- SHELL-QUOTE EVERY USER VALUE INTERPOLATED INTO A PRINTED COMMAND.
A printed remediation that carries a user-supplied value (``--feature-id`` /
``--slice-id`` / ``--repo`` / a path) must ``shlex.quote`` it, ALWAYS. A value
is untrusted input: ``--feature-id "examine;whoami"`` or a value bearing a
newline would otherwise print a CHAINED or MULTI-LINE command in our own error
message -- command injection staged through our surface, and a corrupted
"copy-paste as printed" instruction (2026-07-14, found by an independent
examiner). Quoting is not cosmetic: it is the difference between a value that
stays one argument and a value that becomes a second command. This is
orthogonal to whether the value is MEANINGFUL (that ``examine;whoami`` names no
real feature is a SEPARATE gate concern, root #24, escalated) -- the surface
must be safe regardless. Every ``{feature_id}`` / ``{slice_id}`` / ``{repo}`` /
``{path}`` inside a backticked or ``command``-field string in this module goes
through ``shlex.quote``.

Exit codes:
    0 = a verified slice commit was produced.
    1 = the committed-scope digest could not be established (LOUD
        INDETERMINATE -- e.g. not a git work-tree) OR the post-amend verify
        refused the commit OR the slice was EXAMINED and FAILED
        (``ExamineVerdictRefused``) OR the pre-flight E1+E2 gate (ADR-DES-001,
        run against an unreferenced shadow commit BEFORE this commit lands)
        genuinely refused, in which case NO commit lands at all OR the
        post-commit fold-in (Step 6) diverged from the pre-flight verdict
        (a rare flake/race): the commit stays landed but ``verified`` is
        honestly ``false``.
    2 = malformed input (nothing staged, empty message, repo unreadable, or a
        subject violating gitlint's title rules -- ``SubjectViolatesGitlint``
        T1/T7) OR the entering slice fails the examine-verdict gate (missing /
        stale / INDETERMINATE -- ``ExamineVerdictMissing`` /
        ``ExamineVerdictStale`` / ``ExamineVerdictIndeterminate``) OR the
        pre-flight gate returned a malformed-input verdict (e.g. the
        ``--slice-id`` honesty guard).
    3 = the pre-flight gate degraded LOUD INDETERMINATE (propagated verbatim
        from ``_run_verify_checks`` -- no resolvable interpreter, or an
        unrunnable ``--regression-test-file``); no commit lands.

Reference: docs/feature/des-spine-control-plane-ssot (committed-scope trailer),
           #67 facet-4 / MEMORY control-plane SSOT (digest-timing facet).
"""

from __future__ import annotations

import argparse
import configparser
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.git.git_mutate import git_run
from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.git.git_subprocess import is_ancestor as _is_ancestor
from des.adapters.driven.git.git_subprocess import (
    is_merged_contribution as _is_merged_contribution,
)
from des.adapters.driven.git.git_subprocess import (
    resolve_default_base_ref as _resolve_default_base_ref,
)
from des.adapters.driven.logging.at_completion_ledger import (
    TELEMETRY_DIR_RELPATH,
    AtCompletionLedger,
    LedgerIntegrityViolation,
    active_feature_id,
)
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.blast_radius_measurement import (
    BlastRadiusInputRejected,
    BlastRadiusVerdict,
    measure_blast_radius,
)
from des.application.worktree_cleanup_service import WorktreeCleanupService
from des.cli._identity_args import meaningful_identity
from des.cli.carpaccio_format import GateError as _CarpaccioGateError
from des.cli.carpaccio_format import is_slice_coupled as _is_slice_coupled
from des.cli.carpaccio_format import (
    mark_slice_status_shipped as _mark_slice_status_shipped,
)
from des.cli.carpaccio_format import parse_slice_plan as _parse_slice_plan
from des.cli.record_examine_verdict import examine_ledger_path as _examine_ledger_path
from des.cli.run_contract_gate import (
    _committed_scope_digest_value,
    _CommittedScopeDigest,
    _DigestRouteDegrade,
    _DigestRouteResult,
    _maybe_route_digest_through_runner,
    build_tier_exit_verdict,
    extract_gate_scope,
)
from des.cli.verify_deliver_integrity import (
    _declared_slice_plan_slice_ids,
    _slice_commit_verified_slices,
)
from des.cli.verify_slice_commit_completeness import (
    _INDETERMINATE_NO_EXAMINE_RESCUE_HOW,
    _append_slice_commit_indeterminate,
)
from des.domain.blast_radius import BlastRadiusConfigRejected
from des.domain.examine_verdict_signing import charter_seal as _charter_seal
from des.domain.repo_path_resolver import feature_delta_path as _feature_delta_path
from des.domain.slice_id_trailer import extract_slice_ids


# ---------------------------------------------------------------------------
# Worktree-cleanup auto-trigger (parallel-work-cleans-up-after-merge-back
# slice-01, D-2/D-3, ADR-SWARM-002; Ale 2026-07-19 ratified scope: the
# auto-trigger ships INSIDE slice-01, not deferred to Open Question #1).
# PURELY ADDITIVE post-commit side-effect, mirroring `_notify_feature_end_
# unmissable`'s shape (best-effort-loud, never blocks/crashes an already-
# landed commit) -- NOT a refusal gate like `_examine_gate_armed`, since
# removing a worktree is a mechanical CONSEQUENCE of a commit succeeding,
# never a precondition for it.
# ---------------------------------------------------------------------------


def _is_main_worktree(repo: Path) -> bool:
    """True iff ``repo`` is its OWN repository's MAIN worktree.

    Derived from git's own ``--git-dir``/``--git-common-dir`` (equal only
    for the main worktree or a non-worktree repo; a LINKED worktree's
    ``--git-dir`` is a subdirectory of the common dir). Fail-closed to
    ``False`` on any git-state ambiguity -- disarming the sweep below is
    always the safe default.

    SAFETY (why this check exists at all): `des commit-slice --repo .` is
    routinely invoked FROM INSIDE an ephemeral worktree for every ordinary
    per-slice commit (see `nw-crafter-discipline-atdd-pure`). Without this
    check, an auto-sweep could see SIBLING parallel worktrees sharing the
    same `.git` and attempt to remove them from an unrelated commit inside
    a completely different worktree -- armed ONLY on the main worktree
    confines the sweep to the one place a "merge-back landed" is a
    meaningful, safe signal.
    """
    try:
        git_dir = _git(repo, "rev-parse", "--git-dir").strip()
        common_dir = _git(repo, "rev-parse", "--git-common-dir").strip()
    except subprocess.CalledProcessError:
        return False
    if not git_dir or not common_dir:
        return False
    return (repo / git_dir).resolve() == (repo / common_dir).resolve()


def _worktree_cleanup_armed(repo: Path) -> bool:
    """Whether the auto-cleanup sweep applies to this commit.

    Armed ONLY when ``repo`` is the repository's own MAIN worktree (never a
    linked worktree, see `_is_main_worktree`) AND at least one linked
    worktree is currently registered. Fail-open-to-no-op, never fail-open-
    to-mutate.
    """
    if not _is_main_worktree(repo):
        return False
    return bool(GitWorktreeAdapter().list_worktrees(repo))


def _run_worktree_cleanup_sweep(repo: Path) -> None:
    """Best-effort-loud (GDP-6): sweep for any registered LINKED worktree
    whose branch is now a CONFIRMED ancestor of the resolved target branch
    and remove it -- the worktree "disappears on its own" (the slice-01
    charter promise) without a separate manual
    `des verify-worktree-cleanup` call.

    NEVER raises, NEVER blocks/affects the exit code above: the commit has
    already landed by the time this runs. An unresolvable target branch
    (`resolve_default_base_ref` returns `None` -- this repo's own de-facto
    trunk is not always in its candidate list, DESIGN Open Question #2) is
    a silent no-op: NOT guessing a target branch is safer than a false
    removal. A git failure mid-sweep (e.g. `git worktree remove` refused)
    is caught and printed as a diagnostic, matching
    `_notify_feature_end_unmissable`'s own error-handling shape.
    """
    try:
        if not _worktree_cleanup_armed(repo):
            return
        target_branch = _resolve_default_base_ref(repo)
        if target_branch is None:
            return
        service = WorktreeCleanupService(
            git_worktree=GitWorktreeAdapter(), merge_check=_is_merged_contribution
        )
        service.sweep(repo=repo, target_branch=target_branch, check_only=False)
    except Exception as exc:
        print(
            "WARNING: des commit-slice could not run the worktree-cleanup "
            f"auto-sweep for {repo}: {exc}"
        )


# The honest free-text degrade reason the committed-scope-digest step records
# when no pytest interpreter resolves on this machine (a non-Python target). The
# first value the carpaccio-honest AT pins; degrade-LOUD keeps the taxonomy open.
_DEGRADE_REASON_INTERPRETER_UNAVAILABLE = "gate_scope_interpreter_unavailable"

# The honest free-text degrade reason recorded when the resolved NON-pytest
# runner (e.g. cargo-test) cannot produce a trustworthy enumerate -- the
# runner-agnostic sibling of `_DEGRADE_REASON_INTERPRETER_UNAVAILABLE` (F-gate-
# scope-digest-runner-agnostic slice-01). Distinguishes "no runner resolved a
# scope at all" from "a runner resolved but its own enumerate degraded LOUD".
_DEGRADE_REASON_RUNNER_UNAVAILABLE = "gate_scope_runner_unavailable"


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


# ---------------------------------------------------------------------------
# Slice-Plan Status column sync (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED,
# GDP-1/4/6): `des commit-slice` already APPENDS a `SliceCommitVerified`
# ledger record on success but never wrote back to the feature-delta.md
# `[REF] Slice Plan` markdown table -- so a genuinely-shipped slice could
# sit on disk with a stale `pending` row indefinitely, and every consumer
# that reads the table (an orchestrator, `des next`, a human, another
# instance) inherited the lie. PURELY ADDITIVE: runs strictly AFTER the
# fold-in above has genuinely written the ledger record; never affects the
# exit code. Best-effort-loud (GDP-6), mirrors `_notify_feature_end_
# unmissable`'s shape.
# ---------------------------------------------------------------------------


def _sync_slice_plan_status(repo: Path, feature_id: str, slice_ids: list[str]) -> None:
    """Best-effort-loud (GDP-6): flip each verified slice's Slice-Plan
    ``Status`` cell from ``pending`` to ``shipped`` in the feature's
    ``feature-delta.md``.

    PURELY ADDITIVE post-commit side effect: NEVER raises, NEVER blocks or
    affects the exit code -- the ``SliceCommitVerified`` record has already
    been written by the time this runs. A missing ``feature-delta.md``
    (e.g. a bugfix with no Slice Plan) is a silent no-op -- this sync is
    additive-only, never a second oracle the commit depends on. A malformed
    table, an absent row, or a row whose ``Status`` is already something
    other than the literal ``pending`` are ALL no-ops too
    (:func:`_mark_slice_status_shipped`'s own degrade-quiet contract) --
    this function's own ``try``/``except`` only guards against an
    unexpected exception (e.g. a permission error on write), never invents
    a diagnosis for an expected no-rewrite outcome.
    """
    try:
        delta_path = _feature_delta_path(repo, feature_id)
        if not delta_path.is_file():
            return
        original = delta_path.read_text(encoding="utf-8")
        text = original
        for slice_id in slice_ids:
            rewritten = _mark_slice_status_shipped(text, slice_id)
            if rewritten is not None:
                text = rewritten
        if text != original:
            delta_path.write_text(text, encoding="utf-8")
    except Exception as exc:
        print(
            "WARNING: des commit-slice could not sync the Slice-Plan Status "
            f"column for feature {feature_id!r}: {exc}"
        )


# ---------------------------------------------------------------------------
# Feature-end finalize unmissable (deliver-finalize-unmissable slice-01,
# FIX-A, GDP-1/4/5/6): "done" is a CLAIM decoupled from the mechanical
# `FeatureEnd` attestation -- a per-slice commit-slice succeeds individually
# and creates a done-illusion. PURELY ADDITIVE: after a successful slice
# commit, if every declared Slice-Plan row for the feature is now shipped
# (this was the LAST slice), append a durable `FeatureEndPending` ledger
# marker + emit a LOUD self-explaining stdout notice naming
# `des feature-end run` as the HOW. Idempotent (at most once per feature);
# degrades LOUD without ever crashing or blocking the commit.
# ---------------------------------------------------------------------------
_FEATURE_END_PENDING_EVENT = "FeatureEndPending"
_FEATURE_END_RUN_HOW = "des feature-end run"


def _last_declared_slice_shipped(repo: Path, feature_id: str) -> bool:
    """True iff every declared Slice-Plan row for ``feature_id`` has shipped.

    Reuses the declared-slices / shipped-slices readers from
    ``verify_deliver_integrity.py`` (the Reuse Analysis) -- never re-parses
    the feature-delta. An absent/unreadable Slice Plan yields an empty
    declared list, so this returns False (the finalize notice never fires on
    an unreadable plan).
    """
    declared = _declared_slice_plan_slice_ids(repo, feature_id)
    if not declared:
        return False
    shipped = _slice_commit_verified_slices(repo, feature_id)
    return all(slice_id in shipped for slice_id in declared)


def _feature_end_pending_exists(repo: Path, feature_id: str) -> bool:
    """True iff a `FeatureEndPending` ledger record already exists (idempotent)."""
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
    records = ledger.read_records(event_type=_FEATURE_END_PENDING_EVENT)
    return any(record.get("event") == _FEATURE_END_PENDING_EVENT for record in records)


def _notify_feature_end_unmissable(repo: Path, feature_id: str) -> None:
    """Append the `FeatureEndPending` marker + LOUD notice when the last slice ships.

    Best-effort-loud (GDP-6): NEVER raises. Any failure (unreadable Slice
    Plan, ledger append error) is caught and printed as a diagnostic -- the
    commit already succeeded and must never be blocked or crashed by this
    step.
    """
    try:
        if not _last_declared_slice_shipped(repo, feature_id):
            return
        if _feature_end_pending_exists(repo, feature_id):
            return
        ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
        ledger.append_gate_event(_FEATURE_END_PENDING_EVENT, "", feature_id=feature_id)
        print(
            f"WHAT: every declared Slice-Plan slice for feature {feature_id!r} "
            "has shipped -- the feature is NOT done yet.\n"
            "WHY: a feature is done only when a FeatureEnd record attests it "
            "(full-suite + gates + deep-review).\n"
            f"HOW: run: {_FEATURE_END_RUN_HOW} --repo . --feature-id "
            f"{shlex.quote(feature_id)} --feature-dir "
            f"{shlex.quote(f'docs/feature/{feature_id}')} "
            "--reviewer-agent-id <id> --verdict APPROVED "
            "(substitute <id> with the agent id of the reviewer that "
            "performed or will perform the feature-end review; any "
            "stable, non-empty reviewer id identifies who reviewed it)"
        )
    except Exception as exc:
        print(
            "WARNING: des commit-slice could not evaluate/append the "
            f"feature-end-unmissable marker for feature {feature_id!r}: {exc}"
        )


# ---------------------------------------------------------------------------
# Subject-line gitlint self-validation (task #37 -- GDP-6 producing-tool
# self-validation gap): ``des commit-slice`` builds the commit subject but
# never checked it against the repo's own commit linter before committing,
# so a bad subject landed a commit CI's commitlint job then rejected. Read
# the SAME two title rules from ``.gitlint`` (T1 title-max-length, T7
# title-match-regex) and refuse EARLY -- before staging, before the
# (potentially slow) build-tier verify -- never emit a subject CI will
# reject.
# ---------------------------------------------------------------------------
_DEFAULT_TITLE_MAX_LENGTH = 100
_DEFAULT_TITLE_REGEX = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\(.+\))?: [a-zA-Z].*$"
)


def _load_gitlint_title_rules(repo: Path) -> tuple[int, re.Pattern[str]]:
    """The subject-line max-length + regex, read from ``.gitlint`` if present.

    Falls back to nWave's own defaults (100 chars, the conventional-commit
    regex -- the SAME values the repo's ``.gitlint`` currently pins) when the
    file is absent or a section/key/regex is malformed, so this degrades
    LOUD-but-usable on a target machine that carries no ``.gitlint`` -- never
    a hard crash, and never silently permissive (the default IS the rule).
    """
    max_length = _DEFAULT_TITLE_MAX_LENGTH
    pattern = _DEFAULT_TITLE_REGEX
    gitlint_path = repo / ".gitlint"
    if not gitlint_path.is_file():
        return max_length, pattern

    config = configparser.ConfigParser()
    try:
        config.read(gitlint_path, encoding="utf-8")
    except configparser.Error:
        return max_length, pattern

    if config.has_option("title-max-length", "line-length"):
        try:
            max_length = config.getint("title-max-length", "line-length")
        except ValueError:
            pass

    if config.has_option("title-match-regex", "regex"):
        try:
            pattern = re.compile(config.get("title-match-regex", "regex"))
        except re.error:
            pass

    return max_length, pattern


def _gitlint_subject_violation(repo: Path, message: str) -> dict[str, object] | None:
    """The gitlint subject-line violation for ``message``'s first line, or None.

    Mirrors the SAME two rules CI's commitlint job enforces via ``.gitlint``
    (T1 title-max-length, T7 title-match-regex), reading the LIVE limits/
    regex from the repo's own ``.gitlint`` so the check never drifts from
    what CI actually runs. Checked BEFORE staging and BEFORE the build-tier
    verify -- the refusal is fast, never waits on the slow tier.
    """
    stripped = message.strip()
    subject = stripped.splitlines()[0] if stripped else ""
    max_length, pattern = _load_gitlint_title_rules(repo)

    if len(subject) > max_length:
        return {
            "event": "SubjectViolatesGitlint",
            "exit_code": 2,
            "rule": "T1",
            "what": f"the commit subject is {len(subject)} chars, exceeding "
            f"the gitlint title-max-length of {max_length}",
            "why": "CI's commitlint job runs the SAME .gitlint rule (T1) and "
            "would reject this subject after the commit lands.",
            "how": f"shorten the subject to <= {max_length} chars (gitlint T1).",
        }

    if not pattern.match(subject):
        return {
            "event": "SubjectViolatesGitlint",
            "exit_code": 2,
            "rule": "T7",
            "what": f"the commit subject {subject!r} does not match the "
            "conventional-commit title format",
            "why": "CI's commitlint job runs the SAME .gitlint rule (T7 "
            "title-match-regex), which requires the character right after "
            "'type(scope): ' to be a letter.",
            "how": "start the description with a letter, e.g. "
            "'fix(scope): four configuration values were wrong' instead of "
            "'fix(scope): 4 configuration values were wrong' (gitlint T7).",
        }

    return None


# ---------------------------------------------------------------------------
# Remote-ancestry guard (fix-commit-slice-never-amends-pushed, GDP-6): before
# staging/committing anything, ensure local HEAD has never REGRESSED behind an
# already-PUSHED remote-tracking ref. Incident (2026-07-11 ~16:00): an external
# git surface (`git reset --soft HEAD^`, folding in a forgotten charter file)
# regressed local HEAD one commit behind the pushed tip; `commit-slice`'s own
# stage->commit->amend flow then committed blindly on top of the regressed
# HEAD, producing a SIBLING of the pushed commit (same parent) instead of a
# descendant -- orphaning it. Local diverged from origin; the next push was
# rejected non-fast-forward, resolved only via --force-with-lease.
#
# Fix: resolve the upstream tracking ref (or the first `refs/remotes/*` ref
# when no upstream is configured, degrade-honest to "no remote" when neither
# exists -- the byte-identical no-remote guard's precondition). If that ref is
# already an ancestor of local HEAD, nothing changed -- no-op. If local HEAD is
# a strict ancestor of the remote ref (a pure regression, fast-forwardable, no
# unique local commits), re-anchor the branch pointer to the remote tip via
# `git reset --soft` -- soft reset never touches the index/working tree, so
# whatever content is staged/kept from the regression becomes a diff against
# the PUSHED tip, and the next commit lands as its genuine CHILD instead of a
# diverging sibling. Only a GENUINE divergence (neither side is an ancestor of
# the other -- both carry unique commits) cannot be auto-healed without
# silently discarding history; that case refuses LOUD instead.
# ---------------------------------------------------------------------------


def _remote_tracking_ref(repo: Path) -> str | None:
    """The current branch's remote-tracking ref, or None if no remote exists.

    Tries the configured upstream (``@{u}``, set by ``git push -u`` or
    ``git branch --set-upstream-to``) first. Falls back to the first
    ``refs/remotes/*`` ref (excluding a bare ``.../HEAD`` symref) when no
    upstream is configured but at least one remote is -- the design doc's
    "or fall back to scanning refs/remotes/*" degrade-honest path. Returns
    None when no remote is configured at all, the precondition every
    pre-existing (no-remote) commit-slice caller relies on to stay unaffected.
    """
    try:
        ref = _git(
            repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
        ).strip()
        if ref:
            return ref
    except subprocess.CalledProcessError:
        pass
    try:
        refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/")
    except subprocess.CalledProcessError:
        return None
    for line in refs.splitlines():
        candidate = line.strip()
        if candidate and not candidate.endswith("/HEAD"):
            return candidate
    return None


def _guard_head_not_behind_remote(repo: Path) -> dict[str, object] | None:
    """Refuse (or auto-heal) local HEAD having regressed behind a pushed remote.

    Returns None (no-op / auto-healed) in every case that must stay
    byte-identical to pre-fix behavior: no remote configured, an unborn/no-
    commit repo, or the remote ref already an ancestor of local HEAD (the
    common, up-to-date case). A pure regression (local HEAD is a strict
    ancestor of the remote ref -- fast-forwardable, no unique local commits)
    is auto-healed via ``git reset --soft`` to the remote tip and returns
    None. Returns a refusal payload (popped ``exit_code`` by the caller) only
    on GENUINE divergence, where auto-healing would silently discard one
    side's unique history.
    """
    remote_ref = _remote_tracking_ref(repo)
    if remote_ref is None:
        return None

    try:
        remote_sha = _git(repo, "rev-parse", remote_ref).strip()
        head_sha = _git(repo, "rev-parse", "HEAD").strip()
    except subprocess.CalledProcessError:
        # Unborn HEAD or an unresolved remote ref -- degrade-honest no-op;
        # the pre-existing downstream flow already handles those cases.
        return None

    if remote_sha == head_sha or _is_ancestor(repo, remote_sha, head_sha):
        return None  # local already contains everything pushed -- unaffected

    if _is_ancestor(repo, head_sha, remote_sha):
        # Pure regression: re-anchor the branch pointer to the pushed tip.
        # `--soft` never touches the index/working tree, so any content
        # staged/kept across the regression becomes a diff against the
        # PUSHED tip instead of the regressed base.
        git_run(repo, "reset", "--soft", remote_sha)
        return None

    return {
        "event": "HeadDivergedFromRemoteRefused",
        "exit_code": 1,
        "what": f"local HEAD ({head_sha}) and {remote_ref} ({remote_sha}) have "
        "diverged -- neither is an ancestor of the other",
        "why": "committing here would build a NEW commit that is a sibling of "
        f"content already pushed to {remote_ref}, permanently orphaning it "
        "unless a force-push later rewrites the remote history (the "
        "2026-07-11 incident class).",
        "how": f"reconcile manually first (e.g. `git merge {remote_ref}` or "
        f"`git rebase {remote_ref}`), then re-run des commit-slice.",
    }


# ---------------------------------------------------------------------------
# Examine-verdict commit-time gate (evolution-plan P1.2 -- User-Examiner wiring)
# ---------------------------------------------------------------------------
#
# Replaces the per-slice code-reading C_REVIEWER_AUDIT with EXECUTION-
# OBSERVATION: a slice may not commit unless a human-intent charter was walked
# through the REAL surface by nw-user-examiner ("Vera") and a PASS verdict was
# recorded (des record-examine-verdict) whose charter_seal still matches the
# CURRENT charter bytes. ADD-not-mutate (same discipline the build-tier check
# above already established): this is an ADDITIONAL check at the SAME
# chokepoint, before the placeholder commit lands.
#
# ARMING (backward-compat escape): the gate is a no-op unless it is ARMED for
# this commit, so the entire pre-existing commit-slice test suite (no
# charters, no opt-in) stays green. Armed when EITHER:
#   (a) the operator opts in via NWAVE_EXAMINE_GATE_OPT_IN=1, OR
#   (b) a charter exists for the feature under
#       docs/product/expectations/{feature_id}/*.md (i.e. the feature has
#       ADOPTED the User-Examiner charter convention).
# Absent both AND a --feature-id, the gate cannot even resolve which ledger to
# read, so it is a no-op there too -- a caller that never passes --feature-id
# (as several pre-existing call sites do not) is completely unaffected.
_EXAMINE_GATE_ENV = "NWAVE_EXAMINE_GATE_OPT_IN"

_EXAMINE_VERDICT_EVENT = "ExamineVerdictRecorded"

# The distinct DEFER outcome (RCA constraint c): a `@coupled` slice's examine
# is DEFERRED to feature-end, never silently dropped. Discriminated from a
# refusal payload by the ABSENCE of an `exit_code` key -- every refusal this
# module emits carries one; a DEFER payload never does (see
# `check_examine_verdict`'s docstring).
_EXAMINE_DEFERRED_EVENT = "ExamineDeferredToFeatureEnd"


def _slice_is_coupled(repo: Path, feature_id: str, slice_id: str) -> bool:
    """Whether ``slice_id``'s OWN Slice-Plan row (the SAME trusted
    feature-delta the carpaccio entry gate already reads) carries the
    ``@coupled`` annotation.

    Fail-CLOSED to ``False`` on ANY read failure -- an absent feature-delta,
    an absent row for this slice, or a malformed Slice-Plan table -- per RCA
    constraint (d): the deferral must never be granted except through this
    ONE trusted source, never a stray/informal claim of coupling elsewhere
    (e.g. a comment in an AT file).
    """
    delta_path = _feature_delta_path(repo, feature_id)
    if not delta_path.is_file():
        return False
    try:
        feature_delta_text = delta_path.read_text(encoding="utf-8")
        plan = _parse_slice_plan(feature_delta_text)
    except (OSError, UnicodeDecodeError, _CarpaccioGateError):
        return False
    return _is_slice_coupled(plan, slice_id)


def _examine_gate_armed(repo: Path, feature_id: str | None) -> bool:
    """Whether the examine-verdict commit gate applies to this commit.

    See the module-level "ARMING" note above for the two independent
    activation conditions. Fail-open-to-no-op (never fail-open-to-pass): an
    unarmed gate returns ``False`` and ``check_examine_verdict`` then returns
    ``None`` (cleared) unconditionally -- byte-identical to pre-P1.2 behavior.
    """
    if os.environ.get(_EXAMINE_GATE_ENV) == "1":
        return True
    if not feature_id:
        return False
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    return charter_dir.is_dir() and any(charter_dir.glob("*.md"))


def _latest_examine_verdict(
    repo: Path, feature_id: str, slice_id: str
) -> dict[str, object] | None:
    """The latest recorded ``ExamineVerdict`` record for ``slice_id``, or None."""
    ledger_path = _examine_ledger_path(repo, feature_id)
    if not ledger_path.is_file():
        return None
    latest: dict[str, object] | None = None
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") != _EXAMINE_VERDICT_EVENT:
            continue
        if record.get("slice_id") != slice_id:
            continue
        latest = record
    return latest


def _examine_remediation_command(
    repo: Path, feature_id: str, slice_id: str, charter_path: str | None = None
) -> str:
    """The examine remediation, with every knowable value INTERPOLATED.

    ``--repo`` used to print a bare ``<repo>`` slot even though this function
    is only ever reached from ``check_examine_verdict(repo, ...)``, which is
    holding the answer. That is the exact trap the printed-remediation rule
    at the top of this module bans -- and the exact one that bit: an examiner
    substituted a plausible ``.`` for ``<repo>``, aimed the gate at the wrong
    repository, and the verdict had to be thrown away.

    The remaining slots are HONEST FLAG-SLOTS, not traps: ``--verdict`` and
    ``--observations`` are the examiner's FINDINGS -- they do not exist yet
    when this remediation is printed, and no tool can invent them. So this is
    deliberately framed as prose naming the flags to supply, NOT as a
    copy-paste-runnable command: a command that cannot run as printed must not
    be dressed up as one. ``--charter`` is interpolated when the stale/missing
    -charter branches know the path, and named as a slot when it is genuinely
    unknown (the never-examined branch).
    """
    charter_arg = shlex.quote(charter_path) if charter_path else "<the slice's charter>"
    return (
        "dispatch nw-user-examiner with the slice's charter, then record its "
        "verdict with `des record-examine-verdict` -- supplying "
        f"--repo {shlex.quote(str(repo))} --feature-id {shlex.quote(feature_id)} "
        f"--slice {shlex.quote(slice_id)} --charter {charter_arg} "
        "--examiner nw-user-examiner, plus the --verdict and --observations "
        "the examiner actually produces (those are her findings; they cannot "
        "be pre-filled here)"
    )


def check_examine_verdict(
    repo: Path, feature_id: str, slice_id: str
) -> dict[str, object] | None:
    """Assert the entering ``slice_id`` has a fresh PASS examine-verdict.

    Returns ``None`` when the gate is not ARMED for this feature, OR clears
    with a fresh PASS verdict (charter_seal matches the charter's CURRENT
    bytes). Returns a refusal payload (carrying an ``exit_code`` key the
    caller pops before emitting) otherwise -- every refusal states WHAT
    failed, WHY, and HOW to fix it (never a bare event name).

    A THIRD outcome exists for a ``@coupled`` slice with no per-slice record
    (RCA fix-coupled-slice-examine-deferred-to-feature-end): a DEFER payload
    carrying event ``ExamineDeferredToFeatureEnd`` and deliberately NO
    ``exit_code`` key -- the discriminator every caller uses to tell "defer,
    proceed" apart from "refuse, exit_code pops cleanly". A ``@coupled`` slice
    has no independently-observable surface (its guarantee is only checkable
    through the ASSEMBLED feature), so demanding a per-slice PASS asks for
    evidence that cannot exist; feature-end's unconditional per-charter
    examine leg (``feature_end_cycle_service._run_feature_end_examine_leg``)
    covers it instead -- deferred, never dropped.

    Refusal taxonomy (fail-closed, never a silent pass):
      * ``ExamineVerdictMissing``       (exit 2) -- no record at all, and the
        slice is NOT ``@coupled`` (a ``@coupled`` slice defers instead, see
        above).
      * ``ExamineVerdictRefused``       (exit 1) -- recorded verdict is FAIL.
      * ``ExamineVerdictIndeterminate`` (exit 2) -- recorded verdict is
        INDETERMINATE (an unexaminable slice carries no observable value --
        it was not a slice; carpaccio-honesty enforcement).
      * ``ExamineVerdictStale``         (exit 2) -- recorded verdict is PASS
        but the charter no longer exists, OR its CURRENT bytes no longer
        match the recorded ``charter_seal`` (the charter changed after
        examination -- the PASS verdict is void).
    """
    if not _examine_gate_armed(repo, feature_id):
        return None

    record = _latest_examine_verdict(repo, feature_id, slice_id)
    if record is None:
        if _slice_is_coupled(repo, feature_id, slice_id):
            return {
                "event": _EXAMINE_DEFERRED_EVENT,
                "feature_id": feature_id,
                "slice_id": slice_id,
                "what": (
                    f"slice {slice_id} is @coupled -- its examine is "
                    "DEFERRED to feature-end"
                ),
                "why": (
                    "a @coupled Slice-Plan row has no independently-"
                    "observable surface (its guarantee is only checkable "
                    "through the ASSEMBLED feature); feature-end's "
                    "unconditional per-charter examine leg covers it "
                    "instead of a per-slice ExamineVerdict."
                ),
            }
        return {
            "event": "ExamineVerdictMissing",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"slice {slice_id} has no recorded examine-verdict",
            "why": (
                "the commit-time examine gate is ARMED for "
                f"{feature_id} (a charter exists, or the opt-in env is set) "
                "and requires a fresh PASS ExamineVerdict before the slice "
                "may commit -- execution-observation replaces the old "
                "code-reading review for this slice."
            ),
            "how": f"slice not examined: {_examine_remediation_command(repo, feature_id, slice_id)}",
        }

    verdict = record.get("verdict")

    if verdict == "FAIL":
        return {
            "event": "ExamineVerdictRefused",
            "exit_code": 1,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"slice {slice_id} was examined and FAILED",
            "why": str(record.get("observations", "")),
            "how": (
                "fix the slice per the examiner's observations, then "
                f"{_examine_remediation_command(repo, feature_id, slice_id)}"
            ),
        }

    if verdict == "INDETERMINATE":
        return {
            "event": "ExamineVerdictIndeterminate",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"slice {slice_id}'s recorded examine-verdict is INDETERMINATE",
            "why": (
                "an unexaminable slice carries no observable value -- it was "
                "not a slice (carpaccio-honesty enforcement); INDETERMINATE "
                "is never a silent pass."
            ),
            "how": (
                "re-decompose the slice so it exposes an observable surface, "
                f"then {_examine_remediation_command(repo, feature_id, slice_id)}"
            ),
        }

    if verdict != "PASS":
        return {
            "event": "ExamineVerdictStale",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"slice {slice_id}'s recorded verdict is unrecognised: {verdict!r}",
            "why": "only PASS / FAIL / INDETERMINATE are valid examine verdicts.",
            "how": f"re-record a valid verdict: {_examine_remediation_command(repo, feature_id, slice_id)}",
        }

    charter_path_raw = record.get("charter_path")
    recorded_seal = record.get("charter_seal")
    if not isinstance(charter_path_raw, str) or not isinstance(recorded_seal, str):
        return {
            "event": "ExamineVerdictStale",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"slice {slice_id}'s PASS record is malformed (missing charter_path/charter_seal)",
            "why": "a PASS verdict must carry both charter_path and charter_seal to be re-verified.",
            "how": f"re-record a fresh verdict: {_examine_remediation_command(repo, feature_id, slice_id)}",
        }

    charter_path = Path(charter_path_raw)
    if not charter_path.is_absolute():
        charter_path = repo / charter_path
    if not charter_path.is_file():
        return {
            "event": "ExamineVerdictStale",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"the examined charter no longer exists: {charter_path_raw}",
            "why": (
                "a PASS verdict is bound to the charter bytes at exam time; "
                "an absent charter cannot be re-verified -- stale, void."
            ),
            "how": (
                "restore the charter or re-examine against the current one: "
                f"{_examine_remediation_command(repo, feature_id, slice_id, charter_path_raw)}"
            ),
        }

    current_seal = _charter_seal(charter_path.read_bytes())
    if current_seal != recorded_seal:
        return {
            "event": "ExamineVerdictStale",
            "exit_code": 2,
            "feature_id": feature_id,
            "slice_id": slice_id,
            "what": f"the charter changed after examination: {charter_path_raw}",
            "why": (
                "the recorded charter_seal no longer matches the charter's "
                "CURRENT bytes -- the PASS verdict is void (stale-seal, "
                "never a silent pass)."
            ),
            "how": (
                "re-examine against the CURRENT charter and record a fresh "
                f"PASS verdict: {_examine_remediation_command(repo, feature_id, slice_id, charter_path_raw)}"
            ),
        }
    return None


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
        "--repo",
        required=True,
        type=meaningful_identity,
        help="Path to the git repository / project root.",
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
        type=meaningful_identity,
        help="The carpaccio slice identity (slice-NN). Stamped mechanically as a "
        "Slice-Id: trailer (idempotent -- skipped if the message already carries "
        "one). Required unless the --message already carries a Slice-Id: trailer.",
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        type=meaningful_identity,
        help="The feature the slice commit belongs to (kebab-case). REQUIRED: it "
        "is the scope every downstream gate (E1 completeness, E2 contract, E3 "
        "examine, the SliceCommitVerified record) binds itself to. An empty or "
        "whitespace-only value is treated as ABSENT and REFUSED -- a gate that "
        "an argument can switch off is not a gate.",
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
        "--at-kind",
        dest="at_kind",
        default="gherkin",
        choices=("gherkin", "pytest-regression", "native-regression"),
        help=(
            "The acceptance-test kind the slice's E2 leg attests (default: "
            "gherkin, byte-identical for every existing caller). Forwarded "
            "into the Step-6 verify_slice_commit_completeness fold-in so a "
            "real pytest-regression commit runs the BEHAVIORAL (not gherkin/ "
            "feature-scoped-contract) E2 path -- see "
            "verify_slice_commit_completeness.py for the attestation itself. "
            "'native-regression' (fix-rust-regression-at-kind-wiring) routes "
            "the Step-3 digest through the runner seam keyed on --regression-"
            "test-file's OWN suffix, agreeing with E2's execution routing."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        dest="regression_test_file",
        default=None,
        help=(
            "Repo-relative path to the pytest regression file E2 runs "
            "behaviorally (paired with --at-kind pytest-regression); "
            "forwarded into the Step-6 fold-in."
        ),
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-amend run_contract_gate --verify-gate-scope check "
        "(produce + amend only). The verify is the acceptance proof; skipping it "
        "is for callers that verify separately.",
    )
    parser.add_argument(
        "--tier",
        default=None,
        choices=("S", "M", "L"),
        help=(
            "Declared blast-radius tier ceiling for the declared --path scope "
            "(or the resolved --all staged set). When the MEASURED blast "
            "radius (the SAME measure_blast_radius orchestration "
            "`des blast-radius` uses) exceeds the declared tier, the commit "
            "is REFUSED before anything lands (BlastRadiusTierExceeded). "
            "Omitted (default): no cap is applied, byte-identical to today."
        ),
    )
    return parser


def _charter_dir_to_stage(repo: Path, feature_id: str | None) -> list[str]:
    """Repo-relative ``docs/product/expectations/{feature_id}/`` if present.

    Feature-scoped only -- never the whole expectations tree. Absent (no
    ``feature_id``, or the dir does not exist on disk) yields ``[]``, no error
    (backward-compat: an @infrastructure slice with no charter never blocks).
    """
    if feature_id is None:
        return []
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    if not charter_dir.is_dir():
        return []
    return [str(charter_dir.relative_to(repo))]


# ---------------------------------------------------------------------------
# Extraneous-staged-content guard (fix-commit-slice-index-isolation, GDP-3/6):
# `commit-slice` stages the DECLARED scope (`_stage` below) but
# `_commit_with_placeholder` then commits the ENTIRE index -- any content
# staged BEFOREHAND by another actor (a concurrent agent, a stray `git add`,
# a test writing to the live repo) travels silently inside the slice commit.
# Incident (2026-07-11, CRITICAL): commit `140da7ceb` shipped a poisoned
# test-fixture `pyproject.toml` + `tests/test_fail.py` this way; the poisoned
# commit was PUSHED and required a dedicated bonifica commit (`b3c5f4784`).
#
# Fix: snapshot `git diff --cached --name-only` BEFORE staging the declared
# paths; after staging, any snapshot entry NOT covered by the declared scope
# (prefix-match on directories, exact match on files -- the same
# normalization git pathspecs use) is EXTRANEOUS -> refuse LOUD (what/why/
# how, naming both cures) and exit before any commit lands. `--all` is
# exempt by construction (the operator explicitly asked for everything).
# ---------------------------------------------------------------------------


def _staged_paths(repo: Path) -> list[str]:
    """The repo-relative paths currently staged (``git diff --cached --name-only``)."""
    output = _git(repo, "diff", "--cached", "--name-only")
    return [line.strip() for line in output.splitlines() if line.strip()]


def _slice_build_tier_paths(repo: Path) -> list[Path]:
    """The entering slice's OWN currently-staged paths under ``tests/build/``.

    Design B refinement (fix-gherkin-slice-build-tier-scoping, slice-02):
    called AFTER ``_stage()`` has already run, so ``_staged_paths`` reflects
    exactly what THIS slice is about to commit (its declared ``--path`` list,
    or the full ``--all`` staged fileset). Intersecting that with
    ``tests/build/`` yields the slice's own committed build-tier content --
    never an unrelated future-slice/in-flight scaffold that merely lives
    elsewhere under the tree (that content stays untouched, deferred to
    feature-end via the existing ``BuildTierWholeTreeDeferred`` event).
    Empty when the slice touches nothing under ``tests/build/`` (the common
    Gherkin per-slice case) -- ``build_tier_exit_verdict`` already resolves an
    empty scope to the honest ``BuildTierNotApplicable`` no-op.

    Existence-filtered (RCA docs/analysis/root-cause-analysis-build-tier-arch-
    scope-zero-collect.md, Permanent fix P1, Branch A defense-in-depth): a
    staged path that is a DELETION or the delete-half of an unflagged rename
    is reported by plain ``git diff --cached --name-only`` identically to a
    live addition/modification -- ``git`` gives no rename/delete signal here.
    A path that no longer exists on disk cannot carry a live arch-invariant
    test, so it is dropped before reaching ``_run_arch_invariant_set`` (pure
    narrowing -- behavior-preserving for every path that does exist;
    ``build_tier_exit_verdict``'s own scope-kind branch is the primary fix and
    still degrades correctly if a stale path reaches it another way).
    """
    return [
        repo / path
        for path in _staged_paths(repo)
        if (path == "tests/build" or path.startswith("tests/build/"))
        and (repo / path).exists()
    ]


def _covered_by_declared_scope(staged_path: str, declared_paths: list[str]) -> bool:
    """True iff ``staged_path`` is exactly, or nested under, a declared path."""
    for declared in declared_paths:
        normalized = declared.rstrip("/")
        if staged_path == normalized or staged_path.startswith(f"{normalized}/"):
            return True
    return False


def _extraneous_staged_paths(
    pre_stage_snapshot: list[str], declared_paths: list[str]
) -> list[str]:
    """Snapshot entries NOT covered by the declared ``--path`` scope."""
    return [
        path
        for path in pre_stage_snapshot
        if not _covered_by_declared_scope(path, declared_paths)
    ]


def _extraneous_staged_content_refusal(
    repo: Path, extraneous: list[str]
) -> dict[str, object]:
    """The ``CommitRefusedExtraneousStagedContent`` payload naming both cures.

    The unstage cure is emitted as a COMPLETE, runnable command carrying the
    actual extraneous paths (shell-quoted), never a ``<file>`` slot: this
    payload already KNOWS the filenames (they are right there in
    ``extraneous``), so asking the operator to transcribe them out of the
    JSON and assemble the invocation by hand puts the cost on the wrong
    party. See §The printed-remediation rule at the top of this module.

    ``git -C <repo>`` pins the target explicitly rather than relying on the
    operator's cwd: ``commit-slice`` takes ``--repo``, so it may well be
    driving a repository the operator is NOT standing in, and a cwd-relative
    ``git restore`` pasted from the wrong directory would unstage files in
    the WRONG repository -- the same aim-at-the-wrong-repo failure the
    placeholder ban exists to prevent.
    """
    listed = ", ".join(extraneous)
    unstage_command = (
        f"git -C {shlex.quote(str(repo))} restore --staged -- "
        + " ".join(shlex.quote(path) for path in extraneous)
    )
    return {
        "event": "CommitRefusedExtraneousStagedContent",
        "exit_code": 1,
        "extraneous": extraneous,
        "what": f"{len(extraneous)} file(s) were already staged outside the "
        f"declared --path scope: {listed}",
        "why": "commit-slice commits the ENTIRE index, not just the declared "
        "paths -- pre-staged content from another actor would travel "
        "silently into this slice commit (the 140da7ceb poisoned-pyproject "
        "incident).",
        "how": "unstage the extraneous file(s) with `git restore --staged` -- "
        "the complete command, carrying their actual paths, is below: run it "
        "EXACTLY as printed (no substitution needed), then re-run this "
        "invocation. Or, if they genuinely belong to this commit, include them "
        "intentionally via --path (or --all).",
        "command": unstage_command,
    }


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


# ---------------------------------------------------------------------------
# Blast-radius tier cap (slice-03 of blast-radius-measured-tier, GDP-1/3/6):
# refuses BEFORE any commit lands when the MEASURED blast radius of the
# declared scope exceeds the declared ``--tier``. A no-op when ``--tier`` is
# omitted (byte-identical to today). Reuses the SAME ``measure_blast_radius``
# orchestration slice-02 shipped (DT2) -- never a parallel, simplified
# escalation rule; an indeterminate measurement (an unparseable touched file)
# already escalates to L inside ``classify_tier`` (GDP-6), inherited
# unchanged, so "unknown blast radius" is never silently trusted.
# ---------------------------------------------------------------------------

_BLAST_RADIUS_TIER_ORDER: dict[str, int] = {"S": 0, "M": 1, "L": 2}


def _blast_radius_scope_arg(use_all: bool, declared_paths: list[str]) -> str:
    """The ``des blast-radius`` scope flag mirroring a declared commit-slice
    scope: ``--staged`` for ``--all``, else ``--paths <declared_paths>``."""
    if use_all:
        return "--staged"
    return "--paths " + " ".join(shlex.quote(p) for p in declared_paths)


def _blast_radius_tier_how(
    repo: Path,
    declared_tier: str,
    measured_tier: str,
    declared_paths: list[str],
    use_all: bool,
) -> str:
    """The self-explaining HOW for a ``BlastRadiusTierExceeded`` refusal (GDP-3).

    Interpolates the REAL repo path and, for a ``--path``-declared scope, the
    ACTUAL declared paths (never a ``<placeholder>``, per the printed-
    remediation rule at the top of this module) into a runnable
    ``des blast-radius`` command that re-measures the SAME scope, then names
    a concrete remediation: accept the real tier, or split the slice smaller.
    """
    repo_arg = shlex.quote(str(repo))
    scope_arg = _blast_radius_scope_arg(use_all, declared_paths)
    return (
        f"re-measure with `des blast-radius --repo {repo_arg} {scope_arg}` -- "
        f"the declared scope measures tier {measured_tier}, exceeding the "
        f"declared --tier {declared_tier}. Either accept the real tier "
        f"(--tier {measured_tier}) or split the slice into a smaller scope."
    )


def _blast_radius_tier_refusal(
    repo: Path,
    declared_tier: str,
    verdict: BlastRadiusVerdict,
    declared_paths: list[str],
    use_all: bool,
) -> dict[str, object]:
    """The ``BlastRadiusTierExceeded`` payload -- structured tiers (DT1) +
    self-explaining what/why/how prose naming the driving measure, never a
    bare tier letter."""
    measured_tier = verdict.tier.value
    why = (
        "; ".join(verdict.reasons)
        if verdict.reasons
        else (f"measured tier {measured_tier} exceeds declared tier {declared_tier}")
    )
    return {
        "event": "BlastRadiusTierExceeded",
        "exit_code": 1,
        "declared_tier": declared_tier,
        "measured_tier": measured_tier,
        "what": (
            f"the measured blast radius is tier {measured_tier}, which "
            f"exceeds the declared --tier {declared_tier}"
        ),
        "why": why,
        "how": _blast_radius_tier_how(
            repo, declared_tier, measured_tier, declared_paths, use_all
        ),
    }


def _reset_preserving_pre_existing_staging(
    repo: Path, pre_stage_snapshot: list[str]
) -> None:
    """Unstage only what THIS invocation added, preserving whatever the
    operator had ALREADY staged before invoking ``commit-slice`` (D8, GDP-6).

    A plain ``git reset`` unstages the ENTIRE index unconditionally --
    correct only when nothing was staged before this invocation began. Under
    ``--all`` the extraneous-staged-content guard is exempt by construction
    (the operator explicitly asked for everything), so pre-existing staged
    content (e.g. curated ``git add -p`` hunks for unrelated work) rides
    along into the index. Staging intent is real work, not reconstructible
    from the working tree -- so on refusal, the delta between what is staged
    NOW and ``pre_stage_snapshot`` (taken before ``_stage()`` ran) is exactly
    what THIS invocation added; unstaging only that delta leaves the
    operator's own staged paths untouched. An empty delta is a no-op --
    nothing this invocation staged remains to undo.
    """
    delta = sorted(set(_staged_paths(repo)) - set(pre_stage_snapshot))
    if delta:
        git_run(repo, "reset", "--", *delta)


def _check_blast_radius_tier(
    repo: Path, declared_tier: str, declared_paths: list[str], use_all: bool
) -> dict[str, object] | None:
    """Measure the declared scope; return a refusal payload iff it exceeds
    ``declared_tier`` (or the measurement itself was rejected), else None.

    Called AFTER staging (the SAME staged scope the commit is about to
    carry): ``--all`` measures ``des blast-radius --staged`` (the resolved
    ``--all`` staged set, D3); an explicit ``--path`` list measures
    ``des blast-radius --paths <declared_paths>`` (DT2) -- the SAME
    orchestration ``des blast-radius`` itself runs, never a re-derived rule.

    D3 (blocker fix): ``measure_blast_radius`` can raise
    ``BlastRadiusInputRejected`` (a declared ``--path`` entry does not exist
    -- e.g. it was DELETED, which ``_stage()`` above has already staged) or
    ``BlastRadiusConfigRejected`` (a present, well-typed threshold outside
    its floor/ceiling). Both are caught HERE and turned into a structured
    refusal payload -- mirroring ``des blast-radius``'s own CLI (D3, GDP-3)
    -- so the caller's ``_reset_preserving_pre_existing_staging`` +
    exit-code-pop handling always runs before returning: never an uncaught
    exception escaping ``main()`` with a staged deletion left dangling in
    the index.

    D7: every OTHER exception is caught by a TOTAL handler below (not an
    ever-growing except tuple) and mapped to the same structured shape --
    the tier cap sits on the pre-commit chokepoint, so its failure surface
    must be total, degrading LOUD rather than escaping as a traceback that
    skips the caller's cleanup.
    """
    try:
        verdict = (
            measure_blast_radius(repo, staged=True)
            if use_all
            else measure_blast_radius(repo, paths=declared_paths)
        )
    except BlastRadiusInputRejected as exc:
        return {
            "event": "BlastRadiusInputRejected",
            "exit_code": 2,
            "what": str(exc),
            "why": "the declared --tier scope could not be measured -- a "
            "declared --path entry does not exist (e.g. it was deleted).",
            "how": "verify every --path entry exists in the SAME scope you "
            "are about to commit, or drop --tier for this invocation.",
        }
    except BlastRadiusConfigRejected as exc:
        return {
            "event": "BlastRadiusConfigRejected",
            "exit_code": 2,
            "what": str(exc),
            "why": f"a configured blast_radius threshold under {repo} is "
            "outside its documented floor/ceiling range.",
            "how": "fix the offending threshold in .nwave/des-config.json, "
            "or drop --tier for this invocation.",
        }
    except Exception as exc:
        # ANY other failure inside `measure_blast_radius` / `_resolve_scope`
        # (a failing `git diff`, an unparseable git object, a filesystem
        # error, ...) -- a total handler, not an ever-growing except tuple.
        # The tier cap sits on the pre-commit chokepoint: its failure
        # surface must be total, degrading LOUD to a structured, self-
        # explaining refusal (GDP-3/6) that still reaches the caller's
        # D8-corrected cleanup, rather than an uncaught traceback that skips
        # it and leaves staged content dangling.
        return {
            "event": "BlastRadiusMeasurementFailed",
            "exit_code": 1,
            "what": f"measuring the declared --tier scope failed: {exc}",
            "why": f"an unexpected {type(exc).__name__} escaped the blast-"
            "radius measurement -- the scope could not be reliably "
            "measured, so the tier cap cannot be evaluated.",
            "how": "re-run `des blast-radius --repo "
            f"{shlex.quote(str(repo))} "
            f"{_blast_radius_scope_arg(use_all, declared_paths)}` "
            "to reproduce and diagnose the underlying failure, or drop "
            "--tier for this invocation.",
        }
    if (
        _BLAST_RADIUS_TIER_ORDER[verdict.tier.value]
        <= _BLAST_RADIUS_TIER_ORDER[declared_tier]
    ):
        return None
    return _blast_radius_tier_refusal(
        repo, declared_tier, verdict, declared_paths, use_all
    )


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


def _mint_shadow_commit(repo: Path, message: str) -> str:
    """Mint an UNREFERENCED ``git commit-tree`` shadow object from the
    currently-staged index (ADR-DES-001, the pre-flight gates-before-commit
    reorder).

    ``git write-tree`` snapshots the staged index into a tree object -- a
    read of the index, touching neither ``HEAD`` nor any ref. ``git
    commit-tree <tree> -p HEAD`` wraps that tree into a floating commit
    OBJECT with the real HEAD as parent: it writes NO ref, NO branch
    pointer, and leaves NO reflog entry, so it is invisible to ``git log``/
    ``git status``/``git for-each-ref`` and ages out on the next ``git gc``
    if it is never referenced. This gives E1's git-plumbing primitives
    (``git show <commit>``, ``<commit>~1:path``) a REAL commit-ish to
    inspect pre-flight, at zero code change to E1 itself -- the message
    content is irrelevant (the committed-scope digest is over the TREE, not
    the message), so the caller's own commit message is reused verbatim.
    """
    tree_sha = git_run(repo, "write-tree").strip()
    return git_run(repo, "commit-tree", tree_sha, "-p", "HEAD", "-m", message).strip()


def _committed_scope_digest_or_degrade_reason(
    repo: Path,
    at_kind: str | None = None,
    regression_test_file: Path | None = None,
) -> tuple[str, None] | tuple[None, str]:
    """Step 3's committed-scope digest, routed through the runner seam FIRST.

    Mirrors the SAME runner-resolution seam the digest CLI modes already use
    (``_maybe_route_digest_through_runner`` -> ``--committed-scope-digest`` /
    ``--print-digest`` / ``--verify-gate-scope``), so a cargo-test (or any
    future non-pytest) target earns a runner-derived digest instead of the
    pytest-native one -- never a vacuous pytest digest over a Rust tree
    (F-gate-scope-digest-runner-agnostic slice-01).

    ``at_kind == "pytest-regression"`` (fix-runner-resolves-per-scope-language
    slice-01) SKIPS the whole-tree runner seam entirely: a pytest-regression
    slice is Python-specific by construction (it declares its OWN
    ``--regression-test-file``), so routing its digest through the repo's
    OTHER lockfile-resolved runner (e.g. cargo on a Rust-primary repo) is
    never correct -- that repo-root lockfile scan has no awareness of which
    language THIS slice actually touched, and an empty cargo scope would
    degrade a genuinely-passing Python slice to indeterminate.

    ``at_kind == "native-regression"`` (fix-rust-regression-at-kind-wiring,
    Branch C closure) routes on ``regression_test_file``'s OWN suffix --
    mirroring ``verify_slice_commit_completeness._routes_through_runner_
    port``'s execution-leg decision, so the digest leg can never contradict
    what E2 actually ran: a non-``.py`` file ALWAYS routes through the
    runner seam (never falls through to the Python-native path, even on a
    ``None``/pytest resolution -- a Rust file earning a Python digest is
    the exact defect this closes); a genuine ``.py`` file keeps the EXISTING
    marker-agnostic Python-native path, the runner seam never consulted.
    Every other ``--at-kind`` (default ``gherkin``) keeps the EXISTING
    runner-routed behavior unchanged.

    * pytest / lockfile-less target -- the runner seam returns ``None`` (its
      OWN unchanged fall-through contract): falls through to the EXISTING
      ``_committed_scope_digest_value`` pytest path, byte-identical to before.
    * a resolved non-pytest runner (e.g. cargo-test) -- its OWN enumerate
      facet already produced the digest (``_DigestRouteResult``); used as-is.
    * either leg degrading (``RunnerAdapterUnavailable`` / no interpreter) --
      returns ``(None, reason)``; the reason names WHICH leg degraded so the
      caller mints the honest ``SliceCommitIndeterminate`` record, never a
      fabricated digest.
    """
    if at_kind == "native-regression" and regression_test_file is not None:
        if regression_test_file.suffix != ".py":
            route = _maybe_route_digest_through_runner(repo)
            if isinstance(route, _DigestRouteResult):
                return route.digest, None
            return None, _DEGRADE_REASON_RUNNER_UNAVAILABLE
        digest_result = _committed_scope_digest_value(repo, "HEAD", markers=None)
    elif at_kind != "pytest-regression":
        route = _maybe_route_digest_through_runner(repo)
        if isinstance(route, _DigestRouteResult):
            return route.digest, None
        if isinstance(route, _DigestRouteDegrade):
            return None, _DEGRADE_REASON_RUNNER_UNAVAILABLE
        digest_result = _committed_scope_digest_value(repo, "HEAD")
    else:
        # pytest-regression: collect MARKER-AGNOSTICALLY. The committed
        # regression test on an arbitrary target repo (no auto-marking
        # conftest applying the contract markers) would otherwise be
        # DESELECTED by the default marker filter -> an empty scope hashed
        # to the vacuous sha256('') digest. Marker-agnostic collection
        # digests the real committed Python scope (the "digest over the
        # committed tree" this docstring promises), and the verify leg
        # (_mode_verify_gate_scope, same --at-kind) mirrors it exactly.
        digest_result = _committed_scope_digest_value(repo, "HEAD", markers=None)
    if isinstance(digest_result, _CommittedScopeDigest):
        return digest_result.digest, None
    return None, _DEGRADE_REASON_INTERPRETER_UNAVAILABLE


def _call_committed_scope_digest_or_degrade_reason(
    repo: Path, at_kind: str | None, regression_test_file: Path | None
) -> tuple[str, None] | tuple[None, str]:
    """Call the (possibly monkeypatched) Step-3 digest/degrade seam.

    Compatibility normalization (mirrors ``verify_slice_commit_completeness
    .py``'s documented bare-int ``_run_contract_gate`` stub normalization,
    "single-locus constraint"): several PRE-EXISTING regression ATs (e.g.
    ``test_indeterminate_seal_affordance_how_key.py``'s Site B) monkeypatch
    ``_committed_scope_digest_or_degrade_reason`` with the LEGACY 2-positional
    -argument stub shape that predates the ``regression_test_file`` parameter
    (fix-rust-regression-at-kind-wiring). Calling a 2-arg stub with 3
    positional arguments raises ``TypeError`` -- introspect the CURRENTLY
    bound callable's arity (picks up a monkeypatch, since the module-level
    name is resolved at call time) and fall back to the legacy 2-arg call
    shape when the bound callable cannot accept a third parameter. Keeps both
    call shapes working without touching those pre-existing tests.
    """
    try:
        accepts_three = (
            len(inspect.signature(_committed_scope_digest_or_degrade_reason).parameters)
            >= 3
        )
    except (TypeError, ValueError):
        accepts_three = True
    if accepts_three:
        return _committed_scope_digest_or_degrade_reason(
            repo, at_kind, regression_test_file
        )
    return _committed_scope_digest_or_degrade_reason(repo, at_kind)


def _verify(repo: Path, at_kind: str | None = None) -> int:
    """Run ``run_contract_gate --verify-gate-scope --commit HEAD``; return exit.

    Invoked in-process (the SAME definition the G_COMMIT exit gate runs -- no
    stub, no reimplementation). A clean exit 0 here is the acceptance proof: the
    produced commit verifies with NO manual amend.

    ``at_kind`` is forwarded as ``--at-kind`` so the re-derived digest mirrors
    Step 3's own routing decision (``_committed_scope_digest_or_degrade_reason``)
    -- a pytest-regression slice's digest was pinned WITHOUT the whole-tree
    runner seam, so its re-verification must skip that seam too, or a
    Rust-primary repo's cargo route would refuse a genuinely-verified Python
    digest it never produced.
    """
    from des.cli.run_contract_gate import main as run_contract_gate_main

    argv = ["--repo", str(repo), "--verify-gate-scope", "--commit", "HEAD"]
    if at_kind == "pytest-regression":
        argv.extend(["--at-kind", "pytest-regression"])
    return run_contract_gate_main(argv)


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
    repo: Path, message: str, slice_ids: list[str], feature_id: str
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

    ``feature_id`` is non-optional: ``main()`` refuses a ``--feature-id``-less
    invocation up-front, so it is ALWAYS known by the time the warning is
    printed and is interpolated verbatim. The old ``<feature-id>`` fallback
    that stood here is deleted -- it had become structurally unreachable, and
    dead code that prints a placeholder is a landmine for whoever makes it
    reachable again. The one remaining angle-bracket token below,
    ``<id>``, is an honest FLAG-slot: the reviewer's agent id is a value only
    the operator can supply, it is explicitly labelled as such, and the line
    is prose -- not a command claimed to run as printed. See §The
    printed-remediation rule at the top of this module.
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
                f"--feature-id {shlex.quote(feature_id)} "
                f"--slice-id {shlex.quote(slice_id)} "
                f"--verdict APPROVED --reviewer-agent-id <id>` (substitute <id> "
                f"with the agent id of the reviewer that performed the review; "
                f"any stable, non-empty reviewer id identifies who reviewed "
                f"it), then re-run des commit-slice.\n"
            )
            continue
        trailers.append(f"Reviewed-by: {record_hash} ({_VERDICT_APPROVED})")

    if not trailers:
        return message
    return f"{message.rstrip()}\n\n" + "\n".join(trailers)


# ---------------------------------------------------------------------------
# Missing --feature-id guard (fix-precommit-fabricates-vacuous-scaffold,
# slice-02, RCA §4a): --feature-id used to be OPTIONAL and every downstream
# gate below was individually guarded behind `if args.feature_id is not
# None` -- so omitting the flag silently disarmed all four of them and
# landed an unattested "SliceCommitted" anyway. The canonical crafter skill's
# ONE documented invocation omitted the flag, so the documented path was the
# disarmed one. An optional flag must never be able to disarm a gate
# (feature-delta C4 arch invariant): the absence is now refused LOUD, before
# any staging or git mutation, naming every gate the omission would have
# skipped -- never a quiet downgrade to an unattested commit.
# ---------------------------------------------------------------------------


def _ledger_stems(repo: Path) -> list[str]:
    """The AT-completion ledger stems on disk (the resolution EVIDENCE).

    ``active_feature_id`` answers WHICH feature (or ``None``); this answers
    WHY it could not say -- zero ledgers, or several, and their names. The
    refusal's HOW quotes them, so an honest "I cannot know this" is
    accompanied by the fact that made it unknowable.
    """
    telemetry = repo / TELEMETRY_DIR_RELPATH
    if not telemetry.is_dir():
        return []
    return sorted(path.stem for path in telemetry.glob("*.jsonl"))


def _rerun_command(args: argparse.Namespace, feature_id: str) -> str:
    """The SAME invocation, re-composed from the args actually in hand, with
    the REAL ``feature_id`` in it -- executable EXACTLY as printed.

    NEVER emits a ``<placeholder>``. A token that looks like a value and is
    not one is a trap with instructions attached: twice on 2026-07-13 an
    examiner was handed a command carrying a ``<placeholder>``, substituted
    something plausible, aimed a gate at the wrong repository, and produced
    a verdict that had to be thrown away. When the id cannot be resolved the
    caller does NOT print a fillable-looking command at all -- it says so,
    and says why (see ``_missing_feature_id_refusal``).

    Pins ``sys.executable`` so the command runs the SAME interpreter that is
    emitting it, never a possibly-stale ``des`` shim resolved off PATH
    (slice-01's ``run_slice_ats._rerun_command`` discipline, reused). Every
    argument is shell-quoted: a repo path containing a space would otherwise
    print a command that silently parses into the wrong arguments.
    """
    parts = [
        shlex.quote(sys.executable),
        "-m",
        "des.cli.commit_slice",
        "--repo",
        shlex.quote(str(args.repo)),
        "--feature-id",
        shlex.quote(feature_id),
    ]
    if args.all:
        parts.append("--all")
    for path in args.paths:
        parts.extend(["--path", shlex.quote(path)])
    if args.slice_id is not None:
        parts.extend(["--slice-id", shlex.quote(args.slice_id)])
    parts.extend(["--message", shlex.quote(args.message)])
    return " ".join(parts)


_WHY_FOUR_GATES_DISARMED = (
    "every downstream gate this command runs is feature-scoped and was "
    "individually guarded behind `if args.feature_id is not None` -- "
    "omitting the flag silently skipped ALL FOUR of them: (1) the E3 "
    "examine-verdict gate, (2) the E1 completeness / "
    "SliceCommitIndeterminate honesty mint, (3) the E2 feature-scoped "
    "contract gate / SliceCommitVerified record, and (4) the "
    "feature-end-pending notice -- landing an unattested SliceCommitted "
    "anyway. An optional flag must never be able to disarm a gate."
)


def _missing_feature_id_refusal(
    args: argparse.Namespace, repo: Path
) -> dict[str, object]:
    """The ``CommitRefusedMissingFeatureId`` payload naming every gate the
    omission would have skipped (RCA §4a) -- what/why/how, self-explaining.

    The HOW is split by whether the SYSTEM can answer the question it is
    about to ask the operator (GDP-5 -- the cost falls on the system, not
    the operator):

    * **Resolvable** (exactly one AT-completion ledger on disk):
      ``active_feature_id`` KNOWS the id. Emit the complete, real,
      copy-paste-executable command with that id already in it. Asking the
      operator to fill in a slot the tool is already holding the answer to
      puts the cost on the wrong party.
    * **Unresolvable** (zero ledgers, or several -- ``active_feature_id``
      returns ``None`` and never guesses): print NO command. Say precisely
      that the id could not be resolved, how many ledgers were found and
      their names, and that ``--feature-id`` must be supplied. An honest
      "I cannot know this, and here is why" is a fine HOW; a fillable-looking
      ``<placeholder>`` masquerading as one is not.
    """
    payload: dict[str, object] = {
        "event": "CommitRefusedMissingFeatureId",
        "exit_code": 1,
        "what": "--feature-id was omitted",
        "why": _WHY_FOUR_GATES_DISARMED,
    }

    feature_id = active_feature_id(repo)
    if feature_id is not None:
        payload["resolved_feature_id"] = feature_id
        payload["how"] = (
            f"pass --feature-id so all four gates re-arm. The feature id "
            f"resolved from the single AT-completion ledger under "
            f"{TELEMETRY_DIR_RELPATH}/ is '{feature_id}' -- re-run the "
            f"command below EXACTLY as printed (no substitution needed):"
        )
        payload["command"] = _rerun_command(args, feature_id)
        return payload

    stems = _ledger_stems(repo)
    found = f"{len(stems)} ledger(s) found under {TELEMETRY_DIR_RELPATH}/"
    if stems:
        found += ": " + ", ".join(stems)
    payload["ledgers_found"] = stems
    payload["how"] = (
        f"pass --feature-id so all four gates re-arm. This tool could NOT "
        f"resolve the feature id for you ({found}) -- it resolves one only "
        f"when EXACTLY one AT-completion ledger is on disk, and it never "
        f"guesses. Re-run this same invocation with `--feature-id <the "
        f"feature you are delivering>` added; no runnable command is printed "
        f"here because printing one would mean inventing the id."
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """Produce a correct-by-construction slice commit (stage->commit->amend->verify)."""
    args = _build_parser().parse_args(argv)

    # `--repo ""` normalizes to None (meaningful_identity) rather than
    # `Path("")`, which Python silently resolves to `.` -- i.e. a blank --repo
    # used to retarget the command at whatever directory the caller happened to
    # be standing in. Same aim-at-the-wrong-repo class as the placeholder ban.
    if args.repo is None:
        _emit(
            {
                "event": "MalformedInput",
                "exit_code": 2,
                "what": "--repo was empty or whitespace-only",
                "why": "a blank --repo would resolve to the CURRENT directory, "
                "silently committing into whichever repository the caller "
                "happened to be standing in -- never a guess.",
                "how": "pass --repo <path-to-the-target-repository>",
            }
        )
        return 2
    repo = Path(args.repo)

    # Earliest possible guard (GDP-1): refuse BEFORE any git mutation -- before
    # staging, before the commit -- see the module note above. `is None` is
    # SOUND here (and not the empty-string hole it was) only because
    # `meaningful_identity` has already collapsed ""/"   " to None at the
    # parse boundary: absent and meaningless are now the SAME state.
    if args.feature_id is None:
        refusal = _missing_feature_id_refusal(args, repo)
        exit_code = refusal.pop("exit_code")
        _emit(refusal)
        assert isinstance(exit_code, int)
        return exit_code

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

    # Self-validate the subject against gitlint (task #37, GDP-6): refuse a
    # subject CI's commitlint would reject BEFORE staging/committing anything
    # -- the earliest possible guard, fast (no git mutation yet).
    subject_violation = _gitlint_subject_violation(repo, args.message)
    if subject_violation is not None:
        exit_code = subject_violation.pop("exit_code")
        _emit(subject_violation)
        assert isinstance(exit_code, int)
        return exit_code

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

    # Remote-ancestry guard (fix-commit-slice-never-amends-pushed): refuse or
    # auto-heal a local HEAD regressed behind an already-pushed remote-
    # tracking ref BEFORE any staging/commit happens -- see the guard's
    # docstring for the full incident + fix rationale.
    remote_regression = _guard_head_not_behind_remote(repo)
    if remote_regression is not None:
        exit_code = remote_regression.pop("exit_code")
        _emit(remote_regression)
        assert isinstance(exit_code, int)
        return exit_code

    # Auto-stage the feature's expectation charter (GDP-5: the cost of
    # remembering --path docs/product/expectations/{feature_id}/ sits on the
    # operator today; this makes the charter first-class, never left behind).
    # Feature-scoped only, and skipped under --all (git add -A already covers
    # it); git add is idempotent so an explicit --path to the same dir stays
    # a no-op double-add.
    if not args.all:
        args.paths = [*args.paths, *_charter_dir_to_stage(repo, args.feature_id)]

    try:
        # Snapshot BEFORE staging the declared paths -- unconditional (D8,
        # fix-commit-slice-index-isolation-follow-up): the extraneous-staged-
        # content guard below still EXEMPTS `--all` by construction (the
        # operator explicitly asked for everything), but the snapshot itself
        # must exist even under `--all` so a LATER refusal (the tier cap,
        # below) can unstage only the delta THIS invocation added instead of
        # discarding the operator's own pre-existing staged content.
        pre_stage_snapshot = _staged_paths(repo)
        malformed = _stage(repo, args.paths, args.all)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "MalformedInput", "error": f"git staging failed: {exc}"})
        return 2
    if malformed is not None:
        _emit(malformed)
        return 2

    if not args.all:
        extraneous = _extraneous_staged_paths(pre_stage_snapshot, args.paths)
        if extraneous:
            refusal = _extraneous_staged_content_refusal(repo, extraneous)
            exit_code = refusal.pop("exit_code")
            _emit(refusal)
            assert isinstance(exit_code, int)
            return exit_code

    # Blast-radius tier cap (slice-03, F-blast-radius-measured-tier): refuses
    # BEFORE any commit lands when the MEASURED blast radius of the declared
    # scope exceeds the declared --tier. A no-op when --tier is omitted
    # (byte-identical to today). Refusal unstages only what THIS invocation
    # staged (D8) -- the operator's own pre-existing staged content (only
    # reachable under `--all`, since the guard above already refuses it
    # otherwise) is preserved, never silently swept away by the cleanup.
    if args.tier is not None:
        tier_refusal = _check_blast_radius_tier(repo, args.tier, args.paths, args.all)
        if tier_refusal is not None:
            _reset_preserving_pre_existing_staging(repo, pre_stage_snapshot)
            exit_code = tier_refusal.pop("exit_code")
            _emit(tier_refusal)
            assert isinstance(exit_code, int)
            return exit_code

    # Build-tier exit check (F-CONTRACT-GATE-EXCLUDES-BUILD-TIER-ARCH-TESTS,
    # evolution P1 deletion-safety precondition): EXECUTE tests/build/** BEFORE
    # the commit lands, so an arch/contract violation is refused at the slice
    # exit -- fail-closed, nothing ships. ADD-not-mutate (design option i): the
    # committed-scope digest machinery is untouched, so historic Gate-Scope:
    # trailers stay byte-identically verifiable. tests/build absent -> honest
    # BuildTierNotApplicable + proceed (target projects may carry no build
    # tier); interpreter absence -> LOUD indeterminate + proceed (the digest
    # step downstream mints the honest SliceCommitIndeterminate).
    regression_test_file = (
        repo / args.regression_test_file if args.regression_test_file else None
    )
    # Design B refinement (fix-gherkin-slice-build-tier-scoping, slice-02,
    # 2026-07-17): opt every per-slice seal into the SCOPED build tier
    # explicitly, not only the --regression-test-file case -- unchanged from
    # slice-01. When a regression_test_file IS declared, light_invariant_paths
    # stays [] (scoped_paths = [regression_test_file], byte-identical to
    # before). When NO regression_test_file is declared (the Gherkin
    # per-slice case), slice-01 always passed light_invariant_paths=[],
    # which LOST fail-closed for a slice that commits its OWN failing
    # tests/build/** test: the empty scope deferred the WHOLE tree
    # unconditionally, even though the slice's own committed content under
    # tests/build/ was never actually run. Fix: resolve the entering slice's
    # OWN committed paths under tests/build/ (its --path list, or the --all
    # staged fileset, intersected with tests/build/**) via
    # _slice_build_tier_paths and hand THAT as light_invariant_paths. An
    # empty intersection (the slice touches nothing under tests/build/, the
    # common Gherkin case) still resolves to the existing
    # BuildTierNotApplicable + BuildTierWholeTreeDeferred no-op
    # (poison-avoidance preserved -- an unrelated in-flight tests/build/**
    # scaffold never sweeps in). A non-empty intersection runs the arch
    # invariants on exactly those committed paths and REFUSES on violation --
    # restoring fail-closed for the slice's own committed build-tier content.
    light_invariant_paths = (
        [] if regression_test_file is not None else _slice_build_tier_paths(repo)
    )
    if (
        build_tier_exit_verdict(
            repo,
            regression_test_file=regression_test_file,
            light_invariant_paths=light_invariant_paths,
        )
        != 0
    ):
        return 1

    # Examine-verdict exit check (evolution-plan P1.2 -- User-Examiner wiring):
    # the SAME chokepoint as the build-tier check above. A no-op unless ARMED
    # for this feature (see the module-level note); when armed, EVERY entering
    # slice-id must carry a fresh PASS ExamineVerdict or the commit is refused
    # fail-closed BEFORE the placeholder commit lands -- UNLESS the slice is
    # `@coupled` (RCA fix-coupled-slice-examine-deferred-to-feature-end), in
    # which case `check_examine_verdict` returns a DEFER payload (no
    # `exit_code` key -- the discriminator) instead of a refusal: this guard
    # lets the commit proceed, and the deferral is attested ONCE downstream
    # at `_run_verify_then_record`'s single-write chokepoint (Step 6 fold-in
    # below), never here.
    if args.feature_id is not None:
        for slice_id in extract_slice_ids(message):
            examine_rejection = check_examine_verdict(repo, args.feature_id, slice_id)
            if examine_rejection is not None and "exit_code" in examine_rejection:
                exit_code = examine_rejection.pop("exit_code")
                _emit(examine_rejection)
                assert isinstance(exit_code, int)
                return exit_code

    # Step 1.5 (ADR-DES-001, THE reorder): mint an unreferenced shadow commit
    # from the staged index and run the pure E1+E2(+E3) verify half
    # (`_run_verify_checks`, the Prefactoring slice-00 seam) against it
    # BEFORE the real commit lands. A refusal here means NO commit lands at
    # all -- the shadow object stays unreferenced and ages out; the refusal
    # payload is already emitted by `_run_verify_checks` itself (E1/E2's own
    # self-explaining what/why/how), so this only needs to propagate the
    # exit code. A clear pre-flight changes nothing about Steps 2-6 below:
    # the real commit's tree is byte-identical to the shadow's (same staged
    # index, same HEAD parent), so the digest computed at Step 3 is
    # unaffected. Imported locally (not at module level) because
    # `verify_slice_commit_completeness` itself imports
    # `check_examine_verdict` from this module -- a module-level import
    # would be circular.
    # `preflight_already_minted` (DDD-6, slice-02): True ONLY when the
    # preflight itself has ALREADY appended the honest
    # SliceCommitIndeterminate record (the `_GATE_INDETERMINATE_EXIT_CODE`
    # branch below, per `_run_verify_checks`'s own documented contract).
    # Step 3 reads it to avoid MINTING A SECOND record for the SAME degrade
    # (the ledger is append-only and not itself dedup-on-reason, so an
    # unconditional second mint would double-count). The RESCUE branch
    # (further below) does NOT set this -- it only decides to proceed
    # instead of refuse; it mints nothing itself, so Step 3 remains the
    # sole, first mint on that path.
    preflight_already_minted = False
    if args.feature_id is not None:
        from des.cli.verify_slice_commit_completeness import (
            _GATE_INDETERMINATE_EXIT_CODE,
            _run_verify_checks,
        )
        from des.cli.verify_slice_commit_completeness import (
            _build_parser as _build_verify_parser,
        )

        shadow_sha = _mint_shadow_commit(repo, message)
        preflight_argv = [
            "--repo",
            str(repo),
            "--feature-id",
            args.feature_id,
            "--commit",
            shadow_sha,
        ]
        if args.at_kind in ("pytest-regression", "native-regression"):
            preflight_argv.extend(
                [
                    "--at-kind",
                    args.at_kind,
                    "--regression-test-file",
                    args.regression_test_file,
                ]
            )
        preflight_args = _build_verify_parser().parse_args(preflight_argv)
        preflight_exit_code, _preflight_context = _run_verify_checks(
            repo, preflight_args
        )
        # ADR-DES-001 addendum Rule 3: _GATE_INDETERMINATE_EXIT_CODE (3) is
        # this gate's OWN documented "record honestly and PROCEED" contract
        # (the SliceCommitIndeterminate ledger record is already minted by
        # _run_verify_checks itself, during this same call) -- it must
        # PROCEED to the real commit below, never reset+refuse. Every OTHER
        # non-zero code (a genuine E1/E2/E3 refusal) still resets the index
        # and refuses exactly as before -- Rule 3 narrows the exemption to
        # exactly this one code, it never widens the set that proceeds.
        if preflight_exit_code == _GATE_INDETERMINATE_EXIT_CODE:
            preflight_already_minted = True
        elif preflight_exit_code != 0:
            # Rescue check (DDD-6, slice-02): a hard E1/E2 refusal MAY be a
            # MASKED symptom of the exact same "no resolvable
            # interpreter/runner" condition Step 3's committed-scope digest
            # degrades honestly for -- e.g. a genuine non-Python target where
            # ZERO .feature files can ever exist, so E2's gherkin-scope
            # resolver refuses "zero-collected" BEFORE it ever reaches an
            # interpreter check (the check that exists further downstream in
            # `_mode_feature_scoped` never runs). Probe the SAME digest seam
            # Step 3 uses -- ONLY on this already-refusing path, so a normal
            # successful commit pays no extra collection cost. If it ALSO
            # degrades, the refusal is that masked case: fall through to the
            # honest degrade-mint path below instead of reset+refuse.
            #
            # PYTHONDONTWRITEBYTECODE=1 for the DURATION of this probe only
            # (restored in `finally`): a genuine refusal must leave the
            # working tree byte-identical to the operator's pre-invocation
            # state (test_commit_slice_gates_run_before_commit's own
            # invariant) -- an ordinary pytest collection writes `__pycache__`
            # directories as an unavoidable import side effect, which would
            # otherwise pollute a refusal that never lands a commit. `git
            # reset` (mixed mode) only unstages; it does not remove untracked
            # bytecode cache, so the cache must never be written in the
            # first place on this probe-only call.
            _prev_dont_write_bytecode = os.environ.get("PYTHONDONTWRITEBYTECODE")
            os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
            try:
                _, rescue_reason = _call_committed_scope_digest_or_degrade_reason(
                    repo, args.at_kind, regression_test_file
                )
            finally:
                if _prev_dont_write_bytecode is None:
                    os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
                else:
                    os.environ["PYTHONDONTWRITEBYTECODE"] = _prev_dont_write_bytecode
            if rescue_reason is None:
                # Unstage `_stage()`'s `git add -A`/`--path` -- a refusal
                # must leave no half-committed dangling state (no ref/HEAD
                # move: the commit was never made). Any file the OPERATOR
                # wrote before this invocation (tracked or untracked) is
                # content, never deleted by a refusal.
                #
                # D10: this uses the DELTA reset, not a bare `git reset`.
                # A bare reset clears the WHOLE index, which under `--all`
                # also discards staging the operator curated BEFORE
                # invoking (the extraneous-staged-content guard is exempt
                # under `--all`, so that content rides along into the
                # index) -- the SAME defect D8 corrected in the tier-cap
                # refusal path, which survived here in the second, MORE
                # frequently taken refusal path. Both properties hold
                # together: everything THIS invocation staged is undone,
                # and nothing staged before it is touched.
                _reset_preserving_pre_existing_staging(repo, pre_stage_snapshot)
                return preflight_exit_code
            # rescue_reason is not None: fall through. `preflight_already_minted`
            # stays False -- this branch minted nothing; Step 3's mint below
            # (using its own freshly-computed `degrade_reason`) is the sole one.

    # Step 2: commit with the placeholder trailer. HEAD now carries the slice.
    try:
        _commit_with_placeholder(repo, message, args.no_verify_commit)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "CommitFailed", "error": f"git commit failed: {exc}"})
        return 2

    # Step 3: the committed-scope digest of the RESULTING HEAD. This now
    # includes the slice's previously-untracked AT files -- the whole point.
    # Routed through the SAME runner-resolution seam the digest CLI modes use
    # (cargo-test target -> a runner-derived digest, never a vacuous pytest
    # one); git absent / not a work-tree / an un-enumerable runner scope emits
    # the LOUD INDETERMINATE event (exit 2 propagated as 1 -- the commit
    # landed but is un-verifiable).
    digest, degrade_reason = _call_committed_scope_digest_or_degrade_reason(
        repo, args.at_kind, regression_test_file
    )
    if digest is None:
        assert degrade_reason is not None  # the tuple contract: exactly one is set
        # The committed-scope machinery (pytest OR runner leg) already emitted
        # its LOUD event. The commit LANDED at step 2 carrying its Slice-Id
        # trailer, but the digest could not be pinned (a non-Python target
        # with no resolvable pytest interpreter, OR a resolved non-pytest
        # runner whose enumerate facet degraded). DDD-6: instead of returning
        # record-less -- which wedges the successor slice ("predecessor has no
        # honest record") -- route the degrade to MINT the honest
        # SliceCommitIndeterminate record (the SAME SSOT mint
        # `des verify-slice-commit`'s E2 degrade uses). The in-order gate
        # accepts an INDETERMINATE predecessor, so the chain progresses; a
        # fabricated SliceCommitVerified is NEVER written (the honesty invariant).
        if args.feature_id is not None:
            slice_ids = extract_slice_ids(message)
            if not preflight_already_minted:
                # The preflight has NOT already minted a record for this
                # degrade -- this is the FIRST and only mint. Covers BOTH
                # the rescue fall-through (which mints nothing itself) AND
                # the ordinary case where Step 1.5 never ran at all
                # (`args.feature_id is None` -- unreachable here since we
                # are inside `if args.feature_id is not None` -- or the
                # digest degraded WITHOUT the preflight ever having seen
                # `_GATE_INDETERMINATE_EXIT_CODE`). When
                # `preflight_already_minted` is True, the Step 1.5 preflight
                # already appended the honest record via
                # `_run_verify_checks`'s own `_GATE_INDETERMINATE_EXIT_CODE`
                # contract -- skip the duplicate append, but still emit the
                # SAME informative event below (never silent).
                _append_slice_commit_indeterminate(
                    repo,
                    args.feature_id,
                    slice_ids,
                    reason=degrade_reason,
                )
            _emit(
                {
                    "event": "SliceCommitIndeterminate",
                    "commit": _git(repo, "rev-parse", "HEAD").strip(),
                    "feature_id": args.feature_id,
                    "slice_ids": slice_ids,
                    "reason": degrade_reason,
                    "error": "the committed-scope digest could not be established "
                    "(no resolvable interpreter, or the resolved runner's "
                    "enumerate facet was untrustworthy) -- recorded an honest "
                    "SliceCommitIndeterminate (unverified here), never a "
                    "fabricated pass",
                    "how": _INDETERMINATE_NO_EXAMINE_RESCUE_HOW,
                }
            )
        return 1

    # Step 4: amend the message-only trailer to the committed-scope digest.
    try:
        _amend_trailer(repo, digest)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "CommitFailed", "error": f"git amend failed: {exc}"})
        return 2

    head = _git(repo, "rev-parse", "HEAD").strip()

    # Step 5: the acceptance proof -- verify clean with NO human amend.
    if not args.skip_verify:
        verify_code = _verify(repo, args.at_kind)
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

    # Step 6 (GDP-1 fold-in): guarantee the SliceCommitVerified record itself,
    # so a folded lean-cycle commit -- where the SubagentStop hook never fires
    # -- does not orphan its successor's carpaccio-order check. Invokes the
    # SAME canonical verify-then-record `des verify-slice-commit --feature-id`
    # runs (E1 completeness + E2 feature-scoped contract + E3 examine),
    # writing `SliceCommitVerified` IFF all three clear -- byte-identical
    # record shape, no reimplementation (Ale-authorized canonical form).
    # Honesty invariant: a genuine E1/E2/E3 failure writes NO record; the
    # failure is surfaced via the fold-in's own JSON event (emitted before the
    # `SliceCommitted` line below), never silently swallowed. Idempotent by
    # construction: `AtCompletionLedger.verified_slices()` is set-valued, so
    # a later re-run (e.g. the hook, or a stale `des verify-slice-commit`)
    # for an already-verified slice changes nothing observable -- no
    # double-counted verification.
    #
    # `verified` (the SliceCommitted payload below) is derived EXCLUSIVELY
    # from this fold-in's own exit code -- never from `args.skip_verify`
    # (the RCA'd defect: `verified` used to restate a CLI flag instead of
    # reporting what the gates actually returned). The pre-flight gate above
    # already cleared E1+E2 against a byte-identical tree, so on the
    # ordinary path this fold-in re-clears too and `fold_in_exit_code`
    # stays 0. The residual case ADR-DES-001 names (a flake/race between the
    # pre-flight and post-commit checks) degrades LOUD instead of silently
    # restating success: the commit stays landed (never auto-reverted -- the
    # same rejected shape as commit-then-revert), but `verified` is honestly
    # `False` and `main()`'s own exit code reflects the divergence.
    fold_in_exit_code = 0
    if args.feature_id is not None:
        from des.cli.verify_slice_commit_completeness import (
            main as _verify_then_record_main,
        )

        fold_in_argv = [
            "--repo",
            str(repo),
            "--feature-id",
            args.feature_id,
            "--commit",
            "HEAD",
        ]
        if args.at_kind in ("pytest-regression", "native-regression"):
            fold_in_argv.extend(
                [
                    "--at-kind",
                    args.at_kind,
                    "--regression-test-file",
                    args.regression_test_file,
                ]
            )
        fold_in_exit_code = _verify_then_record_main(fold_in_argv)

    # Step 6.5 (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED): PURELY ADDITIVE,
    # best-effort-loud markdown sync. Runs ONLY when the fold-in above
    # genuinely wrote a `SliceCommitVerified` record (`fold_in_exit_code ==
    # 0`) -- never on a degrade, so the Status column is never flipped on
    # the strength of an unverified commit. Never affects the exit code.
    if args.feature_id is not None and fold_in_exit_code == 0:
        _sync_slice_plan_status(repo, args.feature_id, extract_slice_ids(message))

    # Step 7 (deliver-finalize-unmissable slice-01, FIX-A): PURELY ADDITIVE,
    # best-effort-loud last-slice notice. Runs strictly AFTER the commit has
    # already succeeded and verified -- never affects the exit code above.
    if args.feature_id is not None:
        _notify_feature_end_unmissable(repo, args.feature_id)

    # Step 8 (parallel-work-cleans-up-after-merge-back slice-01, D-2/D-3,
    # ADR-SWARM-002): PURELY ADDITIVE worktree-cleanup auto-trigger. Never
    # gated on --feature-id (unlike Step 7 above) -- a merge-back's worktree
    # cleanup is not a feature-scoped concern. Armed only on the repo's own
    # MAIN worktree (`_worktree_cleanup_armed`); a no-op everywhere else,
    # including the ordinary in-worktree per-slice commit.
    _run_worktree_cleanup_sweep(repo)

    verified = fold_in_exit_code == 0
    _emit(
        {
            "event": "SliceCommitted",
            "commit": head,
            "gate_scope_digest": digest,
            "verified": verified,
        }
    )
    if not verified:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
