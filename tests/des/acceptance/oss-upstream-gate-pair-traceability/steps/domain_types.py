"""Typed domain concepts for the decision-table <-> AT traceability gate.

Mandate-12 (SSOT via types): the domain nouns the Gherkin speaks -- the verdict
the gate can reach for a clause, and the loud-emission channel -- are expressed
once here as typed enums, so the composition root consumes typed parameters
rather than raw strings.

slice-01 scope: only the syntactic-join verdicts are modelled (witnessed by
name / unwitnessed-no-AT). slice-03 ADDS the behavioral-witness verdicts the
isolated-copy differential perturbation can reach (ADR-001): a genuine asserting
AT -> WITNESSED; a `pass`-vacuous AT that stays green under perturbation ->
SURVIVED; a clause whose `# target:` does not resolve -> TARGET_UNRESOLVED. The
remaining behavioral verdicts (red-for-wrong-reason, baseline-not-green) are the
slice-04 / slice-05 reason-discrimination + degrade poles, intentionally absent
here -- per-slice-JIT.
"""

from __future__ import annotations

from enum import Enum


class ClauseVerdict(str, Enum):
    """Per-clause verdict the traceability gate can reach (slice-01 + slice-03)."""

    # --- slice-01 syntactic-join verdicts ------------------------------------
    # A clause whose ID appears in >=1 `.feature` `# clause:` comment.
    # slice-01: provisionally witnessed (no behavioral check yet).
    WITNESSED_BY_NAME = "witnessed-by-name"
    # A clause whose ID appears in no `.feature` comment -> warn-loud.
    UNWITNESSED_NO_AT = "unwitnessed-no-at"

    # --- slice-03 behavioral-witness verdicts (ADR-001 differential) ---------
    # A clause whose AT passes on correct code AND fails on the perturbed copy
    # with a semantic AssertionError raised in the AT body -> genuinely witnessed.
    WITNESSED = "witnessed"
    # A clause whose AT stays GREEN against the perturbed copy: it executes (or
    # merely names) the target but asserts nothing -> unwitnessed (the one-line
    # `pass`-vacuous evasion, DT-7 non-vacuity pole).
    SURVIVED = "survived"
    # A clause whose witnessing scenario carries no parseable / non-resolving
    # `# target: module::symbol` -> unwitnessed, surfaced loud (DT-12). NEVER a
    # soft skip that lets a syntactic name-match buy a pass.
    TARGET_UNRESOLVED = "target-unresolved"


class EmissionChannel(str, Enum):
    """Where the gate's loud INDETERMINATE warning is observable."""

    # OSS hooks-only invariant: the warning is loud on stderr, non-halting.
    STDERR = "stderr"


class WitnessKind(str, Enum):
    """The behavioral SHAPE of a witnessing acceptance test (slice-03 DT-7).

    The DT-7 non-vacuity contract requires THREE distinct AT shapes so that ONLY
    a genuine wrong-RETURN-perturbation-with-AssertionError-from-AT-body gate
    passes -- every cheaper gate (coverage, crash-perturbation, has-assert,
    has-assert-referencing-target) is caught by at least one shape. The shape is
    a typed domain noun (Mandate-12), not a raw bool/str flag in the builder.
    """

    # Executes the target AND asserts on its RETURN value
    # (`assert accept(1) is True`). A wrong-RETURN perturbation flips this RED
    # with an AssertionError in the AT body -> WITNESSED.
    GENUINE_ASSERTS_RETURN = "genuine-asserts-return"
    # Executes the target but asserts NOTHING (`accept(1)` only). Stays GREEN
    # under perturbation -> SURVIVED. Catches the coverage-equivalent gate.
    EXECUTES_NO_ASSERT = "executes-no-assert"
    # Executes the target AND has a genuine `assert`, but the assertion is
    # INDEPENDENT of the target's return value (`r = accept(1); assert 1 == 1`).
    # A wrong-RETURN perturbation leaves the independent assert GREEN -> SURVIVED.
    # KEYSTONE pole: the only shape that distinguishes a real wrong-RETURN
    # perturbation gate (surfaces it survived) from a syntactic-assert-shape gate
    # (marks it witnessed because an `assert` node is present) AND from a
    # crash-perturbation gate (marks it witnessed because the AT executes the
    # target). Forces wrong-RETURN over crash, closing the slice-03/slice-04
    # reason-discrimination split coherence.
    EXEC_ASSERT_UNRELATED = "exec-assert-unrelated"
