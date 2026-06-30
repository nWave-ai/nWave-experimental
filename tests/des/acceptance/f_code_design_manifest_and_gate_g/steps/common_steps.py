"""Shared step SSOT for the f-code-design-manifest-and-gate-g suite (S1 compliance).

Step phrases that recur across more than one slice ``.feature`` (the gate-G
driving-port ``When`` + the verdict ``Then``s) are declared ONCE here, with one
body each, and re-used across slices via ``from .common_steps import *`` in each
slice step module. This is the S1 tolerable variant "single SSOT module" -- one
function object, one pytest-bdd registration, NO shadow possible.

Mandate-12: each body is ≤2 statements ending in a composition call; no control
flow. Mandate-13: every body delegates to ``ManifestGateComposition`` driving the
REAL ``evaluate_gate_g`` seam; no production import at the step boundary.

The composition is resolved from the ``manifest_gate`` fixture each slice module
provides (every slice fixture returns a fresh ``ManifestGateComposition``). The
shared step names reference ``manifest_gate`` so the fixture name is part of the
contract across slices.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, then, when

from .composition import ManifestGateComposition
from .domain_types import CoherenceCase, GateVerdict


@pytest.fixture
def manifest_gate() -> ManifestGateComposition:
    """A fresh composition root per scenario (the shared driving-port surface)."""
    return ManifestGateComposition()


# --- shared Given (the bijective manifest -- recurs in slices 01/03/04) ----


@given(
    "a code-design manifest whose example-table rows and the tagged acceptance "
    "scenarios cover each other exactly"
)
def given_bijective_manifest(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_coherence_case(CoherenceCase.BIJECTIVE)


# --- shared When (the gate-G driving port -- recurs in slices 01/02/03) ----


@when("the coherence gate reads the manifest and diffs it against the acceptance tests")
def when_gate_reads_manifest(
    manifest_gate: ManifestGateComposition, tmp_path: Path
) -> None:
    manifest_gate.when_gate_g_reads_contract_or_manifest(tmp_path)


# --- shared Then (the §17 verdicts -- recur across slices) -----------------


@then("the coherence gate returns a passing verdict")
def then_passing_verdict(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_verdict_is(GateVerdict.PASS)


@then("the coherence gate returns a failing verdict")
def then_failing_verdict(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_verdict_is(GateVerdict.FAIL)


@then("the coherence gate returns an unverified verdict")
def then_unverified_verdict(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_verdict_is(GateVerdict.UNVERIFIED)


@then("the coherence gate returns an indeterminate verdict")
def then_indeterminate_verdict(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_verdict_is(GateVerdict.INDETERMINATE)


@then("the coherence gate returns a not-applicable verdict")
def then_not_applicable_verdict(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_verdict_is(GateVerdict.NOT_APPLICABLE)


@then("the coherence gate does not surface the North-Star cap")
def then_no_cap(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_cap_not_surfaced()
