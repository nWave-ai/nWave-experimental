@feature-classic-spine-decommission
Feature: A DELIVER dispatch resolves to atdd_pure by default
  As an nWave framework developer completing release N of the staged cutover
  I want atdd_pure to be the default DELIVER spine and the deprecation advisory
    to fire only when classic is explicitly configured
  So that every real feature runs atdd_pure for a release without false noise

  # slice-13 of classic-spine-decommission. The `workflow.mode` resolver's
  # decision table across all three mode states: an absent mode resolves to the
  # atdd_pure default; an explicit atdd_pure resolves silently; an explicit
  # classic resolves to classic and emits the loud ClassicSpineDeprecated
  # advisory. EXTEND of the resolver -- release N's only behavioural change.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only (Mandate 11).
  # state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: the `workflow.mode` resolver invoked by a DELIVER dispatch.

  @slice-13 @driving_port @contract-shape:bounded-change
  Scenario: An absent workflow mode resolves to the atdd_pure default
    Given a project configured for no workflow mode configured
    When a DELIVER dispatch runs
    Then the dispatch resolves to the atdd_pure spine
    And no classic-spine deprecation advisory is emitted

  @slice-13 @driving_port @contract-shape:bounded-change
  Scenario: An explicit atdd_pure mode resolves to atdd_pure without an advisory
    Given a project configured for the atdd_pure spine
    When a DELIVER dispatch runs
    Then the dispatch resolves to the atdd_pure spine
    And no classic-spine deprecation advisory is emitted

  @slice-13 @driving_port @contract-shape:bounded-change
  Scenario: An explicit classic mode still resolves to classic but emits the advisory
    Given a project configured for the classic spine
    When a DELIVER dispatch runs
    Then the dispatch resolves to the classic spine
    And a classic-spine deprecation advisory is emitted
