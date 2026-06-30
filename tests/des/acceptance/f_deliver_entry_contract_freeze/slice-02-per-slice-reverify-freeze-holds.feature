@feature-f-deliver-entry-contract-freeze
Feature: DELIVER-entry contract freeze holds across per-slice re-verify

  Once the contract is frozen at the first DELIVER gate-IN, every subsequent
  per-slice gate-IN RE-VERIFIES the live feature-delta against the frozen
  baseline (OUT=IN re-earned at each slice seam). The freeze is feature-level
  (ADR-FLOW-002 D8): it holds across ALL per-slice iterations and never re-opens
  the ratification window. The one post-freeze mutation permitted is the
  status-flip "slice shipped"; any other mutation is drift and HALTs.

  # Driving port (Mandate-13, Layer 3 subprocess): the REAL
  # `des verify-deliver-entry-contract` gate, re-invoked per slice against a real
  # temp repo whose live feature-delta is mutated after the freeze. Observables:
  # the §17 verdict (drift -> FAIL) and the count of ContractFrozen baselines.

  @slice-02 @driving_port @contract-shape:unbounded-preservation @CT-5 @CT-7
  Scenario Outline: A permitted post-freeze edit re-earns the freeze without re-freezing
    Given a contract frozen at the first DELIVER gate-IN
    And the live feature-delta has <edit> relative to the frozen baseline
    When a per-slice DELIVER gate-IN re-verifies the contract
    Then the re-verify returns a pass verdict
    And the contract is frozen exactly once in the completion ledger

    Examples: the post-freeze mutations ADR-FLOW-002 D8 permits
      | edit        |
      | unchanged   |
      | status_flip |

  @slice-02 @driving_port @contract-shape:unbounded-preservation @error @CT-5
  Scenario Outline: A forbidden post-freeze mutation halts the per-slice re-verify
    Given a contract frozen at the first DELIVER gate-IN
    And the live feature-delta has <edit> relative to the frozen baseline
    When a per-slice DELIVER gate-IN re-verifies the contract
    Then the re-verify returns a fail verdict

    Examples: post-freeze drift beyond the permitted status-flip
      | edit           |
      | edited_section |
      | added_slice    |
