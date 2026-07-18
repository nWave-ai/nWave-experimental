"""Blast-radius tier value types + the pure classification rule.

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Architecture & Contract Tests -- Tier classification table).

Pure, side-effect-free value types + a pure classifier function -- zero
coupling to `des.*` (Effect Isolation, principle 12). slice-02 completes the
full closed S/M/L decision table (DISTILL D6, 2026-07-18 -- `>=` is
authoritative for `large_min_consumers`):

    L iff ANY of: boundary_files non-empty; any consumer_counts value is
        None (indeterminate); any consumer_counts value >= large_min_consumers
    S iff ALL of: files <= small_max_files; lines_changed is not None AND
        <= small_max_lines; boundary_files empty; every consumer_counts
        value <= small_max_consumers
    M otherwise (the measured band between S and L)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlastRadiusTier(str, Enum):
    """The measured tier of a change's blast radius."""

    S = "S"
    M = "M"
    L = "L"


class BlastRadiusConfigRejected(Exception):
    """A present, well-typed `blast_radius` threshold is outside its sane range.

    GDP-3/GDP-6 hard fail (D4, feature-delta "Floor/ceiling validation"): raised
    by `DESConfig` when a threshold is PRESENT and WELL-TYPED but outside its
    documented floor/ceiling -- never a silent clamp, never a silent fallback
    (that degrade is reserved for an ABSENT or WRONG-TYPE key). The message
    names the offending key, its value, its valid range, and points at
    `.nwave/des-config.json` (GDP-3 what/why/how) -- mirrors
    `BlastRadiusInputRejected`'s shape.
    """


@dataclass(frozen=True)
class BlastRadiusThresholds:
    """The numeric/glob thresholds the closed S/M/L decision table reads.

    Canonical defaults (feature-delta "Canonical default thresholds" table).
    `DESConfig._blast_radius()` wires these through the project -> global ->
    hardcoded-default cascade; this dataclass IS the hardcoded-default rung
    (byte-identical to the canonical `.nwave/des-config.json` shape).
    """

    small_max_files: int = 2
    small_max_lines: int = 10
    small_max_consumers: int = 3
    large_min_consumers: int = 10
    boundary_globs: tuple[str, ...] = (
        "**/ports/**",
        "**/adapters/**",
        "**/schemas/**",
        "**/*.schema.json",
        "**/*.proto",
    )


@dataclass(frozen=True)
class BlastRadiusMeasures:
    """The measured facts a change's blast radius is classified from.

    `lines_changed` is `None` when it could not be honestly determined (no
    git work-tree, git absent) -- never a fabricated `0`. A `consumer_counts`
    value is `None` when the touched file itself could not be parsed (a
    genuine measurement failure) -- never a fabricated `0`.
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
    """Classify `measures` into a tier, per the closed S/M/L decision table.

    Returns `(tier, reasons)` -- `reasons` names every condition that fired,
    the verdict is never a bare tier letter alone (GDP-3). L-tier conditions
    are evaluated FIRST and short-circuit S/M evaluation entirely (a boundary
    crossing or an indeterminate/large consumer count is never softened by an
    otherwise-small files/lines measurement).
    """
    large_reasons = _large_tier_reasons(measures, thresholds)
    if large_reasons:
        return BlastRadiusTier.L, large_reasons

    reasons = _small_medium_reasons(measures, thresholds)
    tier = BlastRadiusTier.M if reasons else BlastRadiusTier.S
    return tier, reasons


def _large_tier_reasons(
    measures: BlastRadiusMeasures, thresholds: BlastRadiusThresholds
) -> list[str]:
    reasons: list[str] = []
    if measures.boundary_files:
        reasons.append(f"boundary_files={list(measures.boundary_files)}")

    null_keys = [
        key for key, value in measures.consumer_counts.items() if value is None
    ]
    if null_keys:
        reasons.append(
            f"consumer_counts is indeterminate (null) for {null_keys} -- an "
            "unknown blast radius is treated as the worst case, never "
            "silently smaller"
        )

    for key, value in measures.consumer_counts.items():
        if value is not None and value >= thresholds.large_min_consumers:
            reasons.append(
                f"consumer_counts[{key}]={value} >= "
                f"large_min_consumers={thresholds.large_min_consumers}"
            )
    return reasons


def _small_medium_reasons(
    measures: BlastRadiusMeasures, thresholds: BlastRadiusThresholds
) -> list[str]:
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
    for key, value in measures.consumer_counts.items():
        if value is not None and value > thresholds.small_max_consumers:
            reasons.append(
                f"consumer_counts[{key}]={value} > "
                f"small_max_consumers={thresholds.small_max_consumers}"
            )
    return reasons


__all__ = [
    "BlastRadiusConfigRejected",
    "BlastRadiusMeasures",
    "BlastRadiusThresholds",
    "BlastRadiusTier",
    "classify_tier",
]
