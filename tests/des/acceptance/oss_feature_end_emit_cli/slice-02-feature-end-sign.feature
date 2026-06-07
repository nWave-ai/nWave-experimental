@feature-oss-feature-end-emit-cli @slice-02
Feature: A reviewer's deep-review verdict is signed into a verifiable hash so the done-gate cannot be satisfied by theater
  As an nWave orchestrator running an atdd_pure feature-end cycle
  I want a `des feature-end sign` command that turns a REAL deep-review verdict
    -- the reviewer agent, its APPROVED or REJECTED decision, and its findings --
    into a signed verdict hash, by HMAC-ing the verdict under the reviewer
    signing key
  So that the hash that feeds `des emit-feature-end` is a genuine signature over
    a real review (never a minted constant), a sign request with no real review
    or no signing key is loudly refused, and the deep-review leg of the done-gate
    is mechanically satisfiable without theater

  # slice-02 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03). slice-01
  # shipped `des emit-feature-end` -- which CONSUMES a `--verdict-hash` but does
  # not produce one. slice-02 ships the PRODUCER: the platform-agnostic signing
  # use-case (reusing the `des.domain.at_review_signing` SSOT) exposed via the
  # consolidated `des feature-end sign` shim. The hash it produces is the hex
  # that feeds `des emit-feature-end --record FeatureEndReviewVerdict
  # --verdict-hash`. Closes the deep-review leg of F-ATDD-PURE-FEATURE-END-CYCLE-
  # UNWIRED.
  #
  # ANTI-THEATER INVARIANT (load-bearing, DDD-5 + feedback_earned_trust_
  # mechanical_evidence_not_llm_verdict): the signer NEVER MINTS. It requires the
  # reviewer's REAL verdict record (agent + APPROVED/REJECTED + findings) and
  # HMACs it via `compute_verdict_hmac(record, require_signing_key(repo))` over
  # `canonical_at_review_json(record)`, env `NWAVE_REVIEWER_SIGNING_KEY`. A sign
  # request with no real verdict / a malformed-or-empty verdict / no signing key
  # is REFUSED (exit non-zero); no hash is produced. The genuineness is proved by
  # recomputing the SAME HMAC independently and asserting equality -- a minted
  # constant cannot equal a real signature over the real input.
  #
  # SINGLE ENTRY POINT (DDD-7, AD-26 1:1 mirror): the feature-end subcommands
  # consolidate under one `des feature-end <verb>` namespace dispatched through
  # the one `des.cli.__main__` dispatcher + the gate catalog. The consolidated
  # surface is reachable and slice-01's `emit` still works under it (back-compat).
  #
  # Driving port: the real `des feature-end sign` subcommand, invoked over the
  # single `des` entry point as a subprocess against a real git working tree and
  # the real reviewer signing key (Mandate-13 driving-port-only, Layer 3
  # subprocess -- the SAME surface as slice-01). The produced hash is verified
  # genuine by an INDEPENDENT recompute through the at_review_signing SSOT (the
  # audit SUBSTRATE the slice-01 consumer reads, not the SUT) and accepted
  # end-to-end by the real `des emit-feature-end` consumer. Example-only, no PBT
  # (Mandate 9/11: a real-I/O layer-3 surface).
  #
  # @coupled: every scenario pins ONE driving-port contract -- the consolidated
  # `des feature-end sign` command's input/output behavior plus its dispatcher
  # reachability -- and cannot be split without severing that single-command
  # closure.

  @slice-02 @walking_skeleton @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: A reviewer's approval is signed into a genuine verdict hash the emitter accepts
    Given an orchestrator at the feature-end of a feature with the reviewer signing key available
    When the reviewer's APPROVED deep-review verdict is signed
    Then the command produces a verdict hash that is a genuine signature over that verdict
    And the produced hash is accepted by the feature-end record emitter
    And the signing command reports success

  @slice-02 @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: A reviewer's rejection is signed into its own genuine verdict hash
    Given an orchestrator at the feature-end of a feature with the reviewer signing key available
    When the reviewer's REJECTED deep-review verdict is signed
    Then the command produces a verdict hash that is a genuine signature over that verdict
    And the signing command reports success

  @slice-02 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: Signing with no deep-review verdict at all is refused
    Given an orchestrator at the feature-end of a feature with the reviewer signing key available
    When a verdict is signed with no deep-review verdict at all
    Then the command refuses to sign
    And the command produces no verdict hash

  @slice-02 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario Outline: Signing a non-real deep-review verdict is refused
    Given an orchestrator at the feature-end of a feature with the reviewer signing key available
    When a verdict is signed with a <defect> deep-review verdict
    Then the command refuses to sign
    And the command produces no verdict hash

    Examples: non-real verdict inputs
      | defect          |
      | empty-agent     |
      | unknown-verdict |
      | missing-verdict |

  @slice-02 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: Signing without the reviewer signing key is loudly refused
    Given an orchestrator at the feature-end of a feature with the reviewer signing key absent
    When the reviewer's APPROVED deep-review verdict is signed
    Then the command refuses to sign
    And the command produces no verdict hash

  @slice-02 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario: The consolidated feature-end command surface is reachable through the single entry point
    Given an orchestrator at the feature-end of a feature with the reviewer signing key available
    When the consolidated feature-end command surface is probed
    Then the feature-end signing verb is reachable through the single entry point
    And the feature-end record emitter still works under the consolidated surface
