@feature-oss-review-verdict-demotion @coupled:slice-01-keyless-veto
Feature: The AT-review slice gate enforces the record-presence veto with no signing key

  An operator (or orchestrator) submitting a slice for implementation on an
  atdd_pure feature is checked at the DELIVER entry gate before any crafter is
  dispatched. The AT-review half of that gate authenticates the reviewer's
  approval. In the OSS threat model the key holder and the would-be forger are
  the same person, so the keyed signature buys no guarantee -- it only adds
  install friction and a failure surface. This slice DEMOTES the gate from
  "HMAC-signed verdict" to "review verdict RECORD present and well-formed":
  the mechanical no-silent-pass veto is preserved in full; only the keyed
  cryptography goes.

  The preserved veto checks the present fields of the record -- an APPROVED
  verdict that names a reviewer, binds the slice, binds the reviewed AT set,
  and carries a content seal over the reviewed scenario bodies. No key is
  resolved anywhere; the gate never demands one. A pre-existing record that
  still carries the old hmac_sha256 field is read on its present fields and the
  stray field is ignored -- it is neither parsed for verification nor a parse
  error (upgrade compatibility).

  The three scenarios below form one coupled AT group
  (@coupled:slice-01-keyless-veto): the keyless-PASS path, the record-absence
  BLOCK (the no-silent-pass spine that must hold before AND after the demotion),
  and the legacy-record tolerance all assert one indivisible contract -- "the
  record IS the control, the key is not". Greening only the keyless-pass path
  without the absence-block would ship a gate that passes blind; greening the
  pass path without legacy tolerance would break every operator mid-upgrade.
  coupling_justification recorded in the slice plan.

  # Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  # Hard contracts (b), (c), (d) from feature-delta DISCUSS [REF] Hard contracts.
  # Driving port: the carpaccio-slice-gate CLI invoked as a DES entry_gate
  #   (des.cli.carpaccio_slice_gate.main via its argv entry) -- Mandate 13
  #   Layer 3 composition root, no direct-domain import of check_at_review.
  # Layer 3 (subprocess/FS acceptance): real filesystem (tmp_path) is the only
  #   driven adapter -> @real-io; example-only, no PBT (Mandate 9 v2 / 11).

  Background:
    Given a repository for an atdd_pure feature with no reviewer signing key anywhere

  @slice-01 @driving_port @walking_skeleton @real-io @contract-shape:unbounded-preservation
  Scenario: A keyless approved verdict clears the slice and the gate writes nothing
    Given the entering slice has an approved review verdict recorded with no signature
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is cleared to enter implementation
    And the gate writes no file in the repository

  @slice-01 @driving_port @error @real-io @contract-shape:bounded-change
  Scenario: An absent review verdict blocks the slice and names the absence
    Given the AT-completion ledger carries no review verdict for the entering slice
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is blocked with an AT-review rejection
    And the rejection names the reason "absent"
    And the gate writes no file in the repository

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A legacy verdict still carrying a signature field is tolerated and clears the slice
    Given the entering slice has an approved review verdict recorded carrying a legacy signature field
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is cleared to enter implementation
    And the legacy signature field triggered no verification and no parse error
    And the gate writes no file in the repository
