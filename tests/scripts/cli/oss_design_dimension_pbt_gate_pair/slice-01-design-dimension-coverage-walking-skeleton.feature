@feature-oss-design-dimension-pbt-gate-pair @slice-01
Feature: The design-dimension coverage check witnesses or flags every DESIGN-declared behavior axis

  A solution architect running DESIGN declares, in the feature-delta, one row
  per orthogonal axis of behavior the feature must cover -- a dimensions block
  keyed by an immutable dimension-ID. Before the feature flows downstream into
  DELIVER, the acceptance designer authors properties that each witness a
  declared dimension by carrying its dimension-ID as a comment. The
  design-dimension coverage check joins the two: every declared dimension must
  be witnessed by at least one property, so a DESIGN axis of behavior that no
  downstream property ever exercises is caught at DISTILL-exit instead of
  flowing on silently -- the drift the gate-or-residue policy forbids.

  This is the existence-join half (P1) of the gate: it asserts that, for each
  declared dimension, at least one property in the acceptance-test corpus
  CLAIMS to witness it by carrying its dimension-ID. The behavioral half --
  "is the witnessing property genuinely perturbation-bound, or does it merely
  name-match while asserting a constant?" -- belongs to the P3 perturbation
  witness (DIM-8, slice-04), which reuses the sibling clause-witness mechanism.
  A passing existence-join is the verdict PASS -- explicitly NOT a claim that
  every witnessing property is behaviorally genuine.

  The check is NON-HALTING at the DISTILL-exit hook: an unwitnessed dimension
  is reported loud as INDETERMINATE and the DISTILL-to-DELIVER move proceeds.
  The OSS tier realizes the gate-PAIR semantics non-haltingly (hooks-only,
  loud-warn, never hard-halt) -- an anticorruption layer over the shared
  published language, not a hard-halt engine.

  # Driving port: scripts/cli/check_design_dimension_coverage.py invoked via
  # main(argv) (Mandate-13 driving-port-only -- never a direct-domain import
  # of the parser functions). Layer 3 (in-process / FS acceptance) -- example
  # only, no PBT (Mandate 9/11): the walking-skeleton verdict set
  # (PASS / INDETERMINATE / MALFORMED) is a finite enumerable closed set.
  #
  # dimension: DIM-1
  # dimension: DIM-3
  # dimension: DIM-5

  Background:
    Given a feature whose design wave has declared a dimensions block

  @slice-01 @coupled @walking_skeleton @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature whose every declared dimension is witnessed passes the coverage check
    Given the feature has every declared dimension is witnessed by a property in the corpus
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the feature passes the design-dimension coverage check
    And the coverage check leaves the feature-delta and the corpus unchanged

  @slice-01 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature with a declared dimension no property witnesses is reported as unwitnessed
    Given the feature has one declared dimension has no witnessing property in the corpus
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the feature is reported as having an unwitnessed dimension
    And the coverage check leaves the feature-delta and the corpus unchanged

  @slice-01 @coupled @walking_skeleton @driving_port @contract-shape:unbounded-preservation
  Scenario: A witnessed feature whose dimensions live under the carpaccio heading passes the coverage check
    Given the feature has every declared dimension is witnessed and the dimensions live under the carpaccio heading
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the feature passes the design-dimension coverage check
    And the coverage check leaves the feature-delta and the corpus unchanged

  @slice-01 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A dimensions block declaring no dimensions is reported as malformed
    Given the feature has a dimensions block with the heading but no declared dimensions
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the feature is reported as malformed
    And the coverage check leaves the feature-delta and the corpus unchanged

  @slice-01 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature whose acceptance-test corpus is absent is reported as malformed
    Given the feature has declared dimensions but no acceptance-test corpus on disk
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the feature is reported as malformed

  @slice-01 @coupled @driving_port @contract-shape:unbounded-preservation
  Scenario: Running the coverage check on a witnessed feature does not mutate any observable
    Given the feature has every declared dimension is witnessed by a property in the corpus
    When the acceptance designer runs the design-dimension coverage check on the feature
    Then the coverage check produced a structured verdict
    And the coverage check leaves the feature-delta and the corpus unchanged
