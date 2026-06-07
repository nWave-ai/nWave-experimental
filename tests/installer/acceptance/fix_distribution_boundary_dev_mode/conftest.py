"""Conftest for fix-distribution-boundary-dev-mode carpaccio slice.

Driving port: `des.runtime.distribution.find_git_root` — loaded via direct
import (composition root). Per Mandate-13: ATs drive via function entry
point on real filesystem (tmp_path), NEVER via internal field
introspection.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class DistributionBoundaryComposition:
    """Composition root for the distribution boundary resolver service.

    Wraps `find_git_root(start)` so step bodies stay ≤2 statements per
    Mandate-12.
    """

    def __init__(self) -> None:
        from des.runtime.distribution import find_git_root

        self._resolver = find_git_root
        self._start_path: str | None = None
        self._result: str | None = None

    def stage_start_path(self, path: Path) -> None:
        self._start_path = str(path)

    def resolve(self) -> None:
        self._result = self._resolver(self._start_path)

    @property
    def result(self) -> str | None:
        return self._result


@pytest.fixture
def composition() -> DistributionBoundaryComposition:
    return DistributionBoundaryComposition()
