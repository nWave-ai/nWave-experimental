"""Walking-skeleton scenarios for distribution boundary dev mode."""

from pytest_bdd import scenarios

from .distribution_steps.steps_distribution import *  # noqa: F403


scenarios("walking-skeleton.feature")
