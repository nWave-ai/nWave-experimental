@feature-oss-hook-side-phase-injection @slice-03
Feature: The reviewer trailer is a mechanical projection of the signed review, not a hand-typed claim
  As an nWave operator authoring an atdd_pure slice commit
  I want the reviewer attribution carried on the commit to be DERIVED from the
    signed review record in the ledger -- both the reviewer line and the matching
    verdict payload it is checked against -- so that the same projection the
    orchestrator embeds is the same one the verifier later recomputes
  So that "this slice was reviewed and approved" is a mechanical consequence of
    the signed ledger record -- never an agent's hand-typed narrative claim --
    and so a forged, drifted, or unpaired attribution fails closed at delivery
    rather than slipping through silently

  # slice-03 of oss-hook-side-phase-injection -- mechanical HMAC trailer
  # projection (friction #35 closure, option (a): OFF the commit lifecycle).
  # The new `scripts/cli/derive_review_trailer.py` CLI is an orchestrator-invoked
  # ledger projection -- NOT a hook, NOT a commit hook. It reads the slice's
  # signed `ATReviewVerdict` record and projects the verifier's EXACTLY-four-field
  # canonical verdict (`verdict`, `timestamp`, `reviewer_agent_id` from the
  # record's signed region; `findings_summary` from its unsigned region), REUSING
  # `verify_commit_trailers.canonical_verdict_json` (the verifier's own serializer
  # = SSOT for what the git-side U2 check recomputes -- NOT the producer's 7-field
  # `canonical_at_review_json`, which is over an INCOMPATIBLE key set). It emits
  # BOTH a `Reviewed-by: <agent>:<hmac>` line AND the matching
  # `Verdict-Payload: {...}` line for the orchestrator to embed.
  #
  # RED scaffold (ADR-028): the file-head `@skip @pending` tags make every
  # scenario COLLECT but not run-green; DELIVER's RED phase strips them one slice
  # at a time. These ATs FAIL for the RIGHT reason when unskipped:
  # `scripts/cli/derive_review_trailer.py` does not exist yet, so the derive
  # subprocess raises a module-not-found and the projection is ABSENT -- AT-1 then
  # fails on the pair-emitted assertion; AT-2/AT-3 fail because no derived pair
  # reaches the verifier. Every failure is a semantic AssertionError against the
  # observable projection / round-trip outcome, never a collection / import error
  # inside the test code itself (the composition imports only test-local types
  # plus the already-shipped AtCompletionLedger + at_review_verdict producer, so
  # the suite COLLECTS cleanly). They PASS once slice-03 lands the derive CLI.
  #
  # The single-serializer invariant -- derive and verify share
  # `verify_commit_trailers.canonical_verdict_json` -- is the mechanical
  # anti-drift guard. AT-2's derive->verify round-trip IS that guard: a GREEN
  # round-trip is structurally impossible under any field-set drift or key
  # mismatch (this was un-representable under the old 7-field spec).
  #
  # HARD INVARIANT (NOT a hook): the derive CLI only READS the ledger record and
  # PROJECTS the trailer pair to stdout. No scenario asserts it mutated the
  # ledger or dispatched an agent -- it cannot. The orchestrator embeds the
  # lines; the existing git-side `verify_commit_trailers` (U2) is the fail-closed
  # check.
  #
  # Round-trip state model (C2/C6): the git-side verifier resolves a derived pair
  # to one of a closed set of outcomes. The decision table:
  #   matching pair, same key                          -> exit 0 (verifies)
  #   different signing key at verify time             -> exit 4 (hash mismatch)
  #   extra key in embedded payload (shape divergence) -> exit 6 (malformed pair)
  #   Reviewed-by with no paired Verdict-Payload        -> exit 6 (malformed pair)
  #
  # NOTE on the shipped verifier's refuse taxonomy (the closed error set this
  # AT-3 set witnesses): an extra/missing key is a SHAPE violation, not a hash
  # mismatch. verify_commit_trailers.canonical_verdict_json RAISES on any
  # extra/missing key (verify_commit_trailers.py:86-93), caught at :230-232 ->
  # exit 6 -- BEFORE any HMAC compare. So only a TRUE in-shape signature failure
  # (a signing-key mismatch over the SAME 4 fields) yields exit 4. The three
  # examples deliberately witness BOTH refuse leaves: one exit-4 (hash mismatch)
  # and two distinct exit-6 causes (extra-key shape divergence + unpaired-trailer
  # count mismatch) -- the full refuse taxonomy of the SHIPPED verifier.
  #
  # Driving ports (Mandate-13 driving-port-only, Layer 3 subprocess):
  #   AT-1 drives the real `derive_review_trailer` CLI subprocess.
  #   AT-2/AT-3 chain the derived pair into the real `verify_commit_trailers` CLI
  #   subprocess (derive->verify round-trip). Ledger seed/read is the adjudicated
  #   precondition-substrate carve-out (through the shipped producer + reader).
  # Example-only, no PBT (Mandate 9/11: layer-3 subprocess, real I/O).

  @slice-03 @driving_port @real-io @contract-shape:pure-function
  Scenario: The reviewer attribution is derived as a complete pair from the signed review
    Given a signed acceptance-test review for a slice is recorded in the ledger
    When the orchestrator derives the reviewer attribution for that slice
    Then a reviewer attribution line is projected for that review
    And a matching verdict payload line is projected alongside it
    And the derivation succeeds with exit code zero

  @slice-03 @driving_port @real-io @contract-shape:pure-function
  Scenario: The derived attribution is accepted by the delivery verifier
    Given a signed acceptance-test review for a slice is recorded in the ledger
    And the orchestrator has derived the reviewer attribution for that slice
    When the derived attribution is embedded in a slice commit and checked at delivery
    Then the delivery verifier accepts the attribution as authentic
    And the verifier reports success with exit code zero

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario Outline: A tampered or unpaired attribution is refused at delivery
    Given a signed acceptance-test review for a slice is recorded in the ledger
    And the orchestrator has derived the reviewer attribution for that slice
    When the derived attribution is embedded in a slice commit but <fault>
    Then the delivery verifier refuses the attribution as <outcome>
    And the verifier reports the refusal with exit code <code>

    Examples:
      | fault                                                                  | outcome           | code |
      | the verifier is given a different signing key                          | tampered          | 4    |
      | an extra field is added to the embedded verdict payload                | a malformed pair  | 6    |
      | the reviewer line is embedded without its matching verdict payload     | a malformed pair  | 6    |
