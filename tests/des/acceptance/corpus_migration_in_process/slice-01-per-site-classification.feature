@feature-f-test-corpus-migration-in-process
Feature: The spawn classifier decides KEEP vs MIGRATE per spawn-site, not per file

  Mara, an nWave maintainer, is migrating the slow acceptance corpus off
  interpreter-forks to in-process driving. The committed scorecard counts the
  forks, but its classification -- and the live readiness gate's -- is at FILE
  level: a file that carries one @walking_skeleton scenario exempts ALL its forks,
  even the non-walking-skeleton ones. The measured corpus has 45 mixed files
  hiding 155 non-WS forks behind exactly this blind spot. A file-level contract is
  gameable: add one WS scenario and arbitrary non-WS forks go free.

  This slice ships the un-gameable enabler: classify each spawn-site by its
  ENCLOSING scenario's tags. A spawn-site is KEEP iff its enclosing scenario
  carries @walking_skeleton; otherwise MIGRATE. The classifier totals over the
  open corpus -- an unrecognized language is NOT_APPLICABLE (no false flag), an
  unparseable file is INDETERMINATE (recorded, never silently dropped), git is
  never invoked. The enforcement gate's blocking scope follows the migrated
  directories, so tightening to per-site does not hard-fail the un-migrated corpus.

  # DESIGN DDD-1 (ADR-TEST-003: per-spawn-site, tag-derived, un-gameable) +
  # DDD-4 (EXTEND axis_b_levers.check_non_ws_spawn to per-site; scope follows
  # migration). Driving port (Architecture-of-Reference "Driving", in-process
  # default): the REAL per-site classifier scan_spawn_sites + the enforcement lever
  # check_non_ws_spawn, driven IN-PROCESS over synthetic tmp corpora -- NO
  # interpreter fork (this feature's own dog food). Mandate-13 satisfied in-process.
  #
  # Layer 3 (in-process composition acceptance) -- example-only, no PBT
  # (Mandate 9/11): each scenario pins a single closed observable (the per-site
  # KEEP/MIGRATE decision, the total-function verdict). The sad paths (unparseable
  # file, unrecognized language, un-migrated corpus) are enumerated explicitly
  # (Mandate 11), never PBT-generated.
  #
  # active-RED mechanism (DESIGN P1-P4): the composition imports ONLY the stable
  # present entries (scan_spawn_sites / check_non_ws_spawn) at module top -- never
  # an absent per-site callable. At HEAD scan_spawn_sites classifies at FILE level
  # (_file_is_walking_skeleton short-circuits the whole file) and exposes NO
  # per-site classified_sites / per_site_verdict surface; check_non_ws_spawn has no
  # migration_scope. So the per-site MIGRATE/KEEP decision, the NOT_APPLICABLE/
  # INDETERMINATE verdict, and the scope-follows-migration behaviour are absent at
  # RUNTIME inside the in-process call -> every observable is a NAMED semantic
  # AssertionError (P4). Collection imports only present names -> COLLECTS cleanly.
  #
  # OPEN QUESTION 1 RESOLUTION (pinned by S3+S4): pytest-bdd per-step WS attribution
  # resolves at the SCENARIO level by binding step -> scenarios. An UNCONDITIONAL
  # spawn in a step a non-WS scenario can reach is ALWAYS a MIGRATE target (the
  # non-WS scenario must not reach a fork); a spawn whose step is bound EXCLUSIVELY
  # to @walking_skeleton scenarios is KEEP (the conservative un-gameable default).

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A non-walking-skeleton fork in a mixed file is classified as a migration target
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a mixed file with a walking-skeleton fork and a plain non-walking-skeleton fork
    When the maintainer classifies each spawn-site in-process
    Then the non-walking-skeleton fork is classified as a migration target
    And the non-walking-skeleton fork is not exempted as a kept walking-skeleton fork
    And the classifier did not fork an interpreter
    And the classifier did not invoke git

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A walking-skeleton fork in the same mixed file is classified as kept
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a mixed file with a walking-skeleton fork and a plain non-walking-skeleton fork
    When the maintainer classifies each spawn-site in-process
    Then the walking-skeleton fork is classified as kept

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A shared pytest-bdd step with an unconditional fork reachable by a non-walking-skeleton scenario is a migration target
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a mixed pytest-bdd feature whose shared step forks unconditionally
    When the maintainer classifies each spawn-site in-process
    Then the shared-step fork is classified as a migration target

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A shared pytest-bdd step bound only to walking-skeleton scenarios is kept
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a pytest-bdd feature whose forking step is bound only to walking-skeleton scenarios
    When the maintainer classifies each spawn-site in-process
    Then the shared-step fork is classified as kept

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: An unparseable file is reported indeterminate, never silently dropped
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a file that does not parse
    When the maintainer classifies each spawn-site in-process
    Then the classifier reports the per-site verdict as indeterminate
    And the unparseable file is recorded rather than silently dropped

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: An unrecognized target language is reported not applicable without a false flag
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the target project is written in "haskell"
    And the corpus has a file with a non-walking-skeleton fork
    When the maintainer classifies each spawn-site in-process
    Then the classifier reports the per-site verdict as not applicable
    And the classifier raises no false migration flag on the unrecognized language

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The enforcement gate flags a non-walking-skeleton fork inside a migrated directory
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a migrated directory and an un-migrated directory each with a non-walking-skeleton fork
    When the maintainer runs the enforcement gate scoped to the migrated directory in-process
    Then the enforcement gate flags the non-walking-skeleton fork in the migrated directory
    And the enforcement gate honours the migration scope

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The enforcement gate does not hard-fail a non-walking-skeleton fork in an un-migrated directory
    Given the maintainer has a synthetic acceptance corpus the classifier can scan
    And the corpus has a migrated directory and an un-migrated directory each with a non-walking-skeleton fork
    When the maintainer runs the enforcement gate scoped to the migrated directory in-process
    Then the enforcement gate does not flag the non-walking-skeleton fork in the un-migrated directory
    And the enforcement gate honours the migration scope
