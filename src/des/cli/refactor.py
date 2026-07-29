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
import contextlib
import os
import shlex
import signal
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterator

    from des.application.refactor_drain_service import (
        BatchDrainResult,
        DrainResult,
        RefactorDrainService,
    )
    from des.ports.driven_ports.git_worktree_port import GitWorktreePort


class DispatchedCommandOrigin(Enum):
    """WHO chose the command a run dispatched.

    Carried beside the command itself because a refusal that names the command
    correctly can still be wrong about whose choice it was, and that error
    sends a reader hunting for an option they never wrote. The two origins are
    genuinely different situations with different next steps -- override the
    default, versus fix your own script -- so they are modelled as a closed
    set rather than left implicit in the rendering.
    """

    #: The operator typed ``--agent-cmd <value>``.
    OPERATOR = "operator"
    #: No ``--agent-cmd`` was given, so ``des refactor`` resolved its own
    #: installed actuator (``_resolve_default_agent_cmd``) and ran that.
    RESOLVED_BY_DES = "resolved-by-des"


@dataclass(frozen=True)
class RefusalContext:
    """What the shared refusal rendering knows about the RUN that produced it.

    A ``DrainResult`` says what happened to an ITEM; these facts are properties
    of the INVOCATION, and a refusal that omits them leaves the operator unable
    to act on it:

    * ``agent_cmd`` -- the command this run actually dispatched, so a
      maintainer with several scripts can see which of theirs a refusal is
      about. The RESOLVED value, never the raw ``--agent-cmd`` argument: on the
      default path that argument is ``None``, and a refusal built from it named
      ``None`` as the command it ran (bugfix-refusal-names-none).
    * ``agent_cmd_origin`` -- whether that command was the operator's choice or
      one ``des refactor`` made for them. Inseparable from the command itself:
      the same string means "your script" in one run and "the default we
      picked" in another, and only the origin tells the two apart.
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
    agent_cmd_origin: DispatchedCommandOrigin
    shadowed_fixer_path: str | None = None


#: HOW for the actuator-not-found refusal -- the producing tool (GDP-4).
_REMEDIATION_HINT = "nwave-ai install"


#: The load-bearing shape of one pending pile item -- printed verbatim in the
#: unparseable-pile refusal so an operator can copy a working line without
#: reading source code or a separate doc (see `_ITEM_LINE_RE`,
#: src/des/domain/refactor/pile.py -- this string mirrors it, kept in sync by
#: hand since the regex itself is not renderable as prose).
#:
#: `discovered_by=` is OPTIONAL in the regex (223 pending rows predate it and
#: must keep parsing) but is shown here as part of the shape on purpose: this
#: message is the only place the tool itself teaches the row format, and a
#: field absent from it is a field nobody fills in (GDP-2).
_GRAMMAR_SHAPE = (
    '- [ ] <item_id>: paradigm=<paradigm> defect="<defect>" '
    'proposed_solution="<solution>" discovered_by=<channel>'
)
_GRAMMAR_EXAMPLE = (
    '- [ ] TD-001: paradigm=object-oriented defect="duplicate helper across '
    'two modules" proposed_solution="extract a shared function" '
    "discovered_by=systematic-audit"
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

    # Annotated, not left as the Namespace's ``Any``: every use below -- the
    # drain calls AND the refusal context -- must see one resolved ``str``.
    # ``args.agent_cmd`` typed as ``Any`` is what let the refusal context be
    # built from the raw, still-``None`` argument without a type error
    # (bugfix-refusal-names-none); past this block the name is a ``str``.
    agent_cmd: str | None = args.agent_cmd
    agent_cmd_origin = DispatchedCommandOrigin.OPERATOR
    if agent_cmd is None:
        agent_cmd = _resolve_default_agent_cmd()
        agent_cmd_origin = DispatchedCommandOrigin.RESOLVED_BY_DES
        if agent_cmd is None:
            print(_actuator_not_found_refusal(), file=sys.stderr)
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
    # The RESOLVED command, never ``args.agent_cmd``: the drain dispatches the
    # resolved one, so a refusal built from the raw argument would be about a
    # command that never ran (and, with no --agent-cmd given, about ``None``).
    context = _refusal_context(repo, agent_cmd, agent_cmd_origin, git_worktree)
    # A drain dispatches a third-party agent subtree into its OWN session (so the
    # timeout reap can killpg it); a SIGTERM/SIGINT to THIS parent would
    # otherwise orphan that subtree and strand the in-flight worktree/branch,
    # because Python's default SIGTERM disposition terminates the process without
    # unwinding drain_one's own cleanup at all. The handler makes the abort as
    # clean as any refusal (bugfix-inherited-stdin-deadlocks-spawns slice-02).
    with _abort_on_signal(service):
        if args.max_parallel > 1:
            batch_result = service.drain_batch(
                repo=repo,
                pile_path=args.pile,
                paid_path=paid_path,
                agent_cmd=agent_cmd,
                max_parallel=args.max_parallel,
            )
            return _report_batch(
                batch_result, DEFAULT_INTEGRATION_BRANCH, skipped_lines, context
            )
        result = service.drain_one(
            repo=repo,
            pile_path=args.pile,
            paid_path=paid_path,
            agent_cmd=agent_cmd,
            prompt_template_path=args.prompt_template,
        )
        return _report(result, DEFAULT_INTEGRATION_BRANCH, skipped_lines, context)


@contextlib.contextmanager
def _abort_on_signal(service: RefactorDrainService) -> Iterator[None]:
    """Install a SIGINT/SIGTERM handler that aborts the drain CLEANLY, then
    restore the previous handlers on the way out.

    Duty on a signal, in order: (1) SIGKILL every in-flight agent process group
    via ``des.runtime.spawn.reap_active_process_groups`` -- reaching the subtree
    the drain detached into its own session, which a bare parent-death would
    orphan; (2) run the same worktree/branch cleanup a mid-drain crash does via
    ``service.cleanup_in_flight`` -- so the abort leaves the repo as clean as any
    refusal; (3) print a WHAT/WHY/HOW abort message; (4) exit non-zero (POSIX
    128+signum), because an operator-initiated abort is not a drained item.

    The handler raises ``SystemExit`` rather than ``os._exit`` on purpose: it
    lets the drain's own ``except BaseException`` cleanup and this manager's
    handler restoration still run (both idempotent with step 2), and it flushes
    stdio. A re-entry flag makes a second signal during cleanup a no-op instead
    of restarting the abort. ``signal.signal`` is a main-thread-only call, which
    is where ``main`` runs; drain_batch's worker threads are reached through the
    process-group registry, not through a per-thread handler.
    """
    from des.runtime.spawn import reap_active_process_groups

    aborting = False

    def _handle(signum: int, _frame: object) -> None:
        nonlocal aborting
        if aborting:
            return
        aborting = True
        reap_active_process_groups()
        service.cleanup_in_flight()
        print(_abort_message(signum), file=sys.stderr, flush=True)
        raise SystemExit(128 + signum)

    previous = {
        sig: signal.signal(sig, _handle) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _abort_message(signum: int) -> str:
    """WHAT/WHY/HOW for an operator-initiated abort -- never a bare traceback or
    a silent exit (the standing what/why/how mandate; the charter negative 'a
    bare non-zero exit code with no human-readable explanation')."""
    name = signal.Signals(signum).name
    return (
        f"des refactor aborted:\n"
        f"WHAT: interrupted by {name} -- the in-flight item was stopped before "
        "it could merge.\n"
        "WHY: you (or your OS) signalled des refactor. The fixer agent subtree "
        "it had dispatched was killed together with its whole process group, "
        "and the in-flight item's worktree and branch were removed, so nothing "
        "is left half-merged or orphaned.\n"
        "HOW: nothing was merged for the interrupted item -- re-run the same "
        "`des refactor --pile ...` to pick it up again from a clean state. To "
        "let long agent work finish instead of aborting it, do not signal the "
        "process: the agent is already bounded by NWAVE_REFACTOR_AGENT_TIMEOUT."
    )


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

    Names the dispatched command VERBATIM, and attributes it to whoever chose
    it: an operator with more than one fixer script cannot otherwise tell which
    of theirs a refusal is about, and an operator who chose nothing at all must
    not be told a command was theirs -- that sends them looking for an option
    they never wrote (bugfix-refusal-names-none). And when that command is a
    repo-relative script git reports as UNCOMMITTED, the shadowed-fixer
    paragraph is appended -- the one case where following the ``Fix:`` line
    above verbatim reproduces this very refusal byte-for-byte, on forever
    (fix-drain-single-item-silent-noop)."""
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
        f"{ENTRY_GATE_VERDICT_MISSING} -- {_dispatched_command_clause(context)} "
        "finished without emitting any recognized entry-gate verdict token in "
        "its output, so the drain refused to merge blind against a green it "
        "could not classify.\n"
        f"Verdict tokens that PERMIT the merge: {permitting}\n"
        f"Verdict tokens that deliberately REFUSE it: {refusing}\n"
        f"{_verdict_fix_line(context)}"
    )
    shadowed = _shadowed_fixer_notice(context)
    if shadowed is None:
        return explanation
    return f"{explanation}\n{shadowed}"


def _dispatched_command_clause(context: RefusalContext) -> str:
    """The subject of the refusal's WHAT: the command that ran, named
    verbatim, and attributed to whoever actually chose it (GDP-3).

    The two origins get two different sentences on purpose. Telling an
    operator who passed nothing that this is "the command you passed to
    --agent-cmd" is a wrong WHAT twice over: it names a choice that was the
    system's, and it points at a flag that is absent from their command line,
    so the one place they are told to look holds nothing at all."""
    if context.agent_cmd_origin is DispatchedCommandOrigin.OPERATOR:
        return f"the command you passed to --agent-cmd ({context.agent_cmd})"
    return (
        "no --agent-cmd was given, so des refactor resolved its own installed "
        f"actuator and ran that ({context.agent_cmd}); it"
    )


def _verdict_fix_line(context: RefusalContext) -> str:
    """The refusal's HOW, routed by who chose the command that just ran.

    An operator with their OWN fixer has one thing to change: their script's
    last line. An operator who passed nothing has a different move -- the
    actuator that ran is nWave's own and does not emit a verdict, so the step
    forward is to override it. Both branches keep the honesty clause: no
    shipped tool emits the verdict for anyone yet (GDP-4 states that plainly
    rather than naming a producing tool that does not exist)."""
    if context.agent_cmd_origin is DispatchedCommandOrigin.OPERATOR:
        return (
            "Fix: make your own --agent-cmd print exactly one of those tokens "
            "on its stdout as its last act -- for example "
            "`your-agent ... && echo REFACTOR_SAFE`. No shipped tool emits "
            "the verdict for you yet: scripts/refactor_agent.py, the actuator "
            "the command catalog names as the --agent-cmd value, does not "
            "print one."
        )
    return (
        "Fix: pass --agent-cmd naming a command that prints exactly one of "
        "those tokens on its stdout as its last act -- for example "
        "`--agent-cmd 'your-agent {prompt} && echo REFACTOR_SAFE'`. The "
        "actuator resolved above is the only one nWave ships, and it does not "
        "print a verdict, so no shipped tool emits it for you yet -- until one "
        "does, this default cannot reach a merge on its own."
    )


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


def _resolve_default_agent_cmd() -> str | None:
    """When ``--agent-cmd`` is omitted, resolve nWave's OWN installed
    actuator via the existing ``des.runtime.interpreter`` seam and build the
    equivalent ``agent_cmd`` template (``<python> <actuator> {prompt}``) --
    same substitution/invocation path an explicit ``--agent-cmd`` gets, so
    the drain lifecycle never has to know which source it came from. Returns
    ``None`` when the actuator cannot be found at either candidate location
    (dev checkout or installed layout)."""
    from des.runtime.interpreter import resolve_installed_actuator

    actuator_path = resolve_installed_actuator()
    if actuator_path is None:
        return None
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(actuator_path))} {{prompt}}"


def _actuator_not_found_refusal() -> str:
    """WHAT/WHY/HOW for a missing installed actuator: names every path
    searched and points at the remediation (`nwave-ai install`) or an
    explicit `--agent-cmd` -- never a bare failure, never mistakable for the
    genuinely-empty-pile message (GDP-3/GDP-4)."""
    from des.runtime.interpreter import actuator_search_paths

    searched = " and ".join(str(path) for path in actuator_search_paths())
    return (
        "des refactor refused: no --agent-cmd was given and the installed "
        f"refactor_agent.py actuator could not be found -- searched: "
        f"{searched}. Fix: run `{_REMEDIATION_HINT}` to install the "
        "actuator, or pass --agent-cmd explicitly to use a different "
        "command."
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
    repo: Path,
    agent_cmd: str,
    agent_cmd_origin: DispatchedCommandOrigin,
    git_worktree: GitWorktreePort,
) -> RefusalContext:
    """Read, ONCE per run, the invocation-level facts a refusal may need.

    ``agent_cmd`` is the command the run DISPATCHES -- the caller's resolved
    value, not the raw ``--agent-cmd`` argument, which is ``None`` whenever the
    default actuator was used.

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
    return RefusalContext(
        agent_cmd=agent_cmd,
        agent_cmd_origin=agent_cmd_origin,
        shadowed_fixer_path=shadowed,
    )


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
    if not isinstance(agent_cmd, str):
        # LOUD, because the alternative is silent-wrong (GDP-6): ``shlex.split``
        # raises ValueError for a non-string too, so without this the ``except``
        # below -- written for ONE cause it names in its own comment -- would
        # absorb a wrong TYPE as if it were an operator's malformed command,
        # answering "no repo-relative paths" and disabling the shadowed-fixer
        # detection for every caller with no trace. That is exactly what
        # happened when the raw, still-``None`` ``--agent-cmd`` argument reached
        # here (bugfix-refusal-names-none).
        raise TypeError(
            "des defect: the shadowed-fixer detection was handed "
            f"{type(agent_cmd).__name__} ({agent_cmd!r}) where the RESOLVED "
            "agent command string was owed. WHY: a caller passed the raw "
            "--agent-cmd argument instead of the value main() resolved, and a "
            "non-string is not a malformed command -- it is a wiring bug that "
            "must not be read as one. HOW: pass the resolved command (see "
            "des.cli.refactor.main's agent_cmd), never args.agent_cmd."
        )
    try:
        tokens = shlex.split(agent_cmd)
    except ValueError:
        # An unbalanced quote leaves no token resolvable, so nothing is
        # claimed about any of them -- never a guess at where the split fell.
        # Reachable ONLY for that cause now: the type guard above means a
        # non-string can no longer arrive here wearing a quoting error's face.
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


def _build_parser() -> argparse.ArgumentParser:
    """Build the real ``des refactor`` argument parser, WITH `help=` text on
    every option (refactor-ux drain, 2026-07-29, repair 1/4).

    Before this fix every option below was bare (`--pile PILE`, no
    description) and `--help` never said the actuator resolved by default
    lives in the nWave INSTALLATION, never inside the operator's own project
    -- a real operator concluded "no actuator here" from her PROJECT repo and
    dispatched an expensive background agent instead of ever running this
    command (incident 1). `--help` is read BEFORE any refusal message has a
    chance to fire, so this is where that fact belongs, not only in
    ``_actuator_not_found_refusal``/``_entry_gate_verdict_missing_refusal``
    (which only teach an operator who already ran the command).

    ``EntryGateVerdict``/``MERGE_PERMITTING_VERDICTS`` are imported from the
    lean domain module (``re`` + ``enum`` only) rather than hardcoding the
    token list a second time, or importing the heavier application-layer
    ``refactor_drain_service`` -- keeping this parser build cheap for every
    invocation, including the ``--driver loop`` refusal path in ``main``
    that deliberately returns before any heavier import.
    """
    from des.domain.refactor.entry_gate import (
        MERGE_PERMITTING_VERDICTS,
        EntryGateVerdict,
    )

    permitting = ", ".join(
        verdict.value
        for verdict in EntryGateVerdict
        if verdict in MERGE_PERMITTING_VERDICTS
    )

    parser = argparse.ArgumentParser(
        prog="des refactor",
        description=(
            "Drain pending pile item(s) (techdebt.md/defects.md) via a dispatched "
            "agent_cmd: worktree-from-tip, green-to-green verification, merge into a "
            "clean integration branch, mandatory cleanup either way."
        ),
    )
    parser.add_argument(
        "--pile",
        required=True,
        type=Path,
        help="Path to the pending pile file to drain (e.g. techdebt.md or defects.md).",
    )
    parser.add_argument(
        "--agent-cmd",
        required=False,
        default=None,
        help=(
            "Command dispatched per item, with {prompt} substituted; must print one of "
            f"{permitting} on its stdout as its last act to permit a merge. Omit to let "
            "des resolve nWave's OWN installed refactor_agent.py actuator -- it lives in "
            "your nWave INSTALLATION, never inside your project repo (a repo-relative "
            "'scripts/refactor_agent.py' will not be found there). Honest declaration: "
            "that default actuator does not print a verdict, so it cannot reach a merge "
            "on its own -- pass your own --agent-cmd to complete a drain."
        ),
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help=(
            "Items to drain concurrently. 1 (default) is the entry-gated safe path; "
            "N>1 runs the batch path, which does NOT consult the entry gate "
            "(fail-open) -- use deliberately."
        ),
    )
    parser.add_argument(
        "--driver",
        choices=("python", "loop"),
        default="python",
        help=(
            "Execution driver. 'python' (default) is the only one implemented; 'loop' "
            "is a parsed stub that refuses immediately."
        ),
    )
    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=None,
        help=(
            "Path to a custom per-item prompt template. Defaults to the repo's own "
            ".nwave/refactor-agent-prompt.md."
        ),
    )
    return parser


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--pile [--agent-cmd] [--max-parallel] [--driver]`` argv
    contract. ``--agent-cmd`` is OPTIONAL -- when omitted, ``main`` resolves
    nWave's own installed actuator (``_resolve_default_agent_cmd``) instead;
    an explicit ``--agent-cmd`` is passed through byte-identical, unaffected."""
    return _build_parser().parse_args(argv)


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    import sys

    sys.exit(main(sys.argv[1:]))
