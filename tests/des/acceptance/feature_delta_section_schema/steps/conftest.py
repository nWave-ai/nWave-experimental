"""Shared step definitions + fixtures for the feature-delta-section-schema ATs.

S1 step-text-uniqueness SSOT: slice-02 (projections) and slice-03 (convergence
section) BOTH drive `des feature-delta-schema verify <file>` and BOTH assert the
PASS verdict. pytest-bdd keys step bodies in a process-global registry by
(step_type, literal_arg); two byte-identical literals across slice modules would
shadow (silent test inversion). Per Mandate-12 (one body per domain noun) the
shared literals live here ONCE.

A conftest.py in the steps directory makes its step definitions visible to EVERY
scenario collected under this directory without a per-module import — the
pytest-bdd-idiomatic way to share steps (a plain `from ... import` of decorated
step functions does NOT register them into the importing module's scenario scope).

Each body is a single delegation to the composition root (no logic / control flow,
Mandate-12). The `verify` fixture is shared so both slices arrange the same
VerifyComposition instance the shared steps operate on.
"""

from __future__ import annotations

import pytest
from pytest_bdd import then, when

from .composition import VerifyComposition


@pytest.fixture
def verify() -> VerifyComposition:
    return VerifyComposition()


@when("the schema gate verifies the document")
def when_verified(verify: VerifyComposition) -> None:
    verify.when_verified()


@then("the verdict is pass")
def then_pass(verify: VerifyComposition) -> None:
    verify.then_verdict_pass()
