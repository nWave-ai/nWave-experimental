@feature-codex-standing-loop-runtime
Feature: A maintainer receives one bounded continuation result in Codex

  A maintainer who has one due continued-work unit needs a single opportunity
  at Codex session start. The execution remains bounded and leaves one
  inspectable receipt.

  @slice-01 @US-01 @driving_port @real-io @covers-R1 @covers-R2 @covers-R3 @covers-R4 @contract-shape:bounded-change
  Scenario: A due continued-work unit runs once with its declared outcome
    Given a maintainer has armed one due continued-work unit for "operator-sentinel: reconcile the Atlas release notes before handoff"
    And the maintainer also has a future-due continued-work unit
    When the maintainer starts Codex in that project
    Then the maintainer sees one bounded execution receipt for "operator-sentinel: reconcile the Atlas release notes before handoff"
    And the receipt names the authorised limits
    And the future-due unit remains untouched
    And inspection shows one applied continued-work receipt

  @slice-01 @US-01 @driving_port @real-io @error @negative @covers-R5 @contract-shape:unbounded-preservation
  Scenario Outline: An unsafe bounded-control request is not started
    Given a maintainer requests continued work with <limit_kind>
    When the maintainer asks to arm the bounded work
    Then the maintainer is told what is unsafe, why it was refused, and how to correct it
    And no bounded work was started

    Examples:
      | limit_kind |
      | no limit   |
      | zero limit |
      | negative limit |

  @slice-01 @US-01 @driving_port @real-io @error @negative @covers-R2 @covers-R5 @covers-R6 @contract-shape:bounded-change
  Scenario: A consumed token allowance stops further continued work
    Given a maintainer has armed continued work with a token allowance of 10
    When the maintainer advances that continued work twice
    Then the first advance consumes no more than the authorised token allowance
    And the second advance is refused because the allowance is exhausted
    And inspection reports the terminal state and why continued work stopped
