@feature-f-wave-contract-coherence @driving_port @real-io @contract-shape:bounded-change
Feature: The DISCUSS wave prose points at the registry instead of restating it

  The DISCUSS wave's shipped prose -- the `/nw-discuss` command (`nWave/tasks/nw/discuss.md`)
  and the `nw-discuss` skill (`nWave/skills/nw-discuss/SKILL.md`) -- carries the
  `gates-ref: discuss` + `outputs-ref: discuss` pointers and DROPS the inline gate-id /
  [REF]-section restatement, so the coherence-check gate (slice-02) PASSes on DISCUSS.
  The gate stack + output contract already live ONCE in the registry
  `nWave/waves/discuss.yaml` (slice-01); the prose points at that single authoring locus
  rather than copying it -- the 2-3 drifting copies become structurally impossible.

  Driving surface (Mandate-13 driving-port-only): the REAL
  `des verify-wave-contract-coherence` subcommand (the slice-02 shipped gate) invoked as a
  Layer-3 subprocess through the shipped `des` dispatcher, over the REAL shipped DISCUSS
  prose + the REAL shipped `nWave/waves` registry. slice-03 adds no executable -- it
  re-points the prose so the existing gate returns PASS. Observable: the §17 GateVerdict
  token the gate emits (AT-8) + the pointer / no-restatement facts the gate keys on (AT-7,
  asserted via the shipped gate's own check primitives -- one rule, no test-private copy).
  Mandate-14 real-io: the gate is spawned as a real OS subprocess and reads the real
  shipped prose + registry over the filesystem -- the AT would fail if either shipped
  artifact were absent.

  # AT-7: each shipped DISCUSS prose locus (command + skill) carries BOTH pointers AND
  #       restates no bare catalog gate_id inline -- the cure's ADD + REMOVE halves,
  #       asserted with the shipped gate's own gates-ref/outputs-ref markers + catalog
  #       gate_id lexical scan (TextSearch floor, ADR-LA-001 tier-3; git-free).
  @slice-03 @feature-f-wave-contract-coherence @AT-7
  Scenario Outline: The shipped DISCUSS prose carries both pointers and restates nothing inline
    Given the shipped DISCUSS <locus> prose
    Then the shipped DISCUSS prose carries both gates-ref and outputs-ref pointers
    And the shipped DISCUSS prose restates no catalog gate-id inline

    Examples:
      | locus   |
      | command |
      | skill   |

  # AT-8: the coherence-check gate (slice-02) emits PASS over each shipped DISCUSS prose
  #       locus -- the end-to-end proof the cure landed on the real files the maintainer
  #       edits, driven through the real `des verify-wave-contract-coherence` subprocess
  #       over the real shipped registry.
  @slice-03 @feature-f-wave-contract-coherence @AT-8
  Scenario Outline: The coherence-check gate passes on the cured shipped DISCUSS prose
    Given the shipped DISCUSS <locus> prose
    When the maintainer runs the coherence-check gate over the DISCUSS prose
    Then the coherence-check gate emits the PASS verdict

    Examples:
      | locus   |
      | command |
      | skill   |
