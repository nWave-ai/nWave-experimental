"""Walking-skeleton binder — claude-code-attribution-migration.

Step definitions + composition root live in steps/steps_attribution.py (loaded
by the feature-root conftest). This module only binds the scenario.
"""

from pytest_bdd import scenario


@scenario(
    "walking-skeleton.feature",
    "Fresh install records enabled preference and leaves no legacy hook",
)
def test_ws_fresh_install_applies_dual_credit():
    """Walking skeleton: real plugin install records the enabled preference
    against a sandboxed HOME (AC1)."""
