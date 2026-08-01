"""ImpactedTestSelectorPort -- driven port for the green-to-green test scope.

CREATE_NEW (des-refactor-fixer-swarm). Selects the impact-selected test subset
(D3): fast tier + tests connected to the modified files -- NEVER the full suite
as the per-item gate. Degrades LOUD per the ``nw-code-analysis-port`` contract:
a Tsunami-absent target emits a named skip event, never a silently-empty
impacted set (the heuristic fallback -- importers of the changed module / same
feature dir -- still runs).

Pure interface -- no behavior to scaffold. The concrete adapter
(``des.adapters.driven.refactor.tsunami_impacted_test_selector_adapter.
HeuristicImpactedTestSelectorAdapter``) carries the Mandate-7 RED scaffold.

``ImpactedTestSelection.narrowed`` is the GDP-8 arity corollary fix for
[[impacted-test-selector-selects-everything-and-its-premise-is-false]]: a
selector that fell back to the whole repo because it genuinely could not
narrow (no ``changed_paths`` given, or the heuristic found no candidate) is a
DIFFERENT observable outcome from one that narrowed and the narrowed set
happens to be everything. Collapsing the two into a bare ``tuple[str, ...]``
is exactly the defect this type exists to end -- a caller could not tell
"I restricted, and this is the impacted set" from "I did not restrict at
all", which is what let the drain silently pay a full-suite run per item
while its own docstring claimed otherwise.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class SelectionOutcome(Enum):
    """Which of three causally distinct things ``select()`` did (GDP-8 arity
    corollary, feature impacted-test-selector-arity-fix). Both non-``NARROWED``
    members REQUIRE a ``reason`` on the ``ImpactedTestSelection`` that carries
    them -- a bare token with no cause is itself a defect (CT-3), enforced by
    ``ImpactedTestSelection.__post_init__`` below: construction refuses loudly
    rather than accept a causeless non-``NARROWED`` outcome.
    """

    #: ``targets`` is a PROPER SUBSET of the tree, computed from a genuine
    #: change set -- the selector actually narrowed.
    NARROWED = "narrowed"
    #: Narrowing RAN and concluded the impacted set genuinely IS the whole
    #: tree (e.g. a changed root conftest, or a module the tree imports
    #: everywhere). ``reason`` names WHICH input forced it.
    NOT_NARROWABLE = "not_narrowable"
    #: Narrowing COULD NOT RUN at all. ``reason`` names WHY (no change set
    #: supplied / an unparseable file / the tree walk failed).
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ImpactedTestSelection:
    """Observable outcome of one ``select()`` call.

    ``targets`` is never empty -- a selector that cannot narrow still names
    the fallback scope (the repo root) rather than returning nothing.
    ``narrowed`` is the arity-correct third state (GDP-8): ``True`` iff
    ``targets`` is a genuine, proper restriction driven by ``changed_paths``;
    ``False`` iff the selector fell back to the whole repo -- either because
    no ``changed_paths`` were given (nothing to narrow against) or because
    the heuristic found no candidate test directory for what was given. A
    caller MUST branch on ``narrowed``, never infer it from ``len(targets)``
    or from ``targets == (str(repo),)`` -- that inference is precisely the
    designation-vs-property confusion GDP-8 forbids.

    ``outcome`` + ``reason`` (feature impacted-test-selector-arity-fix,
    slice-01) are the WIDENED, arity-correct replacement for ``narrowed``
    alone: ``outcome`` names WHICH of the three ``SelectionOutcome`` states
    this call reached, and ``reason`` names WHY for the two non-``NARROWED``
    states. Both default to ``None`` so a construction site that only cares
    about ``narrowed`` (a boundary that has not adopted the widened
    vocabulary) keeps working unchanged -- but a call site that DOES supply a
    non-``NARROWED`` ``outcome`` must also supply a non-empty ``reason``
    (CT-3, enforced below): a bare outcome token with no cause is exactly the
    designation-over-property defect this feature exists to remove, one
    level up from the ``narrowed``/``targets`` confusion GDP-8 already
    forbids above.
    """

    targets: tuple[str, ...]
    narrowed: bool
    outcome: SelectionOutcome | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """CT-3: refuse construction of a non-``NARROWED`` outcome with an
        empty or missing reason -- loudly, at the point of construction,
        rather than let a causeless outcome travel silently into a rendered
        report.

        WHAT -- ``outcome`` is one of ``NOT_NARROWABLE``/``INDETERMINATE``
        and ``reason`` is empty or ``None``. WHY -- CT-3 (feature
        impacted-test-selector-arity-fix): both non-``NARROWED`` states exist
        BECAUSE the selector could not do what it normally does, and a
        cause-free "could not narrow" is indistinguishable from a bug that
        silently drops the reason. HOW -- pass a non-empty ``reason`` naming
        WHY narrowing could not run (``INDETERMINATE``) or WHY it concluded
        the whole tree is impacted (``NOT_NARROWABLE``).
        """
        if self.outcome is not None and self.outcome != SelectionOutcome.NARROWED:
            if not self.reason:
                raise ValueError(
                    "ImpactedTestSelection refuses construction: WHAT -- "
                    f"outcome={self.outcome!r} was constructed with an "
                    f"empty/missing reason ({self.reason!r}). WHY -- CT-3 "
                    "(feature impacted-test-selector-arity-fix): a "
                    "NOT_NARROWABLE or INDETERMINATE outcome always has a "
                    "named cause -- reporting one without it would be the "
                    "designation-over-property defect this type exists to "
                    "prevent. HOW -- pass a non-empty `reason` string naming "
                    "why narrowing could not run or concluded the whole "
                    "tree is impacted."
                )


class ImpactedTestSelectorPort(ABC):
    """Driven port: selects the impact-selected (never full-suite) test scope."""

    @abstractmethod
    def select(
        self, repo: Path, changed_paths: tuple[str, ...]
    ) -> ImpactedTestSelection:
        """Return the test scope impacted by ``changed_paths`` -- fast tier +
        impact-selected, never the full suite -- and whether it is a genuine
        narrowing or an honestly-declared fallback (see
        ``ImpactedTestSelection``)."""
        ...
