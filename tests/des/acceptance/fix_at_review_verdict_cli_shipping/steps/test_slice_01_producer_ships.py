"""pytest-bdd binding for slice-01 — the recorder ships to an installed instance.

Thin binding (Mandate-12 / shared-vocabulary contract): registers the slice's
scenarios and re-exports the slice-01 step vocabulary. No business logic here.

ADR-028 RED scaffold: UNSKIPPED — these scenarios FAIL on current master for
the RIGHT reason (the recorder still lives outside the source tree the
installer ships from, so it is absent from the discovered ship set + the
frozen ship-floor, and cannot be imported from the installed recorder
namespace). DELIVER's slice-01 relocation greens them.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps_slice_01_producer_ships import *  # noqa: F403 -- step vocabulary


scenarios("../slice-01-producer-ships.feature")
