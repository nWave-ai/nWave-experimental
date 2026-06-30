@feature-nwave-flow-v2-enforcement @slice-07c
Feature: Entering a wave is recognized structurally, never by prompt wording
  As an nWave maintainer who trusts the spine to be deterministic
  I want the first dispatch into an armed wave to be entry-gated by a signal
    the anchor itself wrote when it saw the explicit wave command -- never by
    keywords found in an agent-authored prompt -- checked exactly once, with
    a blocked entry staying pending for the retry
  So that wave-entry enforcement cannot be dodged (or falsely triggered) by
    prompt wording, later in-wave work is never re-gated, and an unverifiable
    product-owner review verdict always blocks loud, named by its cause

  # slice-07c of nwave-flow-v2-enforcement -- deterministic wave-entering
  # signal (F3 NORMATIVO) + the 07b routed AT coverage. Follows the DESIGN
  # slice-07c code-design verbatim (`## Wave: DESIGN / [REF] slice-07c
  # code-design (deterministic wave-entering signal + 07b routed AT coverage
  # -- F3)`, architect-reviewer APPROVED a06237ced).
  #
  # DRIVING PORTS (Mandate-13 driving-port-only):
  #   * AT-1 / AT-2 -- Layer 4 wiring: the REAL prompt-submission hook
  #     (`user_prompt_submit_handler`, subprocess, raw `/nw-discuss` literal)
  #     arms the floor; the REAL PreToolUse hook adapter
  #     (`claude_code_hook_adapter pre-tool-use`, subprocess, hook-protocol
  #     stdin JSON) checks the dispatch. The hook adapter is the composition
  #     seat of the net-new peek_entry -> validate(wave_entering=...) ->
  #     clear-on-allow lifecycle, so it IS the real entry point for those
  #     seams. Observables: hook exit code / block reason + the floor record
  #     at the DESIGN-PINNED path `.nwave/wave-active/active.json`.
  #   * AT-3 -- the shipped pure core `DiscussReviewGate.evaluate(record,
  #     key, expected_feature_delta_hash)` invoked direct in-process: the
  #     07b design declared the pure core the contract surface (seam
  #     callable); slice-06 pure-function driving-port precedent;
  #     Mandate-13 adjudicated OK by the architect-reviewer (a06237ced).
  #
  # RED-for-right-reason: `entry_pending` (floor v1.1), `WaveActivationService`
  # (peek_entry / clear_entry) and `PreToolUseInput.wave_entering` DO NOT
  # exist at HEAD -- the anchor writes a floor without the flag and the gate
  # falls back to the AD-66 keyword heuristic, which a wording-free dispatch
  # never trips. So:
  #   * AT-1: the pending-flag assertion fails semantically (the floor record
  #     carries no entry pending mark), and the wording-free dispatch is
  #     ALLOWED where the structural entry gate must BLOCK.
  #   * AT-2: the pending-flag assertion fails semantically (same missing
  #     anchor mark); the allow/once-only legs are preservation at HEAD.
  #   * AT-3: GREEN-preservation -- the 07b core shipped; these rows PIN the
  #     four routed INDETERMINATE reasons (coverage gap, not missing impl).
  # No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2):
  #   floor entry states = {NO_WAVE, ARMED+PENDING, ARMED+CLEARED}.
  #     NO_WAVE       --(/nw-discuss literal, anchor)--> ARMED+PENDING
  #     ARMED+PENDING --(dispatch, product model absent / MIGRATION_UNMET)-->
  #                       ALLOW (advisory, slice-05 declass) -> ARMED+CLEARED
  #     ARMED+PENDING --(dispatch, preconditions met)---> ALLOW -> ARMED+CLEARED
  #     ARMED+CLEARED --(any later in-wave dispatch)----> entry gate NOT re-run
  #   (MISSING_SSOT / INDETERMINATE remain a hard BLOCK that stays PENDING --
  #    the still-vetoing branch, exercised by the slice-07 gate-IN ATs.)
  #   review-verdict audit (AT-3): {key-absent | stale-artefact |
  #     schema-unknown | unknown-verdict-literal} --> INDETERMINATE (degrade-
  #     LOUD; never PASS, never VETOED).

  # AT-1 -- the structural discriminant fires on the anchor-owned signal, and
  # the greenfield entry is a soft ADVISORY (slice-05 declass). Net-new seams
  # witnessed: anchor writes entry_pending on COMMAND arm; peek_entry ->
  # wave_entering threaded into the gate-IN hinge (the dispatch wording carries
  # ZERO entry keywords -- only the anchor-owned signal can make the gate fire);
  # with the product model absent (MIGRATION_UNMET) the gate-IN now ALLOWS the
  # entry (the slice-05 wave-optionality declass: greenfield is advisory, not a
  # veto), so the structural entry check runs exactly once and the allowed entry
  # CLEARS the pending flag (a hard veto would instead keep it pending -- that
  # branch survives for MISSING_SSOT, the still-vetoing precondition).
  @slice-07c @driving_port @real-io @us-entry-signal @contract-shape:bounded-change
  Scenario: The first dispatch into the discuss wave is entry-checked on the anchor signal and allowed with a greenfield advisory
    Given the operator arms the discuss wave with the explicit command
    And the product preconditions for discuss are unmet
    When an in-wave dispatch whose wording never mentions entering is checked
    Then the arming command marked the wave entry as pending
    And the dispatch is allowed
    And the wave entry is cleared by the allowed entry

  # AT-2 -- clear-on-allow + once-only (K2-style non-interference in-wave).
  # Net-new seams witnessed: clear_entry fired ONLY on the allowed entering
  # dispatch (the wave stays armed, only the flag clears); a later in-wave
  # dispatch is never re-gated even when the preconditions have degraded
  # (the entry check ran exactly once).
  @slice-07c @driving_port @real-io @us-entry-signal @contract-shape:bounded-change
  Scenario: A wave entry is checked exactly once and later in-wave work is never re-gated
    Given the operator arms the discuss wave with the explicit command
    And the product preconditions for discuss are met
    When an in-wave dispatch whose wording never mentions entering is checked
    Then the dispatch is allowed
    And the arming command marked the wave entry as pending
    And the wave entry is cleared by the allowed entry
    When a later in-wave dispatch is checked after the preconditions have degraded
    Then the later dispatch is allowed without re-running the entry preconditions

  # AT-3 -- the 07b routed gap: the three production-implemented but
  # not-AT-pinned INDETERMINATE reasons of the shipped review-verdict core
  # (post-demotion: key-absent row REMOVED -- no key to be absent).
  # NOTE row 3: an unknown verdict literal maps to the shipped closed detail
  # reason `schema-unknown` (a record whose verdict is outside the
  # closed DiscussReviewToken set is not a readable reviewer decision --
  # the closed detail set is the contract, the row name is the cause).
  @slice-07c @driving_port @in-memory @us-po-review @error @contract-shape:pure-function
  Scenario Outline: An unverifiable product-owner review verdict is always indeterminate, named by its cause
    Given a recorded product-owner review verdict flawed as <flaw>
    When the review verdict is evaluated against the current artefact
    Then the review gate result is indeterminate naming <cause>

    Examples:
      | flaw                    | cause          |
      | stale-artefact          | stale-artefact |
      | schema-unknown          | schema-unknown |
      | unknown-verdict-literal | schema-unknown |
