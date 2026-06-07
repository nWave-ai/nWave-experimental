@feature-fix-distill-human-signoff
Feature: The signoff signature is bound by a block, a generated trailer, and an engine-written ledger record

  The human signs the in-document signoff block once; the machine derives
  the git trailer from the block; the deterministic engine appends a ledger
  record. The three surfaces are bound to one identity — the canonical-
  content digest the block carries.

  A hand-edited trailer (or a trailer asserted independently of the block)
  diverges from the re-derived value and is refused. An LLM agent that tries
  to author the ledger record is refused at the architecture level: the
  ledger writer is deterministic engine code only, and the only call sites
  live in a whitelisted set of engine modules.

  # Driving port: verify_coverage_map emit-trailer (block -> trailer
  # projection); the ledger writer function and its call graph (architecture
  # test). Layer 3 (subprocess / FS acceptance) -- example-only sad paths
  # (Mandate 11). The architecture test is a static AST check (no subprocess).

  Background:
    Given a feature whose design wave has produced a component manifest
    And a coverage map has been authored and signed by a human

  @slice-04 @driving_port @contract-shape:bounded-change
  Scenario: The trailer re-derived from the signoff block matches the commit trailer
    When the engine emits the trailer derived from the signoff block
    Then the emitted trailer matches the commit trailer carried alongside the coverage map
    And the ledger carries one signed coverage map record whose digest matches the signoff block

  @slice-04 @driving_port @error @contract-shape:bounded-change
  Scenario: A hand edited trailer that diverges from the signoff block is refused
    Given the commit trailer has been hand edited away from the signoff block
    When the reviewer verifies the coverage map
    Then the verify gate refuses for a trailer mismatch
    And the ledger does not gain a new signed coverage map record

  @slice-04 @arch-test @contract-shape:pure-function
  Scenario: The ledger writer is only reachable from engine code, never from an agent
    When a static call graph scan inspects the repository
    Then no agent dispatch path reaches the signed coverage map ledger writer
    And the only callers of the signed coverage map ledger writer are engine modules in the production deterministic tree
