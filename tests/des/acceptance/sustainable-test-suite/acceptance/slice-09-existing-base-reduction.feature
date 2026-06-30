@feature-sustainable-test-suite
Feature: The existing test base improves gradually, not just stays-lean-on-add

  slice-09 of sustainable-test-suite — EXISTING-BASE CONTINUOUS REDUCTION (DDD-16C +
  DDD-17C), the ACTIVE counter-gradient and the LAST slice of the feature. The shipped
  A+C metrics (slice-04) + the consolidate-on-add gain (slice-07) measure reuse at the
  ADD boundary — they are PASSIVE w.r.t. the thousands of pre-existing near-duplicate
  steps. slice-09 closes that: each `/nw-distill` run measurably REDUCES the EXISTING
  base's duplication. The gate REPORTS the existing-base near-duplicate-step ratio (AST
  step-similarity behind the CodeFactPort, git-free) as an EVIDENCE cell, and the trend
  must NOT regress slice-on-slice — advisory-LOUD first, gated on a downward trend
  (DDD-16C non-regression-plus-opportunistic) — so the +94%/feature curve is bent on the
  base that ALREADY exists, not only on new additions.

  Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
  `des validate-feature-delta --require-sustainability --with-metrics --existing-base-trend
  [--prior-existing-base-ratio=<float>] [--corpus-root=<dir>] --format=json` run as a real
  subprocess on a hermetic tmp_path feature-delta + a real AST step-shape corpus. The
  subprocess is the SUT — no production module is imported at the step boundary. The
  trend-bearing scenarios write a real tree of step-definition files (@real-io — the AST
  step-shape corpus the CodeFactPort parses); the degrade-LOUD scenario arranges a corpus
  the AST tier cannot read so the CodeFactPort returns no step-shape fact.

  DISCRIMINATOR (mirrors the slice-07 mode-flag FIX): `--existing-base-trend` is an explicit
  MODE flag DISTINCT from the `--prior-existing-base-ratio` VALUE and from
  `--consolidate-on-add`. The existing-base leg fires ONLY when the mode flag is present, so
  a plain `--with-metrics` run (slice-04 accept-on-trend) and a `--consolidate-on-add` run
  (slice-07) are never routed through the existing-base trend path — no byte-identical CLI
  collision. The prior committed ratio is read GIT-FREE from the prior feature-delta section
  (DDD-17C), supplied as the `--prior-existing-base-ratio` VALUE exactly as slice-07 supplies
  the add-only baseline.

  SCOPE: the existing-base ratio EVIDENCE cell (a real number from
  `existing_base_duplication_ratio` over an AST step-shape corpus) + the closed trend
  cross-check verdict, so an improving run is observably BELOW the prior committed ratio and
  a regressing run is gated. The AST step-shape extraction is unbounded-preservation behind
  the CodeFactPort (DDD-17C) and degrades LOUD to INDETERMINATE when the AST tier is absent —
  NEVER a fabricated `0.0` ratio, NEVER a fabricated downward trend. Error/edge coverage is
  PRIMARY (3/5 error+degrade). The improving happy path carries the @property numeric
  invariants (ratio is a real fraction in [0.0, 1.0]; ratio strictly below the prior
  committed value) as Thens, so the "less" gradient has the same quantified force as the
  completeness "more" gate. DDD-16C: advisory-LOUD on trend non-regression, never an
  absolute cliff.

  Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04 cells
  + the slice-07 consolidate-on-add leg, but accepts NO `--existing-base-trend` flag, NO
  `--prior-existing-base-ratio` argument, and NO `--corpus-root` argument, and emits NO
  `existing_base_duplication_ratio` cell nor an `existing_base_trend` cross-check object
  (`sustainability_metrics.py` has no `existing_base_duplication_ratio` symbol; `code_fact_port.py`
  has no step-shape capability). The `--existing-base-trend` flag does not exist at HEAD, so
  argparse rejects it and the subprocess emits no JSON verdict — each scenario's existing-base
  accessor fires a clean AssertionError (MISSING_FUNCTIONALITY — the pure ratio calc + the
  CodeFactPort step-shape leg + the `--existing-base-trend` mode are not yet implemented), NOT
  an ImportError. DELIVER makes them GREEN by adding the pure `existing_base_duplication_ratio`
  calc to `sustainability_metrics.py` + the CodeFactPort step-shape extraction leg + the
  `--existing-base-trend` mode flag + the `--prior-existing-base-ratio` / `--corpus-root`
  values — it does NOT unskip anything.

  @slice-09 @property @driving_port @real-io @adapter-integration @contract-shape:unbounded-preservation
  Scenario: A run that folds a near-duplicate cluster reports a lower existing-base ratio and is accepted
    Given a maintainer folds an existing near-duplicate step cluster, netting the existing-base ratio below the prior
    When the existing-base trend check runs
    Then the check reports the existing-base near-duplicate-step ratio evidence
    And the reported existing-base ratio is a real fraction
    And the reported existing-base ratio is below the prior committed ratio
    And the existing-base trend cross-check reports "improved"
    And the check accepts the existing-base section

  @slice-09 @driving_port @real-io @adapter-integration @error @contract-shape:unbounded-preservation
  Scenario: A run whose existing-base ratio rises above the prior is gated as a regression
    Given a maintainer's run makes the existing-base near-duplicate-step ratio rise above the prior
    When the existing-base trend check runs
    Then the existing-base trend cross-check reports "regressed"
    And the check reports the verdict "existing-base-duplication-regressed"
    And the check rejects the existing-base section

  @slice-09 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The existing-base ratio degrades LOUD to indeterminate when the AST corpus is unavailable
    Given a maintainer declares existing-base work where the AST step-shape corpus cannot be read
    When the existing-base trend check runs
    Then the existing-base trend cross-check reports "indeterminate"
    And the check rejects the existing-base section

  @slice-09 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The existing-base trend degrades LOUD to indeterminate with no prior committed ratio
    Given a maintainer requests the existing-base trend check but supplies no prior committed ratio
    When the existing-base trend check runs
    Then the existing-base trend cross-check reports "indeterminate"
    And the check rejects the existing-base section
