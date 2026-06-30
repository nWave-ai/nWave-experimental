@feature-nwave-flow-v2-enforcement @slice-07b
Feature: The product-owner review verdict is a mechanical veto at the discuss handoff
  As an nWave maintainer who trusts the spine to be deterministic
  I want the DISCUSS-to-DESIGN handoff to be blocked by a needs-revision
    product-owner review verdict -- read from the ledger, never from the
    agent's say-so -- and blocked degrade-loud when the verdict is absent
  So that the reviewer's veto is MECHANICALLY enforced (never skippable advisory
    text), a missing verdict never masquerades as a reviewer decision
    and never passes silently, and an approval means only "no objection
    found" -- the GO stays human

  # slice-07b of nwave-flow-v2-enforcement -- DISCUSS PO-review MECHANICAL
  # veto-gate (O-3 resolution). Post-demotion (oss-review-verdict-demotion S3):
  # re-authored keyless. The HMAC/signing scenarios are RETIRED; the veto
  # contract is now record-presence only (D-no-disarm / D-veto-preserved).
  #
  # DRIVING PORT (Mandate-13 driving-port-only): Layer 3 composition -- the REAL
  # SubagentStopService.validate via the production composition root
  # (service_factory.create_subagent_stop_service), over a tmp project_root with
  # a `discuss` wave-active floor armed AND a VALUE-BEARING feature-delta seeded,
  # so the slice-07 structural gate-OUT PASSES and the review-gate branch is
  # what decides. Observable = the HookDecision (allow vs block) + the
  # DISCUSS_PO_REVIEW_* reason token. No signing key is provisioned anywhere.
  #
  # CONTRACT SHAPES (Mandate-14): the review-gate is a DECISION over read state
  # (the ledger record + the artefact); it vetoes or allows, mutating
  # nothing -> @contract-shape:unbounded-preservation on all three scenarios.
  #
  # ASYMMETRIC AUTHORITY (§22.0 / §21.1.3): a NEEDS_REVISION is a
  # mechanically-honored VETO; an APPROVED is "no objection found", NEVER
  # an authorizing GO. Absent -> INDETERMINATE (degrade-LOUD block, §17),
  # NEVER coerced to PASS and NEVER coerced to VETOED
  # ("mechanism couldn't run" is not "reviewer said no" -- §22.7).
  #
  # SUT STATE MACHINE (C2):
  #   review-gate states = {DISCUSS_RETURNING (structural PASS reached)}.
  #     event keyless NEEDS_REVISION --------> VETOED (block, reviewer veto)
  #     event verdict-absent  ----------------> INDETERMINATE (degrade-LOUD block)
  #     event keyless APPROVED + artefact-current --> PASS (no objection, NOT a GO)

  # AT-1 -- the reviewer VETO, mechanically enforced (re-authored keyless).
  # DiscussReviewGate.evaluate + DiscussReviewReader.latest threaded into the
  # SubagentStopService gate-OUT host (after the structural MECC).
  @slice-07b @driving_port @real-io @us-po-review @error @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave is blocked when the product-owner review says needs revision
    Given a discuss-wave return carrying a needs-revision product-owner review verdict
    When the discuss-wave handoff is checked against the recorded review verdict
    Then the handoff to design is blocked by the reviewer veto
    And the veto names the reviewer decision read from the recorded verdict, never the agent's say-so

  # AT-2 -- the INDETERMINATE degrade-LOUD floor (absent verdict). A missing
  # verdict is "mechanism couldn't run", NOT "reviewer said no" -- it blocks
  # with an indeterminate-class reason DISTINCT from the veto reason (§22.7).
  @slice-07b @driving_port @real-io @us-po-review @error @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave blocks degrade-loud when no product-owner review verdict is recorded
    Given a discuss-wave return with no recorded product-owner review verdict
    When the discuss-wave handoff is checked against the recorded review verdict
    Then the handoff to design is blocked degrade-loud as indeterminate
    And the indeterminate block never masquerades as a reviewer veto

  # AT-3 -- the PASS = no-objection complement (§22.0 asymmetric authority).
  # A keyless, artefact-current APPROVED verdict allows the handoff --
  # "no objection found", NOT an authorizing GO (the GO stays human).
  @slice-07b @driving_port @real-io @us-po-review @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave is allowed when the product-owner review approves the current artefact
    Given a discuss-wave return carrying an approved product-owner review verdict for the current artefact
    When the discuss-wave handoff is checked against the recorded review verdict
    Then the handoff to design is allowed as no objection found from the review
