# slice-01 -- dead-code-sweep-testarch-rules (techdebt.md item
# dead-code-sweep-2026-08-03-testarch-rules-eight-of-ten-unwired). A manual
# AST-graph + import-graph audit found 8 of the 10 des.testarch.rules modules
# had zero production importers; 6 are cleanly dead and removed by this slice.
# 2 (assert_state_delta, pbt_layer_mode) are kept because registry_conformance's
# own drift-guard self-check reads their AUDITED_LAYERS / PBT_FORBIDDEN_LAYERS
# constants live (registry_conformance_composition.py:54-55). This is a
# behavior-preserving prefactoring slice's own regression net: it pins BOTH the
# removal and the exception so neither silently regresses.
#
# Honest tagging: an in-process filesystem + AST-import check -- @component
# (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no
# real I/O beyond reading files on disk under the repo already checked out.

@feature-dead-code-sweep-testarch-rules @slice-01 @component
Feature: The 6 confirmed-dead testarch rules stay removed and the 2 live exceptions stay present

  As the methodology maintainer
  I want the 6 unwired des.testarch.rules modules gone and their exclusive test
  families gone with them, while the 2 modules registry_conformance still reads
  live constants from stay in place
  So that the dead-code sweep does not silently regress in either direction

  @slice-01 @contract-shape:pure-function
  Scenario: The 6 confirmed-dead rule modules no longer exist
    Given the des.testarch.rules package directory
    When I list the 6 modules retired by the 2026-08-03 dead-code sweep
    Then none of the 6 retired modules exist on disk

  @slice-01 @contract-shape:pure-function
  Scenario: The 2 exception modules registry_conformance depends on stay present
    Given the des.testarch.rules package directory
    When I list the 2 modules registry_conformance's drift-guard still reads live constants from
    Then both exception modules still exist on disk

  @slice-01 @contract-shape:pure-function
  Scenario: The mixed acceptance suite for this rule family still collects and passes
    Given the at-mandate-mechanical-enforcement acceptance suite
    When I collect it with pytest
    Then collection succeeds with no dangling import to a retired module
