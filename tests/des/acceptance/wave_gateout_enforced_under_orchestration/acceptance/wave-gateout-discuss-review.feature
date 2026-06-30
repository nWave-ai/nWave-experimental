@feature-wave-gateout-enforced-under-orchestration @driving_port @real-io
Feature: A DISCUSS wave-agent return under orchestration reaches its PO-review veto

  slice-04 (regression-lock, GREEN-on-keystone). Completes coverage of all FOUR RCA
  blast-radius gate-outs. The keystone wave-parametric route reaches the DISCUSS
  two-row gate-out stack; this slice LOCKS the SECOND row -- the PO-review-verdict
  veto verify-discuss-review (DiscussReviewGate.evaluate). The PO-review row is
  reached only after the structural row passes (halt-at-first-veto), so each
  scenario carries a value-bearing slice plan. A return with no recorded PO review
  is refused (absent verdict read as a refusal -- degrade-LOUD); an approved PO
  review (recorded through the REAL `des record-discuss-review` producer CLI, sealed
  vs the feature-delta hash) lets the same return close the wave.

  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root; the verdict recorded through the
  REAL producer CLI (No Fixture Theater). Reuses the slice-01 driving primitives.
  Real-Surface Binding:
    AT-08 -> handle_subagent_stop reaching SubagentStopService.validate ->
             _discuss_gate_out_declarative -> _gate_out_po_review ->
             DiscussReviewGate.evaluate over the absent DiscussReviewVerdict ledger
             record (structural row passed first); observable = block (degrade-LOUD).
    AT-09 -> the same path with an approved DiscussReviewVerdict recorded through the
             REAL `des record-discuss-review` producer CLI; observable = allow.

  @slice-04 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A discuss return past the structural row with no PO review is refused
    Given a product-owner is returning a DISCUSS deliverable under autonomous orchestration
    And the feature-delta slice plan carries user-observable value
    And no product-owner review has been recorded for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with a missing-review reason

  @slice-04 @feature-wave-gateout-enforced-under-orchestration @contract-shape:unbounded-preservation
  Scenario: A discuss return with an approved product-owner review is allowed to close the wave
    Given a product-owner is returning a DISCUSS deliverable under autonomous orchestration
    And the feature-delta slice plan carries user-observable value
    And the product-owner has recorded an approved review for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is allowed
