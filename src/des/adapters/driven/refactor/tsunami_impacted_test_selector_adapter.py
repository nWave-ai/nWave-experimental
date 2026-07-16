"""HeuristicImpactedTestSelectorAdapter -- ImpactedTestSelectorPort implementation.

CREATE_NEW file (des-refactor-fixer-swarm slice-01). Tsunami-first (the
``nw-code-analysis-port`` chain), degrading LOUD to the heuristic fallback
(importers of the changed module / same feature dir) when Tsunami is absent --
never a silently-empty impacted set.

slice-01 implements the heuristic floor only: the fast+impacted scope is the
target worktree itself (a freshly-cut, small worktree -- collecting the whole
tree IS the fast+impacted subset for a single drained item). No Tsunami
dependency is exercised yet; a Tsunami-first tier is a later-slice addition
once a real multi-module target needs narrower scoping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.ports.driven_ports.impacted_test_selector_port import (
    ImpactedTestSelectorPort,
)


if TYPE_CHECKING:
    from pathlib import Path


class HeuristicImpactedTestSelectorAdapter(ImpactedTestSelectorPort):
    """Real adapter -- heuristic impacted-test selection (whole-worktree floor)."""

    def select(self, repo: Path, changed_paths: tuple[str, ...]) -> tuple[str, ...]:
        return (str(repo),)
