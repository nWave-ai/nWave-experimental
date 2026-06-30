"""Slice-02 entry: classic.yaml flavor config validation."""

from pytest_bdd import scenarios

from .flavor_steps.steps_flavor import *
from .flavor_steps.steps_slice_02 import *


scenarios("slice-02-classic-flavor.feature")
