@feature-oss-feature-end-emit-cli @slice-02
Feature: A reviewer's deep-review verdict is content-hashed into a deterministic verdict hash so the done-gate cannot be satisfied by theater
  As an nWave orchestrator running an atdd_pure feature-end cycle
  I want a `des feature-end sign` command that turns a REAL deep-review verdict
    -- the reviewer agent, its APPROVED or REJECTED decision, and its findings --
    into a deterministic content hash by sha256-ing the verdict region under the
    at_review_signing SSOT keylessly
  So that the hash that feeds `des emit-feature-end` is a genuine content hash over
    a real review (never a minted constant), a sign request with no real review
    is loudly refused, key absence is a non-event, and the deep-review leg of the
    done-gate is mechanically satisfiable without theater

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
  # content-hashes it via sha256(canonical_signed_json(record, SIGNED_FIELDS)).
  # A sign request with no real verdict / a malformed-or-empty verdict is REFUSED
  # (exit non-zero); no hash is produced. Key absence is a non-event (OSS
  # demotion S4): the hash is deterministic, keyless.
  #
  # SINGLE ENTRY POINT (DDD-7, AD-26 1:1 mirror): the feature-end subcommands
  # consolidate under one `des feature-end <verb>` namespace dispatched through
  # the one `des.cli.__main__` dispatcher + the gate catalog. The consolidated
  # surface is reachable and slice-01's `emit` still works under it (back-compat).
  #
  # Driving port: the real `des feature-end sign` subcommand, invoked over the
  # single `des` entry point as a subprocess against a real git working tree
  # (Mandate-13 driving-port-only, Layer 3 subprocess -- the SAME surface as
  # slice-01). The produced hash is verified genuine by an INDEPENDENT recompute
  # via sha256(canonical_signed_json(...)) (the audit SUBSTRATE the slice-01
  # consumer reads, not the SUT). Example-only, no PBT (Mandate 9/11: a
  # real-I/O layer-3 surface).
  #
  # @coupled: every scenario pins ONE driving-port contract -- the consolidated
  # `des feature-end sign` command's input/output behavior plus its dispatcher
  # reachability -- and cannot be split without severing that single-command
  # closure.

  @slice-02 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: Signing with no deep-review verdict at all is refused
    Given an orchestrator at the feature-end of a feature
    When a verdict is signed with no deep-review verdict at all
    Then the command refuses to sign
    And the command produces no verdict hash

  @slice-02 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario Outline: Signing a non-real deep-review verdict is refused
    Given an orchestrator at the feature-end of a feature
    When a verdict is signed with a <defect> deep-review verdict
    Then the command refuses to sign
    And the command produces no verdict hash

    Examples: non-real verdict inputs
      | defect          |
      | empty-agent     |
      | unknown-verdict |
      | missing-verdict |

  @slice-02 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario: The consolidated feature-end command surface is reachable through the single entry point
    Given an orchestrator at the feature-end of a feature
    When the consolidated feature-end command surface is probed
    Then the feature-end signing verb is reachable through the single entry point
    And the feature-end record emitter still works under the consolidated surface
