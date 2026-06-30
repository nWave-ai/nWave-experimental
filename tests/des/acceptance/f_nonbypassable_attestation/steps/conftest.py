"""Shared fixtures + shared step SSOT for the f-nonbypassable-attestation feature.

S1 (step-text uniqueness within feature scope): the done-gate driving verbs that
recur across slices 01-04 ("the developer declares the feature done", "the
done-gate clears the feature", "the done-gate refuses with a definite failure")
are declared ONCE here in conftest -- the canonical pytest-bdd shared-step SSOT
(the S1 tolerable-variant: single source of truth, referenced from multiple slice
features via pytest-bdd's step composition). Per-slice step files declare only the
steps UNIQUE to that slice, so no `(step_type, literal)` key is declared twice
with its own body (no last-loaded shadow).

Mandate-12: step bodies delegate to the composition root; ≤2 statements, final
statement is a composition method call; no control flow.
"""

from __future__ import annotations

import pytest
from pytest_bdd import then, when

from .composition_nonbypassable import AttestationComposition
from .domain_types_nonbypassable import DoneVerdict


@pytest.fixture
def attestation() -> AttestationComposition:
    return AttestationComposition()


# NOTE: the slice-05 `guard` fixture + `WaveDispatchGuardComposition` were
# EXTRACTED to docs/feature/f-nonbypassable-attestation/pending-ats/acceptance/
# steps/composition_slice_05.py (f-nonbypassable-attestation slice-01 hermeticity
# fix): the guard composition reaches `~/.claude/...` (non-hermetic), and slice-05
# is HELD per carpaccio JIT. They return to the collected tree, with a hermetic
# repo-source target, when slice-05 is delivered.


# --- Shared done-gate verbs (SSOT, S1) -------------------------------------


@when("the developer declares the feature done")
def when_declare_done(attestation: AttestationComposition) -> None:
    attestation.when_done_is_declared()


@then("the done-gate clears the feature")
def then_done_gate_clears(attestation: AttestationComposition) -> None:
    attestation.then_verdict_is(DoneVerdict.PASS)


@then("the done-gate refuses with a definite failure")
def then_done_gate_refuses_fail(attestation: AttestationComposition) -> None:
    attestation.then_verdict_is(DoneVerdict.FAIL)


@then("the done-gate cannot certify the feature")
def then_done_gate_cannot_certify(attestation: AttestationComposition) -> None:
    attestation.then_verdict_is(DoneVerdict.INDETERMINATE)
