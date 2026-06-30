@feature-sustainable-test-suite
Feature: A maintainer sees the balanced denominator

  slice-04 of sustainable-test-suite — the BALANCED DENOMINATOR (DDD-4 + DDD-5 +
  DDD-10). The gate now reports the A+C metrics EVIDENCE cells — A (consolidation-
  delta, net test-LOC per slice) + C (generic-framework-adoption-ratio) — AND a
  blind-add cross-check computed against the REAL git diff, so the "less" gradient
  has the same mechanical force as the completeness "more" gate. slice-03 made the
  section's rows mechanically checkable git-free; slice-04 adds the measured
  denominator + the git-dependent cross-check it explicitly DEFERRED here.

  Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
  `des validate-feature-delta --require-sustainability --with-metrics --format=json`
  run as a real subprocess on a hermetic tmp_path feature-delta. The subprocess is
  the SUT — no production module is imported at the step boundary. The blind-add
  cross-check scenarios initialise a REAL git repo on tmp_path (@real-io git diff);
  the degrade-LOUD scenario arranges a NON-git tmp_path so the cross-check cannot run.

  SCOPE: A+C metrics evidence + the blind-add cross-check verdict (the verdict
  slice-03 deferred). The cross-check is unbounded-preservation behind a driven port
  (DDD-10) and degrades LOUD to INDETERMINATE when git is absent (DDD-4) — NEVER a
  fabricated pass; git is NOT a hard dependency. DDD-5: the gate is advisory-LOUD and
  checks the TREND (slice-on-slice non-regression), never an absolute threshold.
  Error/edge coverage is PRIMARY (3/5 error+degrade). The consolidating happy path
  carries the @property numeric invariant (consolidation-delta net test-LOC ≤ 0) as a
  Then, so the "less" gradient has the same quantified force as the "more" gate.

  Active-RED: at HEAD `des validate-feature-delta` has no `--with-metrics` mode and
  (after slice-03) emits no `metrics`/`blind_add` payload, so each scenario's
  metric/verdict accessor fires a clean AssertionError (MISSING_FUNCTIONALITY — the A+C
  calculator + git-diff cross-check + `--with-metrics` mode are not yet implemented),
  not an ImportError. DELIVER makes them GREEN by adding `sustainability_metrics.py` +
  the git-diff cross-check adapter + the `--with-metrics` mode.

  @slice-04 @property @driving_port @real-io @contract-shape:bounded-change
  Scenario: A consolidating section reports the A+C metrics as evidence cells
    Given a maintainer declares consolidation work for a feature with a real net test-LOC reduction
    When the sustainability metrics check runs
    Then the check reports the consolidation-delta net test-LOC evidence
    And the check reports the generic-framework-adoption-ratio evidence
    And the reported consolidation-delta net test-LOC is not positive
    And the check accepts the metrics section

  @slice-04 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A consolidate claim contradicted by the git diff is unmasked as a blind add
    Given a maintainer claims consolidation but the git diff shows a net test-LOC increase
    When the sustainability metrics check runs
    Then the blind-add cross-check reports "blind-add"
    And the check reports the verdict "blind-add-detected"
    And the check rejects the metrics section

  @slice-04 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The git-diff cross-check degrades LOUD to indeterminate when git is absent
    Given a maintainer declares consolidation work where the git-diff cross-check cannot run
    When the sustainability metrics check runs
    Then the blind-add cross-check reports "indeterminate"
    And the check rejects the metrics section

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A non-regressing slice is accepted on trend, with no absolute cliff
    Given a maintainer declares a slice whose net test-LOC trend does not regress
    When the sustainability metrics check runs
    Then the check reports the consolidation-delta net test-LOC evidence
    And the check accepts the metrics section

  @slice-04 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Metrics requested on a section that cannot supply evidence is rejected
    Given a maintainer requests metrics on a sustainability section that supplies no evidence cells
    When the sustainability metrics check runs
    Then the check rejects the metrics section
    And the check reports the verdict "malformed-sustainability-section"
