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
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class ImpactedTestSelectorPort(ABC):
    """Driven port: selects the impact-selected (never full-suite) test scope."""

    @abstractmethod
    def select(self, repo: Path, changed_paths: tuple[str, ...]) -> tuple[str, ...]:
        """Return the test paths impacted by ``changed_paths`` -- fast tier +
        impact-selected, never the full suite."""
        ...
