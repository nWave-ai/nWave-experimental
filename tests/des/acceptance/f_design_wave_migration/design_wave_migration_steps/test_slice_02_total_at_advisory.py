"""pytest-bdd binding for f-design-wave-migration slice-02 scenarios.

Two driving surfaces: the REAL shipped nw-distill skill (AT-3/4 prose) and the
REAL DESConfig port (AT-6). Step bodies delegate to the composition root; no
business logic in the step bindings (Mandate-12 criterion 3). The AT-6 Given steps
parse the typed sentinel/decoy integers and drive the config port against
``tmp_path`` (the prose surface needs no config).

GREEN-not-active-RED: row 7c + the DESConfig @property already ship, so these pass
— the expected state for a format conversion of passing behaviour.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02_total_at_advisory import TotalAtAdvisoryComposition


scenarios("../slice-02-total-at-advisory.feature")

# The typed sentinel/decoy the Gherkin names verbatim (kept in one place so the
# step text and the assertion agree on the value — DSL over a literal).
_SENTINEL = 99
_DECOY = 5


@pytest.fixture
def total_at() -> TotalAtAdvisoryComposition:
    return TotalAtAdvisoryComposition()


# --- Given (AT-6 config-port surface) --------------------------------------


@given("a project config sets the advisory threshold to 99 in its rigor block")
def given_threshold_in_rigor(total_at: TotalAtAdvisoryComposition, tmp_path) -> None:
    total_at.when_a_config_carries_threshold_in_rigor(tmp_path, _SENTINEL)


@given("no rigor config is present in the project or global config")
def given_no_rigor_config(total_at: TotalAtAdvisoryComposition, tmp_path) -> None:
    total_at.when_no_rigor_config_is_present(tmp_path)


@given(
    "a project config sets the advisory threshold to 99 and a decoy carpaccio "
    "ceiling of 5"
)
def given_threshold_and_decoy(total_at: TotalAtAdvisoryComposition, tmp_path) -> None:
    total_at.when_a_config_carries_threshold_and_decoy_slice_max(
        tmp_path, _SENTINEL, _DECOY
    )


# --- When ------------------------------------------------------------------


@when("the shipped nw-distill skill is read")
def when_distill_read(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.when_the_shipped_distill_skill_is_read()


@when("the advisory threshold is read from the config port")
def when_threshold_read(total_at: TotalAtAdvisoryComposition) -> None:
    # The config port was already driven in the Given; this When marks the read
    # boundary so the Then asserts the observable (the @property value).
    pass


# --- Then (AT-3 / AT-4 prose surface) --------------------------------------


@then("nw-distill carries a total-AT advisory that proposes the DISCUSS wave")
def then_trigger_exists(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_total_at_trigger_exists()


@then(
    "the advisory is keyed on the total acceptance-test volume crossing the threshold"
)
def then_keyed_on_total(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_advisory_keyed_on_total_at_volume()


@then("the total-AT advisory stays silent when the count is at or under the threshold")
def then_silent_at_or_under(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_advisory_silent_at_or_under_threshold()


# --- Then (AT-6 config-port surface) ---------------------------------------


@then("the advisory threshold reads the value 99 from the rigor cascade")
def then_reads_rigor_cascade(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_threshold_reads_rigor_cascade(_SENTINEL)


@then("the advisory threshold defaults to a positive integer ceiling")
def then_defaults_positive(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_threshold_defaults_to_positive_int()


@then(
    "the advisory threshold reads 99 from its own rigor key and the config port "
    "exposes no carpaccio ceiling"
)
def then_distinct_locus(total_at: TotalAtAdvisoryComposition) -> None:
    total_at.then_threshold_distinct_from_carpaccio_slice_max(_SENTINEL)
