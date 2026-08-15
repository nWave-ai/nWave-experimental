# slice-01 -- dead-code-sweep-testarch-rules. Repeated AST-graph + import-graph
# audits found unwired des.testarch.rules modules with zero production
# importers; 7 are now removed. ``assert_state_delta`` stays
# because registry_conformance's own drift-guard self-check reads its
# AUDITED_LAYERS constant live. This is a
# behavior-preserving prefactoring slice's own regression net: it pins BOTH the
# removal and the exception so neither silently regresses.
#
# Honest tagging: an in-process filesystem + AST-import check -- @component
# (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no
# real I/O beyond reading files on disk under the repo already checked out.

@feature-dead-code-sweep-testarch-rules @slice-01 @component
Feature: The 7 confirmed-dead testarch rules stay removed and the live exception stays present

  As the methodology maintainer
  I want the 7 unwired des.testarch.rules modules gone and their exclusive test
  families gone with them, while the module whose live constant
  registry_conformance still reads stays in place
  So that the dead-code sweep does not silently regress in either direction

  @slice-01 @contract-shape:pure-function
  Scenario: The 7 confirmed-dead rule modules no longer exist
    Given the des.testarch.rules package directory
    When I list the 7 modules retired by the dead-code sweeps
    Then none of the 7 retired modules exist on disk

  @slice-01 @contract-shape:pure-function
  Scenario: The registry-conformance exception remains present
    Given the des.testarch.rules package directory
    When I list the module registry_conformance's drift-guard still reads live constants from
    Then the exception module still exists on disk

  @slice-01 @contract-shape:pure-function
  Scenario: The mixed acceptance suite for this rule family still collects and passes
    Given the at-mandate-mechanical-enforcement acceptance suite
    When I collect it with pytest
    Then collection succeeds with no dangling import to a retired module
