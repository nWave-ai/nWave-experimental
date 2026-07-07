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
mutate the target repo. When the entering slice has NO real DISTILL-authored
``.feature`` tagged ``@<entering_slice>`` on disk, the executor returns
NOT_APPLICABLE WITHOUT calling ``run_slice_ats`` -- because ``run_slice_ats``
(via ``_ensure_slice_at_scope`` -> ``_materialize_representative_slice_at``)
would FABRICATE an always-green ``assert True`` AT into the target repo and
report a silent false PASS. The real-AT detection consults ``_slice_feature_dir``
(a pure filesystem read that returns the real feature dir or ``None``, NEVER
materializing); only when a real ``.feature`` exists does the executor proceed to
the SCOPE + RUN.

> slice-02 inserts ``TestRunnerPort.resolve`` consulted FIRST (degrade-LOUD
> INDETERMINATE before any pytest-bound collection). This slice-01 executor RUNS
> the dogfood pytest scope; the runner-resolution short-circuit is slice-02's
> hardening.

stdlib + ``des.*`` only (F-D-09 clean: roots = {des}).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary
from des.cli.run_contract_gate import (
    SliceGateRunScope,
    _slice_feature_dir,
    run_slice_ats,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate
from des.ports.test_runner_port import RunnerAdapterUnavailable, resolve


_EVENT = "SliceAtGateResult"

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


# GDP-3/GDP-4 (self-explaining + HOW-invokes-the-producing-tool): the concrete
# remediation named on a FAIL verdict -- green the failing slice acceptance
# test(s) (fix the implementation, not the test), then re-run the SAME
# producing tool (`des run-slice-ats`) and re-commit. Never emitted on PASS.
_FAIL_HOW = (
    "green the failing slice acceptance test(s) -- fix the implementation "
    "until they pass -- then re-run `des run-slice-ats` and re-commit."
)


def _emit_verdict(
    *,
    entering_slice: str,
    verdict: str,
    runner: str,
    scope: SliceGateRunScope,
    reason: str = "",
    how: str | None = None,
) -> None:
    """Print exactly one machine-readable JSON line naming the slice-AT verdict.

    ``how`` names the concrete remediation on a FAIL verdict (GDP-3/GDP-4) --
    omitted entirely (no key at all) on every other verdict, so PASS stays
    clean.
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
    print(json.dumps(payload))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des run-slice-ats",
        description=(
            "Run ONLY the entering slice's acceptance tests at commit (the "
            "acceleration); veto on a RED slice AT."
        ),
    )
    parser.add_argument(
        "--repo-root",
        "--repo",
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

    The no-real-AT guard (DDD-8 / CT-8): reached when ``_slice_feature_dir``
    found no real DISTILL-authored ``.feature`` tagged ``@<entering_slice>`` on
    disk. Distinct from PASS (no slice tests ran) -- it does NOT fabricate an
    always-green AT and does NOT write anything into the target repo. Exit 0
    (non-blocking) so an external target whose slice has no ATs yet is not
    vetoed, mirroring the ``_run_full_suite_leg`` absent-suite NA.
    """
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="NOT_APPLICABLE",
        runner="",
        scope=_EMPTY_SCOPE,
    )
    print_human_summary(
        Verdict.PASS,
        (
            f"slice {entering_slice} has no real acceptance test on disk -- "
            "NOT_APPLICABLE (no fabricated AT, no commit veto)"
        ),
    )
    return 0


def _emit_indeterminate(entering_slice: str, reason: str) -> int:
    """Emit INDETERMINATE for an unrecognized/absent runner -- degrade-LOUD.

    The runner-resolution degrade (DDD-7 / CT-4): reached when
    ``TestRunnerPort.resolve`` returns ``Indeterminate`` (no recognized lockfile)
    or the resolved runner's concrete adapter is absent
    (``RunnerAdapterUnavailable``). Exit ``_INDETERMINATE_EXIT`` (not in {0, 1})
    so the failure is LOUD on the exit-code observable -- NEVER a silent pass and
    NEVER a pytest fallback on a non-Python target. The ``reason`` names the
    unresolved runner so the degrade is honest.
    """
    _emit_verdict(
        entering_slice=entering_slice,
        verdict="INDETERMINATE",
        runner="",
        scope=_EMPTY_SCOPE,
        reason=reason,
    )
    print_human_summary(
        Verdict.DEGRADED,
        (
            f"slice {entering_slice} runner could not be resolved -- "
            f"INDETERMINATE (degrade-LOUD, no silent pass): {reason}"
        ),
    )
    return _INDETERMINATE_EXIT


def main(argv: list[str] | None = None) -> int:
    """Run the entering slice's ATs and project the verdict onto the exit code.

    Exit-code contract (DDD-6): PASS -> 0, FAIL -> 1, NOT_APPLICABLE -> 0,
    INDETERMINATE -> != {0, 1}. The verdict JSON line names FAIL so a genuine veto
    is distinguishable from a bare module-absent exit-1 (the fixture-theater trap
    the AT guards against), names NOT_APPLICABLE so a no-real-AT slice is
    distinguishable from a green PASS, and names INDETERMINATE so an unrecognized
    runner degrades LOUD rather than vacuously passing.

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
        return _emit_indeterminate(entering_slice, resolved.reason)

    # NO-REAL-AT GUARD (DDD-8 / CT-8): only AFTER a runner resolved, consult a
    # PURE filesystem read for a real DISTILL-authored `.feature` BEFORE
    # `run_slice_ats` (which would fabricate an always-green AT into the target
    # repo on absence). A verification run must NEVER mutate the target.
    if _slice_feature_dir(repo_root, entering_slice) is None:
        return _emit_not_applicable(entering_slice)

    scope = run_slice_ats(repo_root, entering_slice)
    try:
        run_verdict = resolved.run(repo_root, scope.ran_node_ids)
    except RunnerAdapterUnavailable as unavailable:
        return _emit_indeterminate(entering_slice, str(unavailable))

    verdict = "PASS" if run_verdict.passed else "FAIL"
    _emit_verdict(
        entering_slice=entering_slice,
        verdict=verdict,
        runner=run_verdict.runner,
        scope=scope,
        how=None if run_verdict.passed else _FAIL_HOW,
    )
    human = Verdict.PASS if run_verdict.passed else Verdict.FAIL
    print_human_summary(
        human,
        (
            f"slice {entering_slice} acceptance tests passed"
            if run_verdict.passed
            else f"slice {entering_slice} acceptance tests FAILED -- commit refused"
        ),
    )
    return 0 if run_verdict.passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
