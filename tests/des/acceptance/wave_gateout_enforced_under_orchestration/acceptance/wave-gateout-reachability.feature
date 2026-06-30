@feature-wave-gateout-enforced-under-orchestration @walking_skeleton @driving_port @real-io
Feature: A wave-agent return under autonomous orchestration cannot close the wave unreviewed

  Under autonomous orchestration (a wave-agent dispatched via the Agent() tool),
  an architect who returns a DESIGN deliverable carrying only a DESIGN wave marker
  -- and no classic execution-log identifiers -- has the mandatory DESIGN review
  veto ACTUALLY FIRE: a missing review refuses the return, an approved review lets
  it through. Today the veto silently no-ops for such a return -- the return reaches
  the maintainer as "wave closed" though its review never ran. After the cure the
  same return is mechanically gated end-to-end, exactly as the maintainer trusts.

  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root, with the review verdict recorded
  through the REAL producer CLI (No Fixture Theater) -- no fixture authors the
  verdict, no mocking inside the hexagon.
    * Layer 3 composition -- the REAL `handle_subagent_stop` hook entry
      (subagent_stop_handler.py) reading a constructed wave-only return off stdin
      and routing it through the production `SubagentStopService.validate`
      (service_factory.create_subagent_stop_service). The observable is the hook
      decision: allow vs block, read as the process exit code.
    * Layer 3 subprocess -- the REAL `des record-design-review` producer CLI as a
      black-box process that records the architect's review verdict into the
      AT-completion ledger the gate-out seals against.

  Synthetic substrate (precondition state, NOT the SUT): a tmp work-tree carrying
  an armed DESIGN wave floor (.nwave/wave-active), a docs/feature/<id>/
  feature-delta.md the verdict seals against, and the AT-completion ledger the
  verdict is recorded into. The wave-only return carries a DESIGN wave marker and a
  project id, but NO classic execution-log step identifier -- the exact shape an
  Agent()-dispatched architect return carries.

  Real-Surface Binding:
    AT-1 -> handle_subagent_stop (subagent_stop_handler.py) via
            service_factory.create_subagent_stop_service; observable = exit code.
    AT-2 -> handle_subagent_stop reaching SubagentStopService.validate ->
            _gate_out_review_verdict -> ReviewVerdictGate.evaluate over the absent
            DesignReviewVerdict ledger record; observable = block (exit 2).
    AT-3 -> the same path with an approved DesignReviewVerdict recorded through the
            REAL `des record-design-review` producer CLI, sealed against the
            feature-delta hash; observable = allow (exit 0).

  # AT-1 (walking skeleton): the thinnest reachability vertical. An architect
  #   returning under Agent() orchestration (a DESIGN wave marker + a project id, no
  #   execution-log step identifier) and NO recorded review verdict must NOT be
  #   silently waved through -- the mandatory DESIGN review veto must refuse the
  #   return. Today the return never reaches the veto (the reachability gate closes
  #   first) so it is silently allowed -- this is the RED.
  @slice-01 @feature-wave-gateout-enforced-under-orchestration @AT-1 @error @contract-shape:unbounded-preservation
  Scenario: An architect returning under autonomous orchestration with no review is refused
    Given an architect is returning a DESIGN deliverable under autonomous orchestration
    And no DESIGN review has been recorded for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused

  # AT-2 (error path, the bug-mirroring assertion): the same architect return whose
  #   review verdict is ABSENT must read absence as a refusal -- never a silent pass.
  #   This NAMES the gate-out review-verdict seam reached through the real entry:
  #   the SubagentStop return reaches ReviewVerdictGate over an absent ledger record
  #   and degrades LOUD to a refusal. RED today: the return never reaches the veto.
  @slice-01 @feature-wave-gateout-enforced-under-orchestration @AT-2 @error @contract-shape:unbounded-preservation
  Scenario: A missing review verdict is read as a refusal, never a silent pass
    Given an architect is returning a DESIGN deliverable under autonomous orchestration
    And no DESIGN review has been recorded for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with an unreviewed-deliverable reason

  # AT-3 (happy path): after the architect's reviewer records an APPROVED verdict
  #   through the REAL producer CLI -- sealed against the feature-delta the architect
  #   returned -- the same orchestration return is ALLOWED. The record->return loop
  #   closes end-to-end. RED today: the return is allowed for the WRONG reason (it
  #   is silently allowed before the veto runs), so the allow is indistinguishable
  #   from the no-review allow -- the cure makes allow conditional on the verdict.
  @slice-01 @feature-wave-gateout-enforced-under-orchestration @AT-3 @contract-shape:unbounded-preservation
  Scenario: An architect return with an approved review verdict is allowed to close the wave
    Given an architect is returning a DESIGN deliverable under autonomous orchestration
    And the architect's reviewer has recorded an approved review for that deliverable
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is allowed
