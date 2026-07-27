@feature-sessionstart-cross-host-contract
Feature: A maintainer receives one compact SessionStart orientation on every claimed host

  @walking_skeleton @driving_port @real-io @covers-R1 @covers-R2 @covers-R3 @covers-R4 @contract-shape:bounded-change
  Scenario: An installed host opens a session without changing maintainer state
    Given a maintainer has installed nWave for Codex or Claude Code
    When the host opens a session
    Then exactly one aggregate orientation is emitted
    And its aggregate text is at most 2 KiB
    And the maintainer project and nWave state are unchanged

  @driving_port @real-io @covers-R2 @covers-R5 @contract-shape:bounded-change
  Scenario: A host gives a conditional throughput directive for parallel delivery
    Given a maintainer has installed nWave for Codex or Claude Code
    When the host opens a session
    Then multi-slice or multi-feature work is told to load nw-throughput before scheduling
