"""slice-03 binder: every repo-internal caller uses `des <subcommand>`.

Layer 3 (filesystem scan + TOML parse). Three CLASS-LEVEL assertions
collapse ~80 individual rewrite sites into:

  AT-07: grep-zero across runtime-authoring trees for `python -m des.cli.X`
  AT-08: grep-zero across same trees for the 5 legacy `des-{shim}` names
  AT-09: pyproject [project.scripts] surface includes dispatcher + installer,
         excludes any des-prefixed legacy entry

GREEN posture today: slice-01 + slice-02 SHIPPED the dispatcher (35a5d02bb)
and the 16-row registry (9302bba63). Slice-03 sweeps every callsite in the
runtime-authoring trees (src/ scripts/ nWave/ tests/) to the new invocation.

Unparked 2026-05-24 (N2 night autonomous PRR push).
"""

from pytest_bdd import scenarios

from .steps.steps_slice_01 import *
from .steps.steps_slice_03 import *


scenarios("slice_03_call_site_migration.feature")
