@feature-test-runner-port
Feature: The test-runner port reports real observations honestly

  A real run reports its runner-owned counts. An unavailable runner reports an
  explicit unobserved outcome; it never fabricates a passing test result.

  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A test target that all passes is reported as a faithful green run
    Given a test target whose tests all pass
    When the test-runner port runs the target
    Then the emitted run result conforms to the test-result contract
    And the emitted run result reports at least one passing test
    And the emitted run result reports no failing tests
    And the emitted run result reports a zero exit code

  @driving_port @real-io @slice-02 @error @contract-shape:unbounded-preservation
  Scenario: A test target with a failing test is reported with a faithful failure count
    Given a test target with at least one failing test
    When the test-runner port runs the target
    Then the emitted run result conforms to the test-result contract
    And the emitted run result reports at least one failing test
    And the emitted run result reports a nonzero exit code

  @driving_port @real-io @slice-02 @error @contract-shape:bounded-change
  Scenario: An absent runner yields an explicit unobserved result
    Given a test target whose runner cannot be invoked
    When the test-runner port runs the target
    Then the emitted result is explicitly unobserved
    And the unobserved reason is "runner-absent"
    And no passing run result is fabricated
