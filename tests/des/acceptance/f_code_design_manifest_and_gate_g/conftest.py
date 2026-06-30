"""pytest-bdd configuration for the f-code-design-manifest-and-gate-g suite.

DISTILL-authored active-RED scaffold (ADR-025 + ADR-028, atdd_pure per-slice JIT):
every scenario across the four slice ``.feature`` files is authored ahead of the
implementation and RUNS -- it is NOT @skip'd (ADR-GV-001 D6). Each scenario fails
RED for the RIGHT reason because the net-new production seams this feature's
DESIGN pins are ABSENT at HEAD:

  * the broad ``code-design.manifest.yaml`` schema
    (``nWave/schemas/code-design-manifest.schema.json``) -- NOT created yet
  * ``evaluate_gate_g``'s manifest-source read branch (the ``example-tables:``
    ``row-id`` ↔ AT ``@row:`` tag bijection) -- gate_g.py reads PROSE only at HEAD
  * the generalized ``@row:<id>`` scenario parser (replacing the hardcoded
    ``_SCENARIO_LINE`` "Operator exports the X case" regex) -- absent at HEAD
  * ``validate_component_manifest``'s WIDENED sut-key iteration over
    ``example-tables[].sut`` / ``signatures[].sut`` -- it scans only
    ``unbounded-input-domains`` at HEAD
  * the ``des gate-design-at-coherence`` subcommand wiring
    (``_REGISTRY`` row + ``nWave/gates/_catalog.yaml`` mirror + the
    ``atdd_pure.yaml`` ``wave_gate_stacks.distill.gate-out`` entry) -- none exist

DRIVING SURFACES (Mandate-13 driving-port-only):
  * slices 01-03 -> Layer 3 composition: the REAL ``evaluate_gate_g`` mechanism +
    the REAL ``validate_component_manifest`` over a real ``tmp_path`` carrying a
    real ``code-design.manifest.yaml`` + a real AT ``.feature`` module. The
    observable is the returned §17 ``GateVerdict`` envelope (verdict + diagnostic +
    cap-surfaced) and the validator exit code.
  * slice-04 -> Layer 3 subprocess (the wired ``des gate-design-at-coherence``
    dispatch) PLUS reads of the shipped wiring artifacts (``_REGISTRY`` /
    ``_catalog.yaml`` / ``atdd_pure.yaml``) -- the wiring is DATA the SUT ships.

The step modules import only test-local types at module top; every production
seam is reached through a LAZY import inside the composition's driving-port
invocation, so an absent seam degrades to a captured "seam absent" sentinel that
the ``Then`` turns into a NAMED semantic ``AssertionError`` (never a collection /
import / setup error). The suite therefore COLLECTS cleanly at HEAD and each
scenario RED-fails for the right reason (the pre-DELIVER fail-for-right-reason
gate).

NO-REGRESSION PRESERVATION SCENARIOS (green at HEAD BY DESIGN, not fixture-theater):
one scenario is intentionally GREEN at HEAD because it asserts behaviour this
feature must PRESERVE, not behaviour it adds:

  * slice-03 ``@row:no-contract-is-not-applicable`` (CT-7 neither-contract): with
    neither a manifest nor a prose ``[REF] Code-Design`` block, gate-G returns
    NOT_APPLICABLE -- this is the EXISTING ``_not_applicable`` behaviour (KPI-4 /
    DDD-3 baseline). "Neither contract present" inherently cannot exercise the
    net-new manifest-source branch, so it can only ever be a preservation guard
    (same class as the arch-test guards AT-A2 / AT-A3). It is included for CT-7
    COVERAGE COMPLETENESS (review HIGH-1) and DELIVER must keep it green.

Every OTHER acceptance scenario is active-RED (fails at HEAD for the missing seam).
The two ex-CRITICAL scenarios were re-shaped (review iter-1) so each fails for the
RIGHT reason and goes green only once DELIVER lands the seam:
  * prose-fallback (CT-7): HEAD FAIL (the @row: parser is absent so _SCENARIO_LINE
    finds 0 subjects -> 3 prose rows vs 0 -> FAIL) -> post-DELIVER UNVERIFIED+cap
    (the generalized @row: reader finds 3 disjoint tags vs 3 prose rows).
  * unsupported-language (CT-6): HEAD NOT_APPLICABLE (the manifest-source branch is
    absent so the manifest YAML is read as design, no prose heading) -> post-DELIVER
    INDETERMINATE (the manifest branch probes the .exs AT, substrate cannot run).
"""

from __future__ import annotations
