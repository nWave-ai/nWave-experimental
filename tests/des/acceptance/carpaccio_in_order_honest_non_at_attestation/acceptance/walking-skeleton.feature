@feature-carpaccio-in-order-honest-non-at-attestation
Feature: A prose-predecessor slice chain un-wedges end-to-end

  A spine operator (Maria) closes a principle-b prose slice that authors no
  acceptance tests. Today the successor slice wedges -- the in-order gate
  refuses a predecessor that has no SliceCommitVerified record. The walking
  skeleton proves the un-wedge: the operator records a SliceProseDelivered
  verdict from a doc-review APPROVED outcome (US-01), and the live in-order
  gate accepts that honest record so the successor enters A_GREEN (US-02). The
  record stays explicit and distinct on the ledger -- never a fabricated
  SliceCommitVerified (the honesty invariant).

  # Walking skeleton -- carries BOTH US-01 (record minted) and US-02 (gate
  # accepts). Without both, the prose chain still wedges, so the skeleton must
  # ship both in one slice. Layer 3 composition; @real-io (real AtCompletionLedger
  # over tmp_path). Driving ports: the production `des record-prose-delivered`
  # CLI (mint) + the production `evaluate_atdd_pure_dispatch` live hook (gate).

  @walking_skeleton @driving_port @slice-01 @real-io @US-01 @US-02 @contract-shape:bounded-change
  Scenario: Recording a prose verdict lets the successor slice proceed
    Given a prose predecessor slice that has been doc-review approved with no acceptance tests
    And the successor slice is wedged because the predecessor carries no honest record
    When the operator records the prose verdict for the predecessor
    And the operator dispatches the successor slice into delivery
    Then the in-order gate accepts the prose predecessor and the successor proceeds

  @walking_skeleton @driving_port @slice-01 @real-io @US-01 @contract-shape:bounded-change
  Scenario: The prose record is explicit and distinct, never a fabricated verified record
    Given a prose predecessor slice that has been doc-review approved with no acceptance tests
    When the operator records the prose verdict for the predecessor
    Then the ledger carries one prose-delivered record attested by the doc-review
    And the ledger carries no fabricated verified record for the prose predecessor
