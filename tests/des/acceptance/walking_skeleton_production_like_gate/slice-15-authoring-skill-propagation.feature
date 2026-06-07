@feature-walking-skeleton-production-like-gate
Feature: The tiered walking-skeleton discipline becomes authoring guidance
  As an acceptance designer authoring a walking-skeleton test
  I want the test-design mandates and the distill command guidance to teach the
    tiered discipline up front
  So that I author a tier-correct walking skeleton, rather than being ambushed
    by the gate at feature-end

  # carpaccio slice-15 (DESIGN slice-08). Authoring-side methodology
  # propagation -- skills + commands. The tiered-e2e discipline (T0 proxy and
  # insufficient; T1 delivered artifact in a clean prefix is the mandatory
  # floor; T2 clean container when Docker is present; the three D6 facets; the
  # @walking-skeleton @wiring_e2e tagging contract; fail-mode-D deferral)
  # becomes authoring guidance in the test-design mandates and the distill
  # command. A mechanical gate that teaches nothing only punishes -- this slice
  # teaches the discipline the enforcement half (slices 01-14) verifies.
  #
  # Layer 4 (integration): a content arch test over the authoring artifacts.
  # Example-pinned, traditional assertions permitted (Mandate 8).
  #
  # Driving port: a `pytest` arch test over the authoring skill + command files.

  @slice-15 @contract-shape:bounded-change
  Scenario: The test-design mandates teach the tiered walking-skeleton discipline
    Given the test-design mandates carries the tiered walking-skeleton discipline
    When the propagation check reads the test-design mandates
    Then the propagation check confirms the test-design mandates teach the tiered discipline

  @slice-15 @contract-shape:bounded-change
  Scenario: The distill command guidance teaches the tiered walking-skeleton discipline
    Given the distill command guidance carries the tiered walking-skeleton discipline
    When the propagation check reads the distill command guidance
    Then the propagation check confirms the distill command guidance teaches the tiered discipline

  @slice-15 @error @contract-shape:bounded-change
  Scenario: The propagation check fails when an authoring skill omits the discipline
    Given the test-design mandates omits the tiered walking-skeleton discipline
    When the propagation check reads the test-design mandates
    Then the propagation check fails naming the authoring artifact that omits the discipline
