"""pytest-bdd binding for slice-01 (walking skeleton) -- manifest validated + gate PASS.

Driving surface (Mandate-13 Layer 3 composition): the REAL ``evaluate_gate_g``
manifest-source branch + the REAL ``validate_component_manifest`` over a real
``tmp_path`` manifest + AT module. Step bodies delegate to ``ManifestGateComposition``
(Mandate-12: each body ≤2 statements ending in a composition call).

Shared step phrases (the bijective Given, the gate-G When, the PASS/no-cap Thens)
are imported from ``common_steps`` -- a single SSOT module, ONE registration per
phrase (S1 tolerable variant; no cross-file literal collision). This module adds
ONLY the slice-01-unique steps (the manifest-validation Given/When/Then + the
empty-bijective Given).

active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER lands the
manifest-source read + the WIDENED validator. Semantic AssertionError, never a
collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, scenarios, then, when

# Shared SSOT steps (bijective Given, gate-G When, PASS / no-cap Thens) -- one
# registration each; re-used, never re-declared (S1).
from .common_steps import *
from .composition import ManifestGateComposition
from .domain_types import CoherenceCase, ManifestHealth


scenarios("../slice-01-walking-skeleton-manifest-validated-and-gate-passes.feature")


# --- slice-01-unique Given --------------------------------------------------


@given(
    "a code-design manifest that is schema-valid and whose every declared symbol is "
    "findable in its cited file"
)
def given_grounded_manifest(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_manifest_health(ManifestHealth.SCHEMA_VALID_GROUNDED)


@given(
    "a code-design manifest declaring zero example-table rows matched by acceptance "
    "tests declaring none"
)
def given_empty_bijective_manifest(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_coherence_case(CoherenceCase.EMPTY_BIJECTIVE)


# --- slice-01-unique When + Then (manifest validation) ----------------------


@when("the manifest is validated at design-out")
def when_manifest_validated(
    manifest_gate: ManifestGateComposition, tmp_path: Path
) -> None:
    manifest_gate.when_manifest_is_validated(tmp_path)


@then("the manifest is accepted")
def then_manifest_accepted(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_validator_accepts()
