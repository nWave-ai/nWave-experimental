"""Slice-01 entry: atdd_pure.yaml flavor config validation."""

from pytest_bdd import scenarios

from .flavor_steps.steps_flavor import *


scenarios("walking-skeleton.feature")
