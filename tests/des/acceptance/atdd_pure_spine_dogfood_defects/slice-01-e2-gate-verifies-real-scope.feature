@feature-fix-atdd-pure-spine-dogfood-defects
Feature: The E2 contract gate verifies a real, non-empty test scope

  As the U2 G_COMMIT exit gate that must refuse a commit whose terminating run
    was narrower than the contract
  I want the contract gate to derive its gate-scope digest from the actual
    collected suite, and to fail closed on an errored or empty collection
  So that the integrity gate cannot pass a commit vacuously -- an absent
    integrity control is worse than a known-missing one

  # slice-01 -- the walking-skeleton E2-gate fix. Today `run_contract_gate`
  # collects under a double `-q` (addopts `-q` + an explicit `-q`), pytest
  # collapses output to per-file count lines, the `::` parser matches zero
  # lines, and the digest is sha256("") -- a vacuous gate, repo-wide.
  #
  # SUT state model -- a `--collect-only` digest run resolves the collection
  # into one of FOUR closed condition classes:
  #   REAL_NON_EMPTY       -- the suite collects N>0 node-ids cleanly -> digest
  #   COLLECTION_ERROR     -- pytest exits non-(0,5) -> guard fires closed
  #   ZERO_NODES_EXIT_ZERO -- exit 0 but zero node-ids parse -> guard fires closed
  #   GENUINELY_EMPTY      -- exit 5, no tests -> digests cleanly (legitimate)
  #
  # Driving port: the real `run_contract_gate.main` CLI entry point -- the same
  # definition the U2 exit gate invokes (port-to-port, not a helper).
  # Layer 3+ (real subprocess collection) -> example-only, the guard's closed
  # condition universe is enumerable -> Scenario Outline parametrize-collapse,
  # NOT PBT (Mandate 9, 11; falsifier-gate: finite enumerable domain).
  #
  # RED contract: every scenario fails on master -- the digest is sha256(""),
  # the guard does not exist. The scaffolds raise AssertionError
  # (MISSING_FUNCTIONALITY). They pass once slice-01 lands the fix.

  @slice-01 @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:pure-function
  Scenario: The contract gate digests a clean non-empty contract suite
    Given a contract test tree that collects clean
    When the operator derives the contract gate-scope digest
     And the operator derives the contract gate-scope digest again
    Then the digest fingerprints the non-empty collected scope
     And the digest is not the empty-suite sentinel
     And the collection that produced the digest preserved strict marker checking
     And both digest derivations produce the identical digest

  @slice-01 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: The contract gate fails closed when the collection is untrustworthy
    Given a contract test tree whose collection is <collection_condition>
    When the operator derives the contract gate-scope digest
    Then the contract gate fails closed instead of digesting a partial scope
     And the operator is told the collection could not be trusted

    Examples:
      | collection_condition                |
      | broken by a collection error        |
      | empty while reporting a populated suite |

  @slice-01 @driving_port @real-io @contract-shape:pure-function
  Scenario: A genuinely empty contract scope still digests cleanly
    Given a contract test tree with no contract-marked tests at all
    When the operator derives the contract gate-scope digest
    Then the contract gate digests the empty scope without failing closed
