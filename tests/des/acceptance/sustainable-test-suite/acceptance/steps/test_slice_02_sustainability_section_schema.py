"""slice-02 step definitions — the sustainability SECTION SCHEMA + registration.

Driving port: `des validate-feature-delta --require-registry-sections distill
--format=json` subprocess (Mandate-13, Layer 3 subprocess). The subprocess is the SUT;
no production module is imported at the step boundary. Each step body delegates to the
`SectionSchemaDriver` composition (Mandate-12: ≤2 statements, no inline logic, no control
flow).

Active-RED: at HEAD the live `nWave/waves/distill.yaml` does NOT register the canonical
sustainability section (DDD-11 not applied), so the registry-section check emits
`undeclared-section`; every scenario asserts the post-registration `accepted` behaviour
and so fails with a clean AssertionError (MISSING_FUNCTIONALITY). DELIVER makes these
GREEN by ADDING the ref_section to distill.yaml — it does NOT unskip anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .slice_02_composition import SectionSchemaDriver


scenarios("../slice-02-sustainability-section-schema.feature")


@pytest.fixture
def section_driver() -> SectionSchemaDriver:
    return SectionSchemaDriver()


# -- Given ------------------------------------------------------------------


@given(
    "a maintainer authors a feature-delta declaring the canonical sustainability "
    "section under DISTILL"
)
def given_delta_declares_section(
    section_driver: SectionSchemaDriver, tmp_path: Path
) -> None:
    section_driver.given_delta_declaring_sustainability_section(tmp_path)


@given(
    "a maintainer authors a complete DISTILL feature-delta and adds the canonical "
    "sustainability section"
)
def given_complete_delta(section_driver: SectionSchemaDriver, tmp_path: Path) -> None:
    section_driver.given_complete_delta_with_sustainability_section(tmp_path)


# -- When -------------------------------------------------------------------


@when("the registry-section check runs against the live DISTILL registry")
def when_registry_check_runs(section_driver: SectionSchemaDriver) -> None:
    section_driver.when_registry_section_check_runs()


# -- Then -------------------------------------------------------------------


@then("the check accepts the feature-delta")
def then_check_accepts(section_driver: SectionSchemaDriver) -> None:
    section_driver.then_check_accepts()


@then("the sustainability section is recognised as a declared DISTILL output")
def then_section_recognised(section_driver: SectionSchemaDriver) -> None:
    section_driver.then_section_recognised_as_declared_output()


@then(
    "the live DISTILL registry declares the canonical sustainability section by its exact id"
)
def then_registry_declares_id(section_driver: SectionSchemaDriver) -> None:
    section_driver.then_live_registry_declares_canonical_section_id()
