@feature-d4-phase-1-catalog-files
Feature: Gate-contract catalog YAML mirrors _REGISTRY (D4 Phase 1 slice-01)

  As nWave maintainer iterating on the gate catalog
  I want `nWave/gates/_catalog.yaml` to be a machine-readable mirror of
  the production gate registry at `src/des/cli/__main__.py:_REGISTRY`
  So that workflow-flavor configs (D7 Phase 2) reference gates by id
  with mechanical schema validation
  And drift between catalog and registry produces a CI-fail (closes H4
  cross-hook contract drift family per M75 + M76 § 3.1)
  And every gate in the catalog declares its language_neutral_contract
  flag explicitly per INV-6 (language independence at contract layer)

  Background:
    Given the gate catalog YAML loader is available

  @walking_skeleton @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Catalog YAML validates against schema YAML
    Given the catalog file at "nWave/gates/_catalog.yaml"
    And the schema file at "nWave/gates/_schema.yaml"
    When the catalog is validated against the schema
    Then validation succeeds with zero errors

  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Catalog gate_id set matches registry name set exactly
    Given the gate catalog loaded from "nWave/gates/_catalog.yaml"
    And the production _REGISTRY loaded from `src.des.cli.__main__`
    When the row counts are compared
    Then every gate_id in the catalog is also a SubcommandRow.name in _REGISTRY
    And every SubcommandRow.name in _REGISTRY is also a gate_id in the catalog

  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function @regression-pin
  Scenario: carpaccio-slice-gate entry matches expected fields byte-for-byte
    Given the catalog entry for gate_id "carpaccio-slice-gate"
    When the entry's module and entry_function are read
    Then the module equals "des.cli.carpaccio_slice_gate"
    And the entry_function equals "main"
    And the language_neutral_contract equals true
