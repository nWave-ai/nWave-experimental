@feature-fix-readiness-gate-reuse-first-invariant
Feature: The readiness gate clears a feature that ran DESIGN or acknowledged skipping it

  As a maintainer who deliberately ran DESIGN, or deliberately acknowledged
  skipping it
  I want the DELIVER-entry readiness gate to clear my first crafter dispatch on
  the reuse-first dimension when I carry either a valid Reuse Analysis or an
  explicit DESIGN-skip witness
  So that the reuse-first guarantee survives a DESIGN-skip without blocking
  legitimate dispatches, and an unreadable feature delta degrades loud rather
  than slipping through

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying a valid reuse analysis clears the reuse-first dimension
    Given a feature workspace cleared on every other invariant carrying a valid Reuse Analysis
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying a methodology-exempt reuse marker clears the reuse-first dimension
    Given a feature workspace cleared on every other invariant carrying a methodology-exempt Reuse Analysis marker
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying a no-overlap-declared reuse marker clears the reuse-first dimension
    Given a feature workspace cleared on every other invariant carrying a no-overlap-declared Reuse Analysis marker
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying a design-skip witness with a rationale clears the reuse-first dimension
    Given a feature workspace with no Reuse Analysis acknowledging the skip with a Design Skipped witness with a rationale
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying a malformed reuse analysis alongside a valid design-skip witness clears the reuse-first dimension
    Given a feature workspace carrying a malformed Reuse Analysis ALONGSIDE a Design Skipped witness with a rationale
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A workspace carrying an unjustified create-new reuse analysis alongside a valid design-skip witness clears the reuse-first dimension
    Given a feature workspace carrying an unjustified create-new Reuse Analysis ALONGSIDE a Design Skipped witness with a rationale
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate clears the reuse-first dimension

  @driving_port @real-io @slice-02 @error @contract-shape:unbounded-preservation
  Scenario: An unreadable feature delta degrades loud and refuses with a naming diagnostic
    Given a feature workspace whose feature delta cannot be read as text
    When the maintainer runs the readiness gate against the unreadable workspace
    Then the readiness gate refuses the unreadable workspace
    And the diagnostic names the unreadable feature delta
