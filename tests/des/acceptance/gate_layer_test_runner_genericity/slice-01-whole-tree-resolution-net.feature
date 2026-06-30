@feature-fix-whole-tree-contract-gate-runner-aware
Feature: Every whole-tree contract-gate mode resolves the runner before any pytest-bound leg

  As nWave's genericity / target-machine-agnosticism mandate (ADR-FLOW-011 D7)
  I want an architecture net that FAILS while any whole-tree contract-gate mode
    reaches a pytest-bound leg (`_collect_scope` / `_run_contract_suite` /
    `_committed_scope_digest_quiet`) WITHOUT first routing through the whole-tree
    runner resolver (`_maybe_route_through_runner_whole_tree`)
  So that the runner-aware whole-tree routing can never erode site-by-site -- a
    new whole-tree mode that hardcodes pytest is caught by construction, the same
    proven static-scan net shape as the existing `python_for` leak scan.

  # ---------------------------------------------------------------------------
  # slice-01 D7 (EXTENDS gate_layer_test_runner_genericity). A stdlib-only STATIC
  # SCAN (AST walk, NO subprocess, NO git, cross-OS -- genericità) over the REAL
  # `src/des/cli/run_contract_gate.py`. The scan IS the driving port (Layer-4
  # static analysis over the shipped source); it reads the module as TEXT and
  # `ast.parse`s it -- it NEVER imports a production gate symbol.
  #
  # The invariant: in EACH of the four whole-tree mode functions (`_mode_run_suite`,
  # `_mode_print_digest`, `_mode_committed_scope_digest`, `_mode_verify_gate_scope`)
  # the FIRST call into a pytest-bound leg must be PRECEDED by a call to the
  # whole-tree runner resolver. A mode that reaches a pytest leg with no preceding
  # resolution is an "unrouted mode" leak.
  #
  # active-RED at HEAD: `_maybe_route_through_runner_whole_tree` does NOT exist, so
  # all four whole-tree modes reach a pytest-bound leg with NO preceding resolver
  # call -> the scan reports four unrouted modes and the net REFUSES to pass. RED,
  # NOT BROKEN: the composition imports only stdlib (`ast`) + the domain types --
  # no not-yet-implemented production module -- and the assertion is reached and
  # fails because the unrouted modes EXIST. DELIVER wires the resolver into each
  # mode's preamble -> the scan returns an empty leak list -> the net goes GREEN.
  #
  # Mandate-9/11 (example-only): the unrouted set is an enumerable fact about HEAD
  # over a fixed module, not an unbounded input space -- no paired PBT.

  @slice-01 @driving_port @real-io @arch-test @contract-shape:unbounded-preservation
  Scenario: Each whole-tree mode routes through the runner resolver before any pytest leg
    Given the whole-tree contract-gate source
    When the architecture net scans each whole-tree mode for the resolution-before-pytest ordering
    Then the net reports every whole-tree mode that reaches a pytest-bound leg with no preceding runner resolution
     And the net refuses to pass while any whole-tree mode reaches pytest without resolving the runner first

  @slice-01 @driving_port @real-io @arch-test @error @contract-shape:unbounded-preservation
  Scenario: The net fails closed when it can locate no whole-tree modes to scan
    Given a whole-tree contract-gate source that resolves to no whole-tree modes
    When the architecture net scans each whole-tree mode for the resolution-before-pytest ordering
    Then the net refuses to report a clean result it never actually earned
