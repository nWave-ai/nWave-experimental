"""GreenToGreenClassifier -- refactor-safety comparison of test observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.test_run import TestRun


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

    A real AFTER observation with no counted failures is safe.  An unobserved
    AFTER leg (for example an unavailable runner) is unsafe: absence of a
    measurement must never become a green result.
    """
    verdict = (
        GreenToGreenVerdict.SAFE
        if after.observed and after.failed == 0
        else GreenToGreenVerdict.UNSAFE
    )
    return GreenToGreenResult(verdict=verdict, before=before, after=after)
