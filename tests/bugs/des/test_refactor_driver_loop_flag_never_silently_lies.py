# @feature-des-refactor-fixer-swarm
"""Regression AT -- `des refactor --driver loop` must never be a silent no-op.

RCA (bugfix-refactor-driver-loop-dead-code dispatch, confirmed 2026-07-21):
`_parse_args` in `src/des/cli/refactor.py:199` parses `--driver
{python,loop}` (default `python`) into `args.driver`, but neither `main()`
in that module nor `RefactorDrainService` (`src/des/application/
refactor_drain_service.py`) ever reads `args.driver` again -- confirmed via
exhaustive grep, zero hits on `args.driver` / `.driver` outside the parser
definition. `--driver loop` is silently ACCEPTED and produces behavior
IDENTICAL to the `python` default: a GDP-6 silent-wrong violation (a
maintainer who explicitly asks for the loop driver gets the python driver,
with no message telling them so).

Charter: docs/product/expectations/fix-refactor-driver-loop-dead-code/
driver-flag-never-silently-lies-about-what-it-does.md

Driving surface (Mandate 16, default IN-PROCESS): Layer 2 in-process via
`RefactorSwarmComposition.call_refactor_main_in_process_with_driver` --
drives the REAL `des.cli.refactor.main` entry directly, no interpreter
fork. Reuses the same production-composition harness `tests/des/refactor/`
already established (Pillar 3, SSOT-via-Types-Services-DSL) rather than
re-deriving a parallel fixture. `capsys` captures the CLI's OWN
stdout/stderr on the SAME call under test -- the exact surface a maintainer
is already looking at.

RED-for-right-reason: `--driver loop` currently drains the pile item and
exits 0 exactly like the default -- `test_driver_loop_refuses_...` below
fails today with a genuine `AssertionError` (expected non-zero exit /
refusal message naming "loop", got a successful silent drain), never an
import/collection error.

covers: bug-observable (EXP-fix-refactor-driver-loop-dead-code-1)
"""

from __future__ import annotations

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# keeps the runtime freshness gate's one-shot stderr event out of every
# test's captured output below regardless of collection/execution order
# (mirrors tests/des/refactor/test_slice_01_observability.py's precedent).
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401
from tests.des.refactor.composition import RefactorSwarmComposition
from tests.des.refactor.domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance


# --- AT-1 (the diagnosed defect): --driver loop refuses, never silently ----
# behaves like --driver python -----------------------------------------------


def test_driver_loop_refuses_with_a_clear_reason_naming_python_as_the_working_default(
    tmp_path, capsys
):
    """Given a pile with one item, When `des refactor --driver loop` runs,
    Then it refuses immediately with a message naming that the loop driver
    isn't available yet and pointing at `python` as the working default --
    it must NEVER silently proceed and drain the item as if `python` had
    been requested.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    exit_code = composition.call_refactor_main_in_process_with_driver(
        driver="loop", agent_cmd=composition.capturing_agent_cmd()
    )
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()

    assert exit_code != 0, (
        "--driver loop must refuse (non-zero exit), not silently proceed "
        f"like the default; got exit_code={exit_code}, "
        f"combined_output={captured.out + captured.err!r}"
    )
    assert "loop" in combined, (
        "the refusal must name the 'loop' driver so the maintainer knows "
        f"which choice triggered it; got: {captured.out + captured.err!r}"
    )
    assert "python" in combined, (
        "the refusal must point at 'python' as the working default so the "
        f"maintainer has a concrete next step; got: {captured.out + captured.err!r}"
    )
    assert composition.agent_was_never_invoked(), (
        "the refusal must happen BEFORE any agent dispatch -- the "
        "configured agent_cmd must never run for a rejected --driver loop "
        "request"
    )
    assert composition.pile_contains("TD-001"), (
        "TD-001 must remain untouched in techdebt.md -- a refused "
        "--driver loop request must never drain the item as a side effect"
    )


def test_driver_loop_never_produces_output_indistinguishable_from_python(
    tmp_path, capsys
):
    """Given the exact same pile+agent_cmd, When `des refactor` runs once
    with `--driver python` and once with `--driver loop`, Then the two runs
    must NOT be observably identical -- pinning the charter's core negative
    oracle directly (today they ARE identical, which is the bug).

    CONTRACT_SHAPE: bounded-change
    """
    python_root = tmp_path / "python-run"
    python_root.mkdir()
    python_run = RefactorSwarmComposition(python_root)
    python_run.init_git_repo()
    python_run.prepare_clean_integration_branch()
    python_run.seed_pile_item(item_id="TD-001")
    python_exit = python_run.call_refactor_main_in_process_with_driver(
        driver="python",
        agent_cmd=python_run.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        ),
    )
    python_captured = capsys.readouterr()

    loop_root = tmp_path / "loop-run"
    loop_root.mkdir()
    loop_run = RefactorSwarmComposition(loop_root)
    loop_run.init_git_repo()
    loop_run.prepare_clean_integration_branch()
    loop_run.seed_pile_item(item_id="TD-001")
    loop_exit = loop_run.call_refactor_main_in_process_with_driver(
        driver="loop",
        agent_cmd=loop_run.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        ),
    )
    loop_captured = capsys.readouterr()

    same_exit = python_exit == loop_exit
    same_output = (python_captured.out, python_captured.err) == (
        loop_captured.out,
        loop_captured.err,
    )
    assert not (same_exit and same_output), (
        "--driver loop and --driver python must be observably different "
        "(loop names itself and refuses, or genuinely runs differently) -- "
        f"got IDENTICAL exit_code={python_exit} and output for both: "
        f"python={python_captured.out + python_captured.err!r}, "
        f"loop={loop_captured.out + loop_captured.err!r}"
    )


# --- AT-2 (negative-safety companion): the already-correct default path ----
# must come out of this fix completely untouched -----------------------------


@pytest.mark.parametrize(
    "driver_argv",
    [
        pytest.param(None, id="no-flag-bare-default"),
        pytest.param("python", id="explicit-driver-python"),
    ],
)
def test_driver_python_and_the_bare_default_are_never_perturbed_by_the_loop_refusal(
    tmp_path, capsys, driver_argv
):
    """Given a pile with one item, When `des refactor` runs with no
    `--driver` flag at all, or with `--driver python` explicit, Then both
    invocations drain the item and exit 0 exactly as before this fix -- the
    loop-refusal logic must never perturb the already-working default path.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")
    agent_cmd = composition.agent_cmd_emitting_verdict(
        EntryGateAgentVerdict.REFACTOR_SAFE
    )

    if driver_argv is None:
        exit_code = composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    else:
        exit_code = composition.call_refactor_main_in_process_with_driver(
            driver=driver_argv, agent_cmd=agent_cmd
        )
    captured = capsys.readouterr()

    assert exit_code == 0, (
        f"driver={driver_argv!r} must still drain TD-001 and exit 0 "
        f"unaffected by the loop-refusal fix; got exit_code={exit_code}, "
        f"stderr={captured.err!r}"
    )
    assert not composition.pile_contains("TD-001"), (
        f"driver={driver_argv!r} must still remove TD-001 from techdebt.md once drained"
    )
    assert composition.paid_contains("TD-001"), (
        f"driver={driver_argv!r} must still record TD-001 in "
        "paidtechdebt.md once drained"
    )
