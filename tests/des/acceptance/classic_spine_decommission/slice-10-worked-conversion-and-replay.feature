@feature-classic-spine-decommission
Feature: The first real legacy feature is converted and audit-log replay is proven
  As a solution architect retiring the classic roadmap spine
  I want the converter proven on a real in-flight feature and the legacy
    audit-log replay proven green before any classic module is ever touched
  So that the conversion is trusted on real input and the N+1 removal sweep
    inherits a verified safety precondition

  # slice-10 of classic-spine-decommission. The worked conversion + the
  # replay-verification gate (M5).
  #
  # (a) The worked-conversion scenario is FIXTURE-MODELLED on the real
  #     `walking-skeleton-production-like-gate` feature shape: a 12-step
  #     roadmap, slice-01 committed, a multi-slice plan -- after conversion
  #     slice-01 is shipped, slice-02 pending, the roadmap archived. It runs
  #     against the generic `convert-target` fixture (a faithful structural
  #     model of that feature), NOT a checkout of the genuine feature dir at
  #     commit c631692f5. The genuine real-feature conversion happens
  #     operationally via the slice-11/12 drain over the live `docs/feature/*`
  #     tree; this AT proves the converter's contract on the modelled shape.
  # (b) Prove audit-log replay: a real pre-2026-05-07 commit replayed through
  #     `verify_commit_trailers` + the `PhaseEventParser` MARK-HISTORICAL path
  #     runs GREEN. This is the precondition the N+1 DELETE sweep depends on.
  #
  # Layer 4 (integration): real git + real converter + real verifier.
  # Example-only (Mandate 11).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` + `verify_commit_trailers`.

  @slice-10 @driving_port @contract-shape:bounded-change
  Scenario: A walking-skeleton-shaped feature is converted onto atdd_pure
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    When the architect converts the feature
    Then the conversion is converted onto the atdd_pure spine
    And slice "slice-01" is reconciled as shipped
    And slice "slice-02" is reconciled as pending
    And the feature now runs on the atdd_pure spine
    And the classic roadmap artifacts are archived under the feature
    And the converted feature passes the carpaccio entry gate dry-run

  @slice-10 @driving_port @contract-shape:pure-function
  Scenario: A pre-decommission legacy commit replays green through the historical parser
    Given a commit predating the classic-spine decommission
    When the legacy commit is replayed
    Then the audit-log replay runs green
