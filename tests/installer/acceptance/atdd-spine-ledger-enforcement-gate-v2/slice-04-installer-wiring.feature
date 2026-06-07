@feature-atdd-spine-ledger-enforcement-gate-v2
Feature: spine-ledger installer wiring + aggregator subcommand — propagate the 3 hook scripts to the target machine and surface bypass density

  As the nWave maintainer shipping the spine-ledger enforcement gate as a first-class installer concern
  I want `nwave-ai install` to propagate the 3 spine-ledger hook scripts (slice-00 gate, slice-02 PreToolUse hook, slice-03 SubagentStop detector) to the operator's `~/.claude/` tree
  And the corresponding HOOK_EVENTS entries (PreToolUse/Bash + SubagentStop) to be registered with `# des-hook:` marker prefixes so `nwave-ai uninstall` cleanly removes them with no orphans
  And a `des verify-slice-ledger-evidence --report --since=<date>` aggregator subcommand that surfaces cumulative bypass / block / audit-event counts since the named date as structured JSON
  So that the spine-ledger enforcement gate ships as a customer-runnable surface (the F1 seam-rot defect class — never-wired enforcement script shipped + forgotten — is closed by mechanical installer wiring + a production-readiness aggregator that proves the gate fires on real operator activity).

  Background:
    Given the operator runs `nwave-ai install` against an isolated installation target
    And the installation target's `settings.json` carries the slice-00 / slice-02 / slice-03 spine-ledger hook entries with `# des-hook:` marker prefixes
    And the installation target's `~/.claude/scripts/` directory carries the 3 spine-ledger hook scripts
    And the `des` dispatcher registry advertises the `verify-slice-ledger-evidence` subcommand

  @slice-04 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: install propagates the 3 spine-ledger hook scripts and uninstall removes them with no orphan hook entries
    Given a clean target machine with no prior `~/.claude/` tree
    When the operator runs `nwave-ai install` against the clean target
    Then the target machine's `~/.claude/scripts/` directory contains "spine_ledger_gate.py" and "spine_ledger_pre_commit_hook.py" and "spine_ledger_subagent_stop_detector.py"
    And the target machine's `settings.json` carries exactly one new "PreToolUse" entry whose command names "spine_ledger_pre_commit_hook"
    And the target machine's `settings.json` carries exactly one new "SubagentStop" entry whose command names "spine_ledger_subagent_stop_detector"
    And the new spine-ledger hook entries carry "# des-hook:" marker prefixes
    When the operator runs `nwave-ai uninstall` against the installed target
    Then the target machine's `settings.json` carries zero "PreToolUse" entries whose command names "spine_ledger_pre_commit_hook"
    And the target machine's `settings.json` carries zero "SubagentStop" entries whose command names "spine_ledger_subagent_stop_detector"
    And the target machine's `~/.claude/scripts/` directory contains zero spine-ledger hook scripts
    And the target machine's pre-existing settings entries outside the spine-ledger hook scope are unchanged

  @slice-04 @driving_port @real-io @contract-shape:pure-function
  Scenario: the aggregator subcommand surfaces cumulative spine-ledger event counts since the named date as structured JSON
    Given a target machine with an audit log carrying 3 "SliceCommitVerified" events on "2026-05-28"
    And the audit log also carries 2 "CarpaccioGateCleared" events on "2026-05-28"
    And the audit log also carries 1 "SpineBypassDetected" events on "2026-05-28"
    And the audit log already carries 1 "SpineBypassUsed" events on "2026-05-27"
    When the operator runs `des verify-slice-ledger-evidence --report --since=2026-05-28`
    Then the subcommand exits with status 0
    And the subcommand emits structured JSON to stdout
    And the structured JSON names the field "since" with value "2026-05-28"
    And the structured JSON names the field "slice_commits_verified" with value 3
    And the structured JSON names the field "carpaccio_gates_cleared" with value 2
    And the structured JSON names the field "bypasses_detected" with value 1
    And the structured JSON names the field "bypasses_used" with value 0
    And the target machine filesystem is unchanged outside transient stdout emission

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: the HOOK_EVENTS registry grows by 2 entries with the slice-04 wiring and all spine-ledger entries carry the `# des-hook:` marker for clean uninstall
    Given the pre-slice-04 `HOOK_EVENTS` tuple in `scripts.shared.hook_definitions` carries exactly 10 entries
    And the pre-slice-04 `HOOK_EVENTS` tuple carries exactly 5 "PreToolUse" entries
    And the pre-slice-04 `HOOK_EVENTS` tuple carries exactly 2 "SubagentStop" entries
    When the operator imports `scripts.shared.hook_definitions` after the slice-04 wiring lands
    Then the post-slice-04 `HOOK_EVENTS` tuple carries exactly 13 entries
    And the post-slice-04 `HOOK_EVENTS` tuple carries exactly 7 "PreToolUse" entries
    And the post-slice-04 `HOOK_EVENTS` tuple carries exactly 3 "SubagentStop" entries
    And every "PreToolUse" entry whose command names "spine_ledger" carries the "# des-hook:" marker prefix
    And every "SubagentStop" entry whose command names "spine_ledger" carries the "# des-hook:" marker prefix
    And the shared `_is_des_command` predicate returns true for every spine-ledger entry's command string
