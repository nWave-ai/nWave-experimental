@feature-wave-gateout-enforced-under-orchestration @driving_port @real-io
Feature: A DEVOPS wave-agent return under orchestration reaches its review veto

  slice-02 (regression-lock, GREEN-on-keystone). The keystone slice-01 delivered
  the FULL wave-parametric reachability route, not just the DESIGN gate-out:
  _resolve_des_context accepts any declared_wave in WAVE_VOCABULARY, and the
  gate-out arms for _REVIEW_GATE_OUT_WAVES = {discuss, design, devops}. So a
  DEVOPS wave-agent returning via Agent() ALREADY reaches verify-devops-review on
  the current committed code. These scenarios LOCK that coverage: a return with no
  recorded DEVOPS review is refused (the verify-devops-review veto fires, reading
  the absent verdict as a refusal -- degrade-LOUD); an approved DEVOPS review
  (recorded through the REAL `des record-devops-review` producer CLI, sealed vs the
  feature-delta hash) lets the same return close the wave.

  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root; the review verdict recorded
  through the REAL producer CLI (No Fixture Theater). Reuses the slice-01 driving
  primitives. Real-Surface Binding:
    AT-04 -> handle_subagent_stop reaching SubagentStopService.validate ->
             _gate_out_review_verdict -> ReviewVerdictGate.evaluate over the absent
             DevopsReviewVerdict ledger record; observable = block (degrade-LOUD).
    AT-05 -> the same path with an approved DevopsReviewVerdict recorded through the
             REAL `des record-devops-review` producer CLI; observable = allow.

  @slice-02 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A devops return under orchestration with no review is refused
    Given a platform-architect is returning a DEVOPS deliverable under autonomous orchestration
    And no DEVOPS review has been recorded for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with a missing-devops-review reason

  @slice-02 @feature-wave-gateout-enforced-under-orchestration @contract-shape:unbounded-preservation
  Scenario: A devops return with an approved review verdict is allowed to close the wave
    Given a platform-architect is returning a DEVOPS deliverable under autonomous orchestration
    And the reviewer has recorded an approved DEVOPS review for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is allowed
