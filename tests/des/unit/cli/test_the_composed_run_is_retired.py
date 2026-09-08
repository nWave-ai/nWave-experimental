"""`des dispatch` and its composer are GONE, and the steps it composed are not.

ADR-SSOT-002 Section 4b: «`des dispatch` is RETIRED as an orchestrator. No
executor in the software composes the steps. No code path calls one step and
then calls the next.»  ADR-DES-003 Section 11 names the composer by member:
«`des dispatch` itself is the composer: `_run_locked` and `_finalize_request`
call one step and then the next.»

WHY A FILE'S DISAPPEARANCE IS NOT THE PROPERTY.  A module can be deleted while
its whole-Request loop is moved one directory sideways, or kept alive under a
second name, and every check keyed on `dispatch.py` staying absent would report
that as a retirement.  What is asserted here is therefore structural and on the
application boundary itself: the class that owned the composition no longer
CARRIES a member that composes, and no registered command can reach it.

The survival half is asserted in the same file on purpose.  An absence test
alone is satisfied by deleting the delivery model, so each assertion of what is
gone is paired with the invocable steps that must still be there.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

from des.cli.__main__ import _REGISTRY


#: The steps of one Request, plus the lane cycle -- the surface that REPLACES
#: the composed run and must survive its removal (ADR-DES-003 Section 14,
#: "Keep, untouched").
SURVIVING_COMMANDS = (
    "state",
    "project",
    "devops",
    "po",
    "design",
    "oracle",
    "craft",
    "verify",
    "integrate",
    "lane",
)

#: The members of `DeliveryContinuationRunner` that exist only to run one step
#: and then the next, measured by static reachability from the step surface
#: (`delivery_steps.py`, `delivery_state.py` and the CLI step modules) before
#: the removal: each one had exactly one caller, itself inside this set.
COMPOSER_MEMBERS = (
    "run",
    "_run_locked",
    "_finalize_request",
    "_terminal",
    "_post_bind_batch",
    "_product_owner_correction",
    "_reviewed_oracle_set",
    "_measured_oracle_set",
    "_aggregate_acceptance_review",
    "_acceptance_evidence",
)

_RUNNER_CLASS = "DeliveryContinuationRunner"


def _runner_members() -> set[str]:
    module = importlib.import_module("des.application.delivery_continuation")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    owner = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == _RUNNER_CLASS
    )
    return {
        node.name
        for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_the_cli_carries_no_dispatch_row_and_still_carries_every_step() -> None:
    """The public command is unregistered; the surface that replaces it is not."""
    registered = {row.name for row in _REGISTRY}
    assert "dispatch" not in registered, (
        "`des dispatch` is still registered -- Section 4b retires the command, "
        "not only its documentation"
    )
    missing = [name for name in SURVIVING_COMMANDS if name not in registered]
    assert not missing, f"the retirement took invocable steps with it: {missing}"


def test_no_module_named_dispatch_can_be_imported_from_the_cli_package() -> None:
    """The entry point is unreachable by name, not merely unlisted."""
    assert importlib.util.find_spec("des.cli.dispatch") is None


@pytest.mark.parametrize("member", COMPOSER_MEMBERS)
def test_the_runner_carries_no_member_that_composes_one_step_into_the_next(
    member: str,
) -> None:
    """The composer is gone from the application boundary that owned it.

    Keyed on the class rather than on a file, so moving the loop to another
    module under another name does not read as a retirement.
    """
    assert member not in _runner_members(), (
        f"`{_RUNNER_CLASS}.{member}` still composes a whole Request -- "
        "«no code path calls one step and then calls the next»"
    )


def test_the_runner_still_carries_the_mechanics_the_single_steps_call() -> None:
    """Retiring the sequencer keeps every per-step entry point the steps use.

    This is the falsifier for a retirement done by deleting the delivery model:
    each name here is a single-turn boundary a CLI step invokes directly.
    """
    members = _runner_members()
    kept = (
        "decompose",
        "rewrite_request",
        "design_value",
        "oracle_value",
        "craft_value",
        "verify_request",
        "integrate_candidate",
        "devops_constraints",
        "derive_authority",
        "record_verified_candidate",
        "record_integration_decision",
    )
    missing = [name for name in kept if name not in members]
    assert not missing, (
        f"single-step mechanics were removed with the composer: {missing}"
    )
