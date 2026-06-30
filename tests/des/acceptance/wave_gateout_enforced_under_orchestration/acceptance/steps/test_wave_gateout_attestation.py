"""pytest-bdd binding for wave-gateout slice-05 (un-gameable attestation property).

Drives the REAL ``handle_subagent_stop`` hook entry (Layer 3 composition) through the
production composition root with a WAVE-ONLY orchestration return, plus the REAL
``des record-<wave>-review`` producer CLIs (Layer 3 subprocess). Step bodies delegate
to ``WaveAttestationComposition`` -- no business logic in steps (Mandate-12). The
driving primitives are REUSED from the slice-01/02..04 surfaces (Mandate-12 reuse).

GREEN-on-keystone: slice-05 is a regression-lock proving the un-gameable attestation
property (absent -> block cross-wave; stale -> block; current -> allow) holds over the
EXISTING ReviewVerdictGate mechanism. It PASSES on the committed code (NOT active-RED,
NOT @skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_wave_attestation import WaveAttestationComposition
from .domain_types import ReviewState, Wave


_ACCEPTANCE_DIR = Path(__file__).resolve().parents[1]

scenarios(str(_ACCEPTANCE_DIR / "wave-gateout-attestation.feature"))


@pytest.fixture
def attestation(tmp_path: Path) -> WaveAttestationComposition:
    """A fresh attestation composition rooted at a tmp work-tree per scenario."""
    return WaveAttestationComposition(repo_dir=tmp_path)


# ---- Given: the orchestration return precondition (per wave) ----------------


@given(
    parsers.parse(
        "a {wave} wave-agent is returning a deliverable under autonomous orchestration"
    )
)
def _given_wave_returning(attestation: WaveAttestationComposition, wave: str) -> None:
    attestation.given_wave(Wave(wave))
    attestation.given_agent_returning_under_orchestration()


# ---- Given: the recorded-review precondition ---------------------------------


@given("no review has been recorded for that deliverable")
def _given_no_review(attestation: WaveAttestationComposition) -> None:
    attestation.given_review_recorded(ReviewState.NONE)


@given("the reviewer recorded an approval then the deliverable was changed")
def _given_stale_review(attestation: WaveAttestationComposition) -> None:
    attestation.given_review_recorded(ReviewState.STALE)


@given("the reviewer recorded a current approval for that deliverable")
def _given_current_review(attestation: WaveAttestationComposition) -> None:
    attestation.given_review_recorded(ReviewState.APPROVED)


# ---- When --------------------------------------------------------------------


@when("the orchestration return is evaluated at the wave boundary")
def _when_return_evaluated(attestation: WaveAttestationComposition) -> None:
    attestation.when_orchestration_return_evaluated()


# ---- Then --------------------------------------------------------------------


@then("the wave closure is refused with a missing-review reason")
def _then_refused_absent(attestation: WaveAttestationComposition) -> None:
    attestation.then_wave_closure_refused_absent()


@then("the wave closure is refused with a stale-seal reason")
def _then_refused_stale(attestation: WaveAttestationComposition) -> None:
    attestation.then_wave_closure_refused_stale()


@then("the wave closure is allowed")
def _then_allowed(attestation: WaveAttestationComposition) -> None:
    attestation.then_wave_closure_allowed()
