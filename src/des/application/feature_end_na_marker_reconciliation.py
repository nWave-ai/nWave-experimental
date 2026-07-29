"""Single shared source of truth for feature-end NA-marker reconciliation.

fix-na-marker-reconcile-drift slice-01. RCA: the reconciliation rule that
lets a `*NotApplicable*` marker stand in for its `*Verified*` / `*Ran*`
sibling at feature-end lived in TWO independently hand-maintained places --
`subagent_stop_handler._missing_feature_end_cycle_records` (inline,
one entry: `FullSuiteLegNotApplicable -> FullSuiteLegRan`) and
`verify_deliver_integrity._verify_atdd_pure` (a local dict literal, three
entries: the two coverage-map pairs PLUS the full-suite-leg pair). The two
coverage-map reconciliations never reached the hook, so a repo with inactive
`coverage_map_adoption` -- the correct, intentional per-project state --
mints only the NA markers, never the Verified records, and the SubagentStop
hook permanently refused F_FINAL_REVIEW for every atdd_pure feature even
though the CLI mirror already passed the identical ledger.

This module removes the second literal. Both consumers call
`feature_end_na_marker_reconciles()`; the drift class ("one surface grows,
the sibling literal is never even wired") becomes structurally impossible
because there is only one place left to grow.

Mirrors the sibling `feature_end_required_records` field precedent
(`subagent_stop_handler._feature_end_required_records`): the live SSOT is
the `subagent.stop` composition's `feature_end_na_marker_reconciles` field
in `nWave/flavors/atdd_pure.yaml` (present-in-YAML wins); the
`_DEFAULT_NA_MARKER_RECONCILES` dict below is the absent-field fallback,
preserving today's reconciliation set (extended to a fourth entry --
`WalkingSkeletonNotApplicable -> WalkingSkeletonTierVerified` --
fix-ws-done-gate-na-reconciliation slice-01). The `NWAVE_FLAVORS_DIR`
env-var seam (`wave_gate_stack_dispatch.shipped_flavors_dir`) lets tests
(and alternate installs) redirect the lookup -- the SAME seam
`_feature_end_required_records()` already uses for its sibling field.
"""

from __future__ import annotations

from des._internal import subset_parser
from des.application.wave_gate_stack_dispatch import shipped_flavors_dir


_ATDD_PURE_FLAVOR_ID = "atdd_pure"
_SUBAGENT_STOP_EVENT_ID = "subagent.stop"
_NA_MARKER_RECONCILES_FIELD = "feature_end_na_marker_reconciles"

# Absent-field fallback -- preserves today's three-entry reconciliation set
# (the two coverage-map touchpoints + the full-suite leg heartbeat).
_DEFAULT_NA_MARKER_RECONCILES: dict[str, str] = {
    "CoverageMapNotApplicableAtDistillExit": "CoverageMapVerifiedAtDistillExit",
    "CoverageMapNotApplicableAtDeliverExit": "CoverageMapVerifiedAtDeliverExit",
    "FullSuiteLegNotApplicable": "FullSuiteLegRan",
    "WalkingSkeletonNotApplicable": "WalkingSkeletonTierVerified",
}


def feature_end_na_marker_reconciles() -> dict[str, str]:
    """The NA-marker -> required-record reconciliation map, from the ONE shared source.

    Reads the `subagent.stop` composition's `feature_end_na_marker_reconciles`
    field from the flavor YAML `shipped_flavors_dir()` resolves (shipped
    default, or the `NWAVE_FLAVORS_DIR` override). Returns the field's mapping
    when the flavor declares it; falls back to `_DEFAULT_NA_MARKER_RECONCILES`
    when the field is absent -- a flavor without the field preserves today's
    three-entry behaviour instead of reconciling nothing.

    Every consumer (the SubagentStop hook's `_missing_feature_end_cycle_records`
    and the `verify_deliver_integrity` CLI mirror) calls this function directly
    -- neither hardcodes its own copy of the mapping.
    """
    flavors_dir = shipped_flavors_dir()
    flavor_doc = subset_parser.load_file(flavors_dir / f"{_ATDD_PURE_FLAVOR_ID}.yaml")
    lifecycle_events = flavor_doc.get("lifecycle_events", {})
    if not isinstance(lifecycle_events, dict):
        return dict(_DEFAULT_NA_MARKER_RECONCILES)
    composition = lifecycle_events.get(_SUBAGENT_STOP_EVENT_ID, [])
    if not isinstance(composition, list):
        return dict(_DEFAULT_NA_MARKER_RECONCILES)
    for gate_spec in composition:
        if not isinstance(gate_spec, dict):
            continue
        reconciles = gate_spec.get(_NA_MARKER_RECONCILES_FIELD)
        if isinstance(reconciles, dict):
            return {str(marker): str(target) for marker, target in reconciles.items()}
    return dict(_DEFAULT_NA_MARKER_RECONCILES)
