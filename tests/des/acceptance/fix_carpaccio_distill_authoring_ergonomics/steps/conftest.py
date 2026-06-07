"""pytest-bdd fixtures for the fix-carpaccio-distill-authoring-ergonomics AT set.

Layer 3 (subprocess / FS acceptance): the composition root drives the real `des`
CLIs as subprocesses against a tmp_path repository fixture. The ``composition``
and ``result_box`` fixtures are shared across the three slice step modules
(slices 01/02 drive `des carpaccio-slice-gate` via the dispatcher subcommand;
slice 03 drives the non-gate `python -m des.cli.carpaccio_precheck` module-direct).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition import CarpaccioErgonomicsComposition, CliResult


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioErgonomicsComposition:
    """Production-wired composition root over a tmp_path repository fixture."""
    return CarpaccioErgonomicsComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, CliResult]:
    """Carrier for the CLI result across When -> Then steps."""
    return {}
