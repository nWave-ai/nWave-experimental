@feature-fix-wave-bypass-recovery-truthful @slice-02
Feature: A maintainer clears a stale wave floor through one sanctioned command
  As a maintainer or LLM-operator facing a stale inferred wave floor
  I want one sanctioned, loud, auditable `des wave-clear --reason` command
  So that I clear the floor that blocks legitimate dispatches without ever
    hand-editing active.json -- and every clear records who authorized it and why

  # slice-02 of fix-wave-bypass-recovery-truthful (JOB-019, OB-B=B1). At HEAD no
  # `des wave-clear` subcommand exists (the dispatcher registry has no wave-clear
  # row -- Tsunami + grep: zero matches tree-wide), so a stale floor's only exit
  # is an unsanctioned hand-edit (and the obvious `provenance:"explicit"` edit is
  # rejected by the closed set). The fix adds ONE operator subcommand reusing the
  # shipped `WaveActiveWriter.clear()` via a new `WaveActivationService.clear_floor()`.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL `des wave-clear`
  # subcommand via the production CLI dispatcher (`python -m des.cli wave-clear`).
  # observables = process exit code + the wave-active floor file on disk + the
  # audit-log file the run appends. The scenarios drive on the operator-visible
  # exit code (the seam), never a line number.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam
  # `WaveActivationService.clear_floor()` is reached from the REAL `des wave-clear`
  # entry point (WaveActiveWriter.clear has ZERO external callers today -- the CLI
  # is its first consumer). These ATs name THAT seam and drive it through the REAL
  # subprocess, asserting the observable effect (floor removed / exit code / audit
  # record), not the component in isolation.
  #
  # EXIT-CODE / FLOOR-STATE CONTRACT (the DESIGN `des wave-clear` CLI contract):
  #   * stale record present -> removed, exit 0, loud + audited -> next dispatch unblocked
  #   * --reason absent       -> usage error exit 2, floor untouched, no audit
  #   * floor absent          -> no-op SUCCESS exit 0, idempotent, still audited
  #   * floor corrupt         -> INDETERMINATE degrade-LOUD exit 1, audited
  #   * provenance closed set {command, inferred} UNCHANGED
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # `des wave-clear` is UNREGISTERED, so the real dispatcher rejects it with
  # `invalid choice: 'wave-clear'` (exit 2). The observable effect never happens
  # (floor not removed / wrong exit code / no audit record), so each Then fires a
  # semantic AssertionError. GREEN once DELIVER ships the subcommand + service
  # method + registry row. No @skip, no import / collection error.

  @slice-02 @driving_port @real-io @us-sanctioned-clear @contract-shape:bounded-change
  Scenario: The maintainer clears a stale inferred floor and unblocks the next dispatch
    Given a wave floor armed in the STALE_INFERRED_RECORD state for the clear
    When the maintainer runs the sanctioned wave-clear command
    Then the wave-clear command exits with the CLEARED outcome
    And the stale floor record is removed by the clear
    And the next markerless dispatch is no longer wave-bypass blocked
    And the clear writes a wave-floor audit record
    And the clear writes no third provenance value

  @slice-02 @driving_port @real-io @us-sanctioned-clear @error @contract-shape:bounded-change
  Scenario: A wave-clear without a reason is refused so the human authorizes the clear
    Given a wave floor armed in the STALE_INFERRED_RECORD state for the clear
    And the maintainer omits the mandatory reason on the clear
    When the maintainer runs the sanctioned wave-clear command
    Then the wave-clear command exits with the USAGE_ERROR outcome
    And the usage error names the mandatory reason argument
    And the stale floor record is left untouched by the refused clear

  @slice-02 @driving_port @real-io @us-sanctioned-clear @error @contract-shape:bounded-change
  Scenario: Clearing when no wave floor exists is an audited idempotent no-op
    Given a wave floor armed in the ABSENT state for the clear
    When the maintainer runs the sanctioned wave-clear command
    Then the wave-clear command exits with the NOOP_SUCCESS outcome
    And the clear writes a wave-floor audit record
    And the no-op message names the inspected project root

  @slice-02 @driving_port @real-io @us-sanctioned-clear @error @contract-shape:bounded-change
  Scenario: Clearing a corrupt floor degrades loud instead of fabricating success
    Given a wave floor armed in the CORRUPT state for the clear
    When the maintainer runs the sanctioned wave-clear command
    Then the wave-clear command exits with the INDETERMINATE outcome
    And the clear writes a wave-floor audit record

  @slice-02 @driving_port @real-io @us-sanctioned-clear @error @contract-shape:bounded-change
  Scenario: A corrupt floor clear routes its degrade-LOUD diagnostic to stderr not stdout
    Given a wave floor armed in the CORRUPT state for the clear
    When the maintainer runs the sanctioned wave-clear command
    Then the wave-clear command exits with the INDETERMINATE outcome
    And the INDETERMINATE diagnostic is written to stderr
    And stdout carries no wave-clear outcome line
