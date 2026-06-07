@feature-walking-skeleton-production-like-gate
Feature: Every hook-invoked command survives the build into the shipped artifact
  As an nWave framework developer changing what gets distributed
  I want a repo-side check that every command a hook depends on still ships and
    is exercised by a wiring test
  So that a command falling off the shipped set is a red build, not a slow
    dogfood

  # carpaccio slice-10 (DESIGN slice-05, part 1 of 2). US-04 / RCA G2: the
  # distribution-completeness arch test core assertions. Repo-side,
  # deterministic, network-free -- the most resilient component (residuality
  # matrix). Layer 4 (integration): the DistributionCompleteness enumeration is
  # pure and statically derived; the unbounded hook-invoked-command set makes
  # it a property domain. @property scenarios are example-pinned at this
  # layer-4 arch test; DELIVER authors the PBT generator at the layer-1
  # pure-function unit test (Mandate 9). Traditional assertions permitted at
  # layer 4 (Mandate 8).
  #
  # Driving port: the `pytest` distribution-completeness arch test.

  @slice-10 @property @contract-shape:bounded-change
  Scenario: A hook-invoked command absent from the shipped set fails the build
    Given any hook that subprocess-invokes a command module
    And that command is absent from the installer distribution whitelist
    When the distribution-completeness check evaluates the hook-invoked command set
    Then the check fails naming the command and the absent-from-shipped-set reason

  @slice-10 @property @contract-shape:bounded-change
  Scenario: A shipped hook-invoked command with no wiring test fails the build
    Given any hook-invoked command that resides on a path surviving the installer whitelist
    And no subprocess-real wiring test exercises that command
    When the distribution-completeness check evaluates the hook-invoked command set
    Then the check fails naming the command and the missing-wiring-test reason

  @slice-10 @contract-shape:bounded-change
  Scenario: Every hook-invoked command shipped and wiring-tested passes the check
    Given every hook-invoked command resides on a path surviving the installer whitelist
    And each hook-invoked command is exercised by at least one subprocess-real wiring test
    When the distribution-completeness check evaluates the hook-invoked command set
    Then the distribution-completeness check passes
