"""Domain types for slice-01 — the agent-prose surface of the SLIM crafter
contract.

slice-01 of F-CRAFTER-SLIM-ATD-EXPERT (DDD-1, DDD-7 walking-skeleton-first).
Every domain noun in the Gherkin is expressed once here as a typed enum or
NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 + 2).

The walking-skeleton SUT is the FILE CONTENT of three project assets — the
two crafter agents and the ``nw-execute`` dispatch skill. The ATs assert
contract presence/absence by grep against those files.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# Absolute repo-relative path to a project asset under audit.
AssetPath = NewType("AssetPath", str)


class CrafterSurface(str, Enum):
    """The three asset surfaces slice-01 audits.

    OOP_CRAFTER_AGENT   — ``nWave/agents/nw-software-crafter.md`` (the OOP
                          crafter; carries the Q3 loophole at L48 / L106
                          on master).
    FP_CRAFTER_AGENT    — ``nWave/agents/nw-functional-software-crafter.md``
                          (the FP crafter; already-clean surface — slice-01
                          AT is the regression guard).
    NW_EXECUTE_DISPATCH — ``nWave/skills/nw-execute/SKILL.md`` (the classic-
                          template loophole at L110-119 on master; the
                          dispatch-layer Q3 closure target).
    """

    OOP_CRAFTER_AGENT = "oop-crafter-agent"
    FP_CRAFTER_AGENT = "fp-crafter-agent"
    NW_EXECUTE_DISPATCH = "nw-execute-dispatch"


class ContractClause(str, Enum):
    """The slim-crafter contract clauses each surface must declare.

    NO_TEST_AUTHORING_ANY_FORM — the surface explicitly forbids test
                                 authoring of any kind (ATs, paired PBT
                                 unit tests, integration tests, fixtures-
                                 as-tests). The Q3 / ADR-031 anchor.
    ESCALATION_ON_AT_INSUFFICIENT — when an AT cannot reach GREEN, the
                                    surface routes to nw-acceptance-designer
                                    with a structured ESCALATION_NEEDED
                                    payload (NOT a conditional author).
    """

    NO_TEST_AUTHORING_ANY_FORM = "no-test-authoring-any-form"
    ESCALATION_ON_AT_INSUFFICIENT = "escalation-on-at-insufficient"


class LoopholePhrase(str, Enum):
    """The exact loophole phrases slice-01 audits as ABSENT.

    Each phrase is a sentinel for the Q3 conditional-authoring escape hatch.
    A passing AT means a grep for this phrase against the audited surface
    returns zero hits.
    """

    CONDITIONAL_UNIT_TEST_AUTHORING = "Conditional unit-test authoring"
    AUTHOR_MIN_PBT_UNIT_FROM_PORT = (
        "author the minimum PBT unit test from the driving port"
    )
    AUTHOR_PBT_UNIT_ONLY_IF = "author PBT unit tests ONLY if"


class EscalationToken(str, Enum):
    """The escalation-contract tokens that MUST be present in the SLIM surface
    once the loophole is closed.

    Each token is a sentinel for the post-fix contract. A passing AT means a
    grep for this token returns at least one hit.
    """

    AT_INSUFFICIENT_FOR_GREEN = "AT_INSUFFICIENT_FOR_GREEN"
    ROUTE_NW_ACCEPTANCE_DESIGNER = "nw-acceptance-designer"


# Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3: no control
# flow in step bodies — each body is a single typed lookup + composition call).

SURFACE_BY_PHRASE: dict[str, CrafterSurface] = {
    "the OOP crafter agent file": CrafterSurface.OOP_CRAFTER_AGENT,
    "the FP crafter agent file": CrafterSurface.FP_CRAFTER_AGENT,
    "the nw-execute dispatch skill file": CrafterSurface.NW_EXECUTE_DISPATCH,
}

CLAUSE_BY_PHRASE: dict[str, ContractClause] = {
    "no test authoring of any form": ContractClause.NO_TEST_AUTHORING_ANY_FORM,
    "escalation on AT-insufficient-for-GREEN": (
        ContractClause.ESCALATION_ON_AT_INSUFFICIENT
    ),
}

LOOPHOLE_BY_PHRASE: dict[str, LoopholePhrase] = {
    "the Conditional unit-test authoring phrase": (
        LoopholePhrase.CONDITIONAL_UNIT_TEST_AUTHORING
    ),
    "the minimum-PBT-unit-from-port phrase": (
        LoopholePhrase.AUTHOR_MIN_PBT_UNIT_FROM_PORT
    ),
    "the author-PBT-unit-only-if phrase": LoopholePhrase.AUTHOR_PBT_UNIT_ONLY_IF,
}

ESCALATION_BY_PHRASE: dict[str, EscalationToken] = {
    "the AT_INSUFFICIENT_FOR_GREEN escalation token": (
        EscalationToken.AT_INSUFFICIENT_FOR_GREEN
    ),
    "the nw-acceptance-designer route token": (
        EscalationToken.ROUTE_NW_ACCEPTANCE_DESIGNER
    ),
}
