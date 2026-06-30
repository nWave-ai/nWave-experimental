@feature-f-test-corpus-migration-in-process
Feature: One migrated exemplar proves the in-process conversion recipe

  The migration is mechanical, not judgment-per-file: every non-walking-skeleton
  forking acceptance test converts by the same recipe -- drive the production EDGE
  (the shipped cli main(argv) / application-service) in-process through a fake
  output sink, never the leaf function; keep the driven-internal ports in-memory;
  preserve the sad-paths (ZOMBIES) 1:1; use a small fixture. The recipe's output
  must satisfy the per-site classifier: zero non-walking-skeleton spawn-sites for
  the migrated file.

  This slice pins the recipe's contract on one exemplar: a migrated form that
  drives the EDGE in-process reports zero non-walking-skeleton spawn-sites, is
  confirmed to drive the production EDGE rather than an isolated leaf (the C13/C14
  anti-theater check), and preserves its error-path scenario. The build-ATs that
  must prove the real gates run keep exactly ONE @walking_skeleton subprocess
  scenario per command; in a build-incapable sandbox that scenario degrades
  LOUD-skip with a structured reason -- never a silent pass, never a hard block.

  # DESIGN DDD-2 (edge-drive in-process recipe; never the leaf; preserve ZOMBIES) +
  # DDD-6 / ADR-TEST-004 (no second exemption tag; the one @walking_skeleton
  # subprocess survives; @requires_external degrades-LOUD-skip in a build-incapable
  # sandbox). Driving port: the REAL per-site classifier + the EDGE wiring lever
  # check_unwired_entry + the future @requires_external resolver, all IN-PROCESS.
  #
  # Layer 3 (in-process composition acceptance) -- example-only (Mandate 9/11). Sad
  # paths (ZOMBIES preservation, build-incapable degrade-LOUD-skip) enumerated
  # explicitly (Mandate 11).
  #
  # active-RED mechanism (DESIGN P1-P4): the recipe-conformance surface (zero non-WS
  # forks AND drives the EDGE AND ZOMBIES preserved) and the @requires_external
  # degrade-LOUD-skip resolver are ABSENT at HEAD -- reached by getattr at RUNTIME
  # inside the in-process call, so each observable is empty -> a NAMED semantic
  # AssertionError (P4). Collection imports only present names.
  #
  # OPEN QUESTION 2 RESOLUTION (pinned by S4): a @walking_skeleton @requires_external
  # build scenario in a build-incapable sandbox produces a SKIP decision carrying a
  # structured, grep-able loud reason naming the missing capability -- silent_pass is
  # forbidden (never minted GREEN), hard_blocked is forbidden (it is a skip, not a
  # failure). Degrade-LOUD, never silent-pass, never hard-block.

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A migrated exemplar reports zero non-walking-skeleton spawn-sites
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has one exemplar migrated to drive the edge in-process
    When the maintainer classifies each spawn-site in-process
    Then the migrated exemplar reports zero non-walking-skeleton spawn-sites
    And the classifier surfaced a per-site resolution for the migrated exemplar

  @slice-01 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: The migrated exemplar drives the production edge rather than an isolated leaf
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has one exemplar migrated to drive the edge in-process
    When the maintainer classifies each spawn-site in-process
    Then the classifier confirms the migrated exemplar drives the production edge
    And the exemplar drives a wired production edge symbol rather than an isolated leaf

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The migrated exemplar preserves its sad-path scenario
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has one exemplar migrated to drive the edge in-process
    When the maintainer classifies each spawn-site in-process
    Then the classifier confirms the migrated exemplar preserves its error-path scenario

  @slice-01 @coupled @driving_port @real-io @error @requires_external @contract-shape:unbounded-preservation
  Scenario: A build-AT walking-skeleton scenario degrades loud-skip in a build-incapable sandbox
    Given the maintainer can drive the requires-external skip resolver in-process
    When the maintainer resolves the requires-external skip decision for a build-incapable sandbox
    Then the build scenario is skipped rather than failed
    And the skip carries a loud structured reason naming the missing capability
    And the build scenario is not silently passed
    And the build scenario is not hard-blocked
