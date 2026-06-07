"""Typed domain vocabulary for dor-items-ssot slice-03 (Mandate-12).

slice-03 closes the SECOND axis at the artifact the reviewer actually loads
(``nWave/skills/nw-dor-validation/SKILL.md``): the loaded skill must TELL the
reviewer, at the point of enforcement, that **job-traceability is a SEPARATE hard
gate ABOVE the nine readiness items** -- NOT readiness item ten (DISCUSS D-5 /
DESIGN DDD-3). Today the skill enumerates the nine but says nothing about
job-traceability at all, so a reviewer following the loaded skill can confuse the
``job_id`` check for an enumerated item (or skip it alongside one). slice-03's
production GREEN adds the separate-gate statement consistent with the SSOT's
``hard_gates`` key.

This module pins, as typed constants, the cross-artifact contract the slice-03
ATs assert over the REAL shipped skill content:

  - the job-traceability gate name the skill must present as SEPARATE (reusing
    the slice-01 ``JOB_TRACEABILITY_GATE`` single source of truth -- no second
    copy);
  - the "above the readiness items" / "separate hard gate" relationship the skill
    must state, expressed as the boolean facts the loaded-skill view exposes.

The cross-artifact pattern mirrors slice-02's ``domain_types_slice_02``: a real
shipped skill file is the SUT, structural-content assertions verify the
human-facing copy, example-only (no PBT -- the contract is a fixed closed shape,
Mandate 9/11).

CRITICAL anti-trap (same as slice-02): the GREEN skill statement MUST NOT contain
the literal ``nWave/data/`` (``validate_no_data_refs.py`` forbids it in any
framework ``.md``). The slice-03 separate-gate statement names the gate by its
bare ``job-traceability`` token and may cite the bare SSOT filename
(``dor-items.yaml``) / the standalone reader -- never the forbidden prefix.
"""

from __future__ import annotations

from dataclasses import dataclass

# Reuse the slice-01 single source of truth for the gate name + the canonical
# nine. slice-03 does NOT restate either (a second copy would be the very drift
# this feature kills).
from .domain_types import (
    CANONICAL_READINESS_ITEMS,
    JOB_TRACEABILITY_GATE,
)


# The separate-hard-gate token the loaded skill must carry. Reuses the slice-01
# constant so there is one name for the gate across all slices.
SEPARATE_HARD_GATE_TOKEN: str = JOB_TRACEABILITY_GATE  # "job-traceability"


@dataclass(frozen=True)
class JobTraceabilityGateView:
    """The loaded skill's port-exposed stance on the job-traceability gate.

    Port-exposed observable shape only (Mandate 8): the structural facts a
    reviewer reads off the shipped skill text about job-traceability -- whether
    the skill TELLS the reviewer it is a separate hard gate above the readiness
    items, and whether the skill (wrongly) counts it as one of the enumerated
    nine. Never an internal parser struct.
    """

    states_job_traceability_is_separate_hard_gate: bool
    states_separate_gate_is_above_readiness_items: bool
    counts_job_traceability_among_readiness_items: bool


__all__ = [
    "CANONICAL_READINESS_ITEMS",
    "JOB_TRACEABILITY_GATE",
    "SEPARATE_HARD_GATE_TOKEN",
    "JobTraceabilityGateView",
]
