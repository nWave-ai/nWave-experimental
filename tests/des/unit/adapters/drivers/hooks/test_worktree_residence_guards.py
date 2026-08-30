from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from des.adapters.driven.platform_residence_durability_adapter import (
    PlatformResidenceDurabilityAdapter,
)
from des.adapters.drivers.hooks.bash_command_guards import (
    evaluate_worktree_add_command,
)
from des.adapters.drivers.hooks.pre_tool_use_handler import (
    evaluate_agent_worktree_isolation,
    evaluate_bash_safety_guards,
)
from des.domain.worktree_residence import ResidenceDurability


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def test_canonical_absolute_repo_local_destination_is_allowed() -> None:
    repo = _repo_root()
    destination = repo / ".nwave" / "worktrees" / "guard-test"

    decision = evaluate_worktree_add_command(
        f"git worktree add {destination} HEAD", repo
    )

    assert decision is not None and decision.allow


def test_real_platform_ephemeral_destination_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    destination = tmp_path / "ephemeral-lane"

    decision = evaluate_worktree_add_command(
        f"git worktree add {destination} HEAD", repo
    )

    assert decision is not None and not decision.allow
    assert "EPHEMERAL" in (decision.reason or "")
    assert "worktree-admit" in (decision.reason or "")


def test_pretooluse_wrapper_blocks_ephemeral_destination(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    destination = tmp_path / "ephemeral-lane"

    result = evaluate_bash_safety_guards(
        {"cwd": str(repo), "session_id": "test"},
        {"command": f"git worktree add {destination} HEAD"},
    )

    assert result is not None
    assert result["decision"] == "block"
    assert "worktree-admit" in result["reason"]


@pytest.mark.parametrize(
    "command",
    [
        "git -C /repo worktree add lane HEAD",
        "git --exec-path worktree add /abs/lane HEAD",
        "git worktree add --detach /abs/lane HEAD",
        "git worktree add relative HEAD",
        "git worktree add",
        "git worktree add /a b c",
        'git worktree add "unterminated',
    ],
)
def test_noncanonical_worktree_add_shapes_refuse_with_constructive_route(
    command: str,
) -> None:
    decision = evaluate_worktree_add_command(command, _repo_root())

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")


@pytest.mark.parametrize(
    "command",
    [
        "git worktree list",
        "echo 'git worktree add /tmp/lane HEAD'",
        "env git worktree add /tmp/lane HEAD",
        "sudo git worktree add /tmp/lane HEAD",
    ],
)
def test_non_git_or_non_add_commands_are_outside_the_claim(command: str) -> None:
    assert evaluate_worktree_add_command(command, _repo_root()) is None


def test_dynamic_subcommand_construction_refuses_worktree_add() -> None:
    decision = evaluate_worktree_add_command(
        'git worktree "$(echo add)" /tmp/lane', _repo_root()
    )

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")


@pytest.mark.parametrize(
    "command",
    [
        'git worktree "$(echo add)" /tmp/lane',
        "git worktree $(echo add) /tmp/lane",
        "git worktree $SUBCMD /tmp/lane",
        "git worktree `echo add` /tmp/lane",
        "git worktree ad$SUFFIX /tmp/lane",
    ],
)
def test_variable_or_backtick_subcommand_construction_refuses(command: str) -> None:
    decision = evaluate_worktree_add_command(command, _repo_root())

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")


# --------------------------------------------------------------------------
# EF-9a (D7a-R) -- five groups, each named for the mutant it alone falsifies.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git worktree $SUB /tmp/lane",
        'git worktree "$(echo add)" /tmp/lane',
        "git worktree ad$SUFFIX /tmp/lane",
        "git -C /repo worktree $SUBCMD /tmp/lane",
        "git --unknown worktree $SUBCMD /tmp/lane",
        "git $GITOPTS worktree $SUB /tmp/x",
    ],
)
def test_ef9a_a_dynamic_worktree_adjacency_refuses_independent_of_flag_position(
    command: str,
) -> None:
    """Falsifier: the breadth-first, option-table scanner being replaced.

    The last row is the bypass measured open at `3f50550c6` -- the scan
    used to start at `argv[1]`, where a non-`-` token ended the search on a
    false subcommand candidate; no flag-table entry closed it.
    """
    decision = evaluate_worktree_add_command(command, _repo_root())

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")


@pytest.mark.parametrize(
    "command",
    [
        "git worktree list",
        'git worktree remove "$LANE"',
        "git grep $PAT -- worktree/",
    ],
)
def test_ef9a_b_negative_controls_still_pass(command: str) -> None:
    """Falsifier: a refuse-all mutant.

    These already passed against the replaced scanner, so it is not their
    falsifier -- only unconditional refusal breaks them.
    """
    assert evaluate_worktree_add_command(command, _repo_root()) is None


@pytest.mark.parametrize(
    "command",
    [
        "git log -- worktree $BRANCH",
        "git --pretty=oneline log -- worktree $BRANCH",
    ],
)
def test_ef9a_c_worktree_pathspec_with_expanded_next_token_is_a_named_false_positive(
    command: str,
) -> None:
    """The declared false-positive class, asserted rather than discovered.

    An ordinary `worktree` pathspec followed by an expanded token now costs
    one refusal -- the adjacency rule cannot distinguish it from an
    unprovable dynamic subcommand, replacing the former pass-through
    expectation.
    """
    decision = evaluate_worktree_add_command(command, _repo_root())

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")


def test_ef9a_d_dynamically_constructed_worktree_token_itself_is_the_declared_residual() -> (
    None
):
    """The declared residual, asserted so it is not silently widened.

    A `worktree` token itself built from a variable is undecidable from
    text and passes through -- distinct from EF-9's non-`git` `argv[0]`
    pass-through.
    """
    assert evaluate_worktree_add_command("git $SUB add /abs/path", _repo_root()) is None


@pytest.mark.parametrize(
    "command",
    [
        "git worktree add /home/alex/nWave-dev/.claude/worktrees/lane-$LANE",
        (
            'git worktree add "/home/alex/nWave-dev/.claude/worktrees/'
            "$(printf '../../../../../../../../tmp/x')\""
        ),
    ],
)
def test_ef9a_e_expansion_shard_destination_refuses_before_classifier_runs(
    command: str,
) -> None:
    """Falsifier: D7a's shipped shape test, which reads only the literal
    `argv[3]`.

    Each row is a single shlex token the shipped test would admit; refusal
    must precede `ResidenceAdmission`, so a classifier double answering
    `DURABLE` is asserted never called.
    """
    with patch.object(
        PlatformResidenceDurabilityAdapter,
        "classify",
        return_value=ResidenceDurability.DURABLE,
    ) as classify:
        decision = evaluate_worktree_add_command(command, _repo_root())

    assert decision is not None and not decision.allow
    assert "worktree-admit" in (decision.reason or "")
    classify.assert_not_called()


@pytest.mark.parametrize(
    "tool_input",
    [
        {"subagent_type": "nw-software-crafter", "isolation": "worktree"},
        {"subagent_type": "external-agent", "isolation": "worktree"},
        {"isolation": "worktree"},
    ],
)
def test_every_agent_worktree_isolation_is_refused(
    tool_input: dict[str, object],
) -> None:
    result = evaluate_agent_worktree_isolation(tool_input)

    assert result is not None
    assert result["decision"] == "block"
    assert "worktree-admit" in result["reason"]


@pytest.mark.parametrize(
    "tool_input",
    [
        {"subagent_type": "nw-software-crafter"},
        {"subagent_type": "external-agent"},
        {"subagent_type": "nw-software-crafter", "isolation": "process"},
        {"subagent_type": "external-agent", "isolation": "process"},
    ],
)
def test_other_agent_invocations_pass_unchanged(tool_input: dict[str, object]) -> None:
    assert evaluate_agent_worktree_isolation(tool_input) is None
