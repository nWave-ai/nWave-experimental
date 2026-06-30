@feature-oss-review-verdict-demotion @coupled:slice-03-keyless-discuss-veto
Feature: The DISCUSS product-owner review veto enforces record-presence with no key and never disarms on key absence

  When a product-owner reviewer judges a DISCUSS artefact, the verdict is
  recorded and the DISCUSS-to-DESIGN handoff is mechanically blocked unless that
  record is present and approves the current artefact. In the OSS threat model
  the key holder and the would-be forger are the same person, so the keyed
  signature buys no guarantee -- it only forces a signing key to be provisioned
  before the gate can decide at all. This slice DEMOTES the DISCUSS veto from
  "HMAC-signed verdict" to "review verdict RECORD present and well-formed": the
  reviewer veto and the no-silent-pass floor are preserved in full; only the
  keyed cryptography goes.

  This slice ALSO closes a live correctness defect. Today the DISCUSS gate is
  silently DISARMED when no signing key is provisioned: with no recorded verdict
  AND no key, the gate returns no objection and the handoff is ALLOWED -- a
  reviewer who never reviewed is indistinguishable from one who approved. After
  the demotion there is no key, so record-presence is the only check: an absent
  verdict ALWAYS blocks degrade-loud, and key absence disarms nothing. The gate
  arms on "a review reader is wired", never on "a key was provisioned".

  The three scenarios below form one coupled AT group
  (@coupled:slice-03-keyless-discuss-veto): the escape-closing block on a
  keyless absent verdict, the keyless approval that clears the handoff, and the
  keyless reviewer veto that blocks it all assert one indivisible contract --
  "the record IS the control, the key is not, and absence never passes". Closing
  the escape without preserving the keyless PASS leg would leave a gate that can
  never be cleared; preserving the PASS leg without the keyless veto leg would
  let a reviewer veto silently pass once the key is gone.

  # Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  # Hard contracts (a) key-absence-never-disarms and (b) record-absence-always-
  #   blocks from feature-delta DISCUSS [REF] Hard contracts; the S3 row.
  # THE ESCAPE being closed: src/des/application/subagent_stop_service.py:372
  #   -- `if record is None and key is None: return None` (gate silently UNARMED).
  # Driving port (Mandate 13, Layer 3 composition root): the production
  #   SubagentStopService.validate built via
  #   des.adapters.drivers.hooks.service_factory.create_subagent_stop_service
  #   -- the real DISCUSS gate-OUT entry point. The discuss wave-active floor +
  #   a value-bearing feature-delta arm the structural gate-OUT to PASS so the
  #   review-gate branch is what decides. NO direct-domain import of
  #   DiscussReviewGate.evaluate or _evaluate_discuss_po_review.
  # Layer 3 (subprocess/FS acceptance): the real filesystem (tmp_path) is the
  #   only driven adapter -> @real-io; example-only, no PBT (Mandate 9 v2 / 11).
  #
  # RED-for-right-reason (pre-DELIVER fail-for-right-reason gate). At tip
  #   (a77815c3e) the DISCUSS gate STILL resolves a signing key and STILL carries
  #   the line-372 escape. The S3 fixtures provision NO key anywhere, so:
  #   * ESCAPE_CLOSED -- with no record and no key the today-gate takes the
  #     line-372 escape (`return None`) and the handoff is ALLOWED; the scenario
  #     expects a BLOCK -> semantic AssertionError (the escape is the live
  #     silent-pass this slice must close: the RED direction is "today passes
  #     where post-demotion it must block").
  #   * KEYLESS_APPROVED_CLEARS -- with an approved record and no key the
  #     today-gate resolves the key FIRST and returns INDETERMINATE("key-absent")
  #     -> the handoff is BLOCKED; the scenario expects ALLOW -> semantic
  #     AssertionError (the demotion must drop the key check and PASS a keyless
  #     approval).
  #   * KEYLESS_VETO_BLOCKS -- with a needs-revision record and no key the
  #     today-gate returns INDETERMINATE("key-absent"), naming an indeterminate
  #     cause, not the reviewer veto; the scenario expects a VETO block naming
  #     the reviewer decision -> semantic AssertionError (the demotion must read
  #     the keyless record and honor the veto).
  #   No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2 -- documented here per the AT-completeness gate):
  #   discuss review-gate states = {DISCUSS_RETURNING (structural gate-OUT PASS)}.
  #     event keyless record absent -----------> INDETERMINATE (degrade-LOUD block,
  #                                               reason `absent`; key absence
  #                                               disarms NOTHING -- escape closed)
  #     event keyless APPROVED + artefact-current -> PASS (no objection, NOT a GO)
  #     event keyless NEEDS_REVISION -----------> VETOED (reviewer veto, honored)

  Background:
    Given a discuss-wave return for an atdd_pure feature with no reviewer signing key anywhere

  @slice-03 @driving_port @walking_skeleton @error @real-io @contract-shape:bounded-change
  Scenario: A discuss handoff with no recorded review verdict and no key is blocked, never silently passed
    Given the DISCUSS review reader is wired and no review verdict is recorded for the feature
    When the discuss-wave handoff is checked at the subagent-stop gate
    Then the handoff to design is blocked degrade-loud as indeterminate
    And the indeterminate block names the reason "absent"
    And the indeterminate block never masquerades as a reviewer veto

  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A keyless approved review verdict clears the discuss handoff as no objection found
    Given the feature has an approved product-owner review verdict recorded with no signature for the current artefact
    When the discuss-wave handoff is checked at the subagent-stop gate
    Then the handoff to design is allowed as no objection found from the review

  @slice-03 @driving_port @error @real-io @contract-shape:unbounded-preservation
  Scenario: A keyless needs-revision review verdict blocks the discuss handoff by the reviewer veto
    Given the feature has a needs-revision product-owner review verdict recorded with no signature for the current artefact
    When the discuss-wave handoff is checked at the subagent-stop gate
    Then the handoff to design is blocked by the reviewer veto
    And the veto names the reviewer decision read from the recorded verdict, never the agent's say-so
