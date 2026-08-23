"""Scenario bindings — attribution-activation-coupling (DISTILL scaffold).

Binds all five `.feature` files (one walking skeleton + four milestones) to the
shared Tier-A step vocabulary in `steps_attribution.py`. The composition root and
all business logic live in `composition.py` (Pillar 3 / Mandate-12 SSOT).

Skip policy (one-at-a-time, ADR-025): the walking-skeleton scenario carries NO
`@skip` tag and therefore RUNS — it is the pre-DELIVER fail-for-right-reason
entry point and must fail RED (MISSING_FUNCTIONALITY), never be skipped. Every
milestone scenario carries `@skip`, translated to `pytest.mark.skip` by the
`pytest_bdd_apply_tag` hook in `conftest.py`; DELIVER unskips them one at a time.

Example-only, no PBT machinery (Mandate 9/11): this is a config-shaped install /
CLI / doctor slice over finite enumerable states (3 activation postures x 3
preferences x 3 settings-availability shapes), so every materially-distinct case
is enumerated as a `Scenario:`. Sad paths (AB-2/AB-3/AB-5/AB-11) are named
example scenarios, never generated.
"""

from pytest_bdd import scenario, scenarios

# Pull the shared Tier-A step vocabulary into this module's namespace so
# pytest-bdd resolves every Given/When/Then.
from .steps_attribution import *


# This scenario carried a STRICT xfail for F-ACTIVATION-INVERTED-IN-PRODUCTION
# while the activation read path collapsed onto ENABLED_DEFAULT. P-SSOT-1 slice
# P5-bis restored the tri-state reader: a non-nWave repo declares nothing in any
# tier, so the `mode` branch resolves it INACTIVE with ENABLED_DEFAULT
# UNCHANGED. The red is RESOLVED, not deferred: P6 (the flip) is still owed.
@scenario(
    "../milestone-1-trailer-scope.feature",
    "Non-nWave repo gets no credit under opt-in default",
)
def test_non_nwave_repo_gets_no_credit_under_opt_in_default() -> None:
    """A repo that never opted in gets no attribution credit."""


scenarios(
    "../walking-skeleton.feature",
    "../milestone-1-trailer-scope.feature",
    "../milestone-2-upgrade-migration.feature",
    "../milestone-3-cli-toggle.feature",
    "../milestone-4-doctor-report.feature",
)
