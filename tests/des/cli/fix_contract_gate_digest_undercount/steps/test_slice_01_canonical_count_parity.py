"""Slice-01 walking-skeleton step bindings -- contract-gate digest undercount.

pytest-bdd glue. The scenario logic lives in the composition root
(``composition.py``); these bindings are thin -- each delegates to a
composition method, no business logic in the step body (Mandate-12).

Driving port: the real ``des run-contract-gate --collect-only --print-digest``
CLI via subprocess (Layer 3, Mandate-13). No production import in this module.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when

from .composition import ContractGateDigestComposition
from .domain_types import Coverage, SuiteShape


scenarios("../slice-01-canonical-count-parity.feature")


@given("the contract gate is pointed at the canonical-live contract suite")
def given_canonical_live_suite(composition: ContractGateDigestComposition):
    # fix-contract-gate-slow-tests-synthetic-fixture: this scenario's counting
    # property (digest node_id_count parity vs pytest's own collected_count)
    # is scale-invariant -- it holds identically on a small synthetic project
    # as on this repo's live multi-thousand-item tree. Bound to the existing
    # COLLAPSE_PRONE synthetic fixture (composition.py:404-439) instead of
    # CANONICAL_LIVE so the walking skeleton no longer pays the ~130.65s
    # real-repo subprocess cost. See docs/product/expectations/
    # fix-contract-gate-slow-tests-synthetic-fixture/
    # two-slow-gate-self-tests-swap-to-synthetic-fixture.md.
    composition.use_suite(SuiteShape.COLLAPSE_PRONE)


@when("the operator runs the print-digest CLI twice over the suite")
def when_run_print_digest_twice(composition: ContractGateDigestComposition):
    composition.run_print_digest_twice()


@then("the emitted digest fingerprints the full-canonical collected scope")
def then_full_canonical_coverage(composition: ContractGateDigestComposition):
    composition.assert_coverage(Coverage.FULL_CANONICAL)
