"""slice-05 witnessing coverage: the TWO under-covered DESIGN wave-owners.

F_FINAL_REVIEW BLOCKER (2026-06-16): the shipped ``WAVE_OWNERS`` map (and the
arch-test expected set, and the test vocabulary) originally listed only
``nw-solution-architect`` + ``nw-platform-architect`` for the DESIGN wave, while
the feature-delta (:114) and ADR-NB-001 (:97) declare FOUR DESIGN authoring
owners: solution-architect (application), ddd-architect (domain modelling),
system-designer (infra-level), platform-architect (infra-design). The two omitted
owners (``nw-ddd-architect``, ``nw-system-designer``) were silently ALLOWED
off-spine -- the exact wave-level silent-entry hole DDD-8 exists to close.

The arch-test pins the owners STRUCTURALLY (the map literal). This module pins the
fix BEHAVIORALLY -- it drives the REAL in-tree gate ``des.cli.verify_wave_dispatch``
(Layer-3 subprocess, the same driving port the slice-05 ``.feature`` ATs use) over
the two previously-missing owners and asserts the verdict, so a future regression
that drops either owner from the map goes RED on a real BLOCK→ALLOW divergence, not
just on a frozenset membership check.

It is a plain pytest module (NOT a pytest-bdd ``.feature`` scenario) on purpose:
the slice-05 ``.feature`` already carries 5 scenarios -- the carpaccio ceiling
(``carpaccio_slice_max=5``) -- so the behavioral witness for the two repaired
owners lands here without inflating the slice's scenario count. It reuses the
slice-05 composition root (hermetic: tmp prompt FILE, no ``~/.claude`` read).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .steps.composition_slice_05 import WaveDispatchGuardComposition
from .steps.domain_types_nonbypassable import WaveOwner


# The two DESIGN wave-owners the original delivery under-covered (BLOCKER).
_REPAIRED_DESIGN_OWNERS = [WaveOwner.DDD_ARCHITECT, WaveOwner.SYSTEM_DESIGNER]


@pytest.mark.parametrize("owner", _REPAIRED_DESIGN_OWNERS, ids=lambda o: o.value)
def test_repaired_design_owner_off_spine_is_blocked(
    owner: WaveOwner, tmp_path: Path
) -> None:
    """An off-spine DESIGN owner (no DES-WAVE marker) is BLOCKED, not silently allowed.

    The pre-fix bug: ``decide_dispatch`` returned ALLOW (exempt -- "not a
    wave-owner") for these two, so the wave was entered off-spine with no spine,
    witness, or pre-grant. Post-fix the gate exits 1 (BLOCK).
    """
    guard = WaveDispatchGuardComposition()
    guard.use_project_root(tmp_path)
    guard.given_wave_owner(owner)
    guard.given_no_des_wave_marker()
    guard.when_agent_dispatched()
    guard.then_block_warns_and_asks()


@pytest.mark.parametrize("owner", _REPAIRED_DESIGN_OWNERS, ids=lambda o: o.value)
def test_repaired_design_owner_on_spine_is_allowed(
    owner: WaveOwner, tmp_path: Path
) -> None:
    """The same DESIGN owner WITH the matching ``design`` DES-WAVE marker is ALLOWED.

    Proves the BLOCK is wave-entry enforcement (off-spine), not a blanket refusal:
    on-spine the gate recognizes the DESIGN signal and allows (exit 0 + a positive
    allow-trace).
    """
    guard = WaveDispatchGuardComposition()
    guard.use_project_root(tmp_path)
    guard.given_wave_owner(owner)
    guard.given_matching_des_wave_marker()
    guard.when_agent_dispatched()
    guard.then_wave_owner_allowed_on_spine()
