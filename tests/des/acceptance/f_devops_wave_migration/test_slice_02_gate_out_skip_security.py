"""Slice-02 gate-OUT / skip / security AT runner.

Binds the slice-02 feature to its step definitions. The `*`-imports register
every `@given/@when/@then` for pytest-bdd collection (shared SSOT steps from
`steps_common`, slice-specific steps from `steps_slice_02`).
"""

from __future__ import annotations

from devops_wave_migration_steps.steps_common import *
from devops_wave_migration_steps.steps_slice_02 import *
from pytest_bdd import scenarios


scenarios("slice_02_gate_out_skip_security.feature")
