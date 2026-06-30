"""Typed domain vocabulary for the fix-cohort-gate-preauthoring slice-01 ATs.

Mandate-15 (SSOT via Types/Services/DSL): every domain noun the slice-01 Gherkin
names is expressed once here as a frozen dataclass, so the composition methods
consume typed parameters (no raw ``str``/``int`` tuples where a typed concept
exists). The scenarios range over these typed feature-delta shapes.

These types are TEST-LOCAL -- they never import production code. The ATs drive the
SUT only through the composition-root driving port (Mandate-16). The single
observable is the candidate-AT count the real cohort classifier reports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDeltaShape:
    """The shape of a crafted hermetic feature-delta the ATs build under a temp dir.

    Two independent dimensions the cohort gate counts:

    * ``placement_candidate_count`` -- number of candidate acceptance tests
      enumerated as a numbered prose list under the
      ``## Wave: DISTILL / [REF] Test Placement`` section (the pre-authoring
      signal). ``None`` means the section is ABSENT entirely.
    * ``authored_scenario_count`` -- number of authored Gherkin ``Scenario:``
      lines present in the feature-delta (the authored-count arm).

    Neither field is a count the test computes from the SUT; both are the
    PRECONDITION volumes the test plants into the crafted feature-delta text.
    """

    placement_candidate_count: int | None
    authored_scenario_count: int


@dataclass(frozen=True)
class CandidateAtCount:
    """The observable: the candidate-AT count the real cohort classifier reports.

    Port-exposed observable only (Mandate-8 universe discipline) -- the integer
    the classifier's count function returns for the ``feature_delta`` kind. NEVER
    an internal classifier field.
    """

    value: int
