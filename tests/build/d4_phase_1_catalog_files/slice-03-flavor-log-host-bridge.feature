@feature-d4-phase-1-catalog-files
Feature: Flavor schema + log defaults + host-bridge events (slice-03)

  As nWave maintainer authoring D4 Phase 1 final slice
  I want the three remaining schema/defaults files to exist and parse
  So that Phase 2 (atdd_pure.yaml + classic.yaml flavors) can validate
  against the flavor schema
  And Phase 3 (D2 dispatcher) can consume host-bridge events vocabulary
  And LogPersistencePort (Phase 3 slice-04) has documented default
  adapter set

  Background:
    Given the gate catalog YAML loader is available

  @driving_port @in-process @real-io @slice-03 @contract-shape:pure-function
  Scenario: Workflow-flavor schema file exists and is valid JSON Schema
    Given the flavor schema file at "nWave/flavors/_schema.yaml"
    When the schema is parsed
    Then the schema has a top-level $schema declaring draft/2020-12
    And the schema requires flavor_id, description, lifecycle_events fields
    And the schema defines a GateInvocation $def with gate_id + on_failure

  @driving_port @in-process @real-io @slice-03 @contract-shape:pure-function
  Scenario: Log persistence defaults declares three adapters
    Given the log defaults file at "nWave/data/log-persistence-defaults.yaml"
    When the defaults are parsed
    Then the active_adapter equals "jsonl"
    And the adapters dict contains keys "jsonl", "stdout", "silent"
    And the jsonl adapter declares per_feature_path AND common_log_path AND fanout

  @driving_port @in-process @real-io @slice-03 @contract-shape:pure-function
  Scenario: Host-bridge events declares closed vocabulary covering 4 hosts
    Given the host-bridge events file at "nWave/data/host-bridge-events.yaml"
    When the events vocabulary is parsed
    Then at least 9 abstract events are declared
    And every event lists hosts dict with keys claude-code, codex, opencode, git-hook
    And the events include "dispatch.pre", "session.init", "slice.committed", "commit.pre"
