@feature-d4-phase-3-flavor-dispatcher
Feature: Workflow flavor dispatcher composes gates per lifecycle event

  As D4 Phase 3 author of the flavor dispatcher
  I want `dispatch_lifecycle_event()` to read a flavor's gate composition
  and invoke each gate in order, honoring per-gate on_failure policies
  So that future workflow changes are YAML edits, not Python edits
  (INV-12 future workflow change = reconfiguration)

  Background:
    Given the flavor dispatcher composition is available

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:pure-function
  Scenario: Dispatcher composes a single-gate event end-to-end
    Given a flavor named "demo_single" with one gate "health-check" on event "session.init" with on_failure "log"
    And the gate invoker records "health-check" as a successful invocation
    When the dispatcher fires the lifecycle event "session.init" for flavor "demo_single"
    Then the composition completes with one gate result
    And the recorded gate is "health-check"
    And the composition did not halt

  @driving_port @real-io @slice-01 @error @contract-shape:pure-function
  Scenario: Dispatcher halts on first failure when on_failure is block
    Given a flavor named "demo_block" with three gates on event "dispatch.pre":
      | gate_id              | on_failure |
      | health-check         | block      |
      | carpaccio-slice-gate | block      |
      | verify-slice-commit  | block      |
    And the gate invoker records "health-check" as a successful invocation
    And the gate invoker records "carpaccio-slice-gate" as a failing invocation
    And the gate invoker records "verify-slice-commit" as a successful invocation
    When the dispatcher fires the lifecycle event "dispatch.pre" for flavor "demo_block"
    Then the composition halted at the blocking gate "carpaccio-slice-gate"
    And the composition recorded two gate results

  @driving_port @real-io @slice-01 @contract-shape:pure-function
  Scenario: Dispatcher continues past failure when on_failure is warn
    Given a flavor named "demo_warn" with three gates on event "subagent.stop":
      | gate_id              | on_failure |
      | health-check         | warn       |
      | carpaccio-slice-gate | warn       |
      | verify-slice-commit  | warn       |
    And the gate invoker records "health-check" as a successful invocation
    And the gate invoker records "carpaccio-slice-gate" as a failing invocation
    And the gate invoker records "verify-slice-commit" as a successful invocation
    When the dispatcher fires the lifecycle event "subagent.stop" for flavor "demo_warn"
    Then the composition completed with three gate results
    And the gate "carpaccio-slice-gate" carries a warning annotation
    And the composition did not halt
