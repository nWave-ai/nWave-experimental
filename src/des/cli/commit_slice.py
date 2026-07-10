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
        refused the commit OR the slice was EXAMINED and FAILED
        (``ExamineVerdictRefused``).
    2 = malformed input (nothing staged, empty message, repo unreadable, or a
        subject violating gitlint's title rules -- ``SubjectViolatesGitlint``
        T1/T7) OR the entering slice fails the examine-verdict gate (missing /
        stale / INDETERMINATE -- ``ExamineVerdictMissing`` /
        ``ExamineVerdictStale`` / ``ExamineVerdictIndeterminate``).

Reference: docs/feature/des-spine-control-plane-ssot (committed-scope trailer),
           #67 facet-4 / MEMORY control-plane SSOT (digest-timing facet).
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
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
from des.cli.verify_slice_commit_completeness import _append_slice_commit_indeterminate
from des.domain.examine_verdict_signing import charter_seal as _charter_seal
from des.domain.slice_id_trailer import extract_slice_ids


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
            f"{feature_id} --feature-dir docs/feature/{feature_id} "
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


def _examine_remediation_command(feature_id: str, slice_id: str) -> str:
    return (
        "dispatch nw-user-examiner with the slice's charter, then record its "
        f"verdict: `des record-examine-verdict --repo <repo> --feature-id "
        f"{feature_id} --slice {slice_id} --charter <path> --verdict PASS "
        "--observations <text> --examiner nw-user-examiner`"
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

    Refusal taxonomy (fail-closed, never a silent pass):
      * ``ExamineVerdictMissing``       (exit 2) -- no record at all.
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
            "how": f"slice not examined: {_examine_remediation_command(feature_id, slice_id)}",
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
                f"{_examine_remediation_command(feature_id, slice_id)}"
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
                f"then {_examine_remediation_command(feature_id, slice_id)}"
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
            "how": f"re-record a valid verdict: {_examine_remediation_command(feature_id, slice_id)}",
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
            "how": f"re-record a fresh verdict: {_examine_remediation_command(feature_id, slice_id)}",
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
                f"{_examine_remediation_command(feature_id, slice_id)}"
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
                f"PASS verdict: {_examine_remediation_command(feature_id, slice_id)}"
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
        "--at-kind",
        dest="at_kind",
        default="gherkin",
        choices=("gherkin", "pytest-regression"),
        help=(
            "The acceptance-test kind the slice's E2 leg attests (default: "
            "gherkin, byte-identical for every existing caller). Forwarded "
            "into the Step-6 verify_slice_commit_completeness fold-in so a "
            "real pytest-regression commit runs the BEHAVIORAL (not gherkin/ "
            "feature-scoped-contract) E2 path -- see "
            "verify_slice_commit_completeness.py for the attestation itself."
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


def _committed_scope_digest_or_degrade_reason(
    repo: Path,
) -> tuple[str, None] | tuple[None, str]:
    """Step 3's committed-scope digest, routed through the runner seam FIRST.

    Mirrors the SAME runner-resolution seam the digest CLI modes already use
    (``_maybe_route_digest_through_runner`` -> ``--committed-scope-digest`` /
    ``--print-digest`` / ``--verify-gate-scope``), so a cargo-test (or any
    future non-pytest) target earns a runner-derived digest instead of the
    pytest-native one -- never a vacuous pytest digest over a Rust tree
    (F-gate-scope-digest-runner-agnostic slice-01).

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
    route = _maybe_route_digest_through_runner(repo)
    if isinstance(route, _DigestRouteResult):
        return route.digest, None
    if isinstance(route, _DigestRouteDegrade):
        return None, _DEGRADE_REASON_RUNNER_UNAVAILABLE
    digest_result = _committed_scope_digest_value(repo, "HEAD")
    if isinstance(digest_result, _CommittedScopeDigest):
        return digest_result.digest, None
    return None, _DEGRADE_REASON_INTERPRETER_UNAVAILABLE


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
            # feature_id is known at print time on the normal path (it is the
            # caller-supplied argument) -- fill it verbatim, mirroring
            # `_notify_feature_end_unmissable`'s `--feature-id {feature_id}`
            # (line 179). Only the genuinely-unknown-at-print-time case (no
            # feature_id resolved at all) falls back to an explained
            # placeholder -- never the bare literal "None".
            feature_id_display = (
                feature_id
                if feature_id is not None
                else "<feature-id> (substitute the feature id you are committing)"
            )
            sys.stderr.write(
                f"WARNING: des commit-slice found NO APPROVED ATReviewVerdict "
                f"record for {slice_id} -- the Reviewed-by: trailer is OMITTED "
                f"for this slice (records-of-truth omission, not a silent pass). "
                f"WHY: no `des record-at-review-verdict ... --verdict APPROVED` "
                f"record is keyed to this slice in "
                f".nwave/telemetry/atdd-pure/ (the AT-review was never recorded, "
                f"or the ledger is unreadable). HOW: after the acceptance-designer "
                f"reviewer APPROVES, run `des record-at-review-verdict "
                f"--feature-id {feature_id_display} --slice-id {slice_id} "
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

    try:
        malformed = _stage(repo, args.paths, args.all)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit({"event": "MalformedInput", "error": f"git staging failed: {exc}"})
        return 2
    if malformed is not None:
        _emit(malformed)
        return 2

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
    if build_tier_exit_verdict(repo, regression_test_file=regression_test_file) != 0:
        return 1

    # Examine-verdict exit check (evolution-plan P1.2 -- User-Examiner wiring):
    # the SAME chokepoint as the build-tier check above. A no-op unless ARMED
    # for this feature (see the module-level note); when armed, EVERY entering
    # slice-id must carry a fresh PASS ExamineVerdict or the commit is refused
    # fail-closed BEFORE the placeholder commit lands.
    if args.feature_id is not None:
        for slice_id in extract_slice_ids(message):
            examine_rejection = check_examine_verdict(repo, args.feature_id, slice_id)
            if examine_rejection is not None:
                exit_code = examine_rejection.pop("exit_code")
                _emit(examine_rejection)
                assert isinstance(exit_code, int)
                return exit_code

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
    digest, degrade_reason = _committed_scope_digest_or_degrade_reason(repo)
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

    # Step 6 (GDP-1 fold-in): guarantee the SliceCommitVerified record itself,
    # so a folded lean-cycle commit -- where the SubagentStop hook never fires
    # -- does not orphan its successor's carpaccio-order check. Invokes the
    # SAME canonical verify-then-record `des verify-slice-commit --feature-id`
    # runs (E1 completeness + E2 feature-scoped contract + E3 examine),
    # writing `SliceCommitVerified` IFF all three clear -- byte-identical
    # record shape, no reimplementation (Ale-authorized canonical form).
    # Honesty invariant: a genuine E1/E2/E3 failure writes NO record; the
    # failure is surfaced via the fold-in's own JSON event (emitted before the
    # `SliceCommitted` line below), never silently swallowed. The commit
    # already landed and verified at step 5, so this fold-in never flips
    # commit-slice's own exit code -- its exit semantics stay unchanged.
    # Idempotent by construction: `AtCompletionLedger.verified_slices()` is
    # set-valued, so a later re-run (e.g. the hook, or a stale
    # `des verify-slice-commit`) for an already-verified slice changes nothing
    # observable -- no double-counted verification.
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
        if args.at_kind == "pytest-regression":
            fold_in_argv.extend(
                [
                    "--at-kind",
                    "pytest-regression",
                    "--regression-test-file",
                    args.regression_test_file,
                ]
            )
        _verify_then_record_main(fold_in_argv)

    # Step 7 (deliver-finalize-unmissable slice-01, FIX-A): PURELY ADDITIVE,
    # best-effort-loud last-slice notice. Runs strictly AFTER the commit has
    # already succeeded and verified -- never affects the exit code above.
    if args.feature_id is not None:
        _notify_feature_end_unmissable(repo, args.feature_id)

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
