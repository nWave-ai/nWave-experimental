@feature-gate-layer-test-runner-genericity
Feature: The gate/wave layer routes interpreter resolution through the runner registry, never hardcoded python

  As nWave's genericity / target-machine-agnosticism mandate
    (CLAUDE.md: "the only runtime dependency is Python; gate/wave logic must be
    language-agnostic behind a per-language port")
  I want an architecture net that ALLOWLISTS the two legitimate interpreter-
    resolution boundaries (the interpreter port + the python run-facet) and FAILS
    on any other `python_for(` interpreter-resolution in the gate/wave layer
  So that gate LOGIC operating on a NON-python target (a Rust/Go crate) can never
    hardcode `python_for("pytest")` and deny that target a genuine
    SliceCommitVerified -- the bug class tsunami hit on a real Rust crate is
    prevented by construction, not patched site-by-site

  # slice-01 (the arch-test net) -- authored FIRST, RED on HEAD.
  #
  # The net is a stdlib-only STATIC SCAN (AST walk, NO subprocess, cross-OS,
  # git-free -- genericità) over the REAL `src/des/` tree, mirroring the existing
  # `tests/build/.../test_des_bundle_steps.py` stdlib-only static-scan precedent.
  #
  # Driving port (Mandate-13): the scan IS the driving port (Layer-4 static
  # analysis over the shipped source). It reads each `src/des/**/*.py` as TEXT
  # and `ast.parse`s it; it NEVER imports a production gate symbol, NEVER spawns a
  # subprocess, NEVER touches git.
  #
  # AST not grep (precision): the net flags actual `python_for(` CALL nodes, never
  # docstring/comment MENTIONS. `carpaccio_intercept.py` (8 comment mentions) and
  # `_reverify_core.py` (1 docstring mention) MENTION `python_for(None)` but never
  # CALL it -- an `ast.Call` walk excludes them; a grep would false-positive.
  #
  # RED at HEAD (the live leak inventory, tsunami `callers_of python_for`,
  # binding-resolved): five gate-LOGIC call sites outside the allowlist --
  #   run_contract_gate.py:228 (_collect_scope),
  #   run_contract_gate.py:372 (_run_arch_invariant_set),
  #   run_contract_gate.py:682 (_run_contract_suite),
  #   verify_deliver_entry_contract.py:321 (_run_manifest_validator),
  #   verify_environmental_e2e.py:235 (_run_e2e_against_installed).
  # After slice-02/03 reroute them through `RunnerAdapter`, the net goes GREEN.
  #
  # Layer 4+ static scan over a fixed tree -> example-only (Mandate 9, 11): the
  # leak set is an enumerable fact about HEAD, not an unbounded input space.

  @slice-01 @driving_port @real-io @arch-test @contract-shape:unbounded-preservation
  Scenario: Every interpreter resolution in the gate/wave layer routes through the allowlist
    Given the gate and wave source layer
    When the architecture net scans it for interpreter-resolution outside the allowlist
    Then the net reports every hardcoded interpreter-resolution site by file and line
     And the net refuses to pass while any interpreter-resolution leak remains outside the allowlist

  @slice-01 @driving_port @real-io @arch-test @contract-shape:unbounded-preservation
  Scenario: The two legitimate interpreter-resolution boundaries are exempt with a stated rationale
    Given the gate and wave source layer
    When the architecture net scans it for interpreter-resolution outside the allowlist
    Then the interpreter port and the python run-facet are exempt from the net
     And each exempt boundary carries a one-line rationale a reviewer can read

  @slice-01 @driving_port @real-io @arch-test @error @contract-shape:unbounded-preservation
  Scenario: The net fails closed when it scans no source at all
    Given a gate and wave source layer that resolves to no source files
    When the architecture net scans it for interpreter-resolution outside the allowlist
    Then the net refuses to report a clean result it never actually earned
