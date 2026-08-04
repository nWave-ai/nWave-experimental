"""Regression AT: the 3 confirmed-dead modules from techdebt.md item
`dead-code-sweep-2026-08-03-orphan-app-domain-modules` stay deleted.

Re-verification (grep + tsunami callers_of, not the original audit's
import-only check) found these 3 of 9 candidates genuinely dead -- zero
production callers, no re-exports, no dynamic imports -- and removed them:

  - src/des/domain/deliver_integrity_verifier.py
  - src/des/install/optional_layers.py
  - src/des/application/walking_skeleton_feature_end_gate.py (already
    documented dead in nWave/flavors/atdd_pure.yaml:173-182)

This test pins the negative observable: importing any of the three raises
ModuleNotFoundError. Without a permanent guard, a future refactor could
recreate the module (e.g. via a stale patch, a bad merge, or a search-driven
"restore what looks missing") and reintroduce dead weight with nobody
noticing -- the same silent-reintroduction risk a regression test exists to
close for any other bugfix.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "des.domain.deliver_integrity_verifier",
        "des.install.optional_layers",
        "des.application.walking_skeleton_feature_end_gate",
    ],
)
def test_dead_module_stays_unimportable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
