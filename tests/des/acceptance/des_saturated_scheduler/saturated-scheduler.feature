@feature-des-saturated-scheduler
Feature: An orchestrator sees every runnable lane and protects scarce local capacity

  An nWave orchestrator asks DES what can run now. DES reads the declared work
  plan and the completion evidence that exists, returns a deterministic lane
  snapshot, and leaves every dispatch to the orchestrator's own agent tooling
  under the existing hooks.

  # The only authority over a lane's state is the artifacts that exist or are
  # missing. Focused scenarios drive the real dispatcher in-process; the single
  # feature walking skeleton assembles the release-shaped candidate once,
  # installs that exact candidate into a clean environment, and asks it from a
  # disposable project with no source tree and no PYTHONPATH to borrow from.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change @covers-R1 @covers-R2 @covers-R3 @covers-R8 @covers-R9
  Scenario: The installed scheduler answers what can run now from a clean environment
    Given the release-shaped candidate is installed once in a clean environment
    And a disposable project declares independent work and one local operation
    When the project asks the installed scheduler what can run now
    Then the installed help offers the scheduling query
    And two installed reads return the same lane snapshot under one policy identity
    And the installed snapshot marks every unblocked cloud lane ready and orders one box lane
    And the installed scheduler records no execution and leaves the disposable project unchanged

  @slice-01 @driving_port @real-io @contract-shape:bounded-change @covers-R1 @covers-R2 @covers-R3 @covers-R8 @covers-R9
  Scenario: The orchestrator receives a deterministic artifact-level lane snapshot
    Given a feature plan declaring independent work and one local operation
    And no lane has produced any completion evidence yet
    When the orchestrator asks DES what can run now twice
    Then both snapshots carry the same lanes in the same order under one policy identity
    And every dependency edge names the consumed artifact and the condition it awaits
    And exactly one box lane is admitted and every remaining box operation is queued with its reason
    And every blocked lane names its missing artifact, its awaited condition, and its next action
    And the snapshot needs no host scheduler on Linux macOS or Windows
    And the snapshot records no execution and leaves the plan and the evidence unchanged

  @slice-01 @driving_port @real-io @contract-shape:bounded-change @covers-R1 @covers-R2 @covers-R3
  Scenario: A lane whose consumed artifact exists is ready before its producing slice finishes
    Given a feature plan declaring independent work and one local operation
    And the acceptance-test artifact is attested while its producing slice is unfinished
    When the orchestrator asks DES what can run now
    Then the lane consuming the attested artifact is ready
    And the lane awaiting the still-missing artifact is blocked by that artifact by name
    And no lane is held back merely because a producing slice is unfinished

  @slice-01 @driving_port @real-io @error @negative @contract-shape:bounded-change @covers-R1 @covers-R2 @covers-R9
  Scenario: Unreadable evidence is named as incapacity and never becomes readiness
    Given a feature plan declaring independent work and one local operation
    And the completion evidence is present but unreadable
    When the orchestrator asks DES what can run now
    Then DES refuses with an evidence-indeterminate verdict naming the unreadable input
    And the refusal states what failed, why it matters, and which existing tool repairs it
    And no lane is reported ready and nothing is executed
