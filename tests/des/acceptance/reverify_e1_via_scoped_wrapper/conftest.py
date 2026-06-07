"""Shared fixtures for the reverify-E1-via-scoped-wrapper acceptance suite.

Lives at the binder-package level so pytest-bdd's scenario wrappers (in the
``test_slice_*`` binders) discover the ``composition`` fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .steps.composition import ReverifyE1WrapperComposition


@pytest.fixture
def composition(tmp_path: Path) -> ReverifyE1WrapperComposition:
    """A fresh composition root: a real temp-git repo + driver methods."""
    return ReverifyE1WrapperComposition(tmp_path)
