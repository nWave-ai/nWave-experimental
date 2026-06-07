"""pytest-bdd binding for oss-spine-watchdog slice-01.

Thin binding: registers the slice-01 scenarios and imports the step vocabulary
from `steps.steps_slice_01_collection_precheck`. No step definitions or business
logic live here — the SSOT for step bodies is the imported module; the SSOT for
the scenarios is the `.feature` file (code is the SSOT, per the DISTILL mandate).

Slice-01 = the walking skeleton: the DES spine runs a contract-suite COLLECTION
precheck before the G_COMMIT exit gate. A collection crash → a LOUD SINGLE failure
NAMING the broken module (KPI-3), terminating — instead of the silent hour-long
re-fire loop (RCA root #68). The KPI-3 named-module assertion lives in AT-01 (the
@walking-skeleton scenario) + AT-03 (the env-parity probe): both assert the
precheck NAMES the crashing module — RED today (the worker emits only
`pytest_exit_code`), GREEN once DELIVER EXTENDs the worker per DESIGN R-1.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_01_collection_precheck import *  # noqa: F403  -- step vocabulary


scenarios("slice-01-collection-health-precheck.feature")
