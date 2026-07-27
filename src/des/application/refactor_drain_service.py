"""RefactorDrainService -- per-item pile-drain lifecycle orchestration.

Composition root (application layer) for ``des refactor`` (ADR-SWARM-001).
CREATE_NEW per feature-delta des-refactor-fixer-swarm Reuse Analysis. This is
the ONE application service the CLI (``des.cli.refactor``) and the acceptance
tests both drive -- the Layer-3-composition driving surface (Mandate 13) for
every slice-01 AT except the single subprocess walking-skeleton.

``drain_one`` is the walking-skeleton's single driving seam: probe every
driven port (Earned Trust, principle 13) -> worktree-from-tip (D1) ->
venv-provision (D2) -> render the user-editable prompt template + invoke the
agent (D6/D7) -> green-to-green (D3) -> merge-into-clean-branch, which itself
guards ``.venv`` hygiene and the dirty-tree refusal (D4/D5) -> mandatory
cleanup gated on a CONFIRMED merge only (D5/D6) -> pile-move.

``drain_batch`` is slice-02's concurrent-drain seam: every item's
worktree-creation, venv-provisioning, and agent dispatch run on their own
thread (the LLM reasoning lanes -- meant to scale concurrently, design doc
Â§9); the green-to-green verification run and merge-back for each item are
serialized behind a ``MergeLockPort`` (the shared box's serial fast+impacted
run-rate is the throughput ceiling, never the agent count) -- and the pile
file rewrite (``move_item`` touches the SAME two files for every item) is
serialized behind its own in-process guard, since it is shared mutable state
the port itself does not otherwise protect.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.earned_verdict import TestRun, test_run_from_envelope
from des.domain.refactor.entry_gate import (
    ENTRY_GATE_VERDICT_MISSING,
    EntryGateVerdict,
    classify_entry_gate,
)
from des.domain.refactor.green_to_green import (
    GreenToGreenVerdict,
    classify_green_to_green,
)
from des.domain.refactor.paradigm_select import select_paradigm_lens
from des.domain.refactor.pile import (
    PileItem,
    PileUnreadable,
    annotate_item_escalated,
    move_item,
    parse_pile_report,
)
from des.domain.refactor.prompt_template import (
    DEFAULT_TEMPLATE_PATH,
    DEFAULT_TEMPLATE_TEXT,
    load_prompt_template,
    render_prompt,
)
from des.runtime.interpreter import des_spawn


if TYPE_CHECKING:
    from des.ports.driven_ports.agent_invocation_port import AgentInvocationPort
    from des.ports.driven_ports.at_completion_ledger_port import (
        AtCompletionLedgerPort,
    )
    from des.ports.driven_ports.env_provision_port import EnvProvisionPort
    from des.ports.driven_ports.git_worktree_port import GitWorktreePort
    from des.ports.driven_ports.impacted_test_selector_port import (
        ImpactedTestSelectorPort,
    )
    from des.ports.driven_ports.merge_lock_port import MergeLockPort

#: The dedicated clean integration branch the drain loop merges into by
#: default (D4/D5) -- never the operator's own working tree.
DEFAULT_INTEGRATION_BRANCH = "refactor-integration"

_FEATURE_ID = "des-refactor-fixer-swarm"
_SLICE_ID = "slice-01"
_DRAINED_EVENT = "RefactorItemDrained"
_ESCALATED_EVENT = "RefactorItemEscalated"

_TEST_SOURCE_ENVELOPE = "envelope"
_TEST_SCOPE_FAST_IMPACTED = "fast+impacted"

#: The entry-gate verdicts that PERMIT the existing green-to-green + merge
#: path to proceed (D9) -- every OTHER recognized verdict, and a missing
#: verdict, refuses the merge. Named once here because two readers need the
#: same answer: ``_entry_gate_refusal`` (which enforces it) and the CLI's
#: operator-facing entry-gate refusal (which TEACHES it). A second hand-typed
#: copy is exactly the drift that produced the silent-no-op defect this
#: constant's introduction accompanies.
MERGE_PERMITTING_ENTRY_GATE_VERDICTS: tuple[EntryGateVerdict, ...] = (
    EntryGateVerdict.REFACTOR_SAFE,
    EntryGateVerdict.MECHANICAL_RENAME_EXEMPT,
)

_TESTS_RED_REASON = "MergeBlockedTestsRed"
_MIKADO_ESCALATION_REASON = "MikadoEscalation"
_NO_TEST_NET_REASON = "EntryGateNoTestNet"
_PROMPT_FILENAME = ".refactor-prompt.md"
_ENVELOPE_FILENAME = "test-result.json"

#: The pre-agent baseline leg's stand-in when nothing has changed yet to
#: narrow a test scope against (BUGFIX 2026-07-26, [[impacted-test-selector-
#: selects-everything-and-its-premise-is-false]]). ``runner`` self-documents
#: in any ledger/DrainResult reader as NOT an observed run -- no pytest
#: process was ever spawned for it, so its passed/failed/exit_code carry no
#: information about this worktree. Safe because
#: ``classify_green_to_green`` decides SAFE/UNSAFE from the AFTER run's
#: failure count alone and never reads ``before``.
_UNOBSERVED_PLACEHOLDER_RUN = TestRun(
    runner="unobserved-placeholder", passed=0, failed=0, exit_code=0
)


@dataclass(frozen=True)
class DrainResult:
    """Observable outcome of draining one pile item (Mandate 8 port-exposed
    universe -- every field here is what a slice-01 AT's ``Then`` asserts on).
    """

    drained: bool
    item_id: str | None
    merged: bool
    merge_blocked_reason: str | None = None
    worktree_head_sha_at_creation: str | None = None
    worktree_removed: bool = False
    branch_deleted: bool = False
    integration_removed: bool = False
    test_target_scope: str | None = None
    test_result_source: str | None = None
    reason: str | None = None
    parsed_count: int = 0
    skipped_lines: tuple[str, ...] = ()

    @property
    def refusal_reason(self) -> str | None:
        """The ONE blocking reason a non-drained outcome must be reported by --
        derived here, once, from whichever field carried it.

        ``reason`` carries a refusal raised before/around the drain (paradigm,
        startup probe, worktree creation); ``merge_blocked_reason`` carries one
        raised at the merge or entry gate. Both reporters in ``des.cli.refactor``
        read THIS accessor: ``_report`` used to branch on ``reason`` alone and
        fell through to a bare ``return 0`` for an item blocked with its reason
        in ``merge_blocked_reason``, while ``_report_batch`` hand-maintained its
        own ``reason or merge_blocked_reason`` derivation. That drift WAS the
        silent-no-op defect (fix-drain-single-item-silent-noop) -- one accessor
        leaves no second copy to drift again.

        ``None`` means, and only means, "nothing refused this outcome".
        """
        return self.reason or self.merge_blocked_reason


@dataclass(frozen=True)
class BatchDrainResult:
    """Observable outcome of draining N DISJOINT pile items concurrently
    (slice-02 Mandate 8 port-exposed universe) -- one ``DrainResult`` per
    item, in the order each item's critical section was granted the merge
    lock (the SAME conservation contract as ``drain_one``'s single-item
    result, extended to a batch: every seeded item MUST appear exactly once,
    success or refusal alike -- an item vanishing from this tuple entirely
    is the silent-drop defect the charter's negative oracle names)."""

    results: tuple[DrainResult, ...]

    @property
    def drained_item_ids(self) -> tuple[str, ...]:
        """The subset that actually merged -- the population this batch's
        drain-count is measured against (COUNT/PARTITION closure: always
        read against ``len(self.results)``, never a bare integer)."""
        return tuple(
            result.item_id
            for result in self.results
            if result.drained and result.item_id
        )


class RefactorDrainService:
    """Application-layer composition root: the per-item drain lifecycle."""

    def __init__(
        self,
        *,
        git_worktree: GitWorktreePort,
        agent_invocation: AgentInvocationPort,
        env_provision: EnvProvisionPort,
        impacted_test_selector: ImpactedTestSelectorPort,
        ledger: AtCompletionLedgerPort,
    ) -> None:
        self._git_worktree = git_worktree
        self._agent_invocation = agent_invocation
        self._env_provision = env_provision
        self._impacted_test_selector = impacted_test_selector
        self._ledger = ledger
        # The per-item worktree/branch state currently mid-drain, so a
        # process-wide SIGINT/SIGTERM handler (des.cli.refactor._abort_on_signal)
        # can clean it up from OUTSIDE the drain call frame -- the parent-signal
        # path drain_one's own ``except BaseException`` cleanup cannot cover
        # (SIGTERM raises no exception to unwind it). A set (not one slot) because
        # drain_batch runs several items concurrently; each drains on its own
        # thread while the handler runs on the main one. Cleared on every exit
        # path so it only ever names items a cleanup still owes.
        self._in_flight_lock = threading.Lock()
        self._in_flight: set[tuple[Path, Path, str]] = set()

    def drain_one(
        self,
        *,
        repo: Path,
        pile_path: Path,
        paid_path: Path,
        agent_cmd: str,
        integration_branch: str = DEFAULT_INTEGRATION_BRANCH,
        prompt_template_path: Path | None = None,
    ) -> DrainResult:
        """Drain exactly ONE pending pile item end to end."""
        report = parse_pile_report(pile_path)
        if report.unreadable is not None:
            # Checked FIRST, ahead of every other startup probe: a pile that
            # cannot be read is the earliest reason this run never started,
            # and reporting a later probe instead would name the wrong cause.
            return self._refused(
                None, reason=_unreadable_pile_reason(pile_path, report.unreadable)
            )
        items = report.items
        if not items:
            return DrainResult(
                drained=False,
                item_id=None,
                merged=False,
                parsed_count=len(items),
                skipped_lines=report.skipped_lines,
            )
        item = items[0]

        paradigm_selection = select_paradigm_lens(item.paradigm)
        if not paradigm_selection.accepted:
            return self._refused(item.item_id, reason=paradigm_selection.reason)

        probe_failure_reason = self._probe_failure_reason(repo, agent_cmd)
        if probe_failure_reason is not None:
            return self._refused(item.item_id, reason=probe_failure_reason)

        branch = f"refactor-{item.item_id}"
        worktree_path = repo.parent / f"{repo.name}-refactor-{item.item_id}"
        try:
            handle = self._git_worktree.create_worktree_from_tip(
                repo, branch, worktree_path
            )
        except subprocess.CalledProcessError as exc:
            return self._refused(
                item.item_id,
                reason=_worktree_creation_failure_message(branch, exc),
            )

        # Registered the instant a worktree exists, forgotten on EVERY exit
        # (the outer try/finally) so a SIGINT/SIGTERM handler can find and clean
        # up exactly the items a cleanup still owes -- the parent-signal path
        # the ``except BaseException`` below cannot cover, because SIGTERM
        # terminates the process without unwinding it at all.
        self._register_in_flight(repo, handle.path, branch)
        try:
            try:
                self._env_provision.provision(handle.path)

                before = self._run_tests(handle.path)
                agent_stdout = self._dispatch_agent(
                    repo, item, handle.path, agent_cmd, prompt_template_path
                )

                entry_gate_refusal = self._entry_gate_refusal(
                    repo,
                    handle.path,
                    branch,
                    item.item_id,
                    agent_stdout,
                    pile_path,
                    handle.head_sha,
                )
                if entry_gate_refusal is not None:
                    return entry_gate_refusal

                changed_paths = self._git_worktree.changed_paths_since(
                    handle.path, handle.head_sha
                )
                after = self._run_tests(handle.path, changed_paths)

                outcome = classify_green_to_green(before, after)
                if outcome.verdict != GreenToGreenVerdict.SAFE:
                    return self._refused_after_cleanup(
                        repo,
                        handle.path,
                        branch,
                        item.item_id,
                        _TESTS_RED_REASON,
                        handle.head_sha,
                    )

                merge_result = self._git_worktree.merge_into(
                    repo, integration_branch, branch
                )
                if not merge_result.merged:
                    return self._refused(
                        item.item_id, merge_result.blocked_reason, handle.head_sha
                    )
            except BaseException:
                self._cleanup_worktree_and_branch(repo, handle.path, branch)
                raise

            self._git_worktree.remove_worktree(repo, handle.path)
            self._git_worktree.delete_branch(repo, branch)
            integration_removed = self._git_worktree.land_and_remove_integration(
                repo, integration_branch
            )
            move_item(pile_path, paid_path, item.item_id)
            self._ledger.append_gate_event(
                _DRAINED_EVENT, _SLICE_ID, feature_id=_FEATURE_ID
            )

            return DrainResult(
                drained=True,
                item_id=item.item_id,
                merged=True,
                worktree_head_sha_at_creation=handle.head_sha,
                worktree_removed=True,
                branch_deleted=True,
                integration_removed=integration_removed,
                test_target_scope=_TEST_SCOPE_FAST_IMPACTED,
                test_result_source=_TEST_SOURCE_ENVELOPE,
            )
        finally:
            self._forget_in_flight(repo, handle.path, branch)

    def drain_batch(
        self,
        *,
        repo: Path,
        pile_path: Path,
        paid_path: Path,
        agent_cmd: str,
        integration_branch: str = DEFAULT_INTEGRATION_BRANCH,
        max_parallel: int = 2,
        merge_lock: MergeLockPort | None = None,
    ) -> BatchDrainResult:
        """Drain ALL pending DISJOINT pile items CONCURRENTLY: each item gets
        its own worktree-from-tip + its own isolated venv, provisioned and
        dispatched in parallel (up to ``max_parallel`` lanes); the
        green-to-green verification run + merge-back for each item is
        serialized behind ``merge_lock`` (design doc Â§9 -- the shared box's
        serial fast+impacted run-rate is the throughput ceiling, never the
        agent count).
        """
        report = parse_pile_report(pile_path)
        if report.unreadable is not None:
            # The SAME refusal ``drain_one`` raises, for the same cause: an
            # unreadable pile is a property of the --pile argument, not of
            # how many lanes were asked for. One refusal, item_id ``None``
            # (no item was ever read to attribute it to), which the CLI's
            # shared ``_refusal_line`` renders identically on either path.
            return BatchDrainResult(
                results=(
                    self._refused(
                        None,
                        reason=_unreadable_pile_reason(pile_path, report.unreadable),
                    ),
                )
            )
        items = report.items
        if not items:
            return BatchDrainResult(results=())

        probe_failure_reason = self._probe_failure_reason(repo, agent_cmd)
        if probe_failure_reason is not None:
            return BatchDrainResult(
                results=tuple(
                    self._refused(item.item_id, reason=probe_failure_reason)
                    for item in items
                )
            )

        lock = merge_lock if merge_lock is not None else _default_merge_lock()
        pile_guard = threading.Lock()

        def _drain_concurrently(item: PileItem) -> DrainResult:
            branch = f"refactor-{item.item_id}"
            worktree_path = repo.parent / f"{repo.name}-refactor-{item.item_id}"
            try:
                handle = self._git_worktree.create_worktree_from_tip(
                    repo, branch, worktree_path
                )
            except subprocess.CalledProcessError as exc:
                return self._refused(
                    item.item_id,
                    reason=_worktree_creation_failure_message(branch, exc),
                )

            try:
                self._env_provision.provision(handle.path)

                before = self._run_tests(handle.path)
                self._dispatch_agent(repo, item, handle.path, agent_cmd, None)

                lock.acquire(item.item_id)
            except BaseException:
                self._cleanup_worktree_and_branch(repo, handle.path, branch)
                raise

            try:
                changed_paths = self._git_worktree.changed_paths_since(
                    handle.path, handle.head_sha
                )
                after = self._run_tests(handle.path, changed_paths)
                outcome = classify_green_to_green(before, after)
                if outcome.verdict != GreenToGreenVerdict.SAFE:
                    return self._refused_after_cleanup(
                        repo,
                        handle.path,
                        branch,
                        item.item_id,
                        _TESTS_RED_REASON,
                        handle.head_sha,
                    )

                merge_result = self._git_worktree.merge_into(
                    repo, integration_branch, branch
                )
                if not merge_result.merged:
                    self._git_worktree.remove_worktree(repo, handle.path)
                    self._git_worktree.delete_branch(repo, branch)
                    return self._refused(
                        item.item_id, merge_result.blocked_reason, handle.head_sha
                    )

                self._git_worktree.remove_worktree(repo, handle.path)
                self._git_worktree.delete_branch(repo, branch)
                with pile_guard:
                    move_item(pile_path, paid_path, item.item_id)
                self._ledger.append_gate_event(
                    _DRAINED_EVENT, _SLICE_ID, feature_id=_FEATURE_ID
                )
                return DrainResult(
                    drained=True,
                    item_id=item.item_id,
                    merged=True,
                    worktree_head_sha_at_creation=handle.head_sha,
                    worktree_removed=True,
                    branch_deleted=True,
                    test_target_scope=_TEST_SCOPE_FAST_IMPACTED,
                    test_result_source=_TEST_SOURCE_ENVELOPE,
                )
            finally:
                lock.release(item.item_id)

        with ThreadPoolExecutor(max_workers=max(max_parallel, 1)) as executor:
            futures = [executor.submit(_drain_concurrently, item) for item in items]
            results = tuple(future.result() for future in futures)

        return BatchDrainResult(results=results)

    # -- internal: startup probes (Earned Trust, principle 13) --------------

    def _probe_failure_reason(self, repo: Path, agent_cmd: str) -> str | None:
        """Which startup probe failed, named WHAT/WHY/HOW -- never a bare bool
        (Earned Trust principle 13; the standing what/why/how mandate)."""
        if self._git_worktree.is_linked_worktree(repo):
            return (
                "the target git repository is a LINKED WORKTREE -- des refactor "
                "creates worktrees and moves branches/HEAD, and here those "
                "operations would mutate the SHARED common .git and corrupt "
                "your other worktrees' refs and HEAD. Fix: run des refactor "
                "from the repository's MAIN checkout (where `git rev-parse "
                "--git-common-dir` equals `--git-dir`), or point it at a "
                "standalone clone."
            )
        if not self._git_worktree.probe(repo):
            return (
                "the git/worktree startup probe failed -- this repo is not a "
                "usable git repository (or `git worktree` is unavailable "
                "here). Fix: run des refactor from inside a real, "
                "initialised git repository."
            )
        if not self._agent_invocation.probe(agent_cmd):
            return (
                f"the --agent-cmd startup probe failed -- {agent_cmd!r}'s "
                "executable could not be resolved on PATH. Fix: point "
                "--agent-cmd at a real, resolvable executable."
            )
        if not self._env_provision.probe():
            return (
                "the env-provisioning startup probe failed -- `uv` could not "
                "be resolved on PATH. Fix: install uv (or ensure it is on "
                "PATH) before running des refactor."
            )
        return None

    def _refused(
        self,
        item_id: str | None,
        merge_blocked_reason: str | None = None,
        worktree_head_sha: str | None = None,
        *,
        reason: str | None = None,
    ) -> DrainResult:
        scope = _TEST_SCOPE_FAST_IMPACTED if worktree_head_sha else None
        source = _TEST_SOURCE_ENVELOPE if worktree_head_sha else None
        return DrainResult(
            drained=False,
            item_id=item_id,
            merged=False,
            merge_blocked_reason=merge_blocked_reason,
            worktree_head_sha_at_creation=worktree_head_sha,
            test_target_scope=scope,
            test_result_source=source,
            reason=reason,
        )

    def _refused_after_cleanup(
        self,
        repo: Path,
        worktree_path: Path,
        branch: str,
        item_id: str | None,
        merge_blocked_reason: str | None = None,
        worktree_head_sha: str | None = None,
    ) -> DrainResult:
        """Same refusal shape as ``_refused``, for a refusal that fires AFTER
        a worktree already exists (D9 entry-gate refusals): removes the
        worktree and deletes the branch before returning, so the refusal
        leaves the repository exactly as clean as a red-tests or
        merge-failure-then-cleanup refusal already does (bugfix-refactor-
        entry-gate-worktree-leak -- an entry-gate refusal must never strand a
        worktree/branch the way a bare ``_refused`` call would)."""
        self._git_worktree.remove_worktree(repo, worktree_path)
        self._git_worktree.delete_branch(repo, branch)
        result = self._refused(item_id, merge_blocked_reason, worktree_head_sha)
        return replace(result, worktree_removed=True, branch_deleted=True)

    def _cleanup_worktree_and_branch(
        self, repo: Path, worktree_path: Path, branch: str
    ) -> None:
        """Best-effort, idempotent-safe cleanup for the mid-drain exception
        guard (bugfix-drain-cleanup-on-every-exit): swallows a failure to
        remove/delete state a refusal branch already cleaned up on this same
        path (e.g. ``_refused_after_cleanup`` ran before the exception
        propagated), so a double-cleanup attempt here never masks the
        original exception this guard re-raises."""
        try:
            self._git_worktree.remove_worktree(repo, worktree_path)
        except Exception:
            pass
        try:
            self._git_worktree.delete_branch(repo, branch)
        except Exception:
            pass

    # -- internal: in-flight tracking for the operator-abort path ------------

    def _register_in_flight(self, repo: Path, worktree_path: Path, branch: str) -> None:
        with self._in_flight_lock:
            self._in_flight.add((repo, worktree_path, branch))

    def _forget_in_flight(self, repo: Path, worktree_path: Path, branch: str) -> None:
        with self._in_flight_lock:
            self._in_flight.discard((repo, worktree_path, branch))

    def cleanup_in_flight(self) -> None:
        """Remove the worktree/branch of every item currently mid-drain.

        The seam a process-wide SIGINT/SIGTERM handler
        (``des.cli.refactor._abort_on_signal``) calls so an operator-initiated
        abort leaves the repository exactly as clean as a tests-red or
        mid-drain-crash refusal already does -- the parent-signal path
        ``drain_one``'s own ``except BaseException`` cleanup cannot reach,
        because SIGTERM terminates the process without unwinding it.

        Reuses the best-effort, idempotent ``_cleanup_worktree_and_branch`` (a
        double cleanup on an already-removed worktree is a no-op), so it is safe
        to run even while ``drain_one``'s own unwinding cleanup races it on the
        same item. A SNAPSHOT is taken under the lock and the git work runs
        OUTSIDE it, so a git subprocess never runs while the lock is held. The
        merge-blocked path preserves its unmerged branch for human recovery
        (``test_an_unmerged_branch_is_never_deleted_after_a_failed_merge``) and
        FORGETS the item on return (the outer ``finally``), precisely so a later
        abort's cleanup never deletes the branch that path deliberately left.
        """
        with self._in_flight_lock:
            pending = list(self._in_flight)
        for repo, worktree_path, branch in pending:
            self._cleanup_worktree_and_branch(repo, worktree_path, branch)
            self._forget_in_flight(repo, worktree_path, branch)

    # -- internal: entry gate (D9, slice-04) ---------------------------------

    def _entry_gate_refusal(
        self,
        repo: Path,
        worktree_path: Path,
        branch: str,
        item_id: str,
        agent_stdout: str,
        pile_path: Path,
        worktree_head_sha: str,
    ) -> DrainResult | None:
        """Classify the agent's own self-reported entry-gate verdict BEFORE
        the green-to-green/merge step (D9). Returns a refusal ``DrainResult``
        when the item must not proceed to merge, or ``None`` to let the
        existing green-to-green + merge path (slice-01) continue. Every
        refusal branch cleans up the worktree/branch it was handed
        (``_refused_after_cleanup``) -- unlike the pre-worktree refusals
        above (paradigm/probe), a worktree already exists by the time the
        entry gate runs."""
        verdict = classify_entry_gate(agent_stdout)
        if verdict is None:
            return self._refused_after_cleanup(
                repo,
                worktree_path,
                branch,
                item_id,
                ENTRY_GATE_VERDICT_MISSING,
                worktree_head_sha,
            )
        if verdict in MERGE_PERMITTING_ENTRY_GATE_VERDICTS:
            return None
        if verdict == EntryGateVerdict.MIKADO_ESCALATION:
            annotate_item_escalated(pile_path, item_id)
            self._ledger.append_gate_event(
                _ESCALATED_EVENT, _SLICE_ID, feature_id=_FEATURE_ID
            )
            return self._refused_after_cleanup(
                repo,
                worktree_path,
                branch,
                item_id,
                _MIKADO_ESCALATION_REASON,
                worktree_head_sha,
            )
        return self._refused_after_cleanup(
            repo, worktree_path, branch, item_id, _NO_TEST_NET_REASON, worktree_head_sha
        )

    # -- internal: prompt rendering + agent dispatch (D6/D7) -----------------

    def _dispatch_agent(
        self,
        repo: Path,
        item: PileItem,
        worktree: Path,
        agent_cmd: str,
        prompt_template_path: Path | None,
    ) -> str:
        template_text = self._load_template_text(repo, prompt_template_path)
        rendered = render_prompt(
            template_text,
            item_id=item.item_id,
            defect=item.defect,
            proposed_solution=item.proposed_solution,
            paradigm=item.paradigm,
            worktree=worktree,
        )
        prompt_path = worktree / _PROMPT_FILENAME
        prompt_path.write_text(rendered, encoding="utf-8")
        result = self._agent_invocation.invoke(agent_cmd, prompt_path, worktree)
        return result.stdout

    def _load_template_text(self, repo: Path, override: Path | None) -> str:
        path = override if override is not None else repo / DEFAULT_TEMPLATE_PATH
        if path.is_file():
            return load_prompt_template(path)
        return DEFAULT_TEMPLATE_TEXT

    # -- internal: green-to-green test execution (D3) ------------------------

    def _run_tests(
        self, worktree: Path, changed_paths: tuple[str, ...] = ()
    ) -> TestRun:
        """Run the fast+impacted test scope for ``worktree`` -- or, for the
        pre-agent baseline call, DON'T run anything at all.

        ``changed_paths`` is empty for the pre-agent baseline call (nothing
        has changed yet) and the real diff for the post-agent call (see the
        ``changed_paths_since`` call at each call site) -- BUGFIX
        [[impacted-test-selector-selects-everything-and-its-premise-is-
        false]]: the selector used to always receive ``()`` regardless, so
        even a correct heuristic had nothing to narrow with.

        BUGFIX (2026-07-26, same pile item, follow-on): an empty
        ``changed_paths`` also means the selector HONESTLY falls back to the
        whole repo (``narrowed=False`` -- there is nothing to narrow
        against yet), and running the whole suite serially for that baseline
        leg measured over the drain's own 2700s spawn timeout on this box --
        a hard crash, not just slow, on literally the first item. The fix is
        not a bigger timeout or a hardcoded "fast tier" directory (rejected:
        no fixed path is generic across the arbitrary target repos this tool
        ships to, and genericity is a standing mandate here) -- it is to
        never spawn pytest for this leg at all. ``classify_green_to_green``
        (``des.domain.refactor.green_to_green``) computes its SAFE/UNSAFE
        verdict from the AFTER run's failure count ONLY -- its own docstring
        says so explicitly -- so a baseline this cheap and this correct do
        not conflict: the real baseline was never consulted by the verdict,
        so there is nothing lost by not running it.

        IMPORTANT for whoever reads ``DrainResult``/the ledger later: for
        this pre-agent call, the returned ``TestRun`` (``runner=
        "unobserved-placeholder"``) is a PLACEHOLDER, not an observed
        baseline -- no test ever ran, nothing was verified, its
        passed/failed/exit_code fields are not a measurement of this
        worktree. Do not read it as "the suite was green before the fix".
        """
        if not changed_paths:
            # Nothing has changed yet -- there is nothing a selector could
            # narrow against, and classify_green_to_green never reads this
            # leg's counts. Skip the selector call AND the real pytest spawn
            # entirely: this is not a cheaper baseline, it is no baseline.
            return _UNOBSERVED_PLACEHOLDER_RUN
        selection = self._impacted_test_selector.select(worktree, changed_paths)
        target = selection.targets[0]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / _ENVELOPE_FILENAME
            des_spawn(
                None,
                "des.cli.run_tests",
                "--target",
                target,
                "--out",
                str(out_path),
                cwd=worktree,
                capture_output=True,
                text=True,
                check=False,
            )
            envelope = json.loads(out_path.read_text(encoding="utf-8"))
        return test_run_from_envelope(envelope)


def _worktree_creation_failure_message(
    branch: str, exc: subprocess.CalledProcessError
) -> str:
    """WHAT/WHY/HOW for a failed `git worktree add` -- never a raw
    ``subprocess.CalledProcessError`` traceback escapes to the operator
    (the standing what/why/how mandate)."""
    stderr = (exc.stderr or "").strip()
    why = stderr if stderr else "git reported a non-zero exit status"
    return (
        f"worktree creation failed for branch {branch!r} -- git said: {why}. "
        f"Fix: ensure branch {branch!r} does not already exist in this repo "
        "(delete it, or re-run des refactor once it is free), then try again."
    )


def _unreadable_pile_reason(pile_path: Path, unreadable: PileUnreadable) -> str:
    """WHAT/WHY/HOW for a ``--pile`` that could not be read as a pile file --
    the sibling of ``_probe_failure_reason``'s ``--agent-cmd`` refusal, for
    the OTHER argument, and deliberately worded as a refusal to LOOK rather
    than a finding ABOUT the pile: nothing was read, so nothing about the
    maintainer's tech debt is known here (the standing what/why/how mandate).
    """
    return (
        f"the --pile startup probe failed -- {str(pile_path)!r} could not be "
        f"read as a pile file ({unreadable.value}), so des refactor never "
        "opened a pile and knows nothing about what it holds. Fix: point "
        "--pile at an existing pile file, or create one at that path first."
    )


def _default_merge_lock() -> MergeLockPort:
    """Production fallback when no ``merge_lock`` is injected -- a
    process-local ``threading.Lock`` wrapper (single-box default)."""
    from des.adapters.driven.refactor.threading_merge_lock import ThreadingMergeLock

    return ThreadingMergeLock()
