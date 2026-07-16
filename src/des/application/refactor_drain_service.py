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
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.earned_verdict import TestRun, test_run_from_envelope
from des.domain.refactor.green_to_green import (
    GreenToGreenVerdict,
    classify_green_to_green,
)
from des.domain.refactor.pile import PileItem, move_item, parse_pile_report
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

#: The dedicated clean integration branch the drain loop merges into by
#: default (D4/D5) -- never the operator's own working tree.
DEFAULT_INTEGRATION_BRANCH = "refactor-integration"

_FEATURE_ID = "des-refactor-fixer-swarm"
_SLICE_ID = "slice-01"
_DRAINED_EVENT = "RefactorItemDrained"

_TEST_SOURCE_ENVELOPE = "envelope"
_TEST_SCOPE_FAST_IMPACTED = "fast+impacted"

_TESTS_RED_REASON = "MergeBlockedTestsRed"
_PROMPT_FILENAME = ".refactor-prompt.md"
_ENVELOPE_FILENAME = "test-result.json"


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
    test_target_scope: str | None = None
    test_result_source: str | None = None
    reason: str | None = None
    parsed_count: int = 0
    skipped_lines: tuple[str, ...] = ()


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
        self._env_provision.provision(handle.path)

        before = self._run_tests(handle.path)
        self._dispatch_agent(repo, item, handle.path, agent_cmd, prompt_template_path)
        after = self._run_tests(handle.path)

        outcome = classify_green_to_green(before, after)
        if outcome.verdict != GreenToGreenVerdict.SAFE:
            return self._refused(item.item_id, _TESTS_RED_REASON, handle.head_sha)

        merge_result = self._git_worktree.merge_into(repo, integration_branch, branch)
        if not merge_result.merged:
            return self._refused(
                item.item_id, merge_result.blocked_reason, handle.head_sha
            )

        self._git_worktree.remove_worktree(repo, handle.path)
        self._git_worktree.delete_branch(repo, branch)
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

    # -- internal: startup probes (Earned Trust, principle 13) --------------

    def _probe_failure_reason(self, repo: Path, agent_cmd: str) -> str | None:
        """Which startup probe failed, named WHAT/WHY/HOW -- never a bare bool
        (Earned Trust principle 13; the standing what/why/how mandate)."""
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

    # -- internal: prompt rendering + agent dispatch (D6/D7) -----------------

    def _dispatch_agent(
        self,
        repo: Path,
        item: PileItem,
        worktree: Path,
        agent_cmd: str,
        prompt_template_path: Path | None,
    ) -> None:
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
        self._agent_invocation.invoke(agent_cmd, prompt_path, worktree)

    def _load_template_text(self, repo: Path, override: Path | None) -> str:
        path = override if override is not None else repo / DEFAULT_TEMPLATE_PATH
        if path.is_file():
            return load_prompt_template(path)
        return DEFAULT_TEMPLATE_TEXT

    # -- internal: green-to-green test execution (D3) ------------------------

    def _run_tests(self, worktree: Path) -> TestRun:
        target = self._impacted_test_selector.select(worktree, ())[0]
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
