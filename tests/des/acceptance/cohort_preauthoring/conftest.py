"""pytest-bdd configuration for the fix-cohort-gate-preauthoring slice-01 suite.

DISTILL-authored active-RED scaffold (ADR-025, atdd_pure per-slice JIT): every
scenario in this slice-01 ``.feature`` file is authored ahead of the
implementation and RUNS (it is NOT @skip'd -- ADR-GV-001 D6). The net-new
production seam the slice extends is the candidate-AT count for the
``feature_delta`` kind in ``scripts/cli/cohort_classifier`` -- a count of the
``## Wave: DISTILL / [REF] Test Placement`` numbered list plus a larger-of-the-two
return alongside the existing authored-scenario count.

DRIVING SURFACE (Mandate-16 driving-port-only, Layer 3 composition): the REAL
``cohort_classifier._count_ats(delta_path, "feature_delta")`` count function (the
[REF] Driving Ports seam; its single production caller is the CLI ``main``) is
driven over a crafted hermetic feature-delta staged under the pytest ``tmp_path``.
No real repository feature-delta is read, and no personal-hook home-directory path
is touched.

active-RED expectations (verified empirically at HEAD):
  * AC-1 placement-only (4 candidate, 0 scenarios)  -> reports 0, expected 4 (RED)
  * AC-2 authored preserved (0 candidate, 3 scenarios) -> reports 3 (live-green)
  * AC-3 both (4 candidate, 2 scenarios)            -> reports 2, expected 4 (RED)
  * AC-4 neither (no section, 0 scenarios)          -> reports 0 (live-green)

The composition reaches the production count function through a lazy import inside
the driving-port invocation, so the suite COLLECTS cleanly at HEAD and each RED
scenario fails for the right reason (the pre-DELIVER fail-for-right-reason gate):
a NAMED semantic ``AssertionError`` on the reported count, never an import /
collection / setup error.
"""

from __future__ import annotations
