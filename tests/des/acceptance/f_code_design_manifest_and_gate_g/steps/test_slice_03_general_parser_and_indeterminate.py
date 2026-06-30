"""pytest-bdd binding for slice-03 (general @row parser + manifest INDETERMINATE).

Driving surface (Mandate-13 Layer 3 composition): the REAL ``evaluate_gate_g``
manifest-source branch over a real ``tmp_path`` manifest + AT module. Step bodies
delegate to ``ManifestGateComposition`` (Mandate-12: each body <=2 statements
ending in a composition call; no control flow).

Shared step phrases (the gate-G driving-port ``When``, the UNVERIFIED and
INDETERMINATE verdict ``Then``s) are imported VERBATIM from ``common_steps`` -- one
registration each (S1 single-SSOT module). This module adds ONLY the slice-03-unique
steps: the untagged-scenario / unsupported-language Givens + the untagged-naming and
mechanism-did-not-run Thens, each delegating to a composition method already present
in the slice-01 substrate (``given_coherence_case`` / ``given_contract_input`` /
``then_diagnostic_names`` / ``then_gate_g_did_not_run`` + the
``untagged_scenario_fragment`` the substrate exposes). No substrate is re-authored.

active-RED scaffold (atdd_pure per-slice JIT -- NOT @skip): RED at HEAD for the
RIGHT reason. Two genuine gaps the audit pinned, verified live:

  * UNTAGGED (CT-10b): the manifest branch reads ``@row:`` tags via ``_at_row_tags``
    (gate_g.py:184) -- an UNTAGGED scenario is INVISIBLE to it, so 3 tagged rows ==
    3 manifest rows -> the gate returns PASS, silently ignoring the untagged
    scenario (probed live: PASS). slice-03's general parser must SEE every scenario
    and cap at UNVERIFIED naming the untagged one (no silent pass). The
    ``then_unverified_verdict`` / untagged-naming Then fires a NAMED semantic
    ``AssertionError`` (got PASS, no diagnostic) -- never a collection error.
  * UNSUPPORTED-LANGUAGE (CT-6): the manifest branch (gate_g.py:135-136) SKIPS
    ``_at_module_is_inspectable`` (:215) -- a ``.exs`` AT under a manifest does NOT
    degrade to INDETERMINATE. Today the manifest YAML is read, the ``.exs`` carries
    no ``@row:`` tag, rows != tags -> a verdict the mechanism could not legitimately
    compute. slice-03 must run the language probe on the manifest path and degrade
    LOUD. ``then_indeterminate_verdict`` / ``then_gate_g_did_not_run`` fires the
    named RED. GREEN once DELIVER runs the inspectability probe on the manifest path
    and the general @row parser sees every scenario.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then

# Shared SSOT steps (the gate-G When + the UNVERIFIED / INDETERMINATE verdict
# Thens) -- one registration each; re-used, never re-declared (S1).
from .common_steps import *
from .composition import ManifestGateComposition
from .domain_types import CoherenceCase, ContractInput


scenarios("../slice-03-general-row-parser-and-manifest-indeterminate.feature")


# --- slice-03-unique Given (untagged scenario + unsupported language) -------


@given(
    "a code-design manifest whose acceptance tests include a generally-worded "
    "scenario with no row tag"
)
def given_untagged_scenario(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_coherence_case(CoherenceCase.UNTAGGED_SCENARIO)


@given(
    "a code-design manifest whose acceptance module is in a language the inspection "
    "substrate cannot parse"
)
def given_unsupported_language(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_contract_input(ContractInput.UNSUPPORTED_LANGUAGE)


@given(
    "a prose design contract whose rows are covered one-to-one by generally-worded "
    "acceptance scenarios"
)
def given_prose_general_wording(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.given_contract_input(ContractInput.PROSE_GENERAL_WORDING_BIJECTIVE)


# --- slice-03-unique Then (untagged naming + mechanism-did-not-run) ---------


@then("the coherence gate diagnostic names the untagged scenario")
def then_names_untagged(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_diagnostic_names(
        ManifestGateComposition.untagged_scenario_fragment()
    )


@then("the coherence gate reports that the mechanism did not run")
def then_mechanism_did_not_run(manifest_gate: ManifestGateComposition) -> None:
    manifest_gate.then_gate_g_did_not_run()
