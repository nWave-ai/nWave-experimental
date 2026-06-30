@slice-03 @discuss-epic-mode
Feature: The feature-plan validator rejects an infrastructure-only epic

  An epic decomposed into features can fall into the 2026-04-24 tech-surface
  anti-pattern: every feature is a piece of plumbing and not one of them carries
  user-visible value. Such an epic never converges -- there is no JTBD outcome to
  ship. The maintainer wants that shape caught MECHANICALLY at the moment the
  epic-delta is checked, so an infrastructure-only epic becomes non-representable
  rather than a problem discovered weeks later.

  When every feature row of the Feature Plan is annotated @infrastructure, the
  feature-plan check rejects the epic as infrastructure-only and names the cause
  in feature terms -- so the maintainer reads "feature rows", not "slice rows",
  and knows it is the EPIC that carries no value. As soon as one feature is
  value-bearing (an empty annotation, @walking-skeleton, or any non-infra token),
  the epic carries shippable value and clears the cohesion floor.

  # discuss-epic-mode slice-03 (feature-granularity cohesion-MECC) + the DESIGN
  # slice-03 code-design: the SAME `_classify_slice_cohesion` floor the slice-plan
  # mode uses, reached at feature granularity through the feature-plan spec's
  # `row_noun="feature"`. The `rejected-infra-only` token is SHARED across both
  # plan modes -- it names the failure CLASS (no user-visible value), not the plan
  # kind; the detail field's "feature rows" is the plan-kind disambiguator
  # (token-coupling constraint H3/M1, NORMATIVE for consumers). Driving port: the
  # production validate-feature-delta CLI invoked with --require-feature-plan
  # --format=json (`des.cli.validate_feature_delta.main`). Layer 3
  # (subprocess/FS acceptance) -- example-only, no PBT (Mandate 9/11): the cohesion
  # shapes form a finite, enumerable closed set, so the falsifier-gate forbids PBT.

  Background:
    Given an epic decomposed into a Feature Plan

  @slice-03 @driving_port @error @contract-shape:pure-function
  Scenario: An epic whose every feature is infrastructure is rejected as infrastructure-only
    Given the epic-delta carries a Feature Plan whose every feature is infrastructure
    When the maintainer runs the cohesion check on the epic
    Then the epic is rejected as infrastructure-only
    And the rejection names the cause in feature terms
    And the cohesion check leaves the epic-delta unchanged

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: An epic with one value-bearing feature clears the cohesion floor
    Given the epic-delta carries a Feature Plan with one value-bearing feature among infrastructure
    When the maintainer runs the cohesion check on the epic
    Then the epic clears the cohesion floor
    And the cohesion check leaves the epic-delta unchanged

  # C3 count-cardinality (Count: One): a single feature row that is infrastructure
  # is still an infrastructure-only epic -- the floor must fire at cardinality one,
  # not only at "many". This pins that the veto is "every row is infra", not "two
  # or more rows are infra".
  @slice-03 @driving_port @error @contract-shape:pure-function
  Scenario: An epic with a single infrastructure feature is rejected as infrastructure-only
    Given the epic-delta carries a Feature Plan with a single infrastructure feature
    When the maintainer runs the cohesion check on the epic
    Then the epic is rejected as infrastructure-only
    And the rejection names the cause in feature terms
    And the cohesion check leaves the epic-delta unchanged
