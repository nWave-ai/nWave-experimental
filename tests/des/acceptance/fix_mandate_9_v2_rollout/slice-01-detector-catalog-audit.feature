@feature-fix-mandate-9-v2-rollout
Feature: Mandate 9 v2 rollout slice-01 — detector + catalog vocabulary + audit scaffold

  As the Mandate 9 v2 rollout author
  I want the carpaccio gate to read a `slice_kinds` vocabulary from
  `framework-catalog.yaml`, emit a non-blocking warning when a scenario tags
  `@real-io` but its composition uses only mock/stub adapters, and ship a
  retro-audit artifact scaffold for slice-03 row population
  So that crafters writing new ATs against the v2 vocabulary cannot drift
  without a mechanical warning surfacing the inconsistency
  (per spike v2 §7 walking-skeleton-first ordering — detector + catalog
  ship FIRST, behavioral skill/agent expansions ship in slice-02, audit
  closure + gate promotion ships in slice-03).

  Background:
    Given the mandate 9 v2 rollout composition is available

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: Carpaccio gate reads slice_kinds vocabulary and recognises adapter-integration
    Given the carpaccio gate loads the slice_kinds vocabulary from the framework catalog
    Then the slice kind "adapter-integration" is registered
    And the slice kind "walking_skeleton" is registered
    And the slice kind "coupled" is registered
    And the slice kind "regression-pin" is registered

  @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: Detector emits MandateNineTagMismatch warning when @real-io scenario uses mock-only composition
    Given a scenario tagged "@real-io" at "tests/example.feature" line 17
    And the composition root constructs only "MockAdapter" and "StubAdapter"
    When the carpaccio gate runs the mandate 9 tag-mismatch detector
    Then the detector verdict is "mismatch"
    And the emitted event is named "MandateNineTagMismatch"
    And the emitted severity is "warning"
    And the stderr capture mentions "tests/example.feature"

  @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: Retro-audit artifact scaffold carries the five-column schema header
    Given the retro-audit artifact at the architecture path is loaded
    Then the retro-audit header carries the column "scenario file:line"
    And the retro-audit header carries the column "tag asserted"
    And the retro-audit header carries the column "composition evidence"
    And the retro-audit header carries the column "verdict"
    And the retro-audit header carries the column "re-tag action"
