@feature-fix-des-self-hosted-gate-sync @slice-02
# DISTILL slice-02 ATs — install plugin writes `_install_manifest.json`;
# gate (wired in slice-01) discriminates states A/B/C/D using the manifest.
# Design SSOT: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md
#              §1.4 + §1.5 + §2.2 Addition 1 + DDD-3, DDD-6, DDD-13 (A-2)
# Layer 3 (subprocess) — example-based + parametrize-collapse per Mandate 11.

Feature: DES install plugin writes the freshness-gate manifest
  As the install plugin
  I want to write `_install_manifest.json` colocated with the installed `des/`
  So that the runtime freshness gate can distinguish state A/B/C/D by data

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: Install plugin writes a schema-v1 manifest for each source kind
    Given a fresh source tree of kind <source_kind>
    When the install plugin completes installation against that source tree
    Then the installed package contains a `_install_manifest.json` file
    And the manifest has schema_version 1
    And the manifest field `source_kind` is <source_kind>
    And the manifest field `tree_hash` matches the recomputed tree-hash

    Examples:
      | source_kind   |
      | dev-checkout  |
      | pre-built     |
      | wheel         |

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: After a fresh install the gate proceeds for the dev checkout
    Given a fresh source tree of kind dev-checkout
    And the install plugin has completed installation against that source tree
    When the operator imports `des.cli` against the installed tree
    Then the freshness gate PROCEEDS the invocation with exit code 0
    And the gate reports state C

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: Mutating a representative installed file makes the gate REFUSE state D
    Given a fresh source tree of kind dev-checkout
    And the install plugin has completed installation against that source tree
    When the operator mutates the installed file <mutated_file>
    And the operator imports `des.cli` against the installed tree
    Then the freshness gate REFUSES the invocation with exit code 78
    And the gate reports state D
    And the refusal reason cites the diverged file's tree-hash component

    Examples:
      | mutated_file                                 |
      | runtime/freshness.py                         |
      | cli/validate_delivery_contract.py            |
      | adapters/driven/freshness/repo_source_probe.py |
