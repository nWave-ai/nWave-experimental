@feature-oss-hook-side-phase-injection @slice-01
Feature: The DISTILL wave does not close until every planned slice has a signed review
  As an nWave operator running an atdd_pure feature hands-off
  I want the DISTILL->DELIVER transition to be refused until every planned
    slice carries a signed acceptance-test review verdict, and to leave a
    durable success record when it is complete
  So that "DISTILL is done" is a mechanical consequence of the signed verdict
    set, never an agent's narrative claim -- and so a feature that completed
    DISTILL leaves the same kind of evidence as one that was blocked

  # slice-01 of oss-hook-side-phase-injection -- the walking-skeleton, thinnest
  # end-to-end hook-enforced DISTILL-exit gate (D1 keystone). The
  # acceptance-designer return is intercepted at the SubagentStop boundary and
  # routed to the new G-DISTILL-EXIT gate.
  #
  # RED scaffold (ADR-028): these ATs FAIL on master for the RIGHT reason --
  # `D_DISTILL` is not yet a member of the `ATDDPurePhase` closed-world enum
  # and the handler has no `_handle_distill_exit_gate` branch, so a `D_DISTILL`
  # return parses to `atdd_pure_phase=None` and falls through to the generic
  # atdd_pure handler, which ALLOWS without emitting a phase event. They PASS
  # once slice-01 lands the three coupled production edits: `D_DISTILL` into the
  # enum + `_FEATURE_END_PHASES`, `append_workflow_phase_completed`, and the
  # `_handle_distill_exit_gate` SubagentStop branch.
  #
  # HARD INVARIANT (hook-can't-spawn-agent): the gate only BLOCKS / EMITS. No
  # scenario asserts the hook dispatched the reviewer -- it cannot. The
  # observable surface is the block decision, the exit code, and the ledger
  # record (SSOT = the M7 AtCompletionLedger, NOT a second event-log).
  #
  # SUT gate state model (C2): the gate evaluates a single `D_DISTILL` return
  # and resolves to ALLOW or BLOCK. Two input axes drive it:
  #   slice-plan table   in {PRESENT, UNPARSEABLE}      -> denominator resolve
  #   signed-verdict set in {COMPLETE, MISSING_ONE}     -> completeness check
  # The gate ALLOWS exactly one combination: (PRESENT, COMPLETE). The three
  # scenarios pin the single ALLOW + the symmetric success terminal, one
  # BLOCK-on-incomplete-verdict (pinning the `_slice_plan_slice_ids`
  # denominator, MAJOR-2), and one fail-closed BLOCK-on-unparseable-plan (no
  # vacuous pass) -- the materially-distinct decision-table rows (C5).
  #
  # Driving port: the real `handle_subagent_stop` SubagentStop hook, invoked
  # over its JSON stdin protocol as a subprocess against a real git repo, a
  # real feature-delta `[REF] Slice Plan`, and a real AT-completion ledger
  # (Mandate-13 driving-port-only, Layer 3/4). Example-only, no PBT
  # (Mandate 9/11).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A complete verdict set lets DISTILL close and leaves a completion record
    Given a DISTILL feature whose plan declares every slice
    And every planned slice has a signed acceptance-test review
    And the acceptance designer returns from the DISTILL phase
    When the SubagentStop hook processes the return
    Then the DISTILL-exit gate allows the transition
    And a DISTILL phase-completed record is written to the ledger
    And the hook exits with code zero

  @slice-01 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A planned slice missing its signed review keeps DISTILL open
    Given a DISTILL feature whose plan declares every slice
    And every planned slice except one has a signed acceptance-test review
    And the acceptance designer returns from the DISTILL phase
    When the SubagentStop hook processes the return
    Then the DISTILL-exit gate reports an incomplete verdict set
    And no DISTILL phase-completed record is written to the ledger
    And the hook exits with code zero

  @slice-01 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: An unreadable slice plan refuses DISTILL closure rather than passing vacuously
    Given a DISTILL feature whose plan cannot be read
    And every planned slice has a signed acceptance-test review
    And the acceptance designer returns from the DISTILL phase
    When the SubagentStop hook processes the return
    Then the DISTILL-exit gate reports an unparseable slice plan
    And no DISTILL phase-completed record is written to the ledger
    And the hook exits with code zero
