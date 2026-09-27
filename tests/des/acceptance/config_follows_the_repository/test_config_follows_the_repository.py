"""Executable oracle: configuration follows the repository across worktrees.

Authority: docs/product/architecture/brief.md#Repository-Rooted Configuration
Across Git Worktrees.

Observation under test -- running a DES command whose working directory sits
inside a git worktree checkout applies the same repository-root
`.nwave/config.json` settings the ordinary non-worktree checkout applies,
resolved in pure Python without the git binary; the non-worktree checkout's
resolution and defaulting behaviour is unchanged; and a worktree whose
repository root cannot be located keeps the pre-fix defaulting behaviour.

The only port driven is the real `des` PROCESS. The observable is whether the
string `files=2 > small_max_files=1` appears in the `reasons` array of the
`BlastRadiusMeasured` stdout token: it is PRESENT exactly when the
repository-rooted threshold `small_max_files=1` is in effect for the two
scope files, and ABSENT under the canonical default of 2.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.des.acceptance.config_follows_the_repository.public_oracle import (
    DISCRIMINATOR_REASON,
    REPO_ROOTED_THRESHOLD,
    make_plain_checkout,
    make_scope_files,
    make_worktree_checkout,
    measure_blast_radius,
    write_config,
)


@pytest.fixture()
def pinned_env(tmp_path: Path) -> dict[str, Path]:
    """An empty global rung and an empty PATH for every child invocation."""
    return {
        "home": tmp_path / "empty_home",
        "path_dir": tmp_path / "empty_path",
    }


def test_worktree_checkout_applies_the_repository_root_configuration(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """The headline: a worktree reads the repository root's config.json."""
    common_root = tmp_path / "repo"
    write_config(common_root, REPO_ROOTED_THRESHOLD)
    checkout = make_worktree_checkout(common_root, tmp_path / "lane")

    outcome = measure_blast_radius(checkout, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON in outcome.reasons


def test_worktree_and_plain_checkout_of_the_same_root_agree(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """`the same settings the ordinary checkout applies` -- both arms agree."""
    common_root = tmp_path / "repo"
    write_config(common_root, REPO_ROOTED_THRESHOLD)
    make_plain_checkout(common_root)
    checkout = make_worktree_checkout(common_root, tmp_path / "lane")

    plain = measure_blast_radius(common_root, **pinned_env)
    worktree = measure_blast_radius(checkout, **pinned_env)

    assert plain.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON in plain.reasons
    assert (DISCRIMINATOR_REASON in worktree.reasons) == (
        DISCRIMINATOR_REASON in plain.reasons
    )


def test_plain_checkout_root_behaviour_is_unchanged(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """A `.git` DIRECTORY marker keeps resolving to the start directory."""
    root = make_plain_checkout(tmp_path / "repo")
    write_config(root, REPO_ROOTED_THRESHOLD)

    outcome = measure_blast_radius(root, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON in outcome.reasons


def test_plain_checkout_subdirectory_defaulting_is_unchanged(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """A subdirectory of an ordinary checkout still does NOT ascend.

    Pre-fix, a working directory below the root read its own (absent)
    `.nwave/config.json` and fell through to the canonical default. Only a
    `.git` FILE bearing `gitdir:` indirection may trigger the new ascent, so
    this arm must stay byte-for-byte unchanged.
    """
    root = make_plain_checkout(tmp_path / "repo")
    write_config(root, REPO_ROOTED_THRESHOLD)
    nested = root / "src" / "deep"
    make_scope_files(nested)

    outcome = measure_blast_radius(nested, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON not in outcome.reasons


def test_worktree_without_repository_configuration_takes_the_default(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """No repository-root config anywhere: the canonical default stands."""
    common_root = tmp_path / "repo"
    checkout = make_worktree_checkout(common_root, tmp_path / "lane")

    outcome = measure_blast_radius(checkout, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON not in outcome.reasons


def test_unresolvable_repository_root_keeps_the_pre_fix_defaulting(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """A broken common-dir chain degrades to the worktree's own start dir.

    The repository root DOES carry the rooted threshold here; a deliberately
    dangling `commondir` marker makes it unreachable. The terminal must be an
    ordinary measurement at exit 0 on the canonical default -- never a new
    diagnostic and never `BlastRadiusConfigRejected`.
    """
    common_root = tmp_path / "repo"
    write_config(common_root, REPO_ROOTED_THRESHOLD)
    checkout = make_worktree_checkout(
        common_root,
        tmp_path / "lane",
        commondir_contents="../../../nowhere-at-all\n",
    )

    outcome = measure_blast_radius(checkout, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON not in outcome.reasons


def test_operator_global_configuration_cannot_forge_the_observation(
    tmp_path: Path, pinned_env: dict[str, Path]
) -> None:
    """Obligation: the observation is operator-independent.

    A hostile `~/.nwave/config.json` carrying the very threshold the
    discriminator detects really CAN forge the token when the child's global
    rung points at it -- that control arm is asserted first, so the pin is
    proven load-bearing rather than merely declared. With HOME and
    NWAVE_AGENTS_HOME pinned to the empty fixture home instead, the same
    repository-config-free worktree must fall back to the canonical default.
    """
    hostile_home = tmp_path / "hostile_home"
    write_config(hostile_home, REPO_ROOTED_THRESHOLD)
    common_root = tmp_path / "repo"
    checkout = make_worktree_checkout(common_root, tmp_path / "lane")

    forged = measure_blast_radius(
        checkout, hostile_home, path_dir=pinned_env["path_dir"]
    )
    assert forged.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON in forged.reasons

    outcome = measure_blast_radius(checkout, **pinned_env)

    assert outcome.exit_code == 0
    assert outcome.event == "BlastRadiusMeasured"
    assert DISCRIMINATOR_REASON not in outcome.reasons
