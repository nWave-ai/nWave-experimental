@feature-f-wave-contract-coherence @driving_port @real-io @contract-shape:bounded-change
Feature: The coherence-check gate holds the no-inline-restatement rule for wave prose

  A maintainer runs the git-free coherence-check gate over a wave's prose + its
  canonical wave-contract registry entry. The gate FAILs when the prose restates
  config truth inline (a bare catalog gate_id token / an enumerated [REF]-section
  list), PASSes when the prose carries valid gates-ref + outputs-ref pointers with
  zero inline restatement and the referenced wave resolves in BOTH SSOTs, and
  degrades LOUD to INDETERMINATE when the registry it must read is unreadable --
  so the drift surface (a config fact restated in prose) becomes a mechanical veto
  instead of an LLM-adherence hope.

  Driving surface (Mandate-13 driving-port-only): the REAL
  `des verify-wave-contract-coherence` subcommand invoked as a Layer-3 subprocess
  through the shipped `des` dispatcher (the kebab CLI seam). Observable: the §17
  GateVerdict token the gate emits on JSON-stdout (ADR-GV-001 -- one of the five
  existing verdicts; no sixth, no engine, per ADR-FLOW-006 D7/D9). Mandate-14
  real-io contract: the gate reads real on-disk prose + registry files over the OS
  filesystem and is spawned as a real OS subprocess -- the AT would fail if either
  shipped artifact (the dispatcher, the registry) were absent.

  # AT-4: the gate FAILs when wave prose restates config truth inline -- a bare
  #       catalog gate_id token appears in the prose (the duplication drift surface
  #       cure-I strips). git-free lexical scan (TextSearch floor, ADR-LA-001 tier-3).
  @slice-02 @feature-f-wave-contract-coherence @AT-4 @error
  Scenario: The gate fails when wave prose restates a catalog gate-id inline
    Given a wave-contract registry entry for the DISCUSS wave carrying both SSOTs
    And wave prose that restates a bare catalog gate-id from the gate stack inline
    When the maintainer runs the coherence-check gate over that wave
    Then the coherence-check gate emits the FAIL verdict
    And the failure diagnostic names the inline restatement it found

  # AT-5: the gate PASSes when the prose carries valid gates-ref + outputs-ref
  #       pointers, restates nothing inline, and the referenced wave resolves in
  #       BOTH SSOTs (gate_stack AND output_contract) with every gate_id in catalog.
  @slice-02 @feature-f-wave-contract-coherence @AT-5
  Scenario: The gate passes on valid pointers with zero inline restatement
    Given a wave-contract registry entry for the DISCUSS wave carrying both SSOTs
    And wave prose that carries valid gates-ref and outputs-ref pointers with zero inline restatement
    When the maintainer runs the coherence-check gate over that wave
    Then the coherence-check gate emits the PASS verdict

  # AT-6: the gate degrades LOUD to INDETERMINATE when the registry it must read
  #       is unreadable (absent / undecodable) -- a refusal-to-decide, never a
  #       silent green (Invariant 2 degrade-LOUD, ADR-FLOW-006 D7).
  @slice-02 @feature-f-wave-contract-coherence @AT-6 @error
  Scenario: The gate is indeterminate when the registry is unreadable
    Given wave prose that carries valid gates-ref and outputs-ref pointers with zero inline restatement
    And the wave-contract registry the gate must read is unreadable
    When the maintainer runs the coherence-check gate over that wave
    Then the coherence-check gate emits the INDETERMINATE verdict
    And the indeterminate diagnostic names the unreadable registry
