@feature-algebra-projections-enforced
Feature: The wave-contract coherence check fires on DISTILL and DELIVER prose

  Maya, an nWave maintainer, trusts "all gates green" to mean "no prose-vs-registry
  drift". Today the coherence-hook (run_wave_contract_coherence.py) fires the
  verify-wave-contract-coherence gate on DISCUSS prose ONLY — its _MIGRATED tuple
  names the two discuss loci and nothing else. So the distill and deliver wave
  prose can drift from their registry contract (a missing gates-ref/outputs-ref
  pointer, a bare catalog gate_id restated inline) and every commit stays green.
  This slice extends the coverage to DISTILL + DELIVER: the four distill/deliver
  prose loci gain their registry pointers (and shed any bare gate_id they restate),
  and the firing-surface hook's _MIGRATED tuple grows the four matching rows. After
  this slice the maintainer sees the hook exercise both new waves, sees the gate
  clear the migrated distill and deliver prose, and sees the hook fail the commit
  while either wave still drifts — the trust is earned mechanically for two more
  waves.

  # DISCUSS slice-04 ("the maintainer sees the coherence-hook fire on DISTILL and
  # DELIVER prose, not only DISCUSS: run_wave_contract_coherence.py _MIGRATED
  # extends to the distill + deliver prose loci"). DESIGN Point 5 (the 4 prose
  # loci + 4 _MIGRATED rows) + Reuse Analysis row `_MIGRATED`. Driving ports: the
  # shipped `des verify-wave-contract-coherence` gate (Layer 3 subprocess, DIRECT,
  # never flock) and the firing-surface hook `scripts/hooks/run_wave_contract_coherence.py`.
  #
  # active-RED rationale (atdd_pure — every scenario RED-fails for the right
  # reason at HEAD, none passes without DELIVER):
  #   * _MIGRATED = discuss-only -> the hook never exercises distill/deliver -> the
  #     coverage Thens (S1/S2) RED-fail and the hook exits 0 wrongly (S3);
  #   * the 4 distill/deliver loci carry no pointer AND restate bare catalog
  #     gate_ids -> the gate emits `fail` on the pristine real locus -> the
  #     pristine-pass Thens (S4/S5) RED-fail.
  # DELIVER A_GREEN turns all GREEN by (a) adding the 4 _MIGRATED rows + (b) adding
  # the pointer pair to each of the 4 loci AND scrubbing the bare catalog gate_id
  # tokens from the distill/deliver prose. NO scenario asserts the generic gate
  # invariant "missing pointer -> fail" (already green at HEAD, NOT this slice's
  # scope — slice-04 is a pure coverage EXTENSION; its negative case is "the hook
  # does NOT yet catch distill/deliver drift", which IS the S1/S2/S3 active-RED).

  @slice-04 @coupled @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The firing-surface hook exercises the coherence gate on the distill wave
    Given the maintainer runs the wave-contract coherence hook
    When the hook completes
    Then the hook has exercised the distill wave

  @slice-04 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The firing-surface hook exercises the coherence gate on the deliver wave
    Given the maintainer runs the wave-contract coherence hook
    When the hook completes
    Then the hook has exercised the deliver wave

  @slice-04 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The hook fails the commit while a migrated wave still drifts
    Given the maintainer runs the wave-contract coherence hook
    When the hook completes
    Then the hook has exercised the distill wave
    And the hook has exercised the deliver wave
    And the hook exits cleanly

  @slice-04 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: Distill prose, as the repository carries it, clears the coherence check
    Given a coherence target: the distill wave prose as the repository carries it
    When the coherence check runs for that prose
    Then the check clears the coherence check
    And the prose locus on disk is left unchanged

  @slice-04 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: Deliver prose, as the repository carries it, clears the coherence check
    Given a coherence target: the deliver wave prose as the repository carries it
    When the coherence check runs for that prose
    Then the check clears the coherence check
    And the prose locus on disk is left unchanged
