"""Typed domain vocabulary for the fix-floor-auto-close-cross-wave ATs.

Mandate-15 (SSOT via Types): every domain noun the slice-01 Gherkin names is a
typed enum here, so composition methods consume typed parameters (no raw ``str``
where an enum exists). These types are TEST-LOCAL: they never import production
code. The ATs drive the SUT only through the composition-root driving port
(Mandate-16): the REAL ``SubagentStopService.validate()`` composed via
``service_factory`` (Layer-3 composition), reading + clearing the REAL
``WaveActiveFilesystemStore`` floor seeded on disk at ``cwd``.

The Universe the ATs track is the port-exposed observable: the wave-active floor
RECORD STATE as read back through ``WaveActiveFilesystemStore.read(cwd)`` (a
``WaveActiveRecord`` armed, or ``NoWaveActive`` cleared) + the
``HookDecision.action`` ("allow"|"block"). NEVER the service's internal fields.
"""

from __future__ import annotations

from enum import Enum


class WaveOwner(Enum):
    """A wave OWNER subagent_type + the wave its terminal return closes (WAVE_OWNERS).

    Each value is the exact ``subagent_type`` the orchestrator dispatches, mirrored
    from the production ``wave_dispatch_guard_policy.WAVE_OWNERS`` map (the AT does
    not import it; it asserts the close behavior keyed on it). A wave OWNER's
    attested terminal gate-OUT PASS is the un-gameable "wave is over" signal that
    must close the floor (AC-1).
    """

    PRODUCT_OWNER = "nw-product-owner"  # DISCUSS
    SOLUTION_ARCHITECT = "nw-solution-architect"  # DESIGN
    PLATFORM_ARCHITECT = "nw-platform-architect"  # DESIGN / DEVOPS
    ACCEPTANCE_DESIGNER = "nw-acceptance-designer"  # DISTILL


# The DES-WAVE token each owner's wave floor carries (mirrors WAVE_OWNERS; the AT
# asserts the close, it does not import the map).
OWNER_WAVE: dict[str, str] = {
    WaveOwner.PRODUCT_OWNER.value: "discuss",
    WaveOwner.SOLUTION_ARCHITECT.value: "design",
    WaveOwner.PLATFORM_ARCHITECT.value: "design",
    WaveOwner.ACCEPTANCE_DESIGNER.value: "distill",
}


# A representative NON-owner subagent_type -- a reviewer, deliberately ABSENT from
# WAVE_OWNERS (a §22.0 control, never wave-authoring). Its attested return must
# NOT close the floor (AC-3): it is not the wave's terminal owner.
NON_OWNER_TYPE = "nw-acceptance-designer-reviewer"


class WaveFloorWave(Enum):
    """The dual-ownership wave whose floor the platform-architect terminally owns.

    fix-floor-auto-close-cross-wave slice-02 (M6 dual-aware completion): the
    platform-architect OWNS BOTH ``design`` AND ``devops`` (mirrored from the
    SHIPPED ``wave_dispatch_guard_policy._PLATFORM_ARCHITECT_WAVES =
    frozenset({"design","devops"})``). The single-valued ``WAVE_OWNERS`` map keys
    ``nw-platform-architect -> "design"`` only, so a ``devops``-wave terminal
    return does NOT close the floor at HEAD (the dual-ownership gap AC-5 surfaces).

    This enum decouples the FLOOR's wave from the OWNER's identity: AC-5 arms a
    ``devops`` floor and returns the platform-architect; AC-6 arms a ``design``
    floor and returns the platform-architect (the slice-01 superset, live-green).
    """

    DESIGN = "design"
    DEVOPS = "devops"


class FloorOutcome(Enum):
    """The observable post-return state of the wave-active floor (the Universe).

    Read back through ``WaveActiveFilesystemStore.read(cwd)`` AFTER the return is
    validated. CLEARED <=> ``NoWaveActive`` (the floor file is gone -> the next
    wave's dispatch is no longer blocked). STILL_ARMED <=> a ``WaveActiveRecord``
    is still present (in-wave persistence preserved / no terminal close happened).
    """

    CLEARED = "cleared"  # NoWaveActive: floor file removed -> auto-close fired
    STILL_ARMED = "still_armed"  # WaveActiveRecord present -> floor persists


class ReturnVerdict(Enum):
    """The observable gate-OUT decision (HookDecision.action) for the return.

    ALLOW = the attested gate-OUT found no objection (the PASS path the close
    chains off). BLOCK = a review-verdict veto (AC-4): the existing BLOCK is
    unchanged and the floor must NOT be cleared.
    """

    ALLOW = "allow"
    BLOCK = "block"
