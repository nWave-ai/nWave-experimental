"""Shared fixtures for the P4 tracked-before fallback acceptance suite.

Lives at the binder-package level so pytest-bdd's scenario wrappers (in the
`test_slice_*` binders) discover the `composition` fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .steps.composition import ReverifyP4Composition


@pytest.fixture
def composition(tmp_path: Path) -> ReverifyP4Composition:
    """A fresh composition root: an empty real temp-git repo + the CLI port."""
    return ReverifyP4Composition(tmp_path)
