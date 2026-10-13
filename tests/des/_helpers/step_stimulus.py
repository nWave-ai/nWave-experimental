"""Explicit test-host role execution followed by deterministic DES operations.

The scripted host is test infrastructure, never a production DES callback.
Each helper performs only the action its caller selected; no continuation loop
or fallback chooses the next role.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    SelectedValue,
)
from des.application.delivery_steps import DeliverySteps, ReplacementModes
from des.application.handover import StoredHandover, load_handover
from tests.des._helpers.host_facts import product_manifest


if TYPE_CHECKING:
    from pathlib import Path


class StepRefused(Exception):
    def __init__(self, step, outcome):
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


def _prompt(**facts):
    return "\n".join(f"{name}: {json.dumps(value)}" for name, value in facts.items())


def decomposed(runner, port, root, request):
    supplied = port.invoke(
        role_id="nw-product-owner", prompt=_prompt(request=request), cwd=root
    )
    manifest = product_manifest(
        request, [value.observation for value in supplied.product_values]
    )
    outcome = DeliverySteps().discuss_document(
        root, json.dumps(manifest), project=False, feature="fixture"
    )
    if not outcome.succeeded:
        raise StepRefused("po", outcome)
    return _reread(root, request)


def designed(runner, port, root, stored, manifest, *, position=0):  # noqa: PLR0913 - explicit host, repository and selected evidence context
    observation = stored.values[position].observation
    port.invoke(
        role_id="nw-solution-architect",
        prompt=_prompt(observation=observation),
        cwd=root,
    )
    outcome = DeliverySteps().design_document(
        root,
        position + 1,
        json.dumps(manifest),
        modes=ReplacementModes(
            replace_current=stored.values[position].authority is not None
        ),
    )
    if not outcome.succeeded:
        raise StepRefused("design", outcome)
    stored = _reread(root, stored.request)
    authority = runner.selected_authority(root, stored, position + 1)
    if isinstance(authority, DeliveryOutcome):
        raise StepRefused("design", authority)
    return stored, authority


def oracled(runner, port, root, stored, design, *, position=0, finding=None):  # noqa: PLR0913 - explicit host, repository and selected evidence context
    port.invoke(
        role_id="nw-acceptance-designer",
        cwd=root,
        prompt=_prompt(
            observation=stored.values[position].observation,
            oracle=design.acceptance_paths[0],
            finding=finding,
        ),
    )
    return runner.measure_oracle(
        root, SelectedValue(stored, stored.values[position], design)
    )


def crafted(runner, port, root, stored, design, *, position=0):  # noqa: PLR0913 - explicit host, repository and selected evidence context
    supplied = port.invoke(
        role_id="nw-software-crafter",
        cwd=root,
        prompt=_prompt(
            observation=stored.values[position].observation,
            mutable_targets=[
                path
                for path, decision in design.target_decisions
                if decision != "REUSE" and path not in design.acceptance_paths
            ],
        ),
    )
    result = {
        "structured_output": {
            "outcome": supplied.outcome.value,
            "diagnostic": supplied.diagnostic,
            "blocked_by": supplied.craft_blocker.value
            if supplied.craft_blocker
            else None,
        }
    }
    outcome = DeliverySteps().craft(root, position + 1, json.dumps(result))
    return (
        ()
        if outcome.succeeded
        else DeliveryOutcome(outcome.disposition, outcome.failure)
    )


def through_oracle(port, root, request, manifest, position=0):
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, root, request)
    stored, design = designed(runner, port, root, stored, manifest, position=position)
    measured = oracled(runner, port, root, stored, design, position=position)
    if measured.refusal is not None:
        raise StepRefused("oracle", measured.refusal)
    return runner, _reread(root, stored.request), design
