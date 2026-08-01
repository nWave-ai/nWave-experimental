"""des run-slice-ats -- the slice-scoped EXECUTOR (THE ACCELERATION).

slice-01 of f-spine-runs-tests-not-git-hooks (CRITICAL-1/CRITICAL-2): the
commit-time test authority that genuinely RUNS only the entering slice's
acceptance tests -- a real execution, not a collect-only walk -- so a RED slice
AT is VETOED at commit with no git test-hook present, and every commit is
slice-proportional rather than whole-tree.

The executor composes three seams:

  1. SCOPE (reuse) -- ``run_contract_gate.run_slice_ats`` collects the entering
     slice's node-ids scoped to its own ``.feature`` directory (collect-only --
     it does NOT run them; its ``ran_*`` field names are misleading).
  2. RUN (NEW, the load-bearing machinery) -- ``RunnerAdapter.run`` shells the
     target's own runner over exactly that scoped node-id set and maps the exit
     to PASS/FAIL. The RUN is what distinguishes this from the obsolete
     collect-only walk: a RED slice AT genuinely FAILS, never collects-green.
  3. VERDICT -- the run verdict is projected onto the 5-value ``GateVerdict``
     SSOT (DDD-6) and onto the process exit code (DDD-6): PASS -> 0, FAIL -> 1,
     NOT_APPLICABLE -> 0 (no-real-AT, non-blocking, NEVER a fabricated pass).

One JSON line is emitted on stdout naming the verdict, the runner, the scoped
node-ids, and the proportionality observables (``ran_whole_tree`` False,
``out_of_slice_ran`` empty) -- the acceleration's machine-readable surface.

NO-REAL-AT GUARD (DDD-8 / CT-8, pulled forward from slice-02 because the executor
is WIRED + documented as the commit authority NOW): a verification run MUST NOT
mutate the target repo. The real-AT detection consults the pytest-aware SSOT
oracle ``des.application.slice_at_completeness.feature_files_for_slice`` (Gherkin
``.feature`` files UNION pytest head-comment-tag-bound test files, a pure
filesystem read that NEVER materializes anything), scoped to the feature id
resolved by ``at_completion_ledger.active_feature_id`` (the ONE canonical
definition all three call-sites import). When the entering slice has NO real
DISTILL-authored AT of either convention on disk, the executor returns
NOT_APPLICABLE WITHOUT calling ``run_slice_ats`` -- because ``run_slice_ats``
(via ``_ensure_slice_at_scope`` -> ``_materialize_representative_slice_at``)
would FABRICATE an always-green ``assert True`` AT into the target repo and
report a silent false PASS. When the feature id itself cannot be resolved (zero
or multiple in-flight telemetry ledgers), the executor degrades LOUD to
INDETERMINATE rather than guessing -- a check that cannot run must never look
like a check that passed (fix-precommit-fabricates-vacuous-scaffold, slice-01).

ZERO-OBSERVED-EXECUTION GUARD (fix-precommit-fabricates-vacuous-scaffold,
slice-01, second pass -- an independent examiner FAILED the first pass): a
declared, head-tagged AT file that pytest reports as GREEN (exit 0 or 5) is
NOT automatically a PASS. pytest's own exit-code contract folds "no tests
collected" (5) and "all collected cases skipped/xfailed" (0, no failures) into
the SAME green bucket as "all collected cases genuinely ran and passed" -- so a
hollow scaffold, a module-level ``pytest.skip``, ``@pytest.mark.skip``,
``@pytest.mark.xfail(run=False)``, and an empty ``parametrize`` set all
byte-for-byte impersonate a real PASS on both the exit code and (via the SAME
``_GREEN_EXIT_CODES`` bug) the developer-visible console line. The invariant
enforced here is the CLASS, not a checklist of those five symptoms: no verdict
may be earned over ZERO observed execution, however the zero is produced.

The invariant binds BOTH authoring arms (Gherkin and pytest) -- neither is
exempt, because an exempt arm has no zero-execution floor at all and a hollow
``.feature`` would walk through exactly as the hollow pytest file did. What
differs per arm is only the CURRENCY the execution is reported in, and
``_slice_run_scope`` normalizes that: each arm resolves the REAL node-ids it
will execute, and the invariant is enforced over that one currency. Three seams
implement it, all in THIS module (the production locus for this slice):

  * ``_slice_run_scope`` puts both arms in ONE currency -- the real node-ids the
    slice will execute. It also closes the scope-leak that made the Gherkin arm's
    green dishonest: a marker-filtered directory-collect that matched nothing
    used to hand ``RunnerAdapter.run`` an EMPTY node-id tuple, which shells
    pytest with no scoping args at all -- a silent WHOLE-TREE run whose green
    came from the target's other tests, never from this slice's AT.
  * an EMPTY collected scope (the hollow-file, module-level-skip, and
    hollow-``.feature`` root causes, where pytest's own collection step already
    yields nothing) short-circuits BEFORE ``RunnerAdapter.run`` is ever called.
  * a NON-EMPTY collected scope that still earns a green ``RunVerdict`` (the
    ``@skip`` / ``xfail(run=False)`` / empty-``parametrize`` root causes, where
    the case IS collected but never reaches pytest's "call" phase) is
    independently re-verified via ``_observe_run`` -- one more pytest
    invocation, ``-rap``-scoped to exactly the SAME node-ids, counting only
    PASSED / FAILED / ERROR / XPASS outcomes (pytest's OWN report of what
    genuinely executed). SKIPPED and XFAIL(not-run) never appear in that count,
    root-cause-agnostic by construction -- the next way a test can zero out its
    own execution needs no new branch here.

Either refusal seam emits the existing ``FAIL`` verdict (never a new value) with
an empty ``ran_node_ids`` -- the field testifies ONLY to what genuinely
executed, never to what was merely declared or collected.

> slice-02 inserts ``TestRunnerPort.resolve`` consulted FIRST (degrade-LOUD
> INDETERMINATE before any pytest-bound collection). This slice-01 executor RUNS
> the dogfood pytest scope; the runner-resolution short-circuit is slice-02's
> hardening.

stdlib + ``des.*`` only (F-D-09 clean: roots = {des}).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    TELEMETRY_DIR_RELPATH,
    AtCompletionLedger,
    active_feature_id,
)
from des.adapters.driven.runner.pytest_runner import (
    pytest_interpreter,
    run_timeout_seconds,
)
from des.application.slice_at_completeness import feature_files_for_slice
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.run_contract_gate import (
    SliceGateRunScope,
    _collect_node_ids,
    _node_belongs_to_slice,
    _slice_feature_dir,
    run_slice_ats,
)
from des.domain.gate_outcome import GateVerdict
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.test_runner_port import RunnerAdapterUnavailable, resolve


_EVENT = "SliceAtGateResult"
_OUTCOME_GATE_NAME = "run-slice-ats"


def _record_outcome(
    repo_root: Path,
    entering_slice: str,
    feature_id: str | None,
    outcome: GateVerdict,
) -> None:
    """Append a `GateOutcomeRecorded` record (slice-04, ADR-GV-003 D5).

    Singleton-shape ledger (`AtCompletionLedger(project_root=repo_root)`),
    threading the SAME `feature_id` already resolved via `active_feature_id`
    before AT discovery -- no second resolution mechanism. The singleton
    shape requires a non-None `feature_id=` on every write; `""` is the
    established sentinel (mirrors `slice_id=""`) for the unresolvable case.
    """
    AtCompletionLedger(project_root=repo_root).append_gate_event(
        "GateOutcomeRecorded",
        entering_slice,
        feature_id=feature_id if feature_id is not None else "",
        gate=_OUTCOME_GATE_NAME,
        outcome=outcome,
    )


# The class invariant (fix-precommit-fabricates-vacuous-scaffold, slice-01
# second pass): pytest reports a genuinely EXECUTED case -- the test body
# actually ran -- as PASSED / FAILED / ERROR / XPASS in its `-rap` short
# summary. SKIPPED and XFAIL (not-run) never appear here, however the zero
# is produced (a hollow file, a module-level skip, `@pytest.mark.skip`,
# `xfail(run=False)`, an empty `parametrize` set, or any future variant this
# regex was never told about) -- root-cause-agnostic BY CONSTRUCTION: it
# counts what pytest itself reports as executed, never enumerates the ways
# execution can be skipped.
_EXECUTED_OUTCOME_RE = re.compile(r"^(?:PASSED|FAILED|ERROR|XPASS)\b", re.MULTILINE)

# The node-ids pytest itself reports as RED in that same `-rap` summary -- the
# WHICH behind a FAIL verdict. The gate HAS this information; until now it threw
# it away and told the developer only "your tests failed", leaving them to re-run
# the suite by hand to learn which ones.
_FAILED_NODE_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)

# How many failing node-ids to NAME before eliding. A WHY that dumps 200 node-ids
# is as unreadable as one that names none; the elision is honest (it says how many
# more) and the full set is always in the JSON `ran_node_ids` / the runner output.
_MAX_NAMED_FAILURES = 10

# The exit code carried on an INDETERMINATE verdict -- the canonical DES
# cannot-evaluate code (aligns with `verify_deliver_integrity.CANNOT_EVALUATE_EXIT`
# = 4, mirroring `gate_outcome.GateOutcome.indeterminate`). Distinct from PASS/NA
# (0), FAIL (1), the hook block code (2), and pytest no-collect (5) so an
# unrecognized/absent runner degrades LOUD on the exit-code observable -- never a
# silent pass, never a vacuous FAIL (DDD-6 / CT-4). It MUST differ from the
# freshness-gate refuse code (`freshness._REFUSE_EXIT_CODE` = 78, EX_CONFIG),
# which fires at package-import time on this SAME invocation path
# (`des.cli.__init__:assert_fresh_or_explain`): a caller keying on the exit code
# must distinguish "target runner unresolved/unsupported" (this, 4) from "your
# install drifted, re-run the installer" (freshness, 78).
_INDETERMINATE_EXIT = 4

# The empty scope carried on a NOT_APPLICABLE verdict -- a no-real-AT slice ran
# nothing, never the whole tree, never out-of-slice. NEVER materialized.
_EMPTY_SCOPE = SliceGateRunScope(
    ran_node_ids=(),
    ran_whole_tree=False,
    out_of_slice_ran=(),
)


def _rerun_command(repo_root: Path, entering_slice: str) -> str:
    """The EXACT command that re-runs this gate -- executable as printed.

    GDP-4 (the HOW invokes the producing tool) is not satisfied by naming the
    tool's VERB. A remediation that says "re-run `des run-slice-ats`" prints a
    fragment that ERRORS when pasted -- the CLI requires ``--repo-root`` and
    ``--entering-slice``, and the operator is left to reconstruct them. An
    instruction you cannot copy-paste is not an instruction.

    Two hazards, both closed here:

    * MISSING ARGUMENTS -- the required flags are filled in from the invocation
      actually in hand (this repo, this entering slice), never left as a verb.
    * THE WRONG BINARY -- a bare ``des`` resolves through ``PATH``, which on a
      developer box may be a STALE INSTALLED shim rather than the runtime that
      just produced this verdict. Naming ``sys.executable`` explicitly pins the
      command to the SAME interpreter that is emitting it, so what the operator
      pastes is what actually ran. (The equivalent `des run-slice-ats` CLI form
      is named alongside it for the ordinary, non-drifted case.)

    Arguments are shell-quoted: a repo path containing a space would otherwise
    print a command that silently parses into the wrong arguments.
    """
    return (
        f"{shlex.quote(sys.executable)} -m des.cli.run_slice_ats "
        f"--repo-root {shlex.quote(str(repo_root))} "
        f"--entering-slice {shlex.quote(entering_slice)}"
    )


# The three HOW prose bodies. Each is PROSE ONLY -- it names the remediation and
# ends by pointing at the command, but it NEVER embeds the command text. The
# command travels separately (`_rerun_command`, the `command` field / its own
# verbatim console line), because prose is wrapped and a wrapped command is a
# broken command. Each still names `des run-slice-ats` so the tool is identifiable
# in the sentence; the runnable invocation is the thing below it.
_FAIL_HOW = (
    "green the failing slice acceptance test(s) named above -- fix the "
    "implementation until they pass, never the test. Then re-run the gate "
    "(`des run-slice-ats`) with the command below, and re-commit:"
)

_ZERO_EXECUTION_HOW = (
    "the declared acceptance test observed ZERO executed cases (an empty file, a "
    "module-level skip, `@pytest.mark.skip`, `xfail(run=False)`, or an empty "
    "`parametrize` set all zero it out) -- author a real, executing acceptance "
    "test for this slice. Then re-run the gate (`des run-slice-ats`) with the "
    "command below, and re-commit:"
)

_INDETERMINATE_HOW = (
    "make the target resolvable -- add the lockfile/manifest for this project's "
    "test runner at the target root, or resolve the ambiguous telemetry ledgers "
    "named above. Then re-run the gate (`des run-slice-ats`) with the command "
    "below:"
)


def _failure_why(failed_node_ids: tuple[str, ...], runner: str) -> str:
    """WHY a plain FAIL verdict was reached -- WHICH tests went red.

    The standing rule is WHAT / WHY / HOW on EVERY failure. The plain FAIL
    carried a WHAT and a HOW but no WHY: the developer was told their tests
    failed and what to do, never which ones -- information the gate HAD and
    discarded. This names them.

    Degrades honestly: if the runner's report could not be parsed for node-ids
    (a non-pytest runner, or an unrecognized summary shape), it says the count
    could not be attributed rather than inventing a WHY or restating the headline.
    """
    if not failed_node_ids:
        return (
            f"at least one acceptance test failed in `{runner}`, but the "
            "individual failing test(s) could not be attributed from the "
            "runner's report -- re-run the command below to see them"
        )
    named = list(failed_node_ids[:_MAX_NAMED_FAILURES])
    elided = len(failed_node_ids) - len(named)
    listed = ", ".join(named)
    suffix = f" (+{elided} more)" if elided > 0 else ""
    return (
        f"{len(failed_node_ids)} acceptance test(s) failed in `{runner}`: "
        f"{listed}{suffix}"
    )


def _emit_verdict(
    *,
    entering_slice: str,
    verdict: str,
    runner: str,
    scope: SliceGateRunScope,
    reason: str = "",
    how: str | None = None,
    command: str | None = None,
) -> None:
    """Print exactly one machine-readable JSON line naming the slice-AT verdict.

    ``command`` is the EXECUTABLE way out, carried as its own field rather than
    buried in the ``how`` prose: an agent consuming this payload can run it
    directly, with no sentence to parse. Same reason the console prints it on its
    own un-wrapped line -- a command is not prose, on either surface.

    ``how`` names the concrete remediation (GDP-3/GDP-4) on every verdict a
    consumer must ACT on -- ``FAIL`` (both flavours) and ``INDETERMINATE``. It is
    omitted entirely (no key at all) on ``PASS`` and ``NOT_APPLICABLE``, which are
    non-blocking and have nothing to remediate: an unconditional key would force a
    consumer to read a "how to fix" that does not apply, and PASS stays clean.

    The rule is remediation-follows-obligation, NOT surface-by-surface: whatever a
    verdict tells a human to do, it tells a machine to do. A payload carrying the
    what and the why but no way out is the same defect as a console line that does
    -- one aimed at an agent, one at a person.
    """
    payload: dict[str, object] = {
        "event": _EVENT,
        "entering_slice": entering_slice,
        "verdict": verdict,
        "runner": runner,
        "reason": reason,
        "ran_node_ids": list(scope.ran_node_ids),
        "ran_whole_tree": scope.ran_whole_tree,
        "out_of_slice_ran": list(scope.out_of_slice_ran),
    }
    if how is not None:
        payload["how"] = how
    if command is not None:
        payload["command"] = command
    print(json.dumps(payload))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des run-slice-ats",
        description=(
            "Run ONLY the entering slice's acceptance tests at commit (the "
            "acceleration); veto on a RED slice AT."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        dest="repo_root",
        required=True,
        help="the target repository root the slice's ATs are scoped within",
    )
    parser.add_argument(
        "--entering-slice",
        dest="entering_slice",
        required=True,
        help="the @<slice> tag of the slice being committed",
    )
    return parser.parse_args(argv)


def _emit_not_applicable(entering_slice: str) -> int:
    """Emit NOT_APPLICABLE for a no-real-AT slice -- non-blocking, no mutation.

    The no-real-AT guard (DDD-8 / CT-8): reached when the pytest-aware SSOT
    oracle (``feature_files_for_slice``) found no real DISTILL-authored AT of
    either convention (Gherkin ``.feature`` or pytest head-comment-tagged) for
    ``entering_slice`` on disk. Distinct from PASS (no slice tests ran) -- it
    does NOT fabricate an always-green AT and does NOT write anything into the
    target repo. Exit 0 (non-blocking) so an external target whose slice has
    no ATs yet is not vetoed, mirroring the ``_run_full_suite_leg``
    absent-suite NA.

    The human FACE is ``Verdict.NOT_APPLICABLE`` (⚪), never ``PASS`` (✅): the
    exit code is shared with PASS, but the developer-visible line must NOT be.
    A green check for "there is no acceptance test on disk" is the same class of
    lie the verdict logic was fixed for -- a face wearing another verdict's badge.
    """
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="NOT_APPLICABLE",
        runner="",
        scope=_EMPTY_SCOPE,
    )
    print_human_summary(
        Verdict.NOT_APPLICABLE,
        (
            f"slice {entering_slice} has no acceptance test on disk yet -- "
            "nothing to check here, not blocking your commit"
        ),
    )
    return 0


def _emit_indeterminate(repo_root: Path, entering_slice: str, reason: str) -> int:
    """Emit INDETERMINATE for an unrecognized/absent runner -- degrade-LOUD.

    The runner-resolution degrade (DDD-7 / CT-4): reached when
    ``TestRunnerPort.resolve`` returns ``Indeterminate`` (no recognized lockfile)
    or the resolved runner's concrete adapter is absent
    (``RunnerAdapterUnavailable``). Exit ``_INDETERMINATE_EXIT`` (not in {0, 1})
    so the failure is LOUD on the exit-code observable -- NEVER a silent pass and
    NEVER a pytest fallback on a non-Python target. The ``reason`` names the
    unresolved runner so the degrade is honest.

    The human FACE is ``Verdict.INDETERMINATE`` (❓), not ``DEGRADED`` (⚠️):
    "degraded" reads as "it ran, partially", but nothing was evaluated at all
    here. The line says so in words a developer reads correctly at a glance --
    neither a pass nor a failure.

    ONE TRUTH, BOTH SURFACES: the ``how`` goes on the JSON payload as well as the
    console. The standing rule is that every failure states WHAT failed, WHY, and
    HOW to fix it -- it does not say "every failure a HUMAN reads". This payload's
    consumers are gates and agents, and they were receiving the what and the why
    with no way out: the exact defect this feature closes, aimed at a machine
    instead of a person. The key is additive -- no existing consumer reads a key
    that was not there.
    """
    command = _rerun_command(repo_root, entering_slice)
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="INDETERMINATE",
        runner="",
        scope=_EMPTY_SCOPE,
        reason=reason,
        how=_INDETERMINATE_HOW,
        command=command,
    )
    print_human_summary(
        Verdict.INDETERMINATE,
        (
            f"slice {entering_slice} could NOT be checked: the gate did not run "
            "(neither a pass nor a failure)"
        ),
        why=reason,
        how=_INDETERMINATE_HOW,
        command=command,
    )
    return _INDETERMINATE_EXIT


def _emit_zero_execution(
    repo_root: Path, entering_slice: str, runner: str, reason: str
) -> int:
    """Refuse -- LOUD, never PASS, never NOT_APPLICABLE -- when the declared
    slice AT observed ZERO executed cases (the class invariant this slice
    exists to close): a file exists on disk and is head-tagged for this
    slice, but genuinely nothing ran. Reuses the existing ``FAIL`` verdict
    value -- no new verdict is introduced. ``ran_node_ids`` stays empty: the
    field testifies ONLY to what actually executed, never to what was merely
    declared or collected (so a skipped/xfailed case's node id can never
    appear in it).

    The human-readable line is deliberately worded differently from BOTH the
    genuine-PASS line and the genuine-FAIL line -- the exact console-line
    asymmetry the examiner's report demanded (a developer must not see the
    same green for "my AT ran and passed" and "my AT file is empty").
    """
    command = _rerun_command(repo_root, entering_slice)
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="FAIL",
        runner=runner,
        scope=_EMPTY_SCOPE,
        reason=reason,
        how=_ZERO_EXECUTION_HOW,
        command=command,
    )
    print_human_summary(
        Verdict.FAIL,
        (
            f"slice {entering_slice} declared an acceptance test but ZERO cases "
            "executed -- refused (not a pass)"
        ),
        why=reason,
        how=_ZERO_EXECUTION_HOW,
        command=command,
    )
    return 1


@dataclass(frozen=True)
class _ObservedRun:
    """What the runner ITSELF reported about the scoped run (the evidence).

    ``executed`` -- how many cases genuinely reached their body (the
    zero-observed-execution invariant reads this). ``failed_node_ids`` -- WHICH
    of them went red (the plain FAIL's WHY reads this). Both are observations of
    the runner's own report, never re-derived judgements: this type carries
    evidence, and the verdict logic elsewhere decides what it means.
    """

    executed: int
    failed_node_ids: tuple[str, ...]


def _normalize_node_id(raw: str) -> str:
    """Make a node-id reported by the runner USABLE as a selector.

    A reporter PLUGIN can render the short-summary node-id in a form pytest will
    not accept back: this repo's ``pytest-pspec`` prints
    ``tests/x.py::::test_a`` (four colons), and pasting that selects ZERO items
    -- silently, with exit 0. Naming a test the developer cannot actually run is
    the same defect class as printing a command that errors when pasted; the WHY
    must be usable, not merely accurate-looking.

    Collapses any run of ``:`` separators back to the canonical ``::``. Only the
    segment BEFORE a ``[`` is touched, so a parametrized id whose PARAMS contain
    colons (``test_slice[1:2]``) is never corrupted -- the id is normalized, the
    data inside it is left exactly as the runner reported it.
    """
    head, bracket, params = raw.partition("[")
    return f"{re.sub(r'::+', '::', head)}{bracket}{params}"


def _observe_run(repo_root: Path, node_ids: tuple[str, ...]) -> _ObservedRun:
    """Ask pytest what it ACTUALLY did with ``node_ids`` -- executed, and failed.

    Re-runs exactly the SAME scoped node-ids with ``-rap`` (report all outcomes
    including passed, without the noisy captured-output section) and reads the
    short summary. Two facts come out of the one report:

    * EXECUTED -- ``PASSED``/``FAILED``/``ERROR``/``XPASS`` lines. Root-cause
      agnostic BY CONSTRUCTION: it counts what pytest reports as executed, and
      never enumerates the ways execution can be skipped, so the next
      construction that zeroes out a test body needs no new code here.
    * FAILED node-ids -- the WHICH behind a red verdict, which the gate had and
      previously discarded.

    A timeout yields zero executed and no attributed failures -- a LOUD refusal
    downstream, never a silent pass.
    """
    interpreter = pytest_interpreter()
    try:
        completed = subprocess.run(
            [interpreter, "-m", "pytest", "-p", "no:cacheprovider", "-rap", *node_ids],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        return _ObservedRun(executed=0, failed_node_ids=())
    return _ObservedRun(
        executed=len(_EXECUTED_OUTCOME_RE.findall(completed.stdout)),
        failed_node_ids=tuple(
            _normalize_node_id(raw) for raw in _FAILED_NODE_RE.findall(completed.stdout)
        ),
    )


def _slice_run_scope(
    repo_root: Path, entering_slice: str, at_files: tuple[str, ...] | list[str]
) -> SliceGateRunScope:
    """Resolve the entering slice's RUN scope -- the node-ids that will actually
    be executed -- for EITHER authoring convention, in ONE currency.

    Both arms must testify to their execution in the same units (executed
    node-ids), because the zero-observed-execution invariant is enforced over
    that testimony. An arm that reports its scope in a different shape gets
    either a blanket refusal (if the invariant reads it as zero) or NO floor at
    all (if the invariant is skipped for it) -- both wrong. So:

    * GHERKIN arm -- the existing ``run_slice_ats`` seam (directory-collect over
      the slice's ``.feature`` dir, marker-filtered) stays the primary, unchanged
      for a target whose ATs carry the contract markers. When that
      marker-filtered collect yields NOTHING, the scope is re-derived
      marker-agnostically (``markers=None``) over the SAME slice directory rather
      than left empty. An empty scope is not a benign detail here: it was
      previously handed to ``RunnerAdapter.run`` as an empty node-id tuple, which
      shells pytest with no scoping args at all -- a silent WHOLE-TREE run whose
      green came from the target's other tests, not from this slice's AT. The
      re-derivation is what lets a genuinely-green Gherkin slice earn its PASS
      from its OWN executed scenario, and a hollow ``.feature`` collect zero and
      be refused by the same rule that refuses a hollow pytest file.
    * PYTEST arm -- scope narrowed to exactly the SSOT-resolved AT file(s),
      marker-agnostic (a head-comment-tagged AT carries no contract marker).

    Either way the returned ``ran_node_ids`` is the REAL set pytest collected for
    this slice and nothing else -- never the whole tree, never out-of-slice.
    """
    slice_dir = _slice_feature_dir(repo_root, entering_slice)
    if slice_dir is None:
        return SliceGateRunScope(
            ran_node_ids=tuple(
                _collect_node_ids(
                    repo_root,
                    paths=[repo_root / at_file for at_file in at_files],
                    markers=None,
                )
            ),
            ran_whole_tree=False,
            out_of_slice_ran=(),
        )

    gherkin_scope = run_slice_ats(repo_root, entering_slice)
    if gherkin_scope.ran_node_ids:
        return gherkin_scope

    marker_agnostic = tuple(
        _collect_node_ids(repo_root, paths=[slice_dir], markers=None)
    )
    return SliceGateRunScope(
        ran_node_ids=marker_agnostic,
        ran_whole_tree=False,
        out_of_slice_ran=tuple(
            node_id
            for node_id in marker_agnostic
            if not _node_belongs_to_slice(repo_root, node_id, entering_slice)
        ),
    )


def _telemetry_ledger_count(repo_root: Path) -> int:
    """How many in-flight ``atdd-pure`` telemetry ledgers exist under ``repo_root``.

    ``active_feature_id`` (the SSOT identity resolver) deliberately collapses
    "zero" and "more than one" into the SAME ``None`` -- it only needs to know
    whether picking ONE is safe. The no-real-AT guard (DDD-8/CT-8) needs to
    tell those two apart: ZERO ledgers means no feature is tracked here at
    all, so there is no ambiguity to hide a pytest-convention AT behind
    (NOT_APPLICABLE is safe); MULTIPLE ledgers is genuine ambiguity (a pytest
    AT could exist and be invisible -- INDETERMINATE, never a guess). This
    function COUNTS; it never PICKS -- the identity resolution stays solely
    in ``active_feature_id``, so there is still exactly one place that decides
    "which feature is active".
    """
    telemetry = repo_root / TELEMETRY_DIR_RELPATH
    if not telemetry.is_dir():
        return 0
    return len(list(telemetry.glob("*.jsonl")))


def main(argv: list[str] | None = None) -> int:
    """Run the entering slice's ATs and project the verdict onto the exit code.

    Exit-code contract (DDD-6): PASS -> 0, FAIL -> 1, NOT_APPLICABLE -> 0,
    INDETERMINATE -> != {0, 1}. The verdict JSON line names FAIL so a genuine veto
    is distinguishable from a bare module-absent exit-1 (the fixture-theater trap
    the AT guards against), names NOT_APPLICABLE so a no-real-AT slice is
    distinguishable from a green PASS, and names INDETERMINATE so an unrecognized
    runner degrades LOUD rather than vacuously passing. A declared-but-never-
    executed slice AT (ZERO observed execution, however produced) also earns
    FAIL, never PASS -- the class invariant this slice's second pass closes.

    Resolution order (CT-4 before CT-8): ``TestRunnerPort.resolve`` is consulted
    FIRST -- BEFORE the no-real-AT guard and BEFORE any pytest-bound collection
    (HIGH-2). An unrecognized/absent runner therefore degrades LOUD to
    INDETERMINATE before AT-detection ever touches the pytest collection path, so
    a non-Python target never hits pytest. Only once a recognized runner with a
    production-ready adapter is resolved does the executor proceed to the
    no-real-AT guard, then the SCOPE + RUN.
    """
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(args.repo_root)
    entering_slice = args.entering_slice

    # RESOLVE FIRST (DDD-2 / HIGH-2 / CT-4): consult the target's own runner via
    # FILESYSTEM lockfile inspection BEFORE any pytest-bound collection. An
    # unrecognized/absent runner -> Indeterminate -> degrade LOUD to the
    # INDETERMINATE verdict here, so the pytest-bound `run_slice_ats` collection
    # is never reached on a non-Python target (no InterpreterUnavailable, no
    # silent pass, no pytest fallback).
    resolved = resolve(repo_root)
    if isinstance(resolved, Indeterminate):
        return _emit_indeterminate(repo_root, entering_slice, resolved.reason)

    # AT DISCOVERY -- each arm requires ONLY what it actually needs.
    #
    # A GHERKIN slice AT is discoverable with NO feature id at all: it is found
    # by its own `@<slice>` tag on disk (`_slice_feature_dir`). A PYTEST-only
    # slice AT is NOT -- the head-comment-tag oracle (`feature_files_for_slice`)
    # is scoped BY feature id, so without one those files are invisible.
    #
    # Hence the feature id is a precondition of the PYTEST arm alone, never of
    # the Gherkin arm. Demanding it up-front for BOTH (as the first pass did)
    # made a plain target -- a real Gherkin AT, no `.nwave/telemetry/` ledger,
    # which is every external repo -- degrade to INDETERMINATE/exit-4 instead of
    # running the acceptance test sitting right there on disk.
    slice_dir = _slice_feature_dir(repo_root, entering_slice)
    feature_id = active_feature_id(repo_root)

    if slice_dir is None:
        # PYTEST arm -- the head-tag oracle NEEDS the feature id. Without one
        # a pytest-convention AT cannot be discovered by feature id alone, but
        # ``active_feature_id`` collapses two DIFFERENT situations into the
        # same ``None`` (ZERO ledgers vs MULTIPLE ledgers) -- and only one of
        # them is genuine ambiguity:
        #
        #   * ZERO ledgers -- no atdd-pure feature is being tracked under this
        #     repo AT ALL. There is no ambiguity to hide a pytest-convention AT
        #     behind: nothing is in flight, so the pytest arm has nothing to
        #     discover either. Combined with no Gherkin AT (``slice_dir is
        #     None``), this slice genuinely has no real AT of either
        #     convention on disk -- DDD-8/CT-8's NOT_APPLICABLE, not a guess.
        #   * MULTIPLE ledgers -- genuine ambiguity: several features ARE in
        #     flight and which one is "active" cannot be told apart, so a
        #     pytest AT COULD exist and be invisible. "No AT found" here would
        #     be a LIE. Degrade LOUD to INDETERMINATE -- never a silent
        #     NOT_APPLICABLE/exit-0, the indistinguishable-from-a-pass failure
        #     this feature exists to close.
        if feature_id is None:
            ledger_count = _telemetry_ledger_count(repo_root)
            if ledger_count == 0:
                return _emit_not_applicable(entering_slice)
            return _emit_indeterminate(
                repo_root,
                entering_slice,
                (
                    "cannot resolve the active feature id -- multiple "
                    f"in-flight telemetry ledgers under {TELEMETRY_DIR_RELPATH} "
                    "(ambiguous); a pytest-convention slice AT is discovered BY "
                    "feature id, so this slice's AT cannot be seen -- which is "
                    "not the same as it not existing"
                ),
            )
        at_files = feature_files_for_slice(repo_root, entering_slice, feature_id)
        # NO-REAL-AT GUARD (DDD-8 / CT-8): genuinely nothing declared for this
        # slice -- non-blocking NOT_APPLICABLE. A pure filesystem read; never
        # `run_slice_ats`'s AT-fabrication fallback (which would materialize an
        # always-green `assert True` into the target and report a false PASS).
        if not at_files:
            return _emit_not_applicable(entering_slice)
    else:
        # GHERKIN arm -- `_slice_run_scope` resolves its scope from `slice_dir`
        # (the `@<slice>`-tagged `.feature` directory) and never reads
        # `at_files`, so no feature-id-scoped discovery is needed here.
        at_files = []

    scope = _slice_run_scope(repo_root, entering_slice, at_files)

    # ZERO-OBSERVED-EXECUTION GUARD, part 1 (empty SCOPE): a declared AT that
    # pytest's OWN collection step could not find a single case in (a hollow
    # file with zero test functions, a module-level `pytest.skip`, a hollow
    # `.feature` with no bound scenario) -- refuse BEFORE ever calling
    # `RunnerAdapter.run`. An empty node-id tuple passed to the runner would
    # invoke pytest with NO scoping args at all, silently widening the run to
    # the WHOLE target tree and earning a verdict from tests that are not this
    # slice's -- refusing here closes that scope-leak as a side effect of
    # enforcing the invariant.
    if not scope.ran_node_ids:
        return _emit_zero_execution(
            repo_root,
            entering_slice,
            resolved.name,
            "the declared acceptance test collected zero executable cases",
        )

    try:
        run_verdict = resolved.run(repo_root, scope.ran_node_ids)
    except RunnerAdapterUnavailable as unavailable:
        return _emit_indeterminate(repo_root, entering_slice, str(unavailable))

    # OBSERVE what the runner ACTUALLY did (pytest-only: the sole production-ready
    # run-facet -- a future non-pytest runner must never have a pytest binary
    # invoked against it, so it degrades to the unattributed WHY below).
    #
    # One observation feeds BOTH obligations: the zero-observed-execution
    # invariant (how many cases reached their body) and the FAIL verdict's WHY
    # (which of them went red). The verdict itself is ALREADY decided by
    # `run_verdict` -- this is evidence-gathering for the surfaces, never a
    # second opinion that could contradict the gate.
    observed = (
        _observe_run(repo_root, scope.ran_node_ids)
        if resolved.name == "pytest"
        else None
    )

    # ZERO-OBSERVED-EXECUTION GUARD, part 2 (collected-but-never-run): the SCOPE
    # was non-empty AND the RUN reported green, yet the collected case(s) may
    # still never have reached pytest's "call" phase (`@skip`, `xfail(run=False)`,
    # an empty `parametrize` set).
    if run_verdict.passed and observed is not None and observed.executed == 0:
        return _emit_zero_execution(
            repo_root,
            entering_slice,
            run_verdict.runner,
            "the declared acceptance test collected non-zero cases but "
            "zero were observed to actually execute (skipped / "
            "xfail(run=False) / empty parametrize set)",
        )

    if run_verdict.passed:
        _emit_verdict(
            entering_slice=entering_slice,
            verdict="PASS",
            runner=run_verdict.runner,
            scope=scope,
        )
        print_human_summary(
            Verdict.PASS,
            f"slice {entering_slice} acceptance tests passed",
        )
        _record_outcome(repo_root, entering_slice, feature_id, GateVerdict.PASS)
        return 0

    # THE PLAIN FAIL -- WHAT / WHY / HOW, on BOTH surfaces.
    #
    # It used to carry a WHAT and (in JSON only) a HOW, and NO WHY at all: the
    # developer was told their tests failed and what to do, but never WHICH tests
    # failed -- information the gate HELD and threw away. `why` now names the red
    # node-ids, and it is passed to `_emit_verdict` as `reason` so the machine
    # channel carries the identical fact (one truth, both surfaces) rather than an
    # empty string.
    why = _failure_why(
        observed.failed_node_ids if observed is not None else (),
        run_verdict.runner,
    )
    command = _rerun_command(repo_root, entering_slice)
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="FAIL",
        runner=run_verdict.runner,
        scope=scope,
        reason=why,
        how=_FAIL_HOW,
        command=command,
    )
    print_human_summary(
        Verdict.FAIL,
        f"slice {entering_slice} acceptance tests FAILED -- commit refused",
        why=why,
        how=_FAIL_HOW,
        command=command,
    )
    _record_outcome(repo_root, entering_slice, feature_id, GateVerdict.FAIL)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
