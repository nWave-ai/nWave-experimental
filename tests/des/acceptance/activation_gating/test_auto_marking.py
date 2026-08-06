"""Auto-marking binding — project-activation-gating (DISTILL scaffold)."""

from pytest_bdd import scenarios

from tests.des.acceptance.activation_gating.steps.steps_activation_gating import *


scenarios("auto-marking.feature")
