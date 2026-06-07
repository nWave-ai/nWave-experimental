"""Walking-skeleton scenarios for D4 Phase 1 slice-01."""

from pytest_bdd import scenarios

from .catalog_steps.steps_catalog import *  # noqa: F403


scenarios("walking-skeleton.feature")
