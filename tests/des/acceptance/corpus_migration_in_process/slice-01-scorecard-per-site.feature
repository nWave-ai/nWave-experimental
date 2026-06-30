@feature-f-test-corpus-migration-in-process
Feature: The migration scorecard counts non-walking-skeleton forks per scenario

  Mara needs an un-gameable DONE measure for the corpus migration. The committed
  scorecard (scripts/at_corpus_migration_scorecard.py) is a FILE-level gradient
  tracker today: it splits files into pure (fork, no WS marker) and mixed (fork +
  a WS marker anywhere), and counts the pure non-WS forks as the contract number.
  Its own docstring names the file-level split a proxy and anticipates the deeper
  per-scenario proof.

  This slice ships that deeper proof: a --per-site mode that counts non-WS
  spawn-sites PER SCENARIO -- so the 155 forks the 45 mixed files hide behind one
  WS scenario are counted, not exempted. The file-level gradient survives as the
  cheap tracker; --per-site is the un-gameable DONE contract (350 -> 0). The
  scorecard is driven IN-PROCESS for its content (main(argv) + captured output);
  ONE @walking_skeleton subprocess scenario proves the installed script is wired
  end-to-end with the new mode.

  # DESIGN DDD-5 (EXTEND the scorecard: file-level = gradient tracker; --per-site =
  # the un-gameable DONE contract). Driving port: the scorecard
  # at_corpus_migration_scorecard.main(argv) driven IN-PROCESS (loaded from its file
  # path, stdout captured) for the content facet; the single @walking_skeleton
  # subprocess proves the terminal-wiring facet (the installed script runs).
  #
  # Layer 3 (in-process composition acceptance) -- example-only (Mandate 9/11): each
  # scenario pins a single closed observable (the per-site count, the JSON contract
  # fields, the DONE flag).
  #
  # active-RED mechanism (DESIGN P1-P4): the composition loads the present scorecard
  # MODULE and calls its present main attribute, passing the future main(argv) shape.
  # At HEAD main() takes no argv and --per-site is unknown, so the call raises inside
  # it (TypeError / argparse SystemExit) and emits no per-site JSON -> the per-site
  # observable is empty -> a NAMED semantic AssertionError (P4). The file-level
  # gradient scenario drives main(["--json"]) -- also the future argv shape -- so it
  # too is active-RED until main(argv) exists. Collection imports no absent name.
  #
  # OPEN QUESTION 4 RESOLUTION (pinned by S2): the --per-site JSON output contract is
  # the field set {per_site_non_ws_count, by_scenario, by_dir, done}. per_site_non_ws_count
  # is the DONE number the per-batch gate consumes; by_scenario carries the per-scenario
  # {file, scenario, tags, spawn_line, decision} records; by_dir drains the heat-map
  # per batch (DDD-3); done is per_site_non_ws_count == 0.

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The per-site mode counts non-walking-skeleton spawn-sites per scenario
    Given the maintainer can drive the migration scorecard in-process
    When the maintainer runs the scorecard in per-site mode in-process
    Then the scorecard reports a per-site non-walking-skeleton spawn-site count
    And the scorecard per-site mode is recognized
    And the scorecard did not fork an interpreter for the per-site count

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The per-site JSON output carries the pinned contract fields
    Given the maintainer can drive the migration scorecard in-process
    When the maintainer runs the scorecard in per-site mode in-process
    Then the per-site JSON output carries the per-site count field
    And the per-site JSON output carries the per-scenario records field
    And the per-site JSON output carries the per-directory heat-map field
    And the per-site JSON output carries the done field

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The file-level gradient tracker still works after the extension
    Given the maintainer can drive the migration scorecard in-process
    When the maintainer runs the scorecard in file-level mode in-process
    Then the scorecard still emits its file-level gradient split

  @slice-01 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: A fully migrated corpus reports the phase done with a zero per-site count
    Given the maintainer can drive the migration scorecard in-process
    When the maintainer runs the scorecard in per-site mode in-process
    Then the scorecard reports the phase done only when the per-site count is zero

  @slice-01 @coupled @walking_skeleton @driving_port @real-io @requires_external @contract-shape:bounded-change
  Scenario: The installed scorecard script is wired end-to-end with the per-site mode
    Given the maintainer can drive the migration scorecard in-process
    When the maintainer runs the installed scorecard script with the per-site mode end-to-end
    Then the installed scorecard script exits successfully
    And the installed scorecard script emits the per-site count on its terminal output
