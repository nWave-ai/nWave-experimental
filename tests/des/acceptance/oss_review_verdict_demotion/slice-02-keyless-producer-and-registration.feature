@feature-oss-review-verdict-demotion @coupled:slice-02-keyless-producer
Feature: The AT-review verdict producer records keyless and is discoverable

  When the acceptance-designer reviewer approves a slice's AT set, DISTILL
  records that approval as an ATReviewVerdict in the feature's AT-completion
  ledger. In the OSS threat model the key holder and the would-be forger are the
  same person, so the keyed signature buys no guarantee -- it only forces the
  operator to provision a signing key before a verdict can be recorded at all.
  This slice DEMOTES the producer: it writes the verdict carrying the reviewer
  identity, the AT-set binding and the content seal but NO hmac_sha256 field,
  it resolves no signing key (key absence is a non-event, never a failure), and
  the new record clears the slice-01 keyless gate end-to-end.

  The producer also becomes discoverable through the des single entry point as
  "des record-at-review-verdict", symmetric with the already-registered
  "des record-discuss-review". Post-demotion the RECORD is the entire control,
  so an undiscoverable producer invites hand-authored ledger lines -- the exact
  bypass the veto refuses. Registering it closes sister Tsunami's "missing
  command" gap on the one command whose record is now the whole control.

  The three scenarios below form one coupled AT group
  (@coupled:slice-02-keyless-producer): the keyless producer->gate round-trip,
  the absence of the signature field on the written record, and the
  discoverability of the producer through the des dispatcher all assert one
  indivisible contract -- "the producer writes a keyless, gate-clearable,
  discoverable verdict". Greening the keyless write without dropping the
  signature field would leave a half-demoted producer; greening the write
  without registering the subcommand would ship a control whose producer no
  operator can find. coupling_justification recorded in the slice plan.

  # Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  # Feature-delta S2 row + D-register + Hard contracts (a)/(b) PASS leg.
  # Driving ports (Mandate 13, Layer 3 composition root):
  #   - the producer CLI (des.cli.at_review_verdict.main via argv);
  #   - the des dispatcher (des.cli.__main__.main with record-at-review-verdict);
  #   - the slice-01 keyless carpaccio gate (round-trip witness, via argv main).
  #   No direct-domain import of record_at_review_verdict or check_at_review.
  # Layer 3 (subprocess/FS acceptance): real filesystem (tmp_path) is the only
  #   driven adapter -> @real-io; example-only, no PBT (Mandate 9 v2 / 11).
  # D-register / S3 dormant-seam witness: the DISPATCHER scenario drives the
  #   net-new dispatcher row through the real des entry point and asserts its
  #   observable effect (the routed producer appends the verdict record).

  Background:
    Given an atdd_pure feature with an empty ledger and no reviewer signing key provisioned

  @slice-02 @driving_port @walking_skeleton @real-io @contract-shape:bounded-change
  Scenario: A keyless approved verdict is recorded and clears the slice-01 gate
    Given the entering slice has an approved AT set ready to record
    When the reviewer records the approved verdict through the at-review-verdict producer directly
    Then the ledger gains one approved verdict for the entering slice
    And the recorded verdict binds the reviewer identity and the content seal
    And the slice-01 keyless gate clears the entering slice on the recorded verdict

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The recorded verdict carries no signature field and needs no key
    Given the entering slice has an approved AT set ready to record
    When the reviewer records the approved verdict through the at-review-verdict producer directly
    Then the ledger gains one approved verdict for the entering slice
    And the recorded verdict carries no signature field
    And no reviewer signing key was provisioned anywhere

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The producer is discoverable through the des single entry point
    Given the entering slice has an approved AT set ready to record
    When the reviewer records the approved verdict through the discoverable des record-at-review-verdict subcommand
    Then the ledger gains one approved verdict for the entering slice
    And the recorded verdict binds the reviewer identity and the content seal
