"""Step definitions: the coherence-hook fires on DISTILL + DELIVER prose (slice-04).

algebra-projections-enforced slice-04 (DISCUSS slice-04, DESIGN Point 5 +
Reuse Analysis row ``_MIGRATED``, ADR-FLOW-006 D4/D7).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the slice-04 input space is a FINITE, enumerable closed set — the two pristine
distill/deliver prose loci plus the single firing-surface hook-coverage example. A
small set of explicit examples is the correct paradigm at this layer; the
falsifier-gate forbids PBT on a closed-world finite domain at layer 3, and the sad
paths are enumerated explicitly (Mandate 11). slice-04 is a PURE coverage
EXTENSION, so it does NOT re-assert the generic gate invariant
"perturbed pointer -> fail" (already green at HEAD); its negative case is "the hook
does NOT yet catch distill/deliver drift", which IS the active-RED hook-coverage
failure.

The gate + hook have a pure-reader contract (they read prose + the registry and
return a verdict; they mutate NO file). A Then asserts via ``assert_state_delta``
over a port-exposed filesystem universe that the real prose locus is NOT mutated
(Mandate 8). The hook-coverage walking skeleton is
``@contract-shape:unbounded-preservation`` — it preserves the existing DISCUSS
coverage while ADDING the distill+deliver coverage.

Step bodies delegate to ``CoherenceHookComposition``; no inline business logic
(Mandate-12 criterion 3) — each body is a typed lookup plus a composition call.

active-RED scaffold (atdd_pure — NOT @skip). At HEAD:
  * ``run_wave_contract_coherence.py:_MIGRATED`` = DISCUSS-only, so the hook never
    exercises the distill/deliver waves -> the hook-coverage Thens RED-fail;
  * the four distill/deliver prose loci carry no ``gates-ref``/``outputs-ref``
    pointer AND restate bare catalog gate_ids inline, so the gate emits ``fail`` on
    a pristine locus -> the pristine ``pass`` Thens RED-fail.
DELIVER A_GREEN turns these GREEN by adding the 4 _MIGRATED rows + the 4 pointer
pairs AND scrubbing the bare catalog gate_id tokens from the distill/deliver prose.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition_slice_04 import CoherenceHookComposition, MigratedWave
from .domain_types_slice_04 import (
    COHERENCE_VERDICT_BY_PHRASE,
    PROSE_ARMING_BY_PHRASE,
    ProseLocus,
)


scenarios("../slice-04-coherence-hook-covers-distill-deliver.feature")


_LOCUS_BY_WAVE = {
    MigratedWave.DISTILL: ProseLocus.DISTILL_SKILL,
    MigratedWave.DELIVER: ProseLocus.DELIVER_SKILL,
}


@pytest.fixture
def coherence_composition() -> CoherenceHookComposition:
    """Production-wired composition root driving the real gate + firing-surface hook."""
    return CoherenceHookComposition()


# --- Given -------------------------------------------------------------------


@given("the maintainer runs the wave-contract coherence hook")
def given_hook_armed(coherence_composition: CoherenceHookComposition) -> None:
    # No state to arm — the hook reads its own _MIGRATED tuple. The When runs it.
    pass


@given(parsers.parse("a coherence target: {arming_phrase}"))
def given_prose(
    coherence_composition: CoherenceHookComposition,
    arming_phrase: str,
) -> None:
    wave, mutation = PROSE_ARMING_BY_PHRASE[arming_phrase]
    coherence_composition.given_prose_locus(_LOCUS_BY_WAVE[wave])
    coherence_composition.given_prose_mutation(mutation)


# --- When --------------------------------------------------------------------


@when("the hook completes")
def when_hook_runs(coherence_composition: CoherenceHookComposition) -> None:
    coherence_composition.when_the_coherence_hook_runs()


@when("the coherence check runs for that prose")
def when_gate_runs(
    coherence_composition: CoherenceHookComposition, tmp_path: Path
) -> None:
    coherence_composition.when_the_coherence_gate_runs(tmp_path)


# --- Then --------------------------------------------------------------------


@then("the hook has exercised the distill wave")
def then_hook_covers_distill(coherence_composition: CoherenceHookComposition) -> None:
    assert coherence_composition.hook_covered_wave(MigratedWave.DISTILL), (
        "the coherence-hook _MIGRATED tuple must cover the distill wave so the gate "
        "fires on distill prose at commit time (slice-04). At HEAD _MIGRATED is "
        "discuss-only -> distill is uncovered (active-RED)."
    )


@then("the hook has exercised the deliver wave")
def then_hook_covers_deliver(coherence_composition: CoherenceHookComposition) -> None:
    assert coherence_composition.hook_covered_wave(MigratedWave.DELIVER), (
        "the coherence-hook _MIGRATED tuple must cover the deliver wave so the gate "
        "fires on deliver prose at commit time (slice-04). At HEAD _MIGRATED is "
        "discuss-only -> deliver is uncovered (active-RED)."
    )


@then("the hook exits cleanly")
def then_hook_clean(coherence_composition: CoherenceHookComposition) -> None:
    code = coherence_composition.hook_exit_code()
    assert code == 0, (
        f"the coherence-hook must exit 0 once the distill/deliver prose carries valid "
        f"pointers and restates no bare gate_id; got exit {code}. At HEAD the migrated "
        f"loci have no pointer and restate bare gate_ids -> non-zero (active-RED)."
    )


@then("the check clears the coherence check")
def then_gate_pass(coherence_composition: CoherenceHookComposition) -> None:
    expected = COHERENCE_VERDICT_BY_PHRASE["clears the coherence check"]
    observed = coherence_composition.observed_gate_verdict()
    assert observed == expected.value, (
        f"the coherence gate must return {expected.value!r} for the pristine migrated "
        f"prose; got {observed!r} (diagnostic: "
        f"{coherence_composition.gate_diagnostic()!r}). At HEAD the locus has no pointer "
        f"and restates bare gate_ids -> 'fail' (active-RED)."
    )


@then("the prose locus on disk is left unchanged")
def then_locus_unchanged(coherence_composition: CoherenceHookComposition) -> None:
    before = coherence_composition.capture_universe()
    after = coherence_composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"prose_locus.exists", "prose_locus.bytes"},
        expected={
            "prose_locus.exists": unchanged(),
            "prose_locus.bytes": unchanged(),
        },
    )
    assert coherence_composition.real_locus_unchanged(), (
        "the coherence gate/hook are pure readers — the real prose locus on disk "
        "must be byte-identical before and after the check."
    )
