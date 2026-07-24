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
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.application.refactor_drain_service import BatchDrainResult, DrainResult
    from des.ports.driven_ports.git_worktree_port import GitWorktreePort


@dataclass(frozen=True)
class RefusalContext:
    """What the shared refusal rendering knows about the RUN that produced it.

    A ``DrainResult`` says what happened to an ITEM; these two facts are
    properties of the INVOCATION, and a refusal that omits them leaves the
    operator unable to act on it:

    * ``agent_cmd`` -- the ``--agent-cmd`` value this run actually dispatched,
      so a maintainer with several scripts can see which of theirs a refusal is
      about.
    * ``shadowed_fixer_path`` -- the repo-relative path of a fixer script whose
      WORKING-TREE copy is uncommitted, and which the drain therefore could not
      have run (it dispatches inside a worktree cut from the last commit).
      ``None`` means no such shadowing was DETECTED -- never "provably absent".

    Carried through ``_report``/``_report_batch`` into the one shared
    ``_refusal_line`` rather than re-derived per reporter: a second copy of
    this derivation is exactly the drift that produced the silent no-op these
    reporters were unified to fix.
    """

    agent_cmd: str
    shadowed_fixer_path: str | None = None


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

#: Rendered in place of a blocking reason when a drain did not complete yet
#: named no reason at all. Unreachable through any current refusal path, and
#: deliberately kept anyway: it is what makes "no silent fall-through remains"
#: structurally true rather than a claim about today's branches (GDP-6, no
#: silent-wrong).
_UNNAMED_REFUSAL_REASON = (
    "the drain did not complete and named no reason -- that missing reason is "
    "a des defect, not a mistake in your pile. Fix: re-run `des refactor` with "
    "the same --pile and report this output; a refusal must always name its "
    "own cause."
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
    # Held by name (not inlined into the service) because the REPORTING side
    # needs the same port: a refusal has to be able to say whether the fixer
    # it dispatched was one this repo's last commit actually carried.
    git_worktree = GitWorktreeAdapter()
    service = RefactorDrainService(
        git_worktree=git_worktree,
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
    context = _refusal_context(repo, args.agent_cmd, git_worktree)
    if args.max_parallel > 1:
        batch_result = service.drain_batch(
            repo=repo,
            pile_path=args.pile,
            paid_path=paid_path,
            agent_cmd=args.agent_cmd,
            max_parallel=args.max_parallel,
        )
        return _report_batch(
            batch_result, DEFAULT_INTEGRATION_BRANCH, skipped_lines, context
        )
    result = service.drain_one(
        repo=repo,
        pile_path=args.pile,
        paid_path=paid_path,
        agent_cmd=args.agent_cmd,
        prompt_template_path=args.prompt_template,
    )
    return _report(result, DEFAULT_INTEGRATION_BRANCH, skipped_lines, context)


def _report(
    result: DrainResult,
    integration_branch: str,
    skipped_lines: tuple[str, ...],
    context: RefusalContext,
) -> int:
    """Self-report the drain outcome on stdout/stderr -- never a silent exit
    (the standing what/why/how mandate + the Fixture-Theater/opacity flags
    this CLI is here to close).

    Every path below ends in an EXPLICIT terminal branch: there is no bare
    fall-through ``return 0`` left. The removed one used to swallow an item
    that WAS parsed but did not drain and carried no ``reason`` -- its
    blocking condition sat unread in ``merge_blocked_reason``, so
    ``des refactor`` printed nothing and exited 0, indistinguishable from a
    successful run against an empty pile (fix-drain-single-item-silent-noop).
    Exit 1 for such a refusal is a CONFORMANCE RESTORATION, not a contract
    change: ``nWave/gates/refactor.yaml`` has declared
    ``DrainRefused -> exit_code: 1`` since slice-01.
    """
    if result.drained:
        print(f"Drained 1 item: {result.item_id} -> merged into '{integration_branch}'")
        if skipped_lines:
            # A malformed sibling line must never be silently swallowed just
            # because a real item in the same pile successfully drained.
            print(_skipped_lines_notice(skipped_lines))
        return 0
    if result.item_id is None and result.refusal_reason is None:
        if skipped_lines:
            # Zero items parsed AND at least one non-blank line failed the
            # grammar: this is a REFUSAL (the operator's own input could not
            # be understood), distinct from a genuinely empty pile.
            print(_unparseable_pile_refusal(skipped_lines), file=sys.stderr)
            return 1
        print("0 parsed -- the pile is empty, nothing to drain")
        return 0
    print(_refusal_line(result, context), file=sys.stderr)
    if skipped_lines:
        print(_skipped_lines_notice(skipped_lines))
    return 1


def _report_batch(
    batch_result: BatchDrainResult,
    integration_branch: str,
    skipped_lines: tuple[str, ...],
    context: RefusalContext,
) -> int:
    """Self-report a ``--max-parallel`` > 1 drain outcome on stdout/stderr --
    one line per seeded item, sharing ``_report``'s refusal rendering
    (``_refusal_line``) outright so an operator sees the same vocabulary
    regardless of which path ran. Sharing it is the point: the two reporters
    hand-maintaining their own copies is how they drifted apart into the
    single-item silent no-op."""
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
            print(_refusal_line(result, context), file=sys.stderr)
            exit_code = 1
    if skipped_lines:
        # A malformed sibling line must never be silently swallowed just
        # because at least one real item in the same pile successfully
        # drained.
        print(_skipped_lines_notice(skipped_lines))
    return exit_code


def _refusal_line(result: DrainResult, context: RefusalContext) -> str:
    """The ONE refusal rendering -- shared by ``_report`` and ``_report_batch``.

    Both reporters previously hand-maintained their own refusal line, and had
    ALREADY DRIFTED: the batch one read ``reason or merge_blocked_reason`` while
    the single-item one read ``reason`` alone and silently dropped everything
    else. That divergence IS the defect being fixed here, so the derivation
    (``DrainResult.refusal_reason``), the item attribution, and the expansion of
    a bare internal token into a what/why/how explanation all live here, once --
    the two reporters can no longer disagree about what an operator is told.
    """
    reason = result.refusal_reason or _UNNAMED_REFUSAL_REASON
    explained = _explained_refusal_reason(reason, context)
    if result.item_id is None:
        return f"des refactor refused: {explained}"
    return f"des refactor refused: {result.item_id}: {explained}"


def _explained_refusal_reason(reason: str, context: RefusalContext) -> str:
    """Expand a bare internal refusal TOKEN into a what/why/how explanation.

    Reasons that are already prose (the probe, paradigm, and worktree-creation
    refusals) pass through untouched -- only the named domain tokens, which are
    a WHAT with no WHY and no HOW on their own, are expanded.
    """
    from des.domain.refactor.entry_gate import ENTRY_GATE_VERDICT_MISSING

    if reason == ENTRY_GATE_VERDICT_MISSING:
        return _entry_gate_verdict_missing_refusal(context)
    return reason


def _entry_gate_verdict_missing_refusal(context: RefusalContext) -> str:
    """WHAT/WHY/HOW for a drain blocked because the dispatched agent emitted no
    recognized entry-gate verdict: keeps the named token (WHAT), says why the
    drain refused to merge (WHY), lists the recognized tokens read straight off
    the ``EntryGateVerdict`` enum -- split by which ones actually permit the
    merge -- and names the concrete next step, stating honestly that no shipped
    tool emits the verdict for the operator today (GDP-3 self-explaining /
    GDP-4 HOW invokes the producing tool, modelled on
    ``_unparseable_pile_refusal`` above, honesty clause included).

    Names the ``--agent-cmd`` value VERBATIM: an operator with more than one
    fixer script cannot otherwise tell which of theirs a refusal is about. And
    when that command is a repo-relative script git reports as UNCOMMITTED, the
    shadowed-fixer paragraph is appended -- the one case where following the
    ``Fix:`` line above verbatim reproduces this very refusal byte-for-byte, on
    forever (fix-drain-single-item-silent-noop)."""
    from des.application.refactor_drain_service import (
        MERGE_PERMITTING_ENTRY_GATE_VERDICTS,
    )
    from des.domain.refactor.entry_gate import (
        ENTRY_GATE_VERDICT_MISSING,
        EntryGateVerdict,
    )

    permitting = ", ".join(
        verdict.value for verdict in MERGE_PERMITTING_ENTRY_GATE_VERDICTS
    )
    refusing = ", ".join(
        verdict.value
        for verdict in EntryGateVerdict
        if verdict not in MERGE_PERMITTING_ENTRY_GATE_VERDICTS
    )
    explanation = (
        f"{ENTRY_GATE_VERDICT_MISSING} -- the command you passed to "
        f"--agent-cmd ({context.agent_cmd}) finished without emitting any "
        "recognized entry-gate verdict token in its output, so the drain "
        "refused to merge blind against a green it could not classify.\n"
        f"Verdict tokens that PERMIT the merge: {permitting}\n"
        f"Verdict tokens that deliberately REFUSE it: {refusing}\n"
        "Fix: make your own --agent-cmd print exactly one of those tokens on "
        "its stdout as its last act -- for example "
        "`your-agent ... && echo REFACTOR_SAFE`. No shipped tool emits the "
        "verdict for you yet: scripts/refactor_agent.py, the actuator the "
        "command catalog names as the --agent-cmd value, does not print one."
    )
    shadowed = _shadowed_fixer_notice(context)
    if shadowed is None:
        return explanation
    return f"{explanation}\n{shadowed}"


def _shadowed_fixer_notice(context: RefusalContext) -> str | None:
    """The paragraph that keeps an operator who ALREADY followed the ``Fix:``
    line from looping on an unchanged refusal -- or ``None`` when no shadowed
    fixer was detected, so a refusal that does not apply never carries it.

    Detected case only, deliberately: a caveat appended to every refusal is
    noise the healthy paths pay for, and it could not make two otherwise
    byte-identical runs tellable apart -- which is the whole point. The three
    things it must carry are the three an operator needs to act: WHAT is
    shadowed (their own script, by path), WHY it never ran (the drain
    dispatches inside an isolated worktree checked out from the last commit,
    so a repo-relative command resolves to the COMMITTED copy), and the two
    routes forward that are verified to work -- commit it, or point
    ``--agent-cmd`` at an absolute path outside the repo.

    The WHY names the ASYMMETRY rather than just the rule, because the rule
    alone reads as arbitrary: this command takes TWO operator-supplied inputs
    and resolves them from DIFFERENT bases. The prompt template is read from
    ``repo`` -- the LIVE checkout (``RefactorDrainService._load_template_text``:
    ``repo / DEFAULT_TEMPLATE_PATH``), so an edit there takes effect at once
    and needs no commit; ``--agent-cmd`` runs with ``cwd=<worktree>``, so it
    does not. An operator edits both the same way and only one takes effect --
    naming that is what stops "commit it" being over-generalized into "commit
    everything" (the template is commonly git-ignored and cannot be committed
    at all)."""
    path = context.shadowed_fixer_path
    if path is None:
        return None
    return (
        f"Already did that? Then note: {path} has UNCOMMITTED changes here, "
        "and this run never saw them. des refactor executes --agent-cmd "
        "inside an ISOLATED WORKTREE checked out from your last commit, so a "
        f"repo-relative command resolves to the COMMITTED copy of {path} "
        "there -- the edit in your working tree did not run, which is why "
        "re-running unchanged reproduces this refusal exactly. Your two "
        "inputs resolve from DIFFERENT bases, which is what makes this "
        "surprising: the prompt template is read LIVE from your checkout (an "
        "edit there takes effect on the next run, no commit involved), while "
        "--agent-cmd is not.\n"
        f"Fix, for the fixer script only: commit it (`git commit -- {path}`) "
        "and re-run, so the next worktree carries your edit -- or point "
        "--agent-cmd at an absolute path OUTSIDE the repo, which resolves to "
        "the same live file from any worktree and needs no commit at all."
    )


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


def _refusal_context(
    repo: Path, agent_cmd: str, git_worktree: GitWorktreePort
) -> RefusalContext:
    """Read, ONCE per run, the invocation-level facts a refusal may need.

    The uncommitted-path read goes through the driven port, never a git call
    inlined here: a git-absent or non-repository target simply reports no
    uncommitted paths, the detection finds nothing, and every refusal renders
    its generic explanation unchanged (degrade to LESS explanation, never to a
    wrong claim).
    """
    dirty = set(git_worktree.uncommitted_paths(repo))
    shadowed = next(
        (path for path in _repo_relative_paths_in(agent_cmd) if path in dirty),
        None,
    )
    return RefusalContext(agent_cmd=agent_cmd, shadowed_fixer_path=shadowed)


def _repo_relative_paths_in(agent_cmd: str) -> tuple[str, ...]:
    """Every ``agent_cmd`` token naming a path INSIDE the repo, normalized to
    the repo-relative form ``git status --porcelain`` reports.

    EVERY token, not merely the first: the executable an operator writes is as
    often an interpreter as a script (``uv run python scripts/fix.py``,
    ``sh -c ./fixer.sh``), and it is the SCRIPT whose committed-ness decides
    what actually ran inside the worktree.

    Deliberately excluded, because git cannot shadow them: an ABSOLUTE path
    (it resolves to the same live file from inside any worktree -- precisely
    the escape route the refusal recommends), a bare program name resolved on
    PATH (``sh``, ``python``), and anything normalizing outside the repo.
    """
    try:
        tokens = shlex.split(agent_cmd)
    except ValueError:
        # An unbalanced quote leaves no token resolvable, so nothing is
        # claimed about any of them -- never a guess at where the split fell.
        return ()
    separators = {"/", os.sep}
    paths: list[str] = []
    for token in tokens:
        if not any(separator in token for separator in separators):
            continue
        candidate = Path(token)
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        paths.append(str(candidate))
    return tuple(paths)


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
