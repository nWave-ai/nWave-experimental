"""des refactor -- the fixer-swarm CLI (ADR-SWARM-001, des-refactor-fixer-swarm).

Thin argparse shell composing ``RefactorDrainService`` with its production
adapters -- mirrors the ``des run-tests`` / ``des validate-feature-delta``
pure-core/thin-shell CLI pattern (Reuse Analysis). CREATE_NEW.

``refactor`` is registered in ``des.cli.__main__``'s subcommand registry.
Drains the single next pending pile item end to end (slice-01 walking
skeleton) -- worktree-from-tip, per-worktree venv, configurable agent_cmd
dispatch, fast+impacted green-to-green, merge into a clean integration
branch, and mandatory cleanup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.application.refactor_drain_service import BatchDrainResult, DrainResult


#: The load-bearing shape of one pending pile item -- printed verbatim in the
#: unparseable-pile refusal so an operator can copy a working line without
#: reading source code or a separate doc (see `_ITEM_LINE_RE`,
#: src/des/domain/refactor/pile.py -- this string mirrors it, kept in sync by
#: hand since the regex itself is not renderable as prose).
_GRAMMAR_SHAPE = (
    '- [ ] <item_id>: paradigm=<paradigm> defect="<defect>" '
    'proposed_solution="<solution>"'
)
_GRAMMAR_EXAMPLE = (
    '- [ ] TD-001: paradigm=object-oriented defect="duplicate helper across '
    'two modules" proposed_solution="extract a shared function"'
)


def main(argv: list[str] | None = None) -> int:
    """Drain pending pile item(s) via the configured agent_cmd.

    ``--max-parallel 1`` (the default) drains exactly ONE item through
    ``drain_one``, unchanged from before this fix. ``--max-parallel N`` for
    N>1 routes to ``drain_batch`` instead -- previously `args.max_parallel`
    was parsed but never consulted here, so the CLI always called
    ``drain_one`` regardless of the flag (bugfix-refactor-cli-max-parallel-
    unwired).

    ``--driver loop`` refuses immediately, before any import, agent
    dispatch, or pile access -- `args.driver` was parsed but never consulted
    anywhere, so `--driver loop` silently behaved identically to the
    `python` default (bugfix-refactor-driver-loop-dead-code, GDP-6
    silent-wrong). `--driver python` and the bare default are unaffected.
    """
    args = _parse_args(argv)

    if args.driver == "loop":
        print(_driver_loop_refusal(), file=sys.stderr)
        return 1

    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
    from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
    from des.adapters.driven.refactor.shell_agent_invocation_adapter import (
        ShellAgentInvocationAdapter,
    )
    from des.adapters.driven.refactor.tsunami_impacted_test_selector_adapter import (
        HeuristicImpactedTestSelectorAdapter,
    )
    from des.adapters.driven.refactor.uv_env_provision_adapter import (
        UvEnvProvisionAdapter,
    )
    from des.application.refactor_drain_service import (
        DEFAULT_INTEGRATION_BRANCH,
        RefactorDrainService,
    )
    from des.domain.refactor.pile import parse_pile_report

    repo = Path.cwd()
    service = RefactorDrainService(
        git_worktree=GitWorktreeAdapter(),
        agent_invocation=ShellAgentInvocationAdapter(),
        env_provision=UvEnvProvisionAdapter(),
        impacted_test_selector=HeuristicImpactedTestSelectorAdapter(),
        ledger=AtCompletionLedger("des-refactor-fixer-swarm", repo),
    )
    paid_path = args.pile.parent / "paidtechdebt.md"
    # Parsed BEFORE drain_one/drain_batch runs: a successful drain rewrites
    # the pile file (move_item), which would otherwise erase the very
    # skipped-line evidence the refusal/AT-6 notice needs to report.
    skipped_lines = parse_pile_report(args.pile).skipped_lines
    if args.max_parallel > 1:
        batch_result = service.drain_batch(
            repo=repo,
            pile_path=args.pile,
            paid_path=paid_path,
            agent_cmd=args.agent_cmd,
            max_parallel=args.max_parallel,
        )
        return _report_batch(batch_result, DEFAULT_INTEGRATION_BRANCH, skipped_lines)
    result = service.drain_one(
        repo=repo,
        pile_path=args.pile,
        paid_path=paid_path,
        agent_cmd=args.agent_cmd,
        prompt_template_path=args.prompt_template,
    )
    return _report(result, DEFAULT_INTEGRATION_BRANCH, skipped_lines)


def _report(
    result: DrainResult,
    integration_branch: str,
    skipped_lines: tuple[str, ...],
) -> int:
    """Self-report the drain outcome on stdout/stderr -- never a silent exit
    (the standing what/why/how mandate + the Fixture-Theater/opacity flags
    this CLI is here to close)."""
    if result.reason is not None:
        print(f"des refactor refused: {result.reason}", file=sys.stderr)
        return 1
    if result.drained:
        print(f"Drained 1 item: {result.item_id} -> merged into '{integration_branch}'")
        if skipped_lines:
            # A malformed sibling line must never be silently swallowed just
            # because a real item in the same pile successfully drained.
            print(_skipped_lines_notice(skipped_lines))
        return 0
    if result.item_id is None:
        if skipped_lines:
            # Zero items parsed AND at least one non-blank line failed the
            # grammar: this is a REFUSAL (the operator's own input could not
            # be understood), distinct from a genuinely empty pile.
            print(_unparseable_pile_refusal(skipped_lines), file=sys.stderr)
            return 1
        print("0 parsed -- the pile is empty, nothing to drain")
        return 0
    return 0


def _report_batch(
    batch_result: BatchDrainResult,
    integration_branch: str,
    skipped_lines: tuple[str, ...],
) -> int:
    """Self-report a ``--max-parallel`` > 1 drain outcome on stdout/stderr --
    one line per seeded item, mirroring ``_report``'s single-item shape so an
    operator sees the same vocabulary regardless of which path ran."""
    if not batch_result.results:
        if skipped_lines:
            print(_unparseable_pile_refusal(skipped_lines), file=sys.stderr)
            return 1
        print("0 parsed -- the pile is empty, nothing to drain")
        return 0
    exit_code = 0
    for result in batch_result.results:
        if result.drained:
            print(
                f"Drained 1 item: {result.item_id} -> "
                f"merged into '{integration_branch}'"
            )
        else:
            reason = result.reason or result.merge_blocked_reason
            print(f"des refactor refused: {result.item_id}: {reason}", file=sys.stderr)
            exit_code = 1
    if skipped_lines:
        # A malformed sibling line must never be silently swallowed just
        # because at least one real item in the same pile successfully
        # drained.
        print(_skipped_lines_notice(skipped_lines))
    return exit_code


def _driver_loop_refusal() -> str:
    """WHAT/WHY/HOW for `--driver loop`: names the requested driver, states
    it is not implemented yet, and points at `python` (the working default)
    as the concrete next step."""
    return (
        "des refactor refused: --driver loop is not implemented yet -- "
        "use --driver python (the working default) or omit --driver "
        "entirely."
    )


def _unparseable_pile_refusal(skipped_lines: tuple[str, ...]) -> str:
    """WHAT/WHY/HOW for a pile whose only content failed the item grammar:
    shows the grammar's literal shape with a concrete example, names the
    offending line(s) verbatim, and routes to a producing tool or states
    honestly that none exists yet (GDP-3 self-explaining / GDP-4 HOW invokes
    the producing tool)."""
    offending = "\n".join(f"  {line}" for line in skipped_lines)
    return (
        "des refactor refused: 0 parsed -- the pile's only content did not "
        "match the item grammar, so there is nothing to drain.\n"
        f"Offending line(s):\n{offending}\n"
        f"Expected item grammar: {_GRAMMAR_SHAPE}\n"
        f"Concrete example: {_GRAMMAR_EXAMPLE}\n"
        "Fix: hand-edit the offending line(s) above to match the grammar. "
        "No scaffolding tool exists yet to generate a valid pile item for "
        "you."
    )


def _skipped_lines_notice(skipped_lines: tuple[str, ...]) -> str:
    """Names a line that failed the item grammar even when a sibling item in
    the same pile successfully drained (never silently swallowed)."""
    skipped_desc = "; ".join(
        f"skipped {line!r} (does not match the item grammar)" for line in skipped_lines
    )
    return f"note: {skipped_desc}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--pile --agent-cmd [--max-parallel] [--driver]`` argv contract."""
    parser = argparse.ArgumentParser(prog="des refactor")
    parser.add_argument("--pile", required=True, type=Path)
    parser.add_argument("--agent-cmd", required=True)
    parser.add_argument("--max-parallel", type=int, default=1)
    parser.add_argument("--driver", choices=("python", "loop"), default="python")
    parser.add_argument("--prompt-template", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    import sys

    sys.exit(main(sys.argv[1:]))
