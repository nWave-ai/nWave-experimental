"""pytest-bdd binding for slice-02 (deterministic FAIL naming the divergence).

Driving surface (Mandate-13 Layer 3 composition): the REAL ``evaluate_gate_g``
manifest-source branch over a real ``tmp_path`` manifest + AT module. Step bodies
delegate to ``ManifestGateComposition`` (Mandate-12: each body <=2 statements
ending in a composition call; no control flow).

Shared step phrases (the gate-G driving-port ``When``, the FAILING-verdict and
no-cap ``Then``s) are imported VERBATIM from ``common_steps`` -- one registration
each (S1 single-SSOT module). This module adds ONLY the slice-02-unique steps: the
DROPPED_ROW / UNDECLARED_SCENARIO Givens + the two divergence-naming Thens, each
delegating to a composition method already present in the slice-01 substrate
(``given_coherence_case`` / ``then_diagnostic_names`` + the ``dropped_row_id`` /
``undeclared_row_id`` fixtures the substrate exposes). No substrate is re-authored.

active-RED scaffold (atdd_pure per-slice JIT -- NOT @skip): RED at HEAD for the
RIGHT reason. Verified: ``_evaluate_manifest_source`` (src/des/cli/gate_g.py:155)
does ``rows == tags -> _manifest_passed() else -> _unverified(...)`` -- there is NO
deterministic FAIL path on a manifest-present divergence. So a manifest with a
dropped / undeclared row returns UNVERIFIED, not the FAIL these scenarios assert ->
``then_verdict_is(FAIL)`` fires a NAMED semantic ``AssertionError`` (the FAIL seam
is absent), never a collection / import / setup error. GREEN once DELIVER routes the
manifest-path divergence through the existing ``_classify`` / ``_failed`` machinery.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then

# Shared SSOT steps (the gate-G When + the FAILING-verdict / no-cap Thens) -- one
# registration each; re-used, never re-declared (S1).
from .common_steps import *
from .composition import ManifestGateComposition
from .domain_types import CoherenceCase


scenarios("../slice-02-deterministic-fail-names-the-divergence.feature")


# --- slice-02-unique Given (the two confirmable-divergence shapes) ----------


@given("a code-design manifest with a row that no tagged acceptance scenario covers")
def given_dropped_row(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_coherence_case(CoherenceCase.DROPPED_ROW)


@given(
    "a code-design manifest against acceptance tests that tag a row the manifest "
    "never declared"
)
def given_undeclared_scenario(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_coherence_case(CoherenceCase.UNDECLARED_SCENARIO)


# --- slice-02-unique Then (the diagnostic NAMES the confirmed divergence) ---


@then("the coherence gate diagnostic names the dropped row")
def then_names_dropped_row(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_diagnostic_names(ManifestGateComposition.dropped_row_id())


@then("the coherence gate diagnostic names the undeclared row")
def then_names_undeclared_row(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_diagnostic_names(ManifestGateComposition.undeclared_row_id())
