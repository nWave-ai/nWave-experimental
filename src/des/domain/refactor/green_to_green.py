"""GreenToGreenClassifier -- refactor-safety comparison of two TestRun values.

CREATE_NEW (des-refactor-fixer-swarm slice-01). Reuses ``TestRun`` from
``des.domain.earned_verdict`` verbatim as the comparison INPUT shape (Reuse
Analysis) -- the COMPARISON RULE here is deliberately NOT ``compute_verdict``:
that function answers "did this ONE seam's baseline survive a PERTURBATION"
(mutation-theater question); this answers "did the FULL fast+impacted subset
stay green across a REFACTOR" (a different closed-world rule over the same
value shape, D3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.earned_verdict import TestRun


class GreenToGreenVerdict(str, Enum):
    """The closed refactor-safety verdict set."""

    SAFE = "SAFE"
    UNSAFE = "UNSAFE"


@dataclass(frozen=True)
class GreenToGreenResult:
    """Observable outcome of a before/after refactor-safety comparison."""

    verdict: GreenToGreenVerdict
    before: TestRun
    after: TestRun


def classify_green_to_green(before: TestRun, after: TestRun) -> GreenToGreenResult:
    """Rule whether the fast+impacted subset stayed green across a refactor.

    The rule is deliberately narrow: only the AFTER run's failure count
    determines safety. A pre-existing collection quirk (e.g. zero tests
    collected in a brand-new worktree) is not itself a failure -- only a
    counted test failure after the agent's own change is unsafe.
    """
    verdict = (
        GreenToGreenVerdict.SAFE if after.failed == 0 else GreenToGreenVerdict.UNSAFE
    )
    return GreenToGreenResult(verdict=verdict, before=before, after=after)
