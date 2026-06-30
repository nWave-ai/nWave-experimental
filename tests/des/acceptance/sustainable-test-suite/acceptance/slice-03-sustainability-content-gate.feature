@feature-sustainable-test-suite
Feature: A maintainer cannot claim sustainability work without having done it

  slice-03 of sustainable-test-suite — the MECHANICAL CONTENT VALIDATION gate
  (DDD-2). The spine validates the feature-delta `## Test Reuse & Consolidation
  Analysis` section CONTENT (structure + decision tokens + justification +
  DDD-9 exemptions) git-free, mirroring the shipped Reuse Analysis validator.
  slice-02 REGISTERED the section as a declared DISTILL output; slice-03 makes
  the section's ROWS mechanically checkable so a maintainer cannot attest the
  sustainability work without actually filling the section correctly.

  Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
  `des validate-feature-delta --require-sustainability --format=json` run as a
  real subprocess on a hermetic tmp_path feature-delta. The subprocess is the
  SUT — no production module is imported at the step boundary.

  SCOPE (HARD): slice-03 is SECTION-CONTENT validation only — git-free,
  Python + filesystem. The `blind-add-detected` verdict requires the git-diff
  cross-check (declared CONSOLIDATE/REUSE vs the real added test-LOC) + the A+C
  metrics calculator; that cross-check is a SEPARATE driven port that
  degrades-LOUD INDETERMINATE when git is absent, and belongs to slice-04/05
  (DESIGN line 511, component-manifest git-diff cross-check port). It is
  correctly ABSENT here. Error-path coverage is PRIMARY for this gate slice
  (3/5 = 60%).

  Active-RED: at HEAD `des validate-feature-delta` has no `--require-sustainability`
  mode (`_parse_args` rejects the unknown flag), so the subprocess exits non-zero
  with no JSON verdict on stdout. Every scenario asserts a post-implementation
  verdict token, so each fails with a clean AssertionError (MISSING_FUNCTIONALITY
  — the mode is not implemented), not an ImportError. DELIVER makes them GREEN by
  adding `validate_sustainability_content` + the `--require-sustainability` mode.

  @slice-03 @walking_skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: A well-formed sustainability section is structurally accepted
    Given a maintainer authors a feature-delta whose sustainability section is well formed
    When the sustainability content check runs
    Then the check accepts the sustainability section
    And the check reports the verdict "structurally-accepted"

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A feature-delta with no sustainability section is rejected
    Given a maintainer authors a feature-delta that omits the sustainability section
    When the sustainability content check runs
    Then the check rejects the sustainability section
    And the check reports the verdict "missing-sustainability-section"

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A sustainability section with the wrong table shape is rejected
    Given a maintainer authors a feature-delta whose sustainability section has the wrong columns
    When the sustainability content check runs
    Then the check rejects the sustainability section
    And the check reports the verdict "malformed-sustainability-section"

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: An unjustified CREATE_NEW claim is rejected
    Given a maintainer authors a feature-delta with a CREATE_NEW row whose justification is empty
    When the sustainability content check runs
    Then the check rejects the sustainability section
    And the check reports the verdict "unjustified-create-new"

  @slice-03 @driving_port @real-io @contract-shape:pure-function
  Scenario: A methodology-exempt feature is accepted without a populated section
    Given a maintainer authors a feature-delta carrying the methodology-exempt marker
    When the sustainability content check runs
    Then the check accepts the sustainability section
    And the check reports the verdict "methodology-exempt"
