@feature-nwave-flow-v2-enforcement @slice-07d
Feature: A wave entered without the explicit command is still gated
  As an nWave maintainer who needs enforcement on every runtime
  I want a dispatch that declares its wave to arm enforcement by itself when
    the submission anchor never fired -- gated in that same pass -- while an
    operator's explicit arming is never overwritten and ad-hoc work without a
    usable wave declaration stays completely untouched
  So that the S2 gap closes even on runtimes whose prompt-submission hook is
    observe-only or missed, a declared wave can only ADD gating (never remove
    it), and non-wave work never pays a false-positive toll

  # slice-07d of nwave-flow-v2-enforcement -- INFERRED fallback strand (F4
  # NORMATIVO-per-la-claim-cross-runtime). Follows the DESIGN slice-07d
  # code-design verbatim (`## Wave: DESIGN / [REF] slice-07d code-design
  # (INFERRED fallback strand -- F4, closes S2 cross-runtime)`,
  # architect-reviewer APPROVED in the joint 07c/07d review a06237ced).
  #
  # DRIVING PORT (Mandate-13): Layer 4 wiring -- the REAL PreToolUse hook
  # adapter (`claude_code_hook_adapter pre-tool-use`, subprocess, hook-protocol
  # stdin JSON) over a tmp project_root; AT-2 arms first via the REAL
  # prompt-submission anchor subprocess. The hook adapter is the composition
  # seat of the net-new fallback branch (reader NoWaveActive + valid
  # declared_wave -> arm_inferred -> proceed as wave-entering in the SAME
  # pass), so it IS the real entry point for the declared seams. Observables:
  # hook exit/reason + the floor record at `.nwave/wave-active/active.json`.
  #
  # §22.7 COHERENCE: the `DES-WAVE` declaration is NEVER the active-wave
  # source and NEVER an authorization -- it is consumed ONLY to ARM
  # enforcement (provenance=INFERRED tags the lower trust class; I3 dominance
  # bounds it). Fail direction: a lying declaration can only ADD gating;
  # an absent/garbage one leaves S1 untouched (strand-2 catches at the seam).
  #
  # RED-for-right-reason: `DES-WAVE` parsing (`DesMarkers.declared_wave`),
  # `WaveActivationService.arm_inferred` and the adapter fallback branch DO
  # NOT exist at HEAD -- the declaration is an inert comment, an empty floor
  # stays empty (S1 allow), so AT-1 fails semantically (ALLOWED + no floor
  # record where same-pass INFERRED gating is expected). AT-2 / AT-3 are
  # preservation-GREEN at HEAD (no-clobber + K2 already hold) and pin the
  # contract end-to-end through DELIVER.
  # No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2):
  #   floor states = {NO_WAVE, ARMED(COMMAND), ARMED(INFERRED)}.
  #     NO_WAVE         --(dispatch declares valid wave, product model absent)-->
  #                       ARMED(INFERRED), entry_pending=false, gate-IN runs SAME
  #                       pass (self-entry) -> ALLOW (greenfield advisory, slice-05
  #                       declass; the arm still happens -- only the veto relaxes)
  #     ARMED(COMMAND)  --(dispatch declares a wave)------> unchanged (I3:
  #                       INFERRED never clobbers COMMAND, end-to-end)
  #     NO_WAVE         --(no/garbage declaration)--------> NO_WAVE (no arm,
  #                       no record, allow untouched -- K2/S1)

  # AT-1 -- the fallback arm + same-pass self-entry, greenfield ADVISORY
  # (slice-05 declass). Net-new seams: DES-WAVE marker parse (declared_wave),
  # arm_inferred(NoWaveActive -> INFERRED record, entry_pending=false), adapter
  # fallback branch proceeding as wave-entering in the same pass. With the
  # product model absent (MIGRATION_UNMET) the same-pass entry gate now ALLOWS
  # (advisory, not a veto) -- BUT the fallback STILL arms the INFERRED record:
  # the declass relaxes only the entry VETO, never the S2-closing arm itself
  # (a declared wave can still only ADD gating; the floor still records the
  # inferred wave so downstream seam gates apply). MISSING_SSOT / INDETERMINATE
  # keep the same-pass hard veto.
  @slice-07d @driving_port @real-io @us-inferred-arm @contract-shape:bounded-change
  Scenario: A dispatch declaring the discuss wave on an empty floor arms inferred enforcement and is allowed with a greenfield advisory
    Given no wave has been armed in the project
    And the product requirements for entering discuss are missing
    When a dispatch declaring the discuss wave is checked on the empty floor
    Then the declaring dispatch is allowed with a greenfield advisory in the same pass
    And the floor records the discuss wave as inferred from the dispatch
    And the inferred entry carries no pending flag

  # AT-2 -- I3 dominance pinned END-TO-END (not just the store unit
  # guarantee): a wave-declaring dispatch on an operator-armed floor leaves
  # the COMMAND record untouched.
  @slice-07d @driving_port @real-io @us-inferred-arm @contract-shape:unbounded-preservation
  Scenario: A wave-declaring dispatch never overwrites the operator's explicit arming
    Given the discuss wave is already armed by the operator's explicit command
    And the product requirements for entering discuss are satisfied
    When a dispatch declaring the discuss wave is checked on the armed floor
    Then the armed dispatch is allowed to proceed
    And the floor keeps the operator's command provenance

  # AT-3 -- K2 / S1 untouched: without a usable declaration the fallback is
  # inert -- no arm, no garbage record, no interference with ad-hoc work.
  @slice-07d @driving_port @real-io @us-inferred-arm @contract-shape:unbounded-preservation
  Scenario Outline: Ad-hoc work without a usable wave declaration is never armed nor gated
    Given no wave has been armed in the project
    When an ad-hoc dispatch with <declaration> is checked
    Then the dispatch is allowed untouched by any wave gate
    And no wave record is created by the dispatch

    Examples:
      | declaration                |
      | no wave declaration        |
      | an unknown wave declaration |
