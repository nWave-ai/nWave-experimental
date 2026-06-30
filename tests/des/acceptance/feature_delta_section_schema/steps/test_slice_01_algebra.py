"""pytest-bdd binding — slice-01 (algebra + registry walking skeleton).

Driving port: `des feature-delta-schema describe` subprocess (Mandate-13, Layer 3).
Each step body is a single delegation to the composition root (Mandate-12: no
business logic / control flow in a step body). Step decorator literals are unique
within this feature directory (S1 step-text-uniqueness invariant).

Active-RED scaffold (ADR-025/028 atdd_pure -- NOT @skip): at HEAD the subcommand
scaffold raises AssertionError, so the subprocess exits non-zero and each `then`
fails with a semantic AssertionError -- never a collection/import/setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then, when

from .composition import DescribeComposition


scenarios("../slice-01-algebra-and-registry.feature")


@pytest.fixture
def describe() -> DescribeComposition:
    return DescribeComposition()


@when("the maintainer describes the feature-delta section-schema")
def when_describe_schema(describe: DescribeComposition) -> None:
    describe.when_described()


@when("the maintainer describes the section-schema constructors")
def when_describe_constructors(describe: DescribeComposition) -> None:
    describe.when_described("--types")


@when("the maintainer describes the section-schema routing")
def when_describe_routing(describe: DescribeComposition) -> None:
    describe.when_described("--consumed-by")


@then("the description succeeds end-to-end")
def then_describe_succeeds(describe: DescribeComposition) -> None:
    describe.then_succeeds()


@then("exactly the five section-type constructors are listed")
def then_five_constructors(describe: DescribeComposition) -> None:
    describe.then_lists_exactly_five_constructors()


@then("each registered section reports exactly one constructor")
def then_one_constructor_per_section(describe: DescribeComposition) -> None:
    describe.then_each_section_has_one_constructor()


@then("every consumed-by token is a kebab-lowercase wave from the eight-wave set")
def then_consumed_by_kebab_subset(describe: DescribeComposition) -> None:
    describe.then_consumed_by_is_kebab_subset_of_waves()
