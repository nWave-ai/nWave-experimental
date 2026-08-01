@feature-codex-host-parity
Feature: One installed nWave candidate gives a Codex user a working specialist, a reacting safeguard and a continued-work loop

  The thin installed vertical. One published candidate is built by the real
  producer, installed into a clean place that borrows nothing, and every
  capability the user then exercises is quoted back by that same candidate on
  that same machine. Nothing here borrows another candidate's or another
  machine's work, and an existing Claude user keeps the behaviour they had
  before.

  Only the walking skeleton below proves WIRING. Every scenario carrying the
  contract-only tag drives the journey in memory against test doubles: those
  scenarios pin the contract, and they are deliberately NOT evidence that
  anything is wired. A capability counts as wired when the walking skeleton
  observes its effect on the clean machine, never because a receipt said so.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change @covers-R-S01-01 @covers-R-S01-08 @covers-R-S01-09 @covers-R-S01-10
  Scenario: A Codex user installs one published candidate and completes the whole journey with it
    Given the team has published one nWave candidate for Codex users
    When a Codex user installs that published candidate on a clean machine and works through the whole journey
    Then the specialist's answer quotes the expertise and the project rule that were really installed
    And the specialist did the one thing its installed role declares it must do
    And the action that needed approval leaves its mark only when the approval was granted
    And the safeguard reacts to the native event and leaves exactly one mark
    And the loop's work is still there after its process ended, and a tick after the stop is turned away
    And the Claude user's own files are byte-for-byte what they were before the install
    And every capability the user exercised carries the same candidate and the same machine
    And the journey the user ran came from the installed candidate and borrowed nothing from the source tree
    And the candidate the user installed carries none of the material nWave keeps private

  @slice-01 @driving_port @in-memory @contract-only @contract-shape:bounded-change @covers-R-S01-02
  Scenario: The installed specialist follows its instructions and reads both its expertise and the project rule
    Given a Codex user has installed that same published candidate
    When the user asks the installed specialist to do its work
    Then the specialist follows the instructions it was installed with
    And the specialist reads the expertise that was installed alongside it
    And the specialist reads the rule the project keeps for everyone who works in it

  @slice-01 @driving_port @in-memory @contract-only @error @negative @contract-shape:bounded-change @covers-R-S01-03
  Scenario: The specialist refuses work when the approval its role requires cannot be honoured, instead of quietly working without it
    Given the installed specialist has been asked to do its work
    And the specialist's role requires approval before it acts
    When this machine cannot honour that approval requirement
    Then the user is told what could not be approved, why it matters and how to remedy it
    And no work is credited as having run under that approval requirement

  @slice-01 @driving_port @in-memory @contract-only @contract-shape:bounded-change @covers-R-S01-04
  Scenario: The workflow safeguard visibly stops a forbidden action and records it exactly once
    Given the specialist's approval requirement has been honoured
    When the user attempts an action the workflow safeguard forbids
    Then the user sees the action stopped rather than completed
    And the safeguard's effect on this user's machine happened exactly once

  @slice-01 @driving_port @in-memory @contract-only @contract-shape:bounded-change @covers-R-S01-05
  Scenario: The operator arms one continued-work loop, ticks it once, sees it attested and stops it
    Given the workflow safeguard has reacted for this user
    When the operator arms one continued-work loop, ticks it once, stops it and then tries to tick it again
    Then the operator sees a durable attestation for the tick that ran
    And the tick attempted after the stop is refused

  @slice-01 @driving_port @in-memory @contract-only @property @negative @error @contract-shape:unbounded-preservation @covers-R-S01-06 @covers-R-S01-08
  Scenario: A capability is never reported proved on work done for a different candidate or a different machine
    Given the operator's continued work has been attested on the installed candidate
    When a capability offers work that was done for a different candidate or on a different machine
    Then the user is told that capability was not proved here
    And the whole journey is refused rather than completed on borrowed work

  @slice-01 @driving_port @in-memory @contract-only @negative @contract-shape:unbounded-preservation @covers-R-S01-07
  Scenario: Installing the candidate never changes what an existing Claude user already had
    Given an existing Claude user already has their own safeguards and specialists on this machine
    When that same published candidate is installed for Codex on the same machine
    Then the Claude user's safeguards and specialists are the same after the install as before it
    And only the material nWave owns has changed
