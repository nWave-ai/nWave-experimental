"""pytest-bdd binding for fix-freshness-gate-dev-checkout-autoskip slice-01.

Thin binding: registers the slice's scenarios and imports the shared step
vocabulary from `freshness_steps.steps_freshness`. No step definitions or
business logic live here. The subpackage is named `freshness_steps` (not
`steps`) to avoid a sys.path-level collision with the sibling installer
feature `tests/installer/acceptance/fix-des-self-hosted-gate-sync/steps/`.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .freshness_steps.steps_freshness import *  # noqa: F403  -- step vocabulary


scenarios("walking-skeleton.feature")
