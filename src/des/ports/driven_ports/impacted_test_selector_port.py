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
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


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
    """

    targets: tuple[str, ...]
    narrowed: bool


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
