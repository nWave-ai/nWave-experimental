@feature-wave-gateout-enforced-under-orchestration @driving_port @real-io
Feature: A closed wave is attested by a current sealed review verdict, ungameably

  slice-05 (regression-lock, GREEN-on-keystone). The un-gameable attestation
  property (cure #2): a per-wave review-verdict ledger record, SEALED against the
  feature-delta hash, is REQUIRED for wave closure under autonomous orchestration.
  The mechanism (ReviewVerdictGate.evaluate over the sealed ledger records) already
  EXISTS; this slice LOCKS the un-gameable property end-to-end through the REAL hook
  entry:

    * ABSENT verdict   -> the wave cannot close, for ANY governed wave (the
      cross-wave invariant). Absence reads as a refusal -- degrade-LOUD, never a
      silent pass.
    * STALE verdict    -> an APPROVED verdict recorded then the feature-delta CHANGED
      (the deliverable was edited after approval) -- the seal no longer matches -- is
      a refusal. The operator cannot record an approval, then edit the deliverable,
      and still close the wave on the stale approval. degrade-LOUD INDETERMINATE
      ("stale-artefact"), never silent-allow.
    * CURRENT approved -> only an artefact-current sealed approved verdict closes the
      wave (the discriminating anchor so the refusals are not unconditional).

  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root; the review verdict recorded
  through the REAL `des record-<wave>-review` producer CLI (No Fixture Theater),
  sealed against the feature-delta hash at record time. The stale arm MUTATES the
  feature-delta after recording -- exactly as an operator editing the deliverable
  post-approval would. Reuses the slice-01/02..04 driving primitives.

  Real-Surface Binding:
    AT-10 -> handle_subagent_stop reaching SubagentStopService.validate ->
             _gate_out_review_verdict -> ReviewVerdictGate.evaluate(None) ->
             INDETERMINATE("absent") over the absent ledger record, for design /
             devops / discuss; observable = block (degrade-LOUD, cross-wave).
    AT-11 -> the same path with an approved verdict recorded through the REAL
             producer CLI, THEN the feature-delta mutated -> ReviewVerdictGate
             reads feature_delta_hash drift -> INDETERMINATE("stale-artefact");
             observable = block (the un-gameable seal property).
    AT-12 -> the same path with an artefact-current approved verdict (no mutation)
             -> ReviewVerdictGate -> PASS; observable = allow (the anchor).

  @slice-05 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario Outline: A wave-agent return with no recorded review cannot close any wave
    Given a <wave> wave-agent is returning a deliverable under autonomous orchestration
    And no review has been recorded for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with a missing-review reason

    Examples:
      | wave    |
      | design  |
      | devops  |
      | discuss |

  @slice-05 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A return whose approval went stale when the deliverable changed cannot close the wave
    Given a design wave-agent is returning a deliverable under autonomous orchestration
    And the reviewer recorded an approval then the deliverable was changed
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with a stale-seal reason

  @slice-05 @feature-wave-gateout-enforced-under-orchestration @contract-shape:unbounded-preservation
  Scenario: A return with a current sealed approval is allowed to close the wave
    Given a design wave-agent is returning a deliverable under autonomous orchestration
    And the reviewer recorded a current approval for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is allowed
