@feature-fix-atdd-pure-spine-dogfood-defects
Feature: The contract test suite collects clean

  As the atdd_pure DES spine that gates every commit on the WHOLE contract
    test scope
  I want the contract test suite to collect with zero collection errors
  So that slice-01's fail-closed guard runs against an already-clean tree and
    the gate-scope digest fingerprints the complete contract, not a partial one

  # slice-00 -- the walking-skeleton prerequisite (hard-sequenced before
  # slice-01). The contract tree has pre-existing collection errors (the 3
  # known ModuleNotFoundErrors are the SEED set, re-enumerated at RED -- they
  # are not a fixed closed set, since fixing import error N can reveal error
  # N+1 in the same module). slice-00 is done only at a fresh-collect 0 errors.
  #
  # SUT state model -- a contract-suite collection probe resolves to one of:
  #   CLEAN      -- 0 collection errors, the tree collects clean
  #   HAS_ERRORS -- >=1 collection error, pytest exits 2
  #
  # Driving port: the real `pytest --collect-only` contract probe (CLI runner
  # via subprocess), with `--strict-markers` preserved (residuality S-1).
  # Layer 3+ (real subprocess I/O) -> example-only, no PBT (Mandate 9, 11).
  #
  # RED contract: AT(1)+AT(2) fail on master while the seed collection errors
  # exist; they pass once slice-00 fixes all path/packaging drift. AT(3) is a
  # RED probe -- deliberately break an import, observe pytest exit 2 + the
  # collection-error summary, then DELIVER closes it.

  @slice-00 @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: The whole contract suite collects with zero collection errors
    Given a contract test tree with all path and packaging drift repaired
    When the operator collects the whole contract suite
    Then the collection reports zero collection errors
     And the collection covers a non-empty set of contract tests

  # LOW 5: AT(2) is intentionally retained alongside AT(1). AT(1) asserts the
  # aggregate CLEAN verdict; AT(2) adds the no-silent-DROP guarantee -- its
  # second Then corroborates exit-code vs collection-error-summary agreement,
  # a distinct check (a module could be dropped WITHOUT erroring the run if
  # the summary line and exit code disagreed). The scenario name reflects that
  # no-silent-drop emphasis rather than re-stating "collects clean".
  @slice-00 @real-io @adapter-integration @contract-shape:unbounded-preservation
  Scenario: No previously-failing module is silently dropped from the scope
    Given a contract test tree with all path and packaging drift repaired
    When the operator collects the whole contract suite
    Then every contract test module imports and contributes its tests
     And no module is silently dropped from the contract scope

  @slice-00 @error @real-io @contract-shape:bounded-change
  Scenario: A broken import is reported as a collection error, not silently dropped
    Given a contract test module with a deliberately broken import
    When the operator collects the whole contract suite
    Then the collection reports a non-zero collection-error count
     And the collection signals failure through a collection-error exit code
