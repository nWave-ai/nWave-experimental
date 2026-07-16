"""Walking-skeleton AT -- `des refactor` drains ONE pile item end to end.

@walking_skeleton @driving_port @contract-shape:bounded-change (slice-01,
feature des-refactor-fixer-swarm). Value statement (feature-delta Slice Plan):
"An operator runs ONE command (`des refactor --pile techdebt.md --agent-cmd
'<cli>'`) and one pile item is drained end to end -- worktree-from-tip,
per-worktree venv, configurable agent_cmd dispatch, fast+impacted
green-to-green, merge into a clean integration branch, and MANDATORY
cleanup -- with zero manual worktree/venv/cleanup babysitting."

Layer 1 subprocess-e2e is reserved for the SINGLE ``@walking_skeleton`` scenario
below -- the one fork per command that proves the installed `des refactor` CLI
dispatches to the real drain loop (terminal-wiring facet, `nw-distill-port-
treatment-policy`). Every other scenario in this file drives the composition
root in-process (Layer 3 composition, L2 default) -- reaching for subprocess on
a non-walking-skeleton scenario is the regression the subprocess-overuse gate
flags.

RED-scaffold note: `des.cli.refactor.main` -> `RefactorDrainService.drain_one`
raises `AssertionError` the instant the drain loop is invoked (Mandate 7) --
the walking-skeleton's child process therefore exits non-zero with that
AssertionError in its traceback on stderr. `refactor` IS registered in
`des.cli.__main__`'s subcommand registry (the wiring landed with this
scaffold), so the failure is genuinely "drain not implemented yet"
(MISSING_FUNCTIONALITY) -- never an argparse `invalid choice` usage error.

covers: R-DES-REFACTOR-WS
"""

from __future__ import annotations

import pytest

from .composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


@pytest.mark.walking_skeleton
def test_operator_drains_one_pile_item_end_to_end_with_a_single_command(tmp_path):
    """Given a pile with one item, When `des refactor` runs, Then it is drained.

    Real installed CLI, real git repo, real pile files (Pillar 3 -- production
    composition). Currently RED: the drain loop is not yet implemented, so the
    process exits non-zero instead of the eventual `0`.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_refactor_cli_subprocess(agent_cmd="true")

    assert result.exit_code == 0, (
        "des refactor should drain TD-001 end to end and exit 0; got "
        f"exit_code={result.exit_code}, stderr={result.stderr!r}"
    )
    assert not composition.pile_contains("TD-001"), (
        "TD-001 must be removed from techdebt.md once drained"
    )
    assert composition.paid_contains("TD-001"), (
        "TD-001 must be recorded in paidtechdebt.md once drained"
    )
    # D5/D6 -- mandatory cleanup: no worktree/branch left behind after a
    # successful drain (see test_slice_01_merge_and_cleanup.py for the
    # dedicated positive/negative pair; asserted here too since it is the
    # walking-skeleton's own end-state).
    assert not composition.branch_exists("refactor-TD-001")


def test_des_refactor_does_not_attempt_a_drain_when_the_pile_has_no_pending_items(
    tmp_path,
):
    """Given an empty pile, When the drain loop runs, Then nothing is drained.

    Negative AT (GS-8): a harness that silently "succeeds" over an empty pile
    by doing nothing is a different bug class from crashing -- this pins that
    the observable NO-OP is the correct outcome, not merely the absence of a
    crash. Layer 3 composition (in-process) -- not walking-skeleton-tagged, so
    this drives the composition root directly rather than forking a second
    interpreter.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_empty_pile()
    worktrees_before = composition.worktree_list()

    result = composition.run_drain_one_item()

    assert result.drained is False, "an empty pile must never report an item as drained"
    assert composition.worktree_list() == worktrees_before, (
        "an empty pile must never create a worktree"
    )


def test_agent_receives_the_rendered_content_of_the_user_edited_prompt_template(
    tmp_path,
):
    """The agent's task text is NEVER hardcoded -- it comes from a real,
    user-editable template file.

    Pins the slice-01 requirement (Ale, 2026-07-14): `des refactor` reads a
    user-editable template file (`.nwave/refactor-agent-prompt.md`), renders
    its placeholders for the pile item being drained, writes the rendered text
    to a prompt FILE, and passes THAT file to `agent_cmd` -- so a maintainer's
    own edit to the template is what the agent actually receives, never a
    string baked into the harness.

    Observable asserted: the CONTENT `agent_cmd` actually received (captured
    by copying the rendered prompt file to a well-known path), never a harness
    internal. A distinctive marker string planted in the user's OWN template
    edit must appear in what `agent_cmd` received -- proving the prompt comes
    from the editable file.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001")
    marker = "USER-EDITED-MARKER-3f9a"
    composition.write_user_prompt_template(
        f"Fix {{defect}} for {{item_id}} -- {marker}\nWorktree: {{worktree}}\n"
    )

    composition.run_drain_one_item(agent_cmd=composition.capturing_agent_cmd())

    received = composition.observed_agent_cmd_input()
    assert marker in received, (
        "agent_cmd must receive the RENDERED content of the user's OWN "
        f"prompt-template edit; the marker {marker!r} is missing from what "
        f"agent_cmd actually received: {received!r}"
    )
