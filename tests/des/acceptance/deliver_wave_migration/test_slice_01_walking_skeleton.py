"""Slice-01 walking-skeleton AT runner.

Binds the slice-01 feature to its step definitions. The `*`-imports register
every `@given/@when/@then` for pytest-bdd collection (shared SSOT steps from
`steps_common`, slice-specific Given steps from `steps_slice_01`).
"""

from __future__ import annotations

from deliver_wave_migration_steps.steps_common import *
from deliver_wave_migration_steps.steps_slice_01 import *
from pytest_bdd import scenarios


scenarios("slice_01_walking_skeleton.feature")
