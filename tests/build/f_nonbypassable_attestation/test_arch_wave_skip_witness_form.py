"""AT-A8 (slice-05, DDD-9): the wave-skip witness FORM check exists and is FORM-only.

RE-HOMED (orchestrator augment 2026-06-16): the wave-parametric skip-witness
predicate is lifted into the DES-runtime domain policy
``src/des/domain/wave_dispatch_guard_policy.py`` (the DDD-9 generalization home),
so BOTH the readiness gate and the new wave-dispatch gate read ONE implementation
-- NOT a ``~/.claude`` personal-hook helper. This arch test imports the IN-TREE
policy module; no ``~/.claude`` path.

Arch-tier, pure-function (no subprocess, no behavioral execution): drives the SHIPPED
wave-parametric skip-witness predicate over crafted markdown and asserts it verifies
the witness FORM (canonical heading + non-empty rationale presence) -- and pins, by
construction, that it CANNOT verify source-authorship. Recognized as an arch test
(``test_arch_`` prefix under ``tests/build/``) per the AT-completeness S2 rule.

DRIVING SURFACE (Mandate-13 protocol-driver): the check drives the REAL shipped
predicate (the DDD-9 net-new seam generalizing ``_design_skip_witness_present`` to
``_wave_skip_witness_present(content, wave)`` lifted into the domain policy), NOT a
test-local reimplementation of the FORM rule -- a test-local heuristic would be a
self-fulfilling fixture (passes with the production predicate deleted, zero
validation power).

HONEST SCOPE (the fourth honest limit, AT-A8): the guarantee is BEHAVIORAL, NOT
CRYPTOGRAPHIC. The predicate verifies FORM only; it cannot prove a human authored
the rationale of plain markdown. This test asserts the FORM contract (heading +
non-empty rationale -> True; missing/empty rationale -> False); it deliberately does
NOT assert a forgery-detection claim, because the guard cannot make one. The
witness's human-authorship is verified by downstream human CODE REVIEW.

DISTILL WITNESS-PROBE NOTE (carried to DELIVER + REVIEW): the skip-witness rationale
must READ as human-authored; an LLM can author form-valid markdown, so the form check
is necessary-not-sufficient. The sufficiency leg is the human reviewer reading the
rationale in code review -- NOT a mechanical guard assertion. Do not add an AT that
claims the guard detects forgery; that AT would be non-representable (and false).

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD ``src/des/domain/wave_dispatch_guard_
policy.py`` does not exist (and only the DESIGN-only ``_design_skip_witness_present``
on verify_readiness_pre_dispatch exists). The "wave-parametric predicate is shipped
+ is FORM-correct" assertion RED-fails with a semantic AssertionError on the absent
module/symbol. GREEN once DELIVER ships the policy with the generalized predicate.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable


def _shipped_wave_skip_witness_predicate() -> Callable[..., bool] | None:
    """The SHIPPED wave-parametric skip-witness predicate, if DELIVER has shipped it.

    Looks for ``_wave_skip_witness_present`` on
    ``des.domain.wave_dispatch_guard_policy`` (the DDD-9 re-home generalization
    home). Returns the callable, or None at HEAD where the policy module does not
    exist yet (only the DESIGN-only ``_design_skip_witness_present`` on the
    readiness gate exists).
    """
    try:
        module = importlib.import_module("des.domain.wave_dispatch_guard_policy")
    except ModuleNotFoundError:
        return None
    return getattr(module, "_wave_skip_witness_present", None)


def _witness(wave: str, rationale_body: str) -> str:
    body = f"\n{rationale_body}\n" if rationale_body else "\n"
    return (
        f"# Feature Delta: probe\n\n"
        f"## Wave: {wave} / [REF] Wave Skipped\n{body}\n## Wave: NEXT\n"
    )


def test_wave_skip_witness_predicate_is_shipped() -> None:
    """AT-A8 leg 1: the wave-parametric skip-witness predicate is SHIPPED (DDD-9)."""
    predicate = _shipped_wave_skip_witness_predicate()
    assert predicate is not None, (
        "DELIVER must ship a wave-parametric `_wave_skip_witness_present(content, "
        "wave)` in src/des/domain/wave_dispatch_guard_policy.py, generalizing the "
        "DESIGN-only `_design_skip_witness_present` so the guard can read a "
        "`## Wave: <WAVE> / [REF] Wave Skipped` witness for ANY wave (DDD-9); at "
        "HEAD the policy module does not exist. GREEN once DELIVER ships it."
    )


def test_form_valid_witness_with_non_empty_rationale_is_accepted() -> None:
    """AT-A8 leg 2: a canonical heading + non-empty rationale -> form-valid (True)."""
    predicate = _shipped_wave_skip_witness_predicate()
    assert predicate is not None, (
        "wave-parametric predicate absent at HEAD -- see "
        "test_wave_skip_witness_predicate_is_shipped. GREEN once DELIVER ships it."
    )
    content = _witness("DESIGN", "Config-only change; reuse-first invariant holds.")
    assert predicate(content, "DESIGN") is True, (
        "a `## Wave: DESIGN / [REF] Wave Skipped` heading followed by a non-empty "
        "rationale body must be FORM-VALID (the off-spine dispatch is conceded by "
        "the recorded witness)."
    )


def test_empty_rationale_witness_is_rejected() -> None:
    """AT-A8 leg 3: a canonical heading with an EMPTY rationale body -> rejected.

    This is the FORM check: a bare heading with no rationale is NOT a valid witness
    -- the off-spine dispatch stays BLOCKED. (It is NOT a forgery claim: the guard
    cannot tell who wrote a non-empty rationale, only that one is present.)
    """
    predicate = _shipped_wave_skip_witness_predicate()
    assert predicate is not None, (
        "wave-parametric predicate absent at HEAD. GREEN once DELIVER ships it."
    )
    content = _witness("DESIGN", "")
    assert predicate(content, "DESIGN") is False, (
        "a `## Wave: DESIGN / [REF] Wave Skipped` heading with an EMPTY rationale "
        "body must be FORM-INVALID so an empty witness cannot concede an off-spine "
        "dispatch (DDD-9 / the fourth honest limit -- FORM check, not forgery "
        "detection)."
    )
