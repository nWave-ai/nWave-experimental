@feature-d4-phase-1-catalog-files
Feature: Per-gate YAML files validate against GateContractFull schema (slice-02)

  As nWave maintainer authoring per-gate full schemas
  I want each of the 30 gates to have a `nWave/gates/<gate-id>.yaml` file
  carrying full GateContractFull (cli_args + log_events + failure_modes
  + idempotency + host_visibility) per M76 §3.1
  So that workflow-flavor compositions (D7) can reference rich per-gate
  metadata
  And language-bound vs neutral gates are mechanically enumerable
  And host-visibility filters per-host dispatch (D6)

  Background:
    Given the gate catalog YAML loader is available

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: All per-gate files exist and validate against GateContractFull schema
    Given the per-gate file directory at "nWave/gates/"
    When each per-gate file is loaded and validated
    Then catalog and per-gate files are coherent (no orphans either direction)
    And every per-gate file validates against the GateContractFull schema

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: Per-gate filename matches gate_id field 1:1 with catalog
    Given the gate catalog loaded from "nWave/gates/_catalog.yaml"
    And the per-gate files loaded from "nWave/gates/"
    When the filenames are compared to catalog gate_ids
    Then every catalog gate_id has a corresponding per-gate file with matching name
    And every per-gate file's internal gate_id field equals its filename stem

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: Catalog and per-gate file agree on every shared contract field
    Given the gate catalog loaded from "nWave/gates/_catalog.yaml"
    And the per-gate files loaded from "nWave/gates/"
    When the shared contract fields are compared entry by entry
    Then no gate declares a different value in the catalog than in its per-gate file

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function @regression-pin
  Scenario: language_neutral_contract:false count equals 2 (env-e2e + contract-gate)
    Given the per-gate files loaded from "nWave/gates/"
    When language_neutral_contract:false entries are enumerated
    Then exactly 2 gates are language-bound
    And the language-bound set equals "verify-environmental-e2e, run-contract-gate"
