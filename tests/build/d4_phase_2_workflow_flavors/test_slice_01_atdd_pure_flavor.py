"""Slice-01 entry: atdd_pure.yaml flavor config validation."""

from pytest_bdd import scenarios

from .flavor_steps.steps_flavor import *  # noqa: F403


scenarios("walking-skeleton.feature")
