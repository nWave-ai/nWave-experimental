"""Blast-radius tier value types + the pure classification rule (slice-01).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Architecture & Contract Tests -- Tier classification table).

Pure, side-effect-free value types + a pure classifier function -- zero
coupling to `des.*` (Effect Isolation, principle 12). The full S/M/L decision
table (boundary_files / consumer_counts) is slice-02 scope; slice-01 ships
the REDUCED files+lines-only S/M rule the walking-skeleton AT pins:

    S iff files <= small_max_files AND lines_changed is not None
          AND lines_changed <= small_max_lines
    M otherwise (an indeterminate lines_changed also forces M -- GDP-6, an
          unknown blast radius is never silently smaller)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlastRadiusTier(str, Enum):
    """The measured tier of a change's blast radius."""

    S = "S"
    M = "M"
    L = "L"


@dataclass(frozen=True)
class BlastRadiusThresholds:
    """The numeric thresholds slice-01's reduced tier rule reads.

    Canonical defaults (feature-delta "Canonical default thresholds" table):
    `small_max_files=2`, `small_max_lines=10`. Slice-02 wires these through
    the `DESConfig` cascade; slice-01 hardcodes the canonical defaults here.
    """

    small_max_files: int = 2
    small_max_lines: int = 10


@dataclass(frozen=True)
class BlastRadiusMeasures:
    """The measured facts a change's blast radius is classified from.

    `lines_changed` is `None` when it could not be honestly determined (no
    git work-tree, git absent) -- never a fabricated `0`. `boundary_files`
    and `consumer_counts` are always empty in slice-01 (not yet wired --
    slice-02 scope); the caller is responsible for naming that in `reasons`,
    never presenting the empty collections as a real zero-crossings signal.
    """

    files: int
    lines_changed: int | None
    boundary_files: tuple[str, ...] = field(default_factory=tuple)
    consumer_counts: dict[str, int | None] = field(default_factory=dict)


_DEFAULT_THRESHOLDS = BlastRadiusThresholds()


def classify_tier(
    measures: BlastRadiusMeasures,
    thresholds: BlastRadiusThresholds = _DEFAULT_THRESHOLDS,
) -> tuple[BlastRadiusTier, list[str]]:
    """Classify `measures` into a tier, per slice-01's reduced files+lines rule.

    Returns `(tier, reasons)` -- `reasons` names every condition that fired,
    the verdict is never a bare tier letter alone (GDP-3).
    """
    reasons: list[str] = []
    if measures.files > thresholds.small_max_files:
        reasons.append(
            f"files={measures.files} > small_max_files={thresholds.small_max_files}"
        )
    if measures.lines_changed is None:
        reasons.append(
            "lines_changed is indeterminate (not a git work-tree, or git "
            "unavailable) -- an unknown blast radius is treated as the "
            "worse case, never silently small"
        )
    elif measures.lines_changed > thresholds.small_max_lines:
        reasons.append(
            f"lines_changed={measures.lines_changed} > "
            f"small_max_lines={thresholds.small_max_lines}"
        )

    tier = BlastRadiusTier.M if reasons else BlastRadiusTier.S
    return tier, reasons


__all__ = [
    "BlastRadiusMeasures",
    "BlastRadiusThresholds",
    "BlastRadiusTier",
    "classify_tier",
]
