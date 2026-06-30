@feature-sustainable-test-suite
Feature: Adding a slice also consolidates the test base (add-AND-improve)

  slice-07 of sustainable-test-suite — CONSOLIDATE-ON-ADD, the test-suite REFACTOR
  phase (DDD-4 + DDD-5 + DDD-6). When a maintainer adds a slice the methodology does
  not only ADD: repeated steps are folded into the shared vocabulary and existing
  tests are deduped, so the net test-LOC of the run leans NEGATIVE relative to the
  add-only baseline. The shipped slice-04 `--with-metrics` mode reports ONE feature's
  net delta against its OWN git diff — it is PASSIVE: it cannot distinguish a run that
  added-AND-improved from one that merely added the same scope. slice-07 closes that:
  the gate measures the consolidate-on-add GAIN — the consolidating run's net test-LOC
  RELATIVE to the declared add-only baseline — so the counter-gradient that bends the
  +94%/feature curve (slice-06 H) carries the same mechanical force as the completeness
  "more" gate.

  Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
  `des validate-feature-delta --require-sustainability --with-metrics
  --consolidate-on-add --add-only-baseline-loc=<N> --format=json` run as a real
  subprocess on a hermetic tmp_path feature-delta with a REAL git repo (@real-io — the
  git diff supplies the run's net test-LOC). The subprocess is the SUT — no production
  module is imported at the step boundary. The slice-07 calc EXTENDS the SHIPPED
  `sustainability_metrics.py` (its A+C metrics are reused as the denominator) with a pure
  consolidate-on-add gain function; no new engine.

  DISCRIMINATOR (the design-defect FIX): `--consolidate-on-add` is an explicit MODE flag,
  DISTINCT from the `--add-only-baseline-loc` VALUE — the coa-leg fires ONLY when the mode
  flag is present. This is what keeps slice-07 consistent with the SHIPPED slice-04
  accept-on-trend AT: a plain `--with-metrics` run with no baseline (slice-04) is ACCEPTED
  on trend; a `--consolidate-on-add` run with no baseline (sc3 below) is rejected
  INDETERMINATE. The two are NOT byte-identical CLI invocations — the gate routes on the
  presence of the coa MODE flag, so a non-regressing plain trend-check and a
  coa-intent-declared-without-denominator are mechanically distinguishable and never demand
  opposite exit codes for identical input. Every slice-07 scenario declares
  `--consolidate-on-add`; slice-04 never does.

  SCOPE — what slice-07 mechanically AT-tests: the gate REPORTS the consolidate-on-add
  gain evidence cell + a closed cross-check verdict, so a real add-AND-improve run is
  observably BELOW the add-only baseline and an add-only run claiming consolidate-on-add
  is unmasked. The agent BEHAVIOR (the ATD actually CHOOSING to consolidate-on-add) is
  irreducibly eval-validated and is slice-08's job — NOT authored here. Error/edge
  coverage is PRIMARY (3/5 error+degrade). The realized happy path carries the @property
  numeric invariant (consolidate-on-add gain ≤ 0) as a Then, so the "less" gradient has
  the same quantified force as the "more" gate. DDD-5: advisory-LOUD on trend
  non-regression, never an absolute cliff.

  Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04
  cells (consolidation_delta_loc, adoption_ratio) + the blind_add cross-check, but accepts
  NO `--consolidate-on-add` flag and NO `--add-only-baseline-loc` argument, and emits NO
  `consolidate_on_add` leg (`sustainability_metrics.py` has only `adoption_ratio` +
  `classify_blind_add` — Tsunami atoms-in-file confirms 7 members, no consolidate-on-add
  symbol). The `--consolidate-on-add` flag does not exist at HEAD, so each scenario's
  consolidate-on-add accessor fires a clean AssertionError (MISSING_FUNCTIONALITY — the
  add-AND-improve calc + the `--consolidate-on-add` mode + the `--add-only-baseline-loc`
  value are not yet implemented) — NOT the slice-04 collision, NOT an ImportError. DELIVER
  makes them GREEN by adding the pure `consolidate_on_add_gain` function to
  `sustainability_metrics.py` + the `--consolidate-on-add` mode flag + the
  `--add-only-baseline-loc` value — it does NOT unskip anything.

  @slice-07 @property @driving_port @real-io @contract-shape:bounded-change
  Scenario: An add-AND-improve slice nets below the add-only baseline and is accepted
    Given a maintainer adds a slice and also consolidates, netting below the add-only baseline
    When the consolidate-on-add check runs
    Then the check reports the consolidate-on-add gain evidence
    And the reported consolidate-on-add gain is not positive
    And the consolidate-on-add cross-check reports "realized"
    And the check accepts the consolidate-on-add section

  @slice-07 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A run that only added while claiming add-AND-improve is unmasked
    Given a maintainer claims add-AND-improve but the run only added the same scope
    When the consolidate-on-add check runs
    Then the consolidate-on-add cross-check reports "not-realized"
    And the check reports the verdict "consolidate-on-add-not-realized"
    And the check rejects the consolidate-on-add section

  @slice-07 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Consolidate-on-add degrades LOUD to indeterminate with no add-only baseline
    Given a maintainer requests the add-AND-improve check but supplies no add-only baseline
    When the consolidate-on-add check runs
    Then the consolidate-on-add cross-check reports "indeterminate"
    And the check rejects the consolidate-on-add section

  @slice-07 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Consolidate-on-add on a section that cannot supply evidence is rejected
    Given a maintainer requests consolidate-on-add on a section that supplies no evidence cells
    When the consolidate-on-add check runs
    Then the check rejects the consolidate-on-add section
    And the check reports the verdict "malformed-sustainability-section"
