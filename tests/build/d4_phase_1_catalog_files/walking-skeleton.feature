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

  # Count re-baseline 28 -> 30 (2026-06-15, f-declarative-gate-composition slice-01
  # + retroactive wave-clear catalog reconcile): adds verify-discuss-review (OB-2)
  # and wave-clear (the latter reconciled -- registry-present since c89be75d1 but
  # catalog + per-gate file were omitted). Both 1:1 across registry/catalog/files.
  # Count re-baseline 30 -> 33 (2026-06-16, f-coherence-and-attestation slice-06):
  # adds gate-g + self-attest + verify-test-runner (the three wired feature modules,
  # thin CLI drivers over slice-03/04/05 logic). All 1:1 across registry/catalog/files.
  # Count 33 -> 34 (2026-06-16, f-nonbypassable-attestation slice-05): adds
  # verify-wave-dispatch (the dispatch.pre guard). 1:1 across registry/catalog/files.
  # Count 34 -> 35 (2026-06-16, f-spine-runs-tests-not-git-hooks slice-01): adds
  # Count 35 -> 36 (2026-06-17, f-wave-contract-coherence slice-02): adds verify-wave-contract-coherence
  # run-slice-ats (the slice-scoped EXECUTOR -- the acceleration). 1:1 across
  # registry/catalog/files.
  # Count 36 -> 38 (2026-06-18, f-design-devops-review-gate slice-01): adds the DESIGN
  # review-verdict pair record-design-review + verify-design-review (DISCUSS parity).
  # Count 38 -> 40 (2026-06-19, f-design-devops-review-gate slice-02): adds the DEVOPS
  # review-verdict pair record-devops-review + verify-devops-review (SSOT-reuse proof).
  # Count 40 -> 41 (2026-06-19, f-deliver-entry-contract-freeze slice-01): adds the
  # DELIVER-entry contract-freeze gate verify-deliver-entry-contract.
  # Count 41 -> 42 (2026-06-20, f-attest-bundled-slice slice-01): adds the
  # bundled-slice attestation command attest-bundled-slice (on reverify's shared core).
  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Catalog row count equals registry count (43 total, adds feature-delta-schema)
    Given the gate catalog loaded from "nWave/gates/_catalog.yaml"
    And the production _REGISTRY loaded from `src.des.cli.__main__`
    When the row counts are compared
    Then both contain exactly 43 entries
    And every gate_id in the catalog is also a SubcommandRow.name in _REGISTRY
    And every SubcommandRow.name in _REGISTRY is also a gate_id in the catalog

  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function @regression-pin
  Scenario: carpaccio-slice-gate entry matches expected fields byte-for-byte
    Given the catalog entry for gate_id "carpaccio-slice-gate"
    When the entry's module and entry_function are read
    Then the module equals "des.cli.carpaccio_slice_gate"
    And the entry_function equals "main"
    And the language_neutral_contract equals true
