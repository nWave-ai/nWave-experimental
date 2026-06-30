"""Step definitions: the inline-restatement clause scopes to enumeration (slice-04).

algebra-projections-enforced slice-04 — ADR-003 (REROUTE_DESIGN #2, DD-A6),
feature-delta Point 5 REVISED. Witnesses the NARROWED `_inline_restatement`
(`src/des/cli/verify_wave_contract_coherence.py:155-171`): a structured gate-stack
ENUMERATION FAILs; a `des <gate-id>` command INVOCATION + the `roadmap.json` artifact
NOUN PASS; the migrated DISCUSS prose stays byte-stable PASS.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the narrowing's input space is a FINITE, enumerable closed set of three prose shapes
(an enumeration / an invocation+noun / the pristine real discuss locus); a small set
of explicit examples is the correct paradigm at this layer, and the sad path (the
enumeration FAIL) is enumerated explicitly (Mandate 11).

The gate is a pure reader (it reads prose + the registry and returns a verdict; it
mutates NO file). The PRISTINE_DISCUSS guard asserts via ``assert_state_delta`` over a
port-exposed filesystem universe that the REAL discuss locus is NOT mutated
(Mandate 8).

Step bodies delegate to ``InlineRestatementNarrowingComposition``; no inline business
logic (Mandate-12 criterion 3) — each body is a typed lookup plus a composition call.

active-RED / preservation classification (atdd_pure — NOT @skip), per the HEAD probe:
  * W1 (enumeration FAILs) — PRESERVATION-GUARD (GREEN at HEAD + post-narrowing);
  * W2 (invocation + roadmap.json PASS) — ACTIVE-RED MISSING_FUNCTIONALITY (HEAD
    ``fail`` on the bare gate_id token -> A_GREEN narrows -> ``pass``);
  * W3 (DISCUSS byte-stable) — PRESERVATION-GUARD (GREEN at HEAD + post-narrowing).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition_slice_04_narrowing import InlineRestatementNarrowingComposition
from .domain_types_slice_04_narrowing import (
    INLINE_PROSE_BY_PHRASE,
    NARROWING_VERDICT_BY_PHRASE,
)


scenarios("../slice-04-inline-restatement-narrows-to-enumeration.feature")


@pytest.fixture
def narrowing_composition() -> InlineRestatementNarrowingComposition:
    """Production-wired composition root driving the real coherence gate."""
    return InlineRestatementNarrowingComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a coherence target whose body is {prose_phrase}"))
def given_prose_shape(
    narrowing_composition: InlineRestatementNarrowingComposition,
    prose_phrase: str,
) -> None:
    narrowing_composition.given_prose_shape(INLINE_PROSE_BY_PHRASE[prose_phrase])


# --- When --------------------------------------------------------------------


@when("the inline-restatement check runs for that prose")
def when_gate_runs(
    narrowing_composition: InlineRestatementNarrowingComposition, tmp_path: Path
) -> None:
    narrowing_composition.when_the_coherence_gate_runs(tmp_path)


# --- Then --------------------------------------------------------------------


@then("the prose is rejected as a gate-stack restatement")
def then_rejected_as_enumeration(
    narrowing_composition: InlineRestatementNarrowingComposition,
) -> None:
    expected = NARROWING_VERDICT_BY_PHRASE["is rejected as a gate-stack restatement"]
    observed = narrowing_composition.observed_gate_verdict()
    assert observed == expected.value, (
        f"a restated gate-stack enumeration must still FAIL the narrowed clause "
        f"(ADR-003 D1/D3 — re-enumeration is vetoed in every wave); expected "
        f"{expected.value!r}, got {observed!r} (diagnostic: "
        f"{narrowing_composition.gate_diagnostic()!r})."
    )


@then("the prose clears the coherence check")
def then_clears(
    narrowing_composition: InlineRestatementNarrowingComposition,
) -> None:
    expected = NARROWING_VERDICT_BY_PHRASE["clears the coherence check"]
    observed = narrowing_composition.observed_gate_verdict()
    assert observed == expected.value, (
        f"the narrowed clause must PASS a `des <gate-id>` command invocation + the "
        f"`roadmap.json` artifact noun (ADR-003 D1 — mention is not enumeration); "
        f"expected {expected.value!r}, got {observed!r} (diagnostic: "
        f"{narrowing_composition.gate_diagnostic()!r}). At HEAD the lexical scan flags "
        f"the bare gate_id token -> 'fail' (active-RED for the invocation+noun shape; "
        f"already 'pass' for the pristine discuss shape)."
    )


@then("the discuss prose locus on disk is left unchanged")
def then_discuss_locus_unchanged(
    narrowing_composition: InlineRestatementNarrowingComposition,
) -> None:
    before = narrowing_composition.capture_universe()
    after = narrowing_composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"discuss_locus.exists", "discuss_locus.bytes"},
        expected={
            "discuss_locus.exists": unchanged(),
            "discuss_locus.bytes": unchanged(),
        },
    )
    assert narrowing_composition.real_discuss_locus_unchanged(), (
        "the coherence gate is a pure reader — the real discuss prose locus on disk "
        "must be byte-identical before and after the check."
    )
