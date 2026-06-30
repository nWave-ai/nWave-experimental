@feature-oss-review-verdict-demotion @coupled:slice-06-verify-repurpose-and-derive-delete
Feature: The delivery verifier audits a slice's review record and the trailer-derivation CLI is gone

  This final slice consolidates the demotion's CLI surface. Two decisions land
  together. First, the orchestrator-invoked trailer-derivation CLI
  (derive_review_trailer) is HARD-DELETED -- with no signing key there is no
  HMAC trailer to project, so the producer of those trailers has no remaining
  job. Second, the commit-trailer verifier (verify-commit-trailers) is
  REPURPOSED: instead of recomputing an HMAC over Reviewed-by/Verdict-Payload
  git trailers, it now AUDITS a commit's review by reading the same
  AT-completion ledger record the slice gate reads, and reaching the SAME
  verdict the slice gate reaches.

  The verifier is an audit window over the gate's verdict logic, never a second
  verifier. It resolves a commit's Slice-Id trailer to a slice, then asks the
  one record-presence check the carpaccio gate already runs: is there a
  well-formed APPROVED review record that binds the slice's AT set and content
  seal? One check, one home. A record the gate refuses must be refused by the
  audit window with the very same reason -- if the audit window could ever
  reach a different verdict than the gate, it would be a second verifier with
  its own drift, exactly the false-confidence oracle this slice rejects.

  The four scenarios below form one coupled AT group
  (@coupled:slice-06-verify-repurpose-and-derive-delete): the audit-clears path,
  the audit-refuses-with-the-gate's-reason path (the no-drift spine), the
  nothing-to-audit honest-indeterminate path (a commit with no slice trailer is
  never silently cleared), and the derive-CLI-is-gone deletion safety all assert
  one indivisible contract -- "the review record is the single source of the
  verdict, the audit window reuses the gate's reading of it, an absent trailer
  is honestly nothing-to-audit, and the keyed trailer-derivation surface no
  longer exists". Greening the clears path without the no-drift path would ship
  an audit window free to diverge from the gate; greening either without the
  nothing-to-audit path would re-introduce the silent-pass class this feature
  kills (a no-trailer commit vacuously clearing); asserting the deletion without
  the repurpose would leave the verifier still recomputing an HMAC over a
  trailer no producer emits anymore. coupling_justification recorded in the
  slice plan.

  # Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  #   (D-verify-repurpose + D-derive-hard-delete; Ale "ok 1-2-3").
  # S6 DESIGN open question RESOLVED (repurpose shape): repurpose-IN-PLACE --
  #   keep the verify-commit-trailers name + dispatcher row + gate file; the CLI
  #   reuses check_at_review's record logic. The "no second verifier, no
  #   parallel gate" Out-of-Scope constraint FORCES in-place over a dedicated
  #   new ledger-verify entry (a new entry + retiring the old would be a
  #   re-architecture against ONE-home + LOC-neutral).
  # Driving port (Mandate 13, Layer 3 subprocess): the production des dispatcher
  #   `des verify-commit-trailers --commit <ref>` invoked as a real subprocess.
  #   The carpaccio gate `des carpaccio-slice-gate` is co-driven in the no-drift
  #   scenario to prove the two surfaces agree. NO direct-domain import of
  #   check_at_review or any verify-commit-trailers internal in the step
  #   composition.
  # Layer 3 (subprocess/FS acceptance): real filesystem (tmp_path) + real git
  #   repo (the commit Slice-Id trailer is read through the production git
  #   commit-read port). Example-only, no PBT (Mandate 9 v2 / 11).
  # Contract axes RESOLVED from the carpaccio gate's existing closed vocabulary
  #   where forced: a present+APPROVED+bound record -> cleared; a record the
  #   gate refuses -> the SAME ATReviewGateRejected reason
  #   (absent/not-approved/stale-at-set/stale-at-content). git-absent ->
  #   the existing INDETERMINATE refusal (the port's degrade-LOUD).
  # The two formerly-escalated axes are RESOLVED at DESIGN (architect-final,
  #   2026-06-11; the feature-delta S6 resolved-axes block is the SSOT):
  #   A-absent-trailer -- a commit with NO Slice-Id trailer -> distinct
  #   INDETERMINATE, exit 7 (cannot-evaluate), reason "no Slice-Id trailer --
  #   nothing to audit" (never a silent exit-0, never a BLOCK; non-slice
  #   commits are legitimate). PINNED by the 4th scenario below; reuses the
  #   verifier's already-existing exit-7 INDETERMINATE channel.
  #   A-multi-trailer -- >=2 Slice-Id trailers -> audit ALL via
  #   des.domain.slice_id_trailer.extract_slice_ids (the blessed F-07
  #   batched-commit shape), fail-closed, first refusal wins with that
  #   slice's reason; trailers-present-but-none-valid collapses into
  #   A-absent-trailer. RESOLVED-in-contract; the squash-flow witness AT is
  #   a deferred follow-on (backlog).

  Background:
    Given a delivered slice commit for an atdd_pure feature with no reviewer signing key anywhere

  @slice-06 @driving_port @walking_skeleton @real-io @contract-shape:unbounded-preservation
  Scenario: The delivery verifier clears a commit whose slice was reviewed and approved
    Given a slice commit whose slice has an approved review verdict recorded with no signature
    When the operator audits that commit with the delivery verifier
    Then the verifier reports the slice's review as present and approved
    And the verifier reports success with exit code zero
    And the audit writes no file in the repository

  @slice-06 @driving_port @error @real-io @contract-shape:bounded-change
  Scenario: The delivery verifier refuses a commit whose review was not approved with the gate's own reason
    Given a slice commit whose slice has a review verdict recorded that was not approved
    When the operator audits that commit with the delivery verifier
    And the operator runs the carpaccio slice gate for the same slice
    Then both surfaces refuse the slice for the reason "not-approved"
    And the audit window and the gate agree on the refusal reason

  @slice-06 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: A commit carrying no Slice-Id trailer is reported as nothing-to-audit, not silently cleared
    Given the audited commit carries no Slice-Id trailer
    When the operator audits that commit with the delivery verifier
    Then the audit is refused as indeterminate with nothing to audit
    And the indeterminate reason names the missing Slice-Id trailer

  @slice-06 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The reviewer-trailer derivation command no longer exists
    Given the demotion has removed the reviewer-trailer derivation command
    When the operator looks for the reviewer-trailer derivation command
    Then the reviewer-trailer derivation command is absent from the codebase
    And no slice can invoke it to project a signed reviewer trailer
