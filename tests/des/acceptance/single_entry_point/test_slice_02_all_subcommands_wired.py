"""slice-02 binder: every subcommand reachable through the dispatcher.

Layer 3 (subprocess + AST acceptance). Parametrize-collapse over the
SUBCOMMAND_TABLE: 16 subcommands × 2 outlines = 32 reachability assertions
through 2 scenarios + 1 bundle-scan scenario = 3 ATs (AT-04 + AT-05 + AT-06).

GREEN posture today: slice-01 SHIPPED the dispatcher + the 16-row registry
in `src/des/cli/__main__.py:_REGISTRY` (commit 35a5d02bb era + subsequent
wiring). Slice-02 ATs exercise the registry end-to-end: every name resolves,
every subcommand's argv passthrough preserves argparse exit codes, the
dispatcher stays stdlib-only at import time.
"""

from pytest_bdd import scenarios

from .steps.steps_slice_01 import *  # noqa: F403 — reuse Background Given
from .steps.steps_slice_02 import *  # noqa: F403


scenarios("slice_02_all_subcommands_wired.feature")
