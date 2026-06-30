@feature-f-wave-contract-coherence @driving_port @real-io @contract-shape:bounded-change
Feature: The DISCUSS output contract is authored once in the registry and the central schema no longer copies it

  A maintainer authors the DISCUSS wave's output contract -- WHICH [REF] sections
  the wave must produce -- ONCE in the canonical, flavor-independent wave-contract
  registry (nWave/waves/discuss.yaml output_contract), and the per-wave section
  list is REMOVED from the central feature-delta schema
  (schemas/feature-delta-tier1-sections.yaml waves.DISCUSS.required_sections), so
  the "which DISCUSS sections" fact has exactly ONE authoring locus -- the registry
  -- that every consumer points at instead of a second drifting copy
  (ADR-FLOW-006 D3 / §C2: the output_contract ABSORBS the required_sections role;
  MOVE-not-COPY, brief §7).

  Driving surface (Mandate-13 driving-port-only, real artifacts): the SHIPPED
  registry nWave/waves/discuss.yaml + the SHIPPED central schema
  schemas/feature-delta-tier1-sections.yaml + the SHIPPED wave-contract JSON-Schema
  nWave/waves/_schema.yaml, all read from the repo over the real filesystem (Layer 3
  composition). Observable: the set of DISCUSS sections each shipped file authors,
  the schema-validity of the registry output_contract, and the greenfield-degradation
  literal. No production module is imported-and-called for its business logic.

  # AT-9: the registry output_contract is the SOLE authored + schema-valid SSOT for
  #       the DISCUSS sections -- the full set (10 tier1 + Slice Plan +
  #       Wave-Decision Reconciliation) is authored in the registry, schema-valid
  #       against nWave/waves/_schema.yaml, and the registry is the ONLY locus that
  #       authors the list (no second enumerating copy survives).
  @slice-04 @feature-f-wave-contract-coherence @AT-9
  Scenario: The DISCUSS output contract is the sole schema-valid authoring locus for the section list
    Given the shipped wave-contract registry and the central feature-delta schema are read from the repo
    When the maintainer resolves the DISCUSS section list from the canonical authoring locus
    Then the registry output contract is schema-valid and authors the full DISCUSS section list
    And the registry is the only locus that authors the DISCUSS section list

  # AT-10: a mandatory DISCUSS section carrying a greenfield_degradation literal
  #        passes a greenfield presence-check via that literal -- and the literal is
  #        authored in the registry as the single source (the dissolution of
  #        mandatory-or-drop, brief §3 / ADR-FLOW-006 D3).
  @slice-04 @feature-f-wave-contract-coherence @AT-10
  Scenario: A mandatory DISCUSS section satisfies a greenfield presence-check through its degradation literal
    Given the shipped wave-contract registry and the central feature-delta schema are read from the repo
    When a greenfield feature is checked for the mandatory "Wave-Decision Reconciliation" DISCUSS section
    Then the section satisfies the presence-check through its greenfield degradation literal
    And the greenfield degradation literal is authored only in the registry

  # AT-11: the MOVE is complete -- the DISCUSS required_sections block is GONE from
  #        the central feature-delta schema and the section list resolves from the
  #        registry alone, so NO duplicate copy survives (MOVE-not-COPY, brief §7).
  @slice-04 @feature-f-wave-contract-coherence @AT-11
  Scenario: The DISCUSS section list is moved out of the central schema with no surviving copy
    Given the shipped wave-contract registry and the central feature-delta schema are read from the repo
    When the maintainer resolves the DISCUSS section list from the canonical authoring locus
    Then the central feature-delta schema no longer carries the DISCUSS required-sections block
    And the DISCUSS section list resolves from the registry as the only surviving source
