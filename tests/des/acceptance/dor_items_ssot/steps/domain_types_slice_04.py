"""Typed domain vocabulary for dor-items-ssot slice-04 (Mandate-12).

slice-04 (the FINAL slice) ships the **drift gate**: a maintainer who edits any
Definition-of-Ready home is mechanically stopped when a home's item-list diverges
from the one authoritative place, so a future drift between the homes and the
canonical set cannot reach a reviewer (DISCUSS K2/K3 / DESIGN DDD-5).

The gate is a dev/CI drift check (``scripts/cli/check_dor_items_drift.py``,
CREATE_NEW per DESIGN component table): a pure functional core + thin CLI shell,
mirroring ``validate_feature_delta.py`` -- it reads the SSOT and each enumerated
DoR home, compares each home's stated item count against the SSOT's, and emits a
CLOSED-TOKEN verdict + exit code.

This module pins, as typed constants + a frozen dataclass, the closed verdict
shape the slice-04 ATs assert over the gate's ``--format json`` stdout:

  - the closed verdict-token set (PASS / FAIL / MALFORMED), reused from a single
    place so no scenario restates the literal tokens;
  - the structured drift report a maintainer reads off the gate (the verdict, the
    list of diverged homes, the homes the gate actually traversed, the
    authoritative item count) -- port-exposed observable shape only (Mandate 8),
    never an internal gate struct.

example-only (no PBT, Mandate 9/11): the verdict is a fixed closed-token set over
a finite home-set; the anti-vacuity discriminator is the divergence-pair (a
divergent-home fixture REDs the gate, the consistent real tree GREENS it), not a
generated input domain.
"""

from __future__ import annotations

from dataclasses import dataclass

# Reuse the slice-01 single source of truth for the canonical count so slice-04
# does NOT restate "9" as an independent literal (a second copy would be the very
# drift this feature kills).
from .domain_types import CANONICAL_READINESS_ITEM_COUNT


# The closed verdict-token set the drift gate emits (mirrors the
# validate_feature_delta.py closed-token contract). PASS = every home consistent
# with the SSOT; FAIL = at least one home diverged; MALFORMED = the SSOT or a
# home could not be parsed. The ATs read these tokens, never a free-text stdout
# substring.
DRIFT_VERDICT_PASS: str = "PASS"
DRIFT_VERDICT_FAIL: str = "FAIL"
DRIFT_VERDICT_MALFORMED: str = "MALFORMED"

# The authoritative item count the gate measures each home against -- the SSOT's
# ``len(items)``. Reused from slice-01 so the expected count has one home.
AUTHORITATIVE_ITEM_COUNT: int = CANONICAL_READINESS_ITEM_COUNT  # 9

# The canonical DoR homes the drift gate's DEFAULT discovery set MUST traverse --
# the COUNT-STATING homes the gate compares against the SSOT (DESIGN-pinned, NOT
# the reconciliation-target set; the two differ). Per the DESIGN component table
# (feature-delta.md:273-279) + the render-vs-pointer rule (:281-295), exactly
# these three homes STATE a number post-reconciliation and are therefore the
# gate's count-check targets:
#
#   - nw-dor-validation/SKILL.md       -- the authoritative-transcription home
#     (:285-288): the ONE home carrying the human-readable 9-item enumeration the
#     gate "mechanically asserts has not drifted". THE primary drift target.
#     Already "9"; the GREEN does NOT edit its count -- it is the home checked.
#   - nw-product-owner.md              -- retains counts (:41, :174); the gate
#     count-checks it post-reconcile (:41 "8"->"9").
#   - nw-product-owner-reviewer.md     -- retains a count (:16,26 "8 DoR items"
#     -> "9 DoR items"); count-checked.
#
# nw-leanux-methodology/SKILL.md is DELIBERATELY EXCLUDED: per the component
# table (:277) it is reconciled by POINTER-CONVERSION (:42 "ALL 8 items" ->
# "all DoR items (see the SSOT)") -- its count is REMOVED, so it becomes
# structurally drift-proof (:289-292: "a pointer cannot drift in count because it
# states no count") and is NOT a count-check target.
#
# Expressed as repo-relative path stems so the discovery-coverage assertion is
# robust to the absolute path the gate reports. An under-discovering GREEN that
# misses any of these fails the consistent-state AT (its ``checked_homes`` would
# not cover the required set), closing the vacuous-pass hole the AT-review
# flagged: a gate that silently inspects fewer count-stating homes than exist can
# report ``diverged_homes == ()`` without ever having looked at the homes it
# failed to find -- including its OWN primary transcription target.
REQUIRED_DISCOVERED_HOMES: tuple[str, ...] = (
    "nw-dor-validation/SKILL.md",
    "nw-product-owner.md",
    "nw-product-owner-reviewer.md",
)


@dataclass(frozen=True)
class DriftReport:
    """The structured drift verdict a maintainer reads off the gate.

    Port-exposed observable shape only (Mandate 8): exactly the fields the gate's
    ``--format json`` stdout carries + the process exit code the subprocess
    returns -- never an internal gate struct.

    - ``verdict``            -- one of the closed token set (PASS/FAIL/MALFORMED).
    - ``diverged_homes``     -- the homes whose stated item count diverged from
                                the SSOT (named, so a maintainer is told WHICH
                                home drifted); empty on PASS.
    - ``checked_homes``      -- the homes the gate ACTUALLY traversed. Makes the
                                gate's discovery set observable so the
                                consistent-state AT can assert COVERAGE: an
                                under-discovering gate (one that silently inspects
                                fewer homes than exist) reports a ``checked_homes``
                                missing a required home and fails the AT, instead
                                of vacuously passing on ``diverged_homes == ()``.
    - ``ssot_item_count``    -- the authoritative item count the gate compared
                                each home against (the SSOT's ``len(items)``).
    - ``exit_code``          -- the process exit code (0 PASS / 1 FAIL / 2
                                MALFORMED) the subprocess returned.
    """

    verdict: str
    diverged_homes: tuple[str, ...]
    checked_homes: tuple[str, ...]
    ssot_item_count: int
    exit_code: int

    def required_homes_not_examined(self) -> tuple[str, ...]:
        """The canonical homes the gate FAILED to traverse (empty when complete).

        A typed-observable accessor (not step-body logic, Mandate-12): for each
        required canonical home, it is "examined" iff its stem appears in some
        ``checked_homes`` entry. The returned tuple is the discovery-coverage gap
        the consistent-state AT asserts is empty.
        """
        return tuple(
            required
            for required in REQUIRED_DISCOVERED_HOMES
            if not any(required in examined for examined in self.checked_homes)
        )


__all__ = [
    "AUTHORITATIVE_ITEM_COUNT",
    "DRIFT_VERDICT_FAIL",
    "DRIFT_VERDICT_MALFORMED",
    "DRIFT_VERDICT_PASS",
    "REQUIRED_DISCOVERED_HOMES",
    "DriftReport",
]
