@feature-oss-review-verdict-demotion @coupled:slice-04-keyless-feature-end-hash
Feature: The feature-end deep-review produces a deterministic content hash with no key and refuses to mint theater

  At the end of an atdd_pure feature the reviewer's deep-review verdict -- the
  agent, its APPROVED or REJECTED decision, its findings -- is turned into a
  verdict hash that binds the verdict to the done-gate record. In the OSS threat
  model the key holder and the would-be forger are the same person, so keying
  that hash buys no guarantee -- it only forces a signing key to be provisioned
  before the feature-end can certify at all. This slice DEMOTES the feature-end
  verdict hash from "HMAC-signed under the reviewer key" to "deterministic
  content hash over the verdict": the anti-theater invariant is preserved in
  full -- a verdict with no named reviewer or no known decision is still
  refused, no hash minted -- only the keyed cryptography goes, and key absence
  becomes a non-event.

  The two scenarios below form one coupled AT group
  (@coupled:slice-04-keyless-feature-end-hash): the APPROVED verdict sealed into
  a keyless content hash the emitter accepts, and the REJECTED verdict that still
  seals with NO key present, together assert one indivisible contract -- "the
  content binds the hash, and key absence is a non-event". Demoting the hash to
  content without proving the emitter still accepts it would ship a hash the
  done-gate cannot read; proving the content hash without proving key absence no
  longer refuses would keep the very provisioning friction this demotion removes.

  The anti-theater refusals (an unnamed reviewer / an unknown or missing verdict
  yields no hash) are RETAINED, not changed -- at tip the signer already checks
  the real-verdict preconditions BEFORE it resolves a key, so those refusals are
  ALREADY keyless and fire for the anti-theater reason today. This slice does NOT
  re-pin them as an active-RED scenario (they would pass at tip -- not missing
  functionality); they stay witnessed keylessly by the re-authored residue of the
  oss-feature-end-emit-cli slice-02 producer suite (the supersede inventory in the
  feature-delta S4 section). Adding a passing refusal scenario here would grow the
  coupled group to re-witness an unchanged behavior -- against per-feature bloat
  removal (the S1 content-seal precedent).

  # Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  #   row "feature_end_sign_service (verdict_hash): keyed HMAC -> deterministic
  #   content hash; anti-theater preserved by non-empty-reviewer + known-verdict
  #   checks". feature-delta D-feature-end-hash + the S4 slice-plan row.
  # The surface being demoted: src/des/application/feature_end_sign_service.py
  #   -- sign_feature_end_review HMACs via compute_verdict_hmac(signed_region,
  #   load_signing_key(repo)) (lines 108-121) and REFUSES when the key is
  #   unresolvable (108-114). Post-demotion verdict_hash =
  #   sha256(canonical_signed_json(signed_region, SIGNED_FIELDS)); no key load,
  #   no key-unresolvable refusal; the non-empty-reviewer + known-verdict refusals
  #   (90-106) stay verbatim.
  # Driving port (Mandate 13, Layer 3 subprocess): the production
  #   `des feature-end sign` subcommand, invoked over the single `des` entry
  #   point as a subprocess against a real git working tree -- the SAME driving
  #   surface as the oss-feature-end-emit-cli slice-02 producer. NO direct-domain
  #   import of sign_feature_end_review or compute_verdict_hmac at the step
  #   boundary; the produced hash is read off the command's stdout and the
  #   genuineness oracle recomputes the content hash KEYLESSLY via
  #   sha256(canonical_signed_json(...)) -- the observable substrate the emitter
  #   consumes, not the SUT.
  # Layer 3 (subprocess/FS acceptance): the real filesystem (tmp_path) is the
  #   only driven adapter -> @real-io; example-only, no PBT (Mandate 9 v2 / 11).
  #
  # RED-for-right-reason (pre-DELIVER fail-for-right-reason gate). At tip
  #   (0d8a76a91) the signer STILL loads a signing key and HMACs the verdict, and
  #   STILL refuses when the key is unresolvable. The S4 fixtures provision NO
  #   key anywhere, so:
  #   * KEYLESS_CONTENT_HASH -- with no key the today-signer hits the
  #     key-unresolvable refusal (108-114) and produces NO hash; the scenario
  #     expects a deterministic content hash the emitter accepts -> semantic
  #     AssertionError (the demotion must drop the key load and hash the content).
  #     Even if a key were present, the today-signer emits the HMAC, which does
  #     NOT equal the keyless content hash the oracle recomputes -> the
  #     genuineness assertion fails. The RED direction is "today refuses (or
  #     produces a keyed hash) where post-demotion it must produce the content
  #     hash".
  #   * KEY_ABSENCE_IS_A_NON_EVENT -- with a valid named reviewer + known verdict
  #     and NO key, the today-signer REFUSES (key unresolvable, 108-114); the
  #     scenario expects success with a content hash -> semantic AssertionError
  #     (the demotion must make key absence a non-event).
  #   No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2 -- documented here per the AT-completeness gate):
  #   feature-end signer states = {SIGN_REQUESTED}.
  #     event named-reviewer + known-verdict, no key -> CONTENT_HASH (a
  #                                               deterministic sha256 hex the
  #                                               emitter accepts; key absence is
  #                                               a non-event)
  #     event unnamed-reviewer | unknown-verdict ----> REFUSED (anti-theater, no
  #                                               hash; the refusal names the
  #                                               real-verdict cause, never a key)

  Background:
    Given an orchestrator at the feature-end of a feature with no reviewer signing key anywhere

  @slice-04 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A reviewer's approval is sealed into a keyless content hash the emitter accepts
    When the reviewer's APPROVED deep-review verdict is sealed
    Then the command produces a deterministic content hash over that verdict
    And the content hash is accepted by the feature-end record emitter
    And the sealing command reports success
    And no reviewer signing key was read

  @slice-04 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Sealing a real verdict succeeds with the signing key absent because key absence is a non-event
    When the reviewer's REJECTED deep-review verdict is sealed
    Then the command produces a deterministic content hash over that verdict
    And the sealing command reports success
    And no reviewer signing key was read
