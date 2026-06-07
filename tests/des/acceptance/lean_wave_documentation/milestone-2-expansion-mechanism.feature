Feature: Marco can expand rationale on demand without re-running the wave
  As Marco working on a complex feature
  I want to request specific rationale sections at wave end without re-running the wave
  So that I pay tokens only for the context I actually need

  Background:
    Given Marco's nWave home is a fresh temporary directory
    And the global configuration records the default density as "lean"

  @skip @US-1 @driving_port
  Scenario: Lean wave produces only [REF] sections by default
    Given the global configuration records the expansion prompt as "ask"
    And no feature directory exists for "small-feat-x"
    When Marco runs the DISCUSS wave on "small-feat-x" without expansion flags
    Then the feature-delta.md for "small-feat-x" is created
    And every wave heading in the file uses the [REF] schema label
    And no heading in the file uses the [WHY] or [HOW] schema labels
    And the file token count is at most sixty percent of the legacy baseline for the same spec

  @skip @US-1 @driving_port
  Scenario: Lean wave still emits every Tier-1 field downstream waves require
    Given Marco has run a lean DISCUSS wave on "small-feat-x"
    When the DESIGN wave reads "small-feat-x"'s feature-delta.md
    Then the file contains the persona, job-to-be-done, locked decisions, user stories, acceptance scenarios, definition of done, out of scope, walking-skeleton strategy, driving ports, and pre-requisites sections
    And every user story has an elevator pitch, a job statement, a demo command, and Tier-1 acceptance criteria
    And no Tier-1 field listed in the wave-doc audit Section 2 is missing

  @skip @US-2 @driving_port
  Scenario: Marco requests JTBD expansion via the expand flag
    Given Marco has run a lean DISCUSS wave on "complex-feat-y"
    When Marco runs the DISCUSS wave on "complex-feat-y" requesting expansion "jtbd-narrative"
    Then the feature-delta.md gains a section labelled [WHY] JTBD narrative
    And no section labelled [REF] is modified
    And the expansion catalog marks "jtbd-narrative" as expanded with a timestamp
    And Marco's audit trail records an expand choice for "jtbd-narrative" on the DISCUSS wave

  @skip @US-2 @driving_port
  Scenario: Wave-end prompt offers expansion choices with one-line descriptions
    Given the global configuration records the expansion prompt as "ask"
    And Marco is running the DISCUSS wave on "complex-feat-y" interactively
    When the wave reaches the wave-end prompt
    Then the prompt lists each expansion identifier from the wave's expansion catalog with a one-line description
    And selecting "skip all" records a skip choice for every expansion in Marco's audit trail
    And the feature-delta.md remains lean with no [WHY] or [HOW] sections added

  @skip @US-2 @driving_port @error
  Scenario: Re-expanding an already-expanded section is idempotent
    Given the feature-delta.md for "complex-feat-y" already contains a [WHY] JTBD narrative section
    When Marco runs the DISCUSS wave on "complex-feat-y" requesting expansion "jtbd-narrative" again
    Then Marco sees the message "expansion already present: jtbd-narrative"
    And no duplicate heading is written to the feature-delta.md
    And no new event is recorded in Marco's audit trail

  @US-7 @driving_port
  Scenario: nw-buddy reads the configuration reference before answering a density question
    Given the nw-buddy skill content is installed
    And the global-config reference document exists with a documentation density schema entry
    When Marco asks nw-buddy why his feature-delta.md is so short
    Then the nw-buddy skill content imperatively requires reading the global-config reference before answering configuration questions
    And the global-config reference document defines both the "lean" and "full" valid values
    And the configuring-doc-density guide cross-references the global-config reference

  @US-7 @driving_port
  Scenario: nw-buddy explains the expansion mechanism when Marco asks for more detail
    Given the nw-buddy skill content is installed
    When Marco asks nw-buddy how to see more detail in his feature documentation
    Then the nw-buddy skill content describes the expand mechanism for wave commands
    And the nw-buddy skill content mentions the wave-end interactive prompt
    And the nw-buddy skill content lists at least three example expansion identifiers

  @US-7 @driving_port @error
  Scenario: nw-buddy degrades gracefully when the configuration reference is missing
    Given the nw-buddy skill content is installed
    And the global-config reference document is absent
    When Marco asks nw-buddy a density-related question
    Then the nw-buddy skill content states that the configuration reference is unavailable when the document is missing
    And the nw-buddy skill content directs Marco to the troubleshooting path
    And the nw-buddy skill content does not provide fabricated valid values

  @property @driving_port @real-io
  Scenario: Telemetry schema is consistent across all wave-end documentation density events
    Given Marco has run any combination of wave-end choices producing documentation density events
    When the events are read from Marco's audit trail
    Then every documentation density event carries the keys "feature_id", "wave", "expansion_id", "choice", and "timestamp"
    And every choice value is one of "expand" or "skip"
    And every wave value is one of "DISCOVER", "DISCUSS", "DESIGN", "DEVOPS", "DISTILL", or "DELIVER"
