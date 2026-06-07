"""Slice-03 entry: flavor schema + log defaults + host-bridge events."""

from pytest_bdd import scenarios

from .catalog_steps.steps_catalog import *  # noqa: F403 — Background step
from .catalog_steps.steps_slice_03 import *  # noqa: F403


scenarios("slice-03-flavor-log-host-bridge.feature")
