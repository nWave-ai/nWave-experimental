"""Authors retain explicit mutation authority; @contract-shape: real-io."""

import pytest
from tests.des.acceptance.design_no_product_change.public_observation import (
    CASES,
    PublicJourney,
)


@pytest.fixture(scope="module")
def authority_journey(tmp_path_factory):
    return PublicJourney(tmp_path_factory.mktemp("design-authority"))


@pytest.mark.parametrize("declaration", CASES, ids=lambda case: case.name)
def test_authors_receive_only_declared_product_mutation_authority(
    authority_journey, declaration
):
    authority_journey.observe(declaration)
