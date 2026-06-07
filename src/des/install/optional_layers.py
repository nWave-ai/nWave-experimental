"""Optional defense-in-depth layer offer decision (slice-04, fix-oss-env-e2e-gate).

The install-time doctor decides whether to offer the optional git pre-push hook
based on the install environment. The floor (the `verify_environmental_e2e`
gate CLI shipped as a `des` subcommand) is ALWAYS installed regardless --
optional layers are defense-in-depth on top of the floor, never replace it.

Reference: feature-delta `## Wave: DESIGN / [REF] Optional Layers --
defense-in-depth, never the floor`. Pure function -- no I/O; the caller
inspects `git --version` / TTY / opt-out env and passes the typed inputs in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GitState(str, Enum):
    """Whether the install environment has git available on PATH."""

    HAS = "has"
    LACKS = "lacks"


class Interactivity(str, Enum):
    """How the install runs -- governs whether the optional hook is offered.

    The opt-out value is part of this enum (not a separate boolean) so the
    decision-table input is one closed-enum lookup, not two flags.
    """

    INTERACTIVE = "interactively"
    NON_INTERACTIVE = "non-interactively"
    NO_GIT_HOOKS_OPT_OUT = "with the no-git-hooks opt-out"


@dataclass(frozen=True)
class OptionalLayersDecision:
    """Observable outcome of the install-time optional-layer offer.

    The two ports the AT asserts on: was the git pre-push hook offered, and
    was the floor installed regardless. Both default to falsey so a missing
    decision is detectable.
    """

    git_prepush_hook_offered: bool
    gate_floor_installed: bool


def decide_optional_layers(
    git_state: GitState, interactivity: Interactivity
) -> OptionalLayersDecision:
    """Decide whether to offer the optional git pre-push hook; floor is always installed.

    Offer-never-mandate rule: offer the hook only when the environment permits
    it -- git present AND running interactively AND not opted out. Every other
    cell of the (git_state x interactivity) grid skips the offer. The floor
    (the `verify_environmental_e2e` CLI shipped via the `des` console script
    and orchestrated by the DELIVER feature-end cycle) is installed in every
    cell -- that is the point of defense-in-depth.
    """
    hook_offered = (
        git_state is GitState.HAS and interactivity is Interactivity.INTERACTIVE
    )
    return OptionalLayersDecision(
        git_prepush_hook_offered=hook_offered,
        gate_floor_installed=True,
    )
