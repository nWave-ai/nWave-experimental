@feature-fix-design-component-manifest
Feature: The design wave produces the component manifest as a named deliverable

  A manifest that can be validated but is never produced is a contract with no
  author. This slice makes the design wave the producer: the design task lists
  the manifest among its deliverables, the architect's quality gates require it,
  and the architecture-patterns guidance the architect reads at design time
  describes it. The feature also produces a manifest for itself -- the producer
  procedure is run once, in anger, before it is mandated for everyone else.

  Read in sequence after slice-03: slices 01-03 made the manifest validatable
  and classifiable; this slice makes it actually produced.

  # Layer 3 (FS acceptance) -- example-based, no PBT universe (framework-asset
  # edit slice). AT3 closes residuality V2: the feature dogfoods its own
  # contract -- its own manifest exists and passes the validation tool.

  @slice-04 @contract-shape:unbounded-preservation
  Scenario: The design wave names the manifest as a required deliverable
    Given the design wave's framework assets
    Then the design task lists the component manifest as an expected output
    And the architect's quality gates require a validated component manifest

  @slice-04 @contract-shape:unbounded-preservation
  Scenario: The architecture guidance the architect reads describes the manifest
    Given the design wave's framework assets
    Then the architecture patterns guidance documents the component manifest

  @slice-04 @driving_port @contract-shape:pure-function
  Scenario: This feature ships and validates its own component manifest
    Given this feature's own component manifest
    When the architect validates the component manifest
    Then the component manifest is accepted
