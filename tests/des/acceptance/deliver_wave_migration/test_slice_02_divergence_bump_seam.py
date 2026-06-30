"""Slice-02 divergence / bump / INDETERMINATE / seam AT runner.

Binds the slice-02 feature to its step definitions. The `*`-imports register
every `@given/@when/@then` for pytest-bdd collection (shared SSOT steps from
`steps_common`, slice-specific steps from `steps_slice_02`).
"""

from __future__ import annotations

from deliver_wave_migration_steps.steps_common import *
from deliver_wave_migration_steps.steps_slice_02 import *
from pytest_bdd import scenarios


scenarios("slice_02_divergence_bump_seam.feature")
