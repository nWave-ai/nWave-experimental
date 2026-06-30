@feature-f-design-wave-migration @slice-02
Feature: DISTILL advises splitting an over-large feature, on a distinct threshold (row 7c)
  As an operator whose feature carries more acceptance tests than fit one iteration
  I want nw-distill to advise me of the too-big-for-one-iteration risk and propose
    /nw-discuss for an elephant-carpaccio split, keyed on a distinct config threshold
  So that a right-sized feature gets no false advisory, and the advisory threshold
    never collapses onto the per-slice carpaccio ceiling

  # slice-02 of f-design-wave-migration. ATs AT-3 / AT-4 / AT-6.
  #
  # TEST-FORMAT CONVERSION: Gherkin form of the passing plain-pytest
  # test_slice02_total_at_advisory.py (6 tests -> 5 scenarios; AT-3's two prose
  # checks folded into one scenario, all coverage retained). PRODUCTION already
  # ships GREEN (row 7c + the DESConfig @property), so these are GREEN-not-active-RED
  # — the expected state for a format conversion of passing behaviour. Each scenario
  # stays GENUINE (mutation-verifiable): perturbing row 7c's prose reds AT-3/4;
  # removing/renaming the @property or collapsing it onto carpaccio_slice_max reds
  # AT-6.
  #
  # TWO DRIVING SURFACES (honest shapes, mirroring the original split):
  #   * AT-3/4 — filesystem read of the REAL shipped nw-distill skill (Mandate-13
  #     prose-surface case), windowed around the /nw-discuss anchor.
  #   * AT-6 — the REAL DESConfig port (a production config port; the one permitted
  #     des.adapters.* import, exactly as the original AT-6 drove it) against a temp
  #     config dir, reading rigor_feature_total_at_advisory_threshold.

  @slice-02 @driving_port @real-io @us-total-at @contract-shape:unbounded-preservation
  Scenario: Total-AT advisory exists and is keyed on the total acceptance-test volume
    When the shipped nw-distill skill is read
    Then nw-distill carries a total-AT advisory that proposes the DISCUSS wave
    And the advisory is keyed on the total acceptance-test volume crossing the threshold

  @slice-02 @driving_port @real-io @us-total-at @contract-shape:unbounded-preservation
  Scenario: The total-AT advisory stays silent at or under the threshold
    When the shipped nw-distill skill is read
    Then the total-AT advisory stays silent when the count is at or under the threshold

  @slice-02 @driving_port @real-io @us-threshold-config @contract-shape:bounded-change
  Scenario: The advisory threshold reads the rigor cascade from project config
    Given a project config sets the advisory threshold to 99 in its rigor block
    When the advisory threshold is read from the config port
    Then the advisory threshold reads the value 99 from the rigor cascade

  @slice-02 @driving_port @real-io @us-threshold-config @contract-shape:bounded-change
  Scenario: The advisory threshold defaults to a positive ceiling when no rigor config is present
    Given no rigor config is present in the project or global config
    When the advisory threshold is read from the config port
    Then the advisory threshold defaults to a positive integer ceiling

  @slice-02 @driving_port @real-io @us-distinct-locus @contract-shape:bounded-change
  Scenario: The advisory threshold is a distinct knob from the per-slice carpaccio ceiling
    Given a project config sets the advisory threshold to 99 and a decoy carpaccio ceiling of 5
    When the advisory threshold is read from the config port
    Then the advisory threshold reads 99 from its own rigor key and the config port exposes no carpaccio ceiling
