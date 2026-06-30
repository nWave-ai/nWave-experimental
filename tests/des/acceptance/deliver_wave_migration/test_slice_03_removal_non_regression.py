"""Slice-03 removal + non-regression AT runner.

Binds the slice-03 feature to its step definitions. The `*`-imports register
every `@given/@when/@then` for pytest-bdd collection (shared SSOT steps from
`steps_common`, slice-specific steps from `steps_slice_03`).
"""

from __future__ import annotations

from deliver_wave_migration_steps.steps_common import *
from deliver_wave_migration_steps.steps_slice_03 import *
from pytest_bdd import scenarios


scenarios("slice_03_removal_non_regression.feature")
