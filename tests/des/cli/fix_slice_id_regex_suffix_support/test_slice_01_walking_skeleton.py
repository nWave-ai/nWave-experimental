"""Walking-skeleton scenarios for slice-id regex suffix support."""

from pytest_bdd import scenarios

from .slice_id_regex_steps.steps_slice_id_regex import *


scenarios("walking-skeleton.feature")
