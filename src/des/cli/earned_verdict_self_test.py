"""des.cli.earned_verdict_self_test -- the earned-verdict gate's self-test (AT-2).

The gate proves it is not itself theater. It perturbs its OWN verdict CORE at the
``verdict-core`` seam and DEMANDS its own verdict flips RED: a gate that stayed
GREEN against a broken CORE would itself be theater. The honesty proof is the
differential

    (perturbed -> RED) and (un-perturbed -> GREEN)

The un-perturbed *control* leg closes the hard-coded-RED hole: a self-test that
emitted RED regardless of perturbation would fail the control.

How it works -- a known-theater probe through the CORE:

  * the self-test holds a fixed *theater* probe: a baseline-green run paired with
    a perturbed run that STILL ran green (it held against broken code). A HONEST
    CORE rules this RED (``theater-held``) -- so the gate's self-test PASSES
    (status GREEN): the core correctly detected theater.
  * when the ``verdict-core`` seam is perturbed (``--perturb-core verdict-core``
    with ``NWAVE_PERTURB=verdict-core``) the CORE is swapped for a deliberately
    broken stand-in that can no longer detect theater (it rules everything
    GREEN). The probe that was RED is now GREEN -- the self-test SEES its core is
    broken and emits status RED, denying its own commit.

The perturbation MUST reach this subprocess for the flip to be genuine: the
``--perturb-core`` argv and the ``NWAVE_PERTURB`` env (the uniform frozen
selector) are both read here, mirroring the ``run_tests`` / ``inject_seam``
adapters. A dropped flag would leave the probe RED un-perturbed too and fail the
control.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from des.domain.earned_verdict import (
    EarnedVerdict,
    TestRun,
    VerdictStatus,
    compute_verdict,
)
from des.domain.seam_injection import PERTURB_ENV


# The CORE's OWN declared seam (GAP-3b). The self-test perturbs THIS seam to prove
# the gate is causally bound to its own perturbation, never hard-wiring RED.
_CORE_SEAM = "verdict-core"

# The fixed theater probe: a baseline-green run + a perturbed run that STILL ran
# green. An HONEST CORE rules this RED (theater-held) -- the probe a working gate
# must be able to detect. The seam / at id name the gate's own self-probe.
_PROBE_BASELINE = TestRun(runner="pytest", passed=1, failed=0, exit_code=0)
_PROBE_PERTURBED = TestRun(runner="pytest", passed=1, failed=0, exit_code=0)
_PROBE_SEAM = "self-test-core-seam"
_PROBE_AT = "self-test-theater-probe"


def main(argv: list[str] | None = None) -> int:
    """Run the gate's self-test. Returns 0 on a GREEN self-test, 2 on a RED one."""
    perturb_core = _core_perturbed(_parse_args(argv))
    status = _self_test_status(perturb_core)
    _emit(status)
    return 0 if status is VerdictStatus.GREEN else 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--perturb-core <seam>`` argv contract."""
    parser = argparse.ArgumentParser(prog="earned-verdict-self-test")
    parser.add_argument("--perturb-core", default=None)
    return parser.parse_args(argv)


def _core_perturbed(args: argparse.Namespace) -> bool:
    """Whether the CORE's own ``verdict-core`` seam is selected for perturbation.

    The uniform frozen selector: the ``--perturb-core`` argv AND the
    ``NWAVE_PERTURB`` env must both name the CORE seam. Both are read so the
    perturbation is a real selection that reached the subprocess, never a dropped
    flag (the control leg would otherwise also flip RED).
    """
    return args.perturb_core == _CORE_SEAM and os.environ.get(PERTURB_ENV) == _CORE_SEAM


def _self_test_status(perturb_core: bool) -> VerdictStatus:
    """Rule the gate's self-test over the theater probe, perturbed or control.

    GREEN -- an HONEST CORE ruled the theater probe RED (theater-held): the gate
             can detect theater, so it is itself honest.
    RED   -- a perturbed/broken CORE ruled the probe GREEN (theater NOT detected):
             the gate's own core is broken, so the gate is itself theater.
    """
    probe_verdict = _rule_probe(perturb_core)
    core_detected_theater = probe_verdict.status is VerdictStatus.RED
    return VerdictStatus.GREEN if core_detected_theater else VerdictStatus.RED


def _rule_probe(perturb_core: bool) -> EarnedVerdict:
    """Rule the fixed theater probe through the CORE (real or fault-swapped).

    The seam swap is a bounded factory-lookup-by-name: ``verdict-core`` resolves
    to the real :func:`compute_verdict` un-perturbed, or to a broken stand-in
    that rules everything GREEN when perturbed.
    """
    core = _broken_core if perturb_core else compute_verdict
    return core(
        _PROBE_BASELINE,
        _PROBE_PERTURBED,
        seam_id=_PROBE_SEAM,
        at_id=_PROBE_AT,
    )


def _broken_core(
    baseline: TestRun,
    perturbed: TestRun,
    seam_id: str,
    at_id: str,
) -> EarnedVerdict:
    """The deliberately-broken ``verdict-core`` fault: it rules everything GREEN.

    A CORE that can no longer detect theater (it never returns RED). The self-test
    swaps the real CORE for this fault when ``verdict-core`` is perturbed, then
    DEMANDS the probe's previously-RED verdict flip GREEN -- proving the gate is
    causally bound to its own seam.
    """
    from des.domain.earned_verdict import VerdictReason

    return EarnedVerdict(
        status=VerdictStatus.GREEN,
        reason=VerdictReason.VERDICT_FLIPPED,
        seam_id=seam_id,
        at_id=at_id,
        baseline=baseline,
        perturbed=perturbed,
    )


def _emit(status: VerdictStatus) -> None:
    """Print the self-test emission: the status + a deny body on RED.

    The composition reads ``status`` for the differential and treats
    ``decision:block`` (set iff RED) as the gate denying its own commit.
    """
    body: dict[str, str] = {"status": status.value}
    if status is VerdictStatus.RED:
        body["decision"] = "block"
        body["reason"] = (
            "self-test RED: the gate's own verdict-core seam was perturbed and the "
            "gate's verdict failed to detect theater -- the gate denies its own "
            "commit"
        )
    print(json.dumps(body))


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))
