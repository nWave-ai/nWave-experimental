@feature-oss-hook-side-phase-injection @slice-02
Feature: The DISTILL dispatch is marker-enforced and DELIVER leaves a symmetric completion record
  As an nWave operator running an atdd_pure feature hands-off
  I want a DISTILL acceptance-designer dispatch to be refused before it runs
    unless it carries a complete, whole-feature marker set, and I want a
    verified slice commit to leave the same kind of durable completion record
    at DELIVER-exit as DISTILL leaves at DISTILL-exit
  So that "a DISTILL dispatch was well-formed" and "a slice was delivered" are
    both mechanical consequences of the marker set and the ledger -- never an
    agent's narrative claim -- and so the DISTILL-exit and DELIVER-exit
    success records are symmetric evidence of the same rigor

  # slice-02 of oss-hook-side-phase-injection -- DISTILL dispatch marker
  # enforcement (G-DISTILL-PRE, PreToolUse) + DELIVER-exit symmetry
  # (G-DELIVER-EXIT, SubagentStop G_COMMIT). Builds on the slice-01
  # walking-skeleton G-DISTILL-EXIT gate (SHIPPED).
  #
  # RED scaffold (ADR-028): these ATs FAIL on master for the RIGHT reason.
  #   AT-1: a complete D_DISTILL dispatch already classifies 'valid' and is
  #         allowed today (the positive decision-table row), pinning that the
  #         new DISTILL-specific marker branch does NOT regress the allow path.
  #   AT-2: a D_DISTILL dispatch missing DES-PROJECT-ID, or carrying a slice-N
  #         scope, is blocked TODAY with the GENERIC `AtddPureMarkerSetIncomplete`
  #         event -- not the DISTILL-specific `DistillDispatchMarkerSetIncomplete`
  #         this slice introduces. The AT fails on the event-name assertion -- a
  #         semantic AssertionError, never a collection / import / setup error.
  #   AT-3: a verified G_COMMIT return emits ONLY `SliceCommitVerified` today;
  #         no `WorkflowPhaseCompletedGCommit` symmetric terminal is written, so
  #         the read-back of that record is absent -- a semantic AssertionError.
  # They PASS once slice-02 lands: a D_DISTILL marker-presence branch in the
  # PreToolUse intercept emitting `DistillDispatchMarkerSetIncomplete`, plus a
  # `WorkflowPhaseCompletedGCommit` emission alongside `SliceCommitVerified` in
  # `_handle_g_commit_exit_gate` (and the `append_workflow_phase_completed_g_commit`
  # ledger writer, phase-in-event-name MAJOR-1).
  #
  # HARD INVARIANT (hook-can't-spawn-agent): every gate only ALLOWS / BLOCKS /
  # EMITS. No scenario asserts a hook dispatched an agent -- it cannot. The
  # observable surface is the block decision, the exit code, and the ledger
  # record (SSOT = the M7 AtCompletionLedger, NOT a second event-log).
  #
  # G-DISTILL-PRE state model (C2/C5): the gate evaluates a single D_DISTILL
  # dispatch marker set and resolves to ALLOW or BLOCK. The decision table:
  #   project-id present + feature-end scope (coherent XOR)  -> ALLOW
  #   project-id absent                                      -> BLOCK
  #   slice-N scope on a feature-end phase (incoherent XOR)  -> BLOCK
  #
  # Driving ports (Mandate-13 driving-port-only, Layer 3/4):
  #   AT-1/AT-2 drive the real `handle_pre_tool_use` PreToolUse hook subprocess.
  #   AT-3 drives the real `handle_subagent_stop` G_COMMIT path subprocess.
  # Example-only, no PBT (Mandate 9/11).

  @slice-02 @driving_port @real-io @contract-shape:pure-function
  Scenario: A complete DISTILL dispatch is allowed to run
    Given a DISTILL acceptance-designer dispatch carrying a complete marker set
    When the PreToolUse hook validates the dispatch
    Then the DISTILL dispatch gate allows the dispatch
    And the hook allows with exit code zero

  @slice-02 @driving_port @real-io @error @contract-shape:pure-function
  Scenario Outline: An incompletely-marked DISTILL dispatch is refused before it runs
    Given a DISTILL acceptance-designer dispatch that <defect>
    When the PreToolUse hook validates the dispatch
    Then the DISTILL dispatch gate reports an incomplete DISTILL dispatch marker set
    And the hook blocks with exit code two

    Examples:
      | defect                                                       |
      | is missing its project identifier                            |
      | is scoped to a single slice instead of the whole feature     |

  # The DELIVER-exit symmetry scenario that stood here asserted that the U2
  # per-slice commit exit gate records a verified slice commit and writes a
  # WorkflowPhaseCompletedGCommit record. That gate is gone: a returning
  # crafter is no longer intercepted, and no hook writes those records.
