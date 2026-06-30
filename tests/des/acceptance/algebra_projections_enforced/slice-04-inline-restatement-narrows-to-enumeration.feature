@feature-algebra-projections-enforced
Feature: The inline-restatement clause scopes to gate-stack enumeration, not command mention

  Maya, an nWave maintainer, trusts the wave-contract coherence gate to veto ONE
  precise drift: a wave's gate-stack re-enumerated inline in its prose (the registry
  block pasted into the command/skill markdown), so the prose POINTS at the registry
  instead of duplicating it. But the gate's inline-restatement clause, as first built
  for the DISCUSS planning wave, flags ANY bare catalog gate_id token — and DELIVER is
  the orchestration wave whose prose IS made of command vocabulary. So the clause
  over-reaches: it rejects a live `des verify-integrity` invocation and the
  `roadmap.json` plan-file noun as if they were gate-stack restatements, blocking the
  DISTILL + DELIVER prose migration (slice-04) for legitimate operational text.

  This slice narrows the clause (ADR-003 / DD-A6) to its true drift surface — a
  STRUCTURED gate-stack enumeration — while leaving the cure in force: a restated
  gate-stack enumeration still FAILs in every wave, and the legitimate command
  invocation + artifact noun now PASS. The DISCUSS prose (the only currently-migrated
  wave) keeps its PASS verdict byte-stable across the narrowing.

  # ADR-003 (REROUTE_DESIGN #2, slice-04 Phase-D) / feature-delta DD-A6 + Point 5
  # REVISED. Driving port: the shipped `des verify-wave-contract-coherence --wave
  # discuss --prose <locus> --waves-dir <dir>` gate (Layer 3 subprocess, DIRECT,
  # never flock). These 3 witnesses COMPLEMENT the 5 existing slice-04 coverage ATs
  # (slice-04-coherence-hook-covers-distill-deliver.feature): the coverage ATs prove
  # the firing-surface hook fires on distill/deliver + the real migrated loci clear;
  # these prove the inline-restatement clause those loci must clear distinguishes a
  # gate-stack ENUMERATION (FAILs) from a command/artifact MENTION (PASSes).
  #
  # HEAD-probe-grounded classification (red-classification slice-04 narrowing table):
  #   * W1 enumeration-FAILs   = PRESERVATION-GUARD: at HEAD the lexical scan flags
  #     the first bare gate_id (`carpaccio-slice-gate`), so the enumeration already
  #     FAILs; the narrowing must KEEP it failing (GREEN at HEAD + post-narrowing).
  #   * W2 invocation+noun-PASS = ACTIVE-RED MISSING_FUNCTIONALITY: at HEAD the scan
  #     flags `verify-integrity`/`init-log`/`roadmap` -> `fail` (the false positive);
  #     A_GREEN narrows the clause -> `pass`.
  #   * W3 DISCUSS byte-stable  = PRESERVATION-GUARD: the real discuss prose carries no
  #     enumeration, PASSes at HEAD; the narrowing must not change it (ADR-003 D2).

  @slice-04 @coupled @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A gate-stack enumeration restated in the prose is still rejected
    Given a coherence target whose body is a restated gate-stack enumeration in the prose
    When the inline-restatement check runs for that prose
    Then the prose is rejected as a gate-stack restatement

  @slice-04 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A command invocation and the roadmap.json artifact noun clear the check
    Given a coherence target whose body is command invocations and the roadmap.json artifact noun, with no enumeration
    When the inline-restatement check runs for that prose
    Then the prose clears the coherence check

  @slice-04 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The migrated DISCUSS prose still clears the check byte-stable
    Given a coherence target whose body is the discuss wave prose exactly as the repository carries it
    When the inline-restatement check runs for that prose
    Then the prose clears the coherence check
    And the discuss prose locus on disk is left unchanged
