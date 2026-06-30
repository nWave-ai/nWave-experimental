"""Slice-02 entry: per-gate YAML files validation."""

from pytest_bdd import scenarios

from .catalog_steps.steps_catalog import *
from .catalog_steps.steps_slice_02 import *


scenarios("slice-02-per-gate-files.feature")
