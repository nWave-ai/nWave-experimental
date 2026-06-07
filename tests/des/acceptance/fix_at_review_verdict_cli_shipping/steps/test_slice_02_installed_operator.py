"""pytest-bdd binding for slice-02 — installed operator clears the carpaccio gate.

Thin binding (Mandate-12 / shared-vocabulary contract): registers the slice's
scenarios and re-exports the slice-02 step vocabulary. No business logic here.

ADR-028 RED scaffold: UNSKIPPED — these scenarios FAIL on current master for
the RIGHT reason (the recorder is not importable from the installed recorder
namespace, so the recording subprocess cannot run on the installed no-
enclosing-repo layout and the gate never sees an approval to clear on).
DELIVER's slice-02 (atop slice-01's relocation) greens them.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps_slice_02_installed_operator import *  # noqa: F403 -- step vocabulary


scenarios("../slice-02-installed-operator-clears-gate.feature")
