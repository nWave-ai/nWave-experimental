"""Typed domain vocabulary for the nwave-flow-v2-enforcement slice-07 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-07
Gherkin names is expressed once here as a typed enum, so the composition methods
consume typed parameters (no raw ``str`` where an enum exists) and the DSL
emerges from the type system rather than from decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13). ``GateDecision``
mirrors slice-04's observable allow/deny surface but is re-declared here so the
slice-07 step modules stay self-contained (each slice owns its vocabulary).
"""

from __future__ import annotations

from enum import Enum


class SsotPreconditions(Enum):
    """Whether a project's DISCUSS product preconditions (SSOT + migration) are met.

    Mirrors the observable ``SsotPresence`` the production ``ProductSsotReader``
    exposes -- the AT arranges one of these states under a tmp ``project_root``
    and observes only the gate's allow/deny decision (never the VO directly).
    """

    MET = "met"  # docs/product/ present with vision+backlog+glossary + jobs (YAML)
    UNMET = "unmet"  # docs/product/ absent or a required SSOT doc missing
    JOBS_AS_YAML = (
        "jobs-as-yaml"  # vision+backlog+glossary .md AND jobs as YAML (no jobs.md)
    )
    JOBS_ABSENT = (
        "jobs-absent"  # vision+backlog+glossary present, jobs missing entirely
    )


class SlicePlanShape(Enum):
    """The cohesion shape of a feature-delta's slice plan (the gate-OUT input).

    The MECC floor (`validate_slice_plan_content`) accepts only a structurally
    well-formed AND value-bearing plan; an all-``@infrastructure`` plan is the
    slice-06 cohesion veto.
    """

    VALUE_BEARING = "value-bearing"  # >=1 row carries user-visible value -> accepted
    INFRASTRUCTURE_ONLY = "infrastructure-only"  # all rows @infrastructure -> rejected
    UNREADABLE = "unreadable"  # the feature-delta is absent / cannot be read


class GateDecision(Enum):
    """The observable hook decision surface (allow vs block) for both gates."""

    ALLOW = "allow"
    BLOCK = "block"
