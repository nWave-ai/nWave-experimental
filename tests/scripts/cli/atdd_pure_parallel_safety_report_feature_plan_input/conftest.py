"""pytest-bdd configuration for the slice-02 acceptance set (parallel-by-
default-feature-plan).

ATDD-pure per-slice JIT: `--epic-delta` is a genuinely new flag on `des
parallel-safety-report` -- every scenario below is active-RED on the current
tip (argparse rejects the unrecognized/missing flag before any measurement,
mirroring the sibling `atdd_pure_validate_feature_delta_feature_dependency_
justification` suite's own active-RED convention). No `@xfail`/`@skip` tags --
every scenario runs; each fails with a real `AssertionError` comparing the
observed argparse-usage-error outcome to the DESIGN'd `--epic-delta` contract,
never a collection/import error.
"""

from __future__ import annotations
