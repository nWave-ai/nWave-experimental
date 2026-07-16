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
    from des.application.refactor_drain_service import DrainResult


def main(argv: list[str] | None = None) -> int:
    """Drain the single next pending pile item via the configured agent_cmd."""
    args = _parse_args(argv)

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

    repo = Path.cwd()
    service = RefactorDrainService(
        git_worktree=GitWorktreeAdapter(),
        agent_invocation=ShellAgentInvocationAdapter(),
        env_provision=UvEnvProvisionAdapter(),
        impacted_test_selector=HeuristicImpactedTestSelectorAdapter(),
        ledger=AtCompletionLedger("des-refactor-fixer-swarm", repo),
    )
    paid_path = args.pile.parent / "paidtechdebt.md"
    result = service.drain_one(
        repo=repo,
        pile_path=args.pile,
        paid_path=paid_path,
        agent_cmd=args.agent_cmd,
        prompt_template_path=args.prompt_template,
    )
    return _report(result, DEFAULT_INTEGRATION_BRANCH)


def _report(result: DrainResult, integration_branch: str) -> int:
    """Self-report the drain outcome on stdout/stderr -- never a silent exit
    (the standing what/why/how mandate + the Fixture-Theater/opacity flags
    this CLI is here to close)."""
    if result.reason is not None:
        print(f"des refactor refused: {result.reason}", file=sys.stderr)
        return 1
    if result.drained:
        print(f"Drained 1 item: {result.item_id} -> merged into '{integration_branch}'")
        return 0
    if result.item_id is None:
        print(f"0 parsed -- {_no_items_reason(result.skipped_lines)}")
        return 0
    return 0


def _no_items_reason(skipped_lines: tuple[str, ...]) -> str:
    if not skipped_lines:
        return "the pile is empty, nothing to drain"
    skipped_desc = "; ".join(
        f"skipped {line!r} (does not match the item grammar)" for line in skipped_lines
    )
    return f"{skipped_desc}"


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
