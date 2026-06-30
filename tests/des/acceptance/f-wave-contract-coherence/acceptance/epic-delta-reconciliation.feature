@feature-f-wave-contract-coherence @driving_port @real-io @contract-shape:bounded-change
Feature: The flow-v2 epic-delta Feature Plan stays reconciled with the live feature set

  The flow-v2-wave-migrations epic-delta carries a Feature Plan that is the
  canonical inventory of the epic's features (LSC-4). The closure scorecard
  (scripts/flow_v2_closure_scorecard.py) declares the SAME live set in its FEATURES
  list -- it is the GOAL CONTRACT, never edited here. The two are independent reads
  of one truth: the epic-delta Feature Plan and the scorecard FEATURES list must name
  exactly the same features, with no drift. Today the epic-delta lists FEWER features
  than the scorecard declares -- the inventory drift this slice closes.

  Driving surface (Mandate-13 driving-port-only): the SHIPPED artifacts as they are
  read in production -- the real epic-delta markdown parsed through the production
  feature-plan parser (Layer 3 composition over its real read path), the real
  des validate-feature-delta --require-feature-plan subprocess (Layer 3 subprocess),
  and the real scorecard FEATURES list sourced from the shipped script. No production
  module is imported-and-called for its business logic beyond the feature-plan parser
  the validator itself uses; the scenarios drive shipped files + the shipped CLI.
  Mandate-14 @real-io: real filesystem reads + a real OS subprocess -- the ATs would
  fail if the epic-delta, the scorecard, or the des dispatcher were absent.

  # AT-19: the epic-delta Feature Plan lists EVERY feature the live set declares --
  #        the scorecard FEATURES id set is a SUBSET of the epic-delta Feature Plan
  #        id set (no live feature is missing from the inventory). RED at HEAD: the
  #        epic-delta lists 6 of the 14 live features, so 8 are missing.
  @slice-07 @feature-f-wave-contract-coherence @AT-19
  Scenario: The epic-delta Feature Plan lists every feature in the live set
    Given the shipped flow-v2 epic-delta and the closure scorecard
    When the epic-delta Feature Plan is read
    Then the epic-delta Feature Plan lists every feature the live set declares

  # AT-20: the feature-plan validator accepts an epic-delta whose Feature Plan covers
  #        the whole live set. The accepted clause is the non-regression guard (the
  #        reconciled epic-delta must stay structurally valid); the coverage clause is
  #        what makes it RED at HEAD (the validator accepts the structure today, but
  #        the structure does NOT yet cover every live feature). GREEN only once
  #        DELIVER adds the missing rows AND the structure stays valid.
  @slice-07 @feature-f-wave-contract-coherence @AT-20
  Scenario: The feature-plan validator accepts an epic-delta covering every live feature
    Given the shipped flow-v2 epic-delta and the closure scorecard
    When the feature-plan validator runs over the epic-delta
    Then the validator accepts an epic-delta Feature Plan covering every live feature

  # AT-21: two INDEPENDENT reads of the live feature set -- the epic-delta Feature
  #        Plan id set and the scorecard FEATURES id set -- are EQUAL (no drift in
  #        either direction: no missing live feature, no stale phantom row). RED at
  #        HEAD: the two sets differ by the 8 features absent from the epic-delta.
  @slice-07 @feature-f-wave-contract-coherence @AT-21
  Scenario: The epic-delta feature-id set equals the scorecard feature-id set
    Given the shipped flow-v2 epic-delta and the closure scorecard
    When the epic-delta Feature Plan id set and the scorecard feature-id set are read
    Then the epic-delta feature-id set equals the scorecard feature-id set
