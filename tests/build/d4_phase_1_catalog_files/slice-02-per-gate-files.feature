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

  # Count re-baseline 28 -> 30 (2026-06-15, f-declarative-gate-composition slice-01
  # + retroactive wave-clear catalog reconcile): per-gate files for the two new
  # subcommands verify-discuss-review + wave-clear, each 1:1 with its catalog entry.
  # Count re-baseline 30 -> 33 (2026-06-16, f-coherence-and-attestation slice-06):
  # per-gate files for the three wired feature modules gate-g + self-attest +
  # verify-test-runner, each 1:1 with its catalog entry.
  # Count 33 -> 34 (2026-06-16, f-nonbypassable-attestation slice-05): per-gate file
  # for verify-wave-dispatch, 1:1 with its catalog entry.
  # Count 34 -> 35 (2026-06-16, f-spine-runs-tests-not-git-hooks slice-01): per-gate
  # Count 35 -> 36 (2026-06-17, f-wave-contract-coherence slice-02): adds verify-wave-contract-coherence
  # file for run-slice-ats (the slice-scoped EXECUTOR), 1:1 with its catalog entry.
  # Count 36 -> 38 (2026-06-18, f-design-devops-review-gate slice-01): per-gate files
  # for the DESIGN review-verdict pair (record/verify-design-review), 1:1 with catalog.
  # Count 38 -> 40 (2026-06-19, f-design-devops-review-gate slice-02): per-gate files
  # for the DEVOPS review-verdict pair (record/verify-devops-review), 1:1 with catalog.
  # Count 40 -> 41 (2026-06-19, f-deliver-entry-contract-freeze slice-01): per-gate file
  # for the DELIVER-entry contract-freeze gate (verify-deliver-entry-contract).
  # Count 41 -> 42 (2026-06-20, f-attest-bundled-slice slice-01): per-gate file for the
  # bundled-slice attestation command (attest-bundled-slice), 1:1 with its catalog entry.
  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: All 42 per-gate files exist and validate against GateContractFull schema
    Given the per-gate file directory at "nWave/gates/"
    When each per-gate file is loaded and validated
    Then exactly 42 per-gate files exist (one per catalog entry)
    And every per-gate file validates against the GateContractFull schema

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: Per-gate filename matches gate_id field 1:1 with catalog
    Given the gate catalog loaded from "nWave/gates/_catalog.yaml"
    And the per-gate files loaded from "nWave/gates/"
    When the filenames are compared to catalog gate_ids
    Then every catalog gate_id has a corresponding per-gate file with matching name
    And every per-gate file's internal gate_id field equals its filename stem

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function @regression-pin
  Scenario: language_neutral_contract:false count equals 2 (env-e2e + contract-gate)
    Given the per-gate files loaded from "nWave/gates/"
    When language_neutral_contract:false entries are enumerated
    Then exactly 2 gates are language-bound
    And the language-bound set equals "verify-environmental-e2e, run-contract-gate"
