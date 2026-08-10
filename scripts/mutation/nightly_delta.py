"""Nightly delta mutation testing — pure helpers.

Scope: select the changed, extant, tracked Python files under the configured
source scopes since the last successful same-workflow run; validate that run
is a real ancestor of HEAD; score a mutmut 3.6 `export-cicd-stats` result
conservatively (unresolved mutant statuses never inflate the score); and
render a compact report plus a bounded GitHub issue summary.

All I/O (git, gh, mutmut) is injected by the caller as plain callables/data so
every function here is unit-testable without a git repo, mutmut, or network
access. No function shells out, writes files, or mutates the checkout.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence


DEFAULT_SOURCE_SCOPES: tuple[str, ...] = (
    "src/des/testarch",
    "src/des",
    "scripts/install",
)
DEFAULT_THRESHOLD = 80.0

# mutmut 3.6 status categories that are conclusive, killed-or-survived:
STATUS_KILLED = "killed"
STATUS_SURVIVED = "survived"

# Every other status mutmut's `export-cicd-stats` JSON can report (see
# mutmut.__main__.save_cicd_stats), plus "not_checked" — this module's own
# bucket for the `total - known` unaccounted remainder (parse_cicd_stats).
# None of these may be counted as "killed" (that would inflate the score)
# nor silently dropped from the report (that would hide an infra problem).
INCOMPLETE_STATUSES: frozenset[str] = frozenset(
    {
        "no_tests",
        "skipped",
        "suspicious",
        "timeout",
        "check_was_interrupted_by_user",
        "segfault",
        "not_checked",
    }
)


# ---------------------------------------------------------------------------
# Baseline selection + ancestor validation
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class WorkflowRun:
    """One prior workflow-run record, as returned by the GitHub API."""

    sha: str
    conclusion: str  # "success" | "failure" | ...
    workflow_name: str
    run_number: int


@dataclasses.dataclass(frozen=True)
class BaselineDecision:
    """Outcome of resolving the delta baseline for this run.

    status:
      "ok"           - baseline_sha is a validated ancestor of head_sha.
      "first_run"    - a successful (possibly empty) run query found no prior
                        successful same-workflow run.
      "non_ancestor" - a prior successful run exists but is NOT an ancestor
                        of head_sha (force-push, rebase, history rewrite).

    A FAILED run query is never resolved through this type — the caller must
    treat it as an infrastructure error directly (see run_nightly_delta.py),
    because an unanswered question ("were there prior runs?") is not evidence
    of "there were none". Both non-"ok" statuses here are terminal,
    deterministic, and loud: the caller takes the bounded no-op path and MUST
    NOT fall back to a full-repo or HEAD~1-guessed range.
    """

    status: str
    baseline_sha: str | None
    reason: str


def select_previous_successful_run(
    runs: Sequence[WorkflowRun],
    workflow_name: str,
    exclude_run_number: int | None = None,
) -> WorkflowRun | None:
    """Most recent successful run of the same workflow, excluding the current run.

    Deterministic: ties broken by highest run_number. Runs of other workflows
    or non-"success" conclusions are never eligible baselines.
    """
    candidates = [
        run
        for run in runs
        if run.workflow_name == workflow_name
        and run.conclusion == "success"
        and run.run_number != exclude_run_number
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: run.run_number)


def resolve_baseline(
    runs: Sequence[WorkflowRun],
    workflow_name: str,
    head_sha: str,
    is_ancestor_fn: Callable[[str, str], bool],
    exclude_run_number: int | None = None,
) -> BaselineDecision:
    """Resolve the baseline commit for this delta run from a SUCCESSFULLY queried run list.

    Caller must only invoke this once the run-list query itself is known to
    have succeeded (an empty list from a successful query is a legitimate
    "first_run"; a failed query is not — see BaselineDecision docstring).

    is_ancestor_fn(candidate_sha, head_sha) must answer "is candidate_sha an
    ancestor of (or equal to) head_sha" (e.g. `git merge-base --is-ancestor`).
    """
    previous = select_previous_successful_run(runs, workflow_name, exclude_run_number)
    if previous is None:
        return BaselineDecision(
            status="first_run",
            baseline_sha=None,
            reason=f"no prior successful run of workflow {workflow_name!r}",
        )
    if not is_ancestor_fn(previous.sha, head_sha):
        return BaselineDecision(
            status="non_ancestor",
            baseline_sha=previous.sha,
            reason=(
                f"baseline {previous.sha} from run #{previous.run_number} is not "
                f"an ancestor of head {head_sha} (history rewritten since)"
            ),
        )
    return BaselineDecision(
        status="ok", baseline_sha=previous.sha, reason="validated ancestor"
    )


# ---------------------------------------------------------------------------
# Changed-file selection
# ---------------------------------------------------------------------------


def is_eligible_source_path(
    path: str, source_scopes: Sequence[str] = DEFAULT_SOURCE_SCOPES
) -> bool:
    """True if path is a *.py file rooted under one of the configured scopes."""
    if not path.endswith(".py"):
        return False
    return any(
        path == scope or path.startswith(scope.rstrip("/") + "/")
        for scope in source_scopes
    )


def select_changed_python_files(
    changed_paths: Iterable[str],
    exists_fn: Callable[[str], bool],
    source_scopes: Sequence[str] = DEFAULT_SOURCE_SCOPES,
) -> list[str]:
    """Deterministic (sorted, deduped) list of eligible changed Python files.

    A changed path only qualifies when it is (a) under a configured source
    scope, (b) a *.py file, and (c) still extant on disk — a deleted file has
    nothing left to mutate, so `exists_fn` filters it out even though git diff
    reports it as "changed". Caller supplies `changed_paths` from
    `git diff --name-only --diff-filter=ACMR <baseline>..<head>` (already
    tracked-only by construction of `git diff`) so no separate tracked check
    is needed here.
    """
    eligible = {
        path
        for path in changed_paths
        if is_eligible_source_path(path, source_scopes) and exists_fn(path)
    }
    return sorted(eligible)


# ---------------------------------------------------------------------------
# mutmut 3.6 `export-cicd-stats` parsing — conservative scoring
# ---------------------------------------------------------------------------


def parse_cicd_stats(stats: Mapping[str, object]) -> dict[str, int]:
    """Map a `mutants/mutmut-cicd-stats.json` payload to this module's vocabulary.

    mutmut.__main__.save_cicd_stats writes exactly
    {killed, survived, total, no_tests, skipped, suspicious, timeout,
    check_was_interrupted_by_user, segfault}. Every recognized non-zero key is
    passed through as-is; `total` minus the sum of all recognized keys present
    is added to "not_checked" (never negative) — a conservative catch-all so
    an unrecognized/future mutmut status can never silently vanish into the
    denominator as an implicit kill.
    """
    total = int(stats.get("total", 0) or 0)
    known_keys = (
        STATUS_KILLED,
        STATUS_SURVIVED,
        *sorted(INCOMPLETE_STATUSES - {"not_checked"}),
    )
    counts: dict[str, int] = {}
    known_sum = 0
    for key in known_keys:
        value = stats.get(key)
        if value:
            counts[key] = int(value)
            known_sum += int(value)
    unaccounted = total - known_sum
    if unaccounted > 0:
        counts["not_checked"] = counts.get("not_checked", 0) + unaccounted
    return counts


# ---------------------------------------------------------------------------
# Conservative scoring
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ScoreResult:
    killed: int
    survived: int
    incomplete: Mapping[str, int]
    threshold: float
    score_pct: float | None  # None when there is nothing conclusive to score
    passed: bool
    has_incomplete: bool

    @property
    def scored_total(self) -> int:
        return self.killed + self.survived

    @property
    def incomplete_total(self) -> int:
        return sum(self.incomplete.values())


def compute_score(
    status_counts: Mapping[str, int],
    threshold: float = DEFAULT_THRESHOLD,
) -> ScoreResult:
    """Conservative mutation score: killed / (killed + survived) only.

    Every status in INCOMPLETE_STATUSES (and every unrecognized status) is
    excluded from both numerator and denominator — an unresolved mutant is
    never counted as killed, so it can never inflate the score. Their
    presence is still reported via `has_incomplete`/`incomplete`, which the
    caller must fail loudly on (infrastructure failure), independent of
    whether the conclusive subset clears `threshold`.
    """
    killed = status_counts.get(STATUS_KILLED, 0)
    survived = status_counts.get(STATUS_SURVIVED, 0)
    incomplete = {
        status: count
        for status, count in status_counts.items()
        if status in INCOMPLETE_STATUSES and count
    }
    unknown = {
        status: count
        for status, count in status_counts.items()
        if status not in INCOMPLETE_STATUSES
        and status not in (STATUS_KILLED, STATUS_SURVIVED)
        and count
    }
    # Unrecognized statuses are treated as incomplete too (conservative default:
    # never silently score a mutmut status this module was not written against).
    incomplete = {**incomplete, **unknown}

    scored_total = killed + survived
    score_pct = (100.0 * killed / scored_total) if scored_total else None
    passed = score_pct is not None and score_pct >= threshold
    return ScoreResult(
        killed=killed,
        survived=survived,
        incomplete=incomplete,
        threshold=threshold,
        score_pct=score_pct,
        passed=passed,
        has_incomplete=bool(incomplete),
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RunReport:
    """Full outcome of one nightly-delta invocation, ready to render.

    Exactly one of (noop_reason, infrastructure_error, score) is set:
      - noop_reason set          -> successful bounded no-op (exit 0).
      - infrastructure_error set -> infra failure (mutmut/query/stats broke).
      - score set                -> a real conclusive delta run completed.
    """

    decision: BaselineDecision
    changed_files: tuple[str, ...]
    score: ScoreResult | None = None
    noop_reason: str | None = None
    infrastructure_error: str | None = None


def build_noop_report(decision: BaselineDecision) -> RunReport:
    """Bounded no-op report: no baseline / non-ancestor baseline / empty diff.

    Always a SUCCESSFUL run (exit 0) — the absence of a valid delta scope is
    not a failure, it is the expected steady state on the first run and on
    any diff with zero eligible changed files. Never triggers a full-repo run.
    """
    return RunReport(
        decision=decision,
        changed_files=(),
        noop_reason=decision.reason,
    )


def build_scored_report(
    decision: BaselineDecision,
    changed_files: Sequence[str],
    score: ScoreResult,
) -> RunReport:
    return RunReport(decision=decision, changed_files=tuple(changed_files), score=score)


def build_infrastructure_report(
    decision: BaselineDecision,
    changed_files: Sequence[str],
    reason: str,
) -> RunReport:
    """A run that could not reach a trustworthy score: query/mutmut/stats broke.

    Never coerced into a no-op or a (necessarily empty) score — infrastructure
    failure is its own terminal class so it cannot be silently swallowed as a
    green run.
    """
    return RunReport(
        decision=decision,
        changed_files=tuple(changed_files),
        infrastructure_error=reason,
    )


def render_report(report: RunReport) -> str:
    """Compact, deterministic markdown — full evidence, no prose padding."""
    lines = [
        "# Nightly delta mutation report",
        "",
        f"- baseline status: `{report.decision.status}`",
        f"- baseline sha: `{report.decision.baseline_sha or 'n/a'}`",
    ]
    if report.infrastructure_error is not None:
        lines += [
            f"- outcome: infrastructure failure (`{report.infrastructure_error}`)",
            f"- changed eligible files: {len(report.changed_files)}",
        ]
        return "\n".join(lines) + "\n"
    if report.score is None:
        lines += [
            f"- outcome: no-op (`{report.noop_reason}`)",
            f"- changed eligible files: {len(report.changed_files)}",
        ]
        return "\n".join(lines) + "\n"

    score = report.score
    score_str = f"{score.score_pct:.1f}%" if score.score_pct is not None else "n/a"
    lines += [
        f"- changed eligible files: {len(report.changed_files)}",
        *[f"  - `{f}`" for f in report.changed_files],
        f"- killed: {score.killed}",
        f"- survived: {score.survived}",
        f"- score: {score_str} (threshold {score.threshold:.0f}%)",
        f"- threshold met: {score.passed}",
        f"- incomplete mutants: {score.incomplete_total}",
    ]
    if score.incomplete:
        lines += [
            f"  - `{status}`: {count}"
            for status, count in sorted(score.incomplete.items())
        ]
    return "\n".join(lines) + "\n"


def bounded_issue_summary(report: RunReport, max_files: int = 10) -> str:
    """Short GitHub-issue body: enough to triage, never the full mutant list."""
    lines = [
        f"Baseline: `{report.decision.status}` (`{report.decision.baseline_sha or 'n/a'}`)"
    ]
    if report.infrastructure_error is not None:
        lines.append(f"Infrastructure failure: {report.infrastructure_error}")
        if report.changed_files:
            shown = list(report.changed_files[:max_files])
            lines.append(f"Changed files ({len(report.changed_files)}):")
            lines += [f"- `{f}`" for f in shown]
        return "\n".join(lines)
    if report.score is None:
        lines.append(f"No-op run: {report.noop_reason}")
        return "\n".join(lines)

    score = report.score
    score_str = f"{score.score_pct:.1f}%" if score.score_pct is not None else "n/a"
    lines.append(
        f"Score {score_str} / threshold {score.threshold:.0f}% — killed {score.killed}, survived {score.survived}"
    )
    if score.has_incomplete:
        detail = ", ".join(
            f"{status}={count}" for status, count in sorted(score.incomplete.items())
        )
        lines.append(f"Incomplete/infrastructure statuses (not scored): {detail}")
    shown = list(report.changed_files[:max_files])
    lines.append(f"Changed files ({len(report.changed_files)}):")
    lines += [f"- `{f}`" for f in shown]
    if len(report.changed_files) > max_files:
        lines.append(f"- ... and {len(report.changed_files) - max_files} more")
    return "\n".join(lines)


def bounded_results_excerpt(results_text: str, max_lines: int = 20) -> str:
    """First `max_lines` of `mutmut results` output, for the issue body only.

    The full text always goes to the uploaded artifact (mutation-results.txt);
    this excerpt exists solely to keep the GitHub issue body bounded.
    """
    lines = results_text.splitlines()
    shown = lines[:max_lines]
    body = "\n".join(shown)
    if len(lines) > max_lines:
        body += f"\n... and {len(lines) - max_lines} more line(s), see the uploaded artifact"
    return body


def issue_dedup_title(workflow_name: str) -> str:
    """Stable, singular issue title — one open issue per workflow, ever updated."""
    return f"[{workflow_name}] nightly mutation delta below threshold"


# ---------------------------------------------------------------------------
# Failure classification (score-threshold vs. infrastructure)
# ---------------------------------------------------------------------------


def classify_failure(report: RunReport) -> str | None:
    """None when green; otherwise the failure class the caller must exit non-zero on.

    "infrastructure" is checked first (explicit infrastructure_error, or a
    scored run with incomplete mutants) so the evidence for the more serious
    class is never masked by a plain score-threshold message.
    """
    if report.infrastructure_error is not None:
        return "infrastructure"
    if report.score is None:
        return None
    if report.score.has_incomplete:
        return "infrastructure"
    if not report.score.passed:
        return "below_threshold"
    return None
