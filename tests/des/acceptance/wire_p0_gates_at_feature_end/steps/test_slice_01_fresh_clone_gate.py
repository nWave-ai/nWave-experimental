"""pytest-bdd binding for slice-01-fresh-clone-gate.

slice-01 is the ONE @walking_skeleton scenario per command
(``nw-distill-port-treatment-policy``: subprocess-e2e reserved for the walking
skeleton). Unlike slice-02/03 -- which still drive the ``run_feature_end_cycle``
FUNCTION in-process (their legs are not yet wired, so a function-level
active-RED suffices) -- slice-01 drives the REAL ``des feature-end run`` CLI as a
genuine subprocess. This reproduces the feature-end EXAMINE finding (Vera): the
assembled CLI exits 0 / signs ``FeatureEndCycleComplete`` on a
fresh-clone-broken fixture even though the standalone ``des verify-fresh-clone``
gate refuses it -- the isolated-green != assembled-green (catalogued-not-wired)
gap a function-level AT can never catch.

The shared Given/When/Then vocabulary in ``common_steps`` is reused verbatim
(Mandate-10 shared-vocabulary); only the ``composition`` fixture is overridden
here to hand those steps the CLI-driving ``FeatureEndRunCliComposition`` (whose
method names match the shared step bodies by duck-typing) instead of the
in-process ``FeatureEndP0GateComposition``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import scenarios

from .common_steps import *
from .composition import FeatureEndRunCliComposition


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndRunCliComposition:
    """Override the shared in-process fixture: slice-01's walking-skeleton
    scenario drives the REAL ``des feature-end run`` CLI subprocess. Defined in
    the test module, this fixture shadows the ``composition`` fixture imported
    from ``common_steps`` for THIS module's scenarios only -- slice-02/03 keep
    the in-process composition."""
    return FeatureEndRunCliComposition(tmp_path=tmp_path)


scenarios("../slice-01-fresh-clone-gate.feature")
