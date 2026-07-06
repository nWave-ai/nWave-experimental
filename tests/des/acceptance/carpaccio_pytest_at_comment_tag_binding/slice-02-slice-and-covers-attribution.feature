@feature-carpaccio-pytest-at-comment-tag-binding
Feature: A pytest AT file's head-comment names its slice and spec rows

  slice-01 generalized ``@feature-{id}`` head-tag discovery from ``.feature``
  files to any test file. A discovered pytest AT file's head-comment can
  ALSO carry ``@slice-NN`` / ``@covers-Rn`` sub-tags -- the same per-file
  resolution a Gherkin scenario's ``@slice-NN`` tag already gives
  (``slice_at_completeness.feature_files_for_slice``). Without this, a
  maintainer cannot tell which slice or spec rows a bound pytest file
  satisfies without opening it.

  # docs/feature/carpaccio-pytest-at-comment-tag-binding/feature-delta.md
  # [REF] Slice Plan slice-02 + EXP-carpaccio-pytest-at-comment-tag-binding-2.
  #
  # Driving surface (Layer 3 composition, Mandate 13): a NEW companion
  # resolver, `resolve_test_file_attribution` (same module,
  # src/des/application/feature_at_files.py), parses the SAME bounded
  # head-window `feature_tagged_test_files` (slice-01) already scans --
  # ADD-not-mutate: `feature_tagged_test_files` and its slice-01 behavior are
  # unchanged; this is a companion, per-file sub-tag resolution.
  #
  # @real-io (Architecture of Reference): real pytest test files written to
  # a real filesystem under pytest tmp_path -- no fake. Example-only, no PBT
  # machinery (Mandate 9/11): three closed cases (attribution resolved;
  # cross-slice guardrail; no-attribution guardrail), not a property.
  #
  # This feature's OWN ATs stay Gherkin (not pytest) so they clear the
  # EXISTING Gherkin-only carpaccio gate -- the chicken-and-egg this feature
  # exists to fix.

  @slice-02 @covers-R2 @real-io @contract-shape:bounded-change
  Scenario: A head-tagged pytest test file resolves to its slice and covered spec rows
    Given a scratch repository containing a pytest test file head-tagged "@feature-test-binding-2 @slice-02 @covers-R7"
    When the maintainer resolves the test file's slice and spec-row attribution
    Then the resolved attribution names slice "slice-02"
    And the resolved attribution covers spec row "R7"

  @slice-02 @covers-R2 @real-io @contract-shape:bounded-change
  Scenario: A cross-slice head-tagged file is not misattributed to another slice
    Given a scratch repository containing a pytest test file head-tagged "@feature-test-binding-2 @slice-01"
    When the maintainer resolves the test file's slice and spec-row attribution
    Then the resolved attribution names slice "slice-01"
    And the resolved attribution does not name slice "slice-02"

  @slice-02 @covers-R2 @real-io @contract-shape:bounded-change
  Scenario: A head-tagged file with no slice tag reports no attribution instead of raising
    Given a scratch repository containing a pytest test file head-tagged "@feature-test-binding-2"
    When the maintainer resolves the test file's slice and spec-row attribution
    Then the resolved attribution reports no slice attribution
    And the resolved attribution reports no covered spec rows
