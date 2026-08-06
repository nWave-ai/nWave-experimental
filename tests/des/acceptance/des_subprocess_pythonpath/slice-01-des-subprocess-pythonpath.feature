@feature-fix-des-subprocess-pythonpath
Feature: A spawned des gate always finds des on the child path

  As a beta tester running des gates from the installed shim on a system Python
  I want every des gate that spawns a child des.cli module to give that child
    des on its import path by construction
  So that the gate records a real Gate-Scope instead of a silent null-scope
    false-DONE when the child cannot import des

  # atdd_pure slice-01: scenarios RUN and fail for the right reason at HEAD --
  # AC-1 on a real non-empty violation list (~18 inline spawn sites), AC-2/AC-3
  # on a real AssertionError (the des_spawn helper is not yet implemented). The
  # centralized helper + the 18-site migration is DELIVER's job to GREEN them.

  @slice-01 @contract-shape:bounded-change @real-io
  Scenario: No des gate spawns a child des module outside the centralized helper
    Given the des source tree as it ships
    When the architecture is inspected for inline des-module spawns
    Then no des gate spawns a child des module outside the centralized helper

  @slice-01 @contract-shape:bounded-change @real-io
  Scenario: A spawned child des command imports des under a des-stripped host
    Given a host where des is stripped from the import path
    When a gate spawns the read-only integrity command through the centralized helper
    Then the child command imports des and succeeds

  @slice-01 @contract-shape:bounded-change @in-memory
  Scenario: The helper applies the interpreter and the des path by construction
    Given a caller that asks the helper to spawn a des command without naming an interpreter or a path
    When the helper spawns the child
    Then the child is launched with the resolved interpreter and des on its path

  @slice-01 @contract-shape:unbounded-preservation @in-memory
  Scenario: The helper forwards the caller's options and preserves the caller's path entries
    Given a caller that asks the helper to spawn a des command with its own options and its own path entry
    When the helper spawns the child
    Then the caller's options are forwarded and the caller's path entry is preserved alongside des
