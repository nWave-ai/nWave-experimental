"""Drive the invocable steps one at a time, as a TEST-SIDE stimulus.

WHY THIS IS NOT A SEQUENCER, and the distinction is the whole point of the
`des dispatch` retirement. ADR-SSOT-002 Section 4b forbids a software executor
that «calls one step and then calls the next» -- in PRODUCTION. A test that
wants to observe the law of `craft` still has to reach a state where a value is
designed and its oracle recorded, and the honest way to reach it is to invoke
those steps explicitly, from the test, exactly as the orchestrator does.

So this module lives under `tests/`, is imported by no production module, takes
NO continuation decision of its own -- it refuses to guess, returning the first
step outcome that is not what the caller asked for -- and offers no loop over a
Request. It is the harness saying «put me in this state», not software deciding
what happens next.

`test_no_step_executes_the_step_it_names` is the guard that keeps that true:
it reads the PRODUCTION registry and its step modules, so nothing here can
satisfy it by accident.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    DesignOptions,
    SelectedValue,
)
from des.application.handover import StoredHandover, load_handover


if TYPE_CHECKING:
    from pathlib import Path

    from des.application.delivery_continuation import AuthorityFacts
    from des.ports.driven_ports.task_invocation_port import TaskInvocationPort


class StepRefused(Exception):
    """A step the stimulus needed answered something other than success.

    Raised rather than returned so a scenario that meant to observe `craft`
    cannot silently assert against a state `design` never produced.
    """

    def __init__(self, step: str, outcome: DeliveryOutcome) -> None:
        what = outcome.failure.what if outcome.failure is not None else "(no failure)"
        super().__init__(
            f"the {step} step answered {outcome.disposition.value}: {what}"
        )
        self.step = step
        self.outcome = outcome


def _reread(root: Path, request: str) -> StoredHandover:
    stored = load_handover(root, request)
    assert isinstance(stored, StoredHandover), stored
    return stored


def decomposed(
    runner: DeliveryContinuationRunner,
    port: TaskInvocationPort,
    root: Path,
    request: str,
) -> StoredHandover:
    """`des po`, once."""
    stored = runner.decompose(root, port, request)
    if isinstance(stored, DeliveryOutcome):
        raise StepRefused("po", stored)
    return stored


# The leading parameters are the ambient context every step helper in this module
# needs: the runner to call, its port, the tree, and the stored handover. Folding
# them into one record would rewrite 45 call sites across the DES unit and
# acceptance suites and would prevent nothing, because `DeliveryContinuationRunner`,
# `TaskInvocationPort`, `Path` and `StoredHandover` are four DISTINCT types: a
# positional transposition fails loudly rather than silently, which is the opposite
# of the same-typed-neighbour hazard this burn-down groups to remove.
#
# These four are not `design_value`'s own arguments forwarded unchanged: `runner` is
# the RECEIVER, and the fourth argument reaching `design_value` is
# `stored.values[position]`, derived here rather than passed through.
def designed(  # noqa: PLR0913 - see the note above
    runner: DeliveryContinuationRunner,
    port: TaskInvocationPort,
    root: Path,
    stored: StoredHandover,
    position: int = 0,
    *,
    competence: str | None = None,
) -> tuple[StoredHandover, AuthorityFacts]:
    """`des design --value N`, once, for the value at `position`.

    There is no `finding` parameter. One existed, forwarded to `design_value`,
    and no caller in the suite ever passed it, so it could only ever forward
    None. Corrections are driven through `oracled`, which does take one.
    """
    bound = runner.design_value(
        root,
        port,
        stored,
        stored.values[position],
        options=DesignOptions(competence=competence),
    )
    if isinstance(bound, DeliveryOutcome):
        raise StepRefused("design", bound)
    return bound


# Same four ambient parameters as `designed` above, plus the bound `design` the
# oracle is measured against and the `position` selecting the value. Those two are
# an `AuthorityFacts` and an `int`, so they are not transposable either, and the
# argument for not folding is `designed`'s argument unchanged.
def oracled(  # noqa: PLR0913 - see `designed` above
    runner: DeliveryContinuationRunner,
    port: TaskInvocationPort,
    root: Path,
    stored: StoredHandover,
    design: AuthorityFacts,
    *,
    position: int = 0,
    finding: str | None = None,
):
    """`des oracle --value N`, once. The measured set travels back unjudged."""
    return runner.oracle_value(
        root,
        port,
        SelectedValue(stored, stored.values[position], design),
        finding=finding,
    )


# Same shape as `oracled` above: the four ambient parameters, the bound `design`,
# and `position`. All six types are distinct, so no positional pair can swap
# silently, and folding would churn this module's call sites for no defect.
def crafted(  # noqa: PLR0913 - see `designed` above
    runner: DeliveryContinuationRunner,
    port: TaskInvocationPort,
    root: Path,
    stored: StoredHandover,
    design: AuthorityFacts,
    *,
    position: int = 0,
) -> DeliveryOutcome | tuple[str, ...]:
    """`des craft --value N`, once. Returns the outcome or the SILENT rows."""
    return runner.craft_value(root, port, stored, stored.values[position], design)


def through_oracle(
    port: TaskInvocationPort,
    root: Path,
    request: str,
    position: int = 0,
) -> tuple[DeliveryContinuationRunner, StoredHandover, AuthorityFacts]:
    """`po`, then `design` and `oracle` for one value -- the state `craft` needs.

    Three named invocations and no decision between them: each is the step the
    CALLER asked for, and a step that answers anything else stops the stimulus
    with `StepRefused` instead of being routed anywhere.
    """
    runner = DeliveryContinuationRunner(port)
    stored = decomposed(runner, port, root, request)
    stored, design = designed(runner, port, root, stored, position)
    measured = oracled(runner, port, root, stored, design, position=position)
    if measured.refusal is not None:
        refusal = measured.refusal
        outcome = getattr(refusal, "terminal", refusal)
        raise StepRefused("oracle", outcome)
    return runner, _reread(root, stored.request), design
