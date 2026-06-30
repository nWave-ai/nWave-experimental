@feature-f-wave-contract-coherence @infrastructure @real-io @contract-shape:unbounded-preservation
Feature: The MOVE completes -- the dead flavor gate-stack block is deleted and the registry is the sole gate-stack source

  slice-01 authored the canonical wave-contract registry (nWave/waves/discuss.yaml)
  and ADDED the registry read path; slice-06 COMPLETES the MOVE (Ale bloat-removal
  mandate, MOVE-not-COPY): the now-dead flavor-private wave_gate_stacks block is
  DELETED from nWave/flavors/atdd_pure.yaml and its $defs schema is removed from the
  flavor _schema.yaml, a reserved overrides hook is present (the SF override seam,
  ADR-FLOW-006 D5), the three glossary terms are added, and the dispatcher reads the
  gate stack FROM the registry only -- KEEPING f-declarative-gate-composition's
  behavioral guarantees (select -> iterate-in-declared-order -> halt-at-first-veto)
  GREEN against the registry source. Behavior preserved, LOCATION moved (OWNED by
  ADR-DGC-001 location-supersession only -- AT-DGC behavior is the preserved invariant).

  Driving surface (Mandate-13 driving-port-only):
    * Layer 3 composition (pure-seam read path) -- the REAL flavor_dispatcher
      resolving the DISCUSS gate stack, read over the SHIPPED nWave/flavors/*.yaml +
      nWave/waves/*.yaml + nWave/waves/_schema.yaml + docs/product/glossary.md repo
      files. Observable: presence/absence of the flavor block + its $defs, presence
      of the registry overrides hook + glossary terms, and the resolved gate-id
      sequence the dispatcher returns when it reads ONLY the registry (no flavor
      block to fall back to).
  No production module is imported-and-called for business logic -- the assertions
  read shipped artifacts (the flavor file, the registry file, the schema, the
  glossary) and drive the REAL resolution seam over the shipped registry.

  # AT-15: PREMISE-UPDATED by f-distill-wiring-to-registry slice-02 (CT-9 / DDD-9).
  #        AT-15 was authored with an EXPLICIT caveat -- the flavor wave_gate_stacks
  #        block + its $defs PERSIST to host the `distill` co-tenant *(pending
  #        f-coherence's own future registry migration)*. slice-01 of
  #        f-distill-wiring-to-registry IS that migration: it REMOVED the flavor block
  #        and MOVE-completed the `distill` co-tenant (self-attest / verify-test-runner)
  #        into the canonical registry nWave/waves/distill.yaml gate-out (ADR-FLOW-006
  #        D6). So the original SURVIVE assertions are now FALSE-of-the-world; AT-15 is
  #        re-pointed to assert the NEW true state it foresaw (the test honoring the
  #        change AT-15 itself anticipated -- NOT a re-opening of f-wave, which STAYS
  #        DONE; see the f-distill-wiring-to-registry feature-delta). Three legs: the
  #        `discuss` entry is gone (GREEN post-MOVE), the `distill` co-tenant resolves
  #        from the LIVE registry (GREEN post-MOVE), and the dead flavor schema $defs is
  #        REMOVED (the leg-c active-RED: still present at HEAD, DELIVER removes it).
  @slice-06 @feature-f-wave-contract-coherence @AT-15
  Scenario: The migrated `discuss` entry is gone and the `distill` co-tenant resolves from the registry
    Given the canonical wave-contract registry is the sole gate-stack source
    When the maintainer inspects the shipped flavor wave_gate_stacks block and its schema
    Then the flavor block no longer declares a `discuss` gate stack
    And the flavor wave_gate_stacks block is gone and the `distill` co-tenant resolves from the registry while the dead schema $defs is removed

  # AT-16: classic is unaffected -- it never carried a wave_gate_stacks block, so the
  #        MOVE is additive for classic (FA-3 non-regression).
  @slice-06 @feature-f-wave-contract-coherence @AT-16
  Scenario: The classic flavor is unaffected by the gate-stack MOVE
    Given the canonical wave-contract registry is the sole gate-stack source
    When the maintainer inspects the shipped classic flavor
    Then the classic flavor carries no wave_gate_stacks declaration before or after the MOVE

  # AT-17: the behavioral guarantee of f-declarative-gate-composition still holds when
  #        the dispatcher reads the gate stack FROM the registry (not the deleted flavor
  #        block): the DISCUSS gate-in / gate-out stacks resolve to the SAME ordered
  #        gate-id sequence, sourced from the registry only. Behavior preserved, location
  #        moved.
  @slice-06 @feature-f-wave-contract-coherence @AT-17
  Scenario Outline: The DISCUSS <boundary> gate stack resolves from the registry only and preserves the gate sequence
    Given the canonical wave-contract registry is the sole gate-stack source
    When the dispatcher resolves the DISCUSS <boundary> stack with no flavor block present
    Then the resolved <boundary> gate-id sequence is sourced from the registry and equals the sequence f-declarative-gate-composition guarantees

    Examples:
      | boundary |
      | gate-in  |
      | gate-out |

  # AT-18: the reserved overrides block is present and schema-valid-but-unused (the SF
  #        override seam, ADR-FLOW-006 D5) AND the three glossary terms are present.
  @slice-06 @feature-f-wave-contract-coherence @AT-18
  Scenario: The reserved overrides hook and the glossary terms are present
    Given the canonical wave-contract registry is the sole gate-stack source
    When the maintainer inspects the registry schema and the product glossary
    Then the registry schema reserves an overrides hook and the glossary defines the wave-contract-registry vocabulary
