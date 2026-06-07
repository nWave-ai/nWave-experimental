@feature-atdd-spine-ledger-enforcement-gate-v2
Feature: spine-ledger PreToolUse hook on Bash — block git commit when ledger evidence is missing

  As a nWave operator working inside a Claude Code session
  I want the spine-ledger gate to refuse a Bash `git commit` whose candidate message carries a Slice-Id trailer for a slice with NO matching SliceCommitVerified ledger record
  And I want the hook to invisibly skip non-commit Bash invocations within a few milliseconds
  And I want the existing pre-bash execution-log guard to keep firing on its own concerns
  So that the closed-loop spine enforcement covers the path the orchestrating LLM actually takes (Bash → git commit) and so that the kill-switch + ledger-evidence contract from slices 00+01 becomes operationally binding without breaking sibling hook concerns.

  Background:
    Given the operator is inside a Claude Code session with the spine-ledger PreToolUse hook installed on Bash
    And the spine-ledger PreToolUse hook entry point is the script "spine_ledger_pre_commit_hook"
    And the hook speaks the Claude Code PreToolUse protocol — JSON stdin, JSON stdout, exit code as decision signal
    And the hook writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format

  @slice-02 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: a Bash git-commit invocation whose candidate message carries an unverified Slice-Id is refused with a block decision
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And a candidate commit message carrying the trailer "Slice-Id: synthetic-001" is staged on disk
    When the Claude Code session prepares to run the Bash command "git commit -F <candidate-commit-msg>"
    And the PreToolUse hook receives the Bash invocation event
    Then the hook returns a block decision to Claude Code
    And the hook's decision reason names the refusal cause "block-ledger-evidence-missing"
    And the hook's decision reason names the unverified slice "synthetic-001"
    And the Bash invocation is refused before the git subprocess is spawned

  @slice-02 @driving_port @real-io @fast-path @contract-shape:unbounded-preservation
  Scenario: a Bash invocation that is NOT a git commit passes the hook within the fast-path budget without invoking the gate
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    When the Claude Code session prepares to run the Bash command "ls -la"
    And the PreToolUse hook receives the Bash invocation event
    Then the hook approves the Bash invocation
    And the hook does NOT invoke the spine-ledger gate subprocess
    And the audit log carries zero new "SpineBypassUsed" events for this invocation
    And the target machine filesystem is unchanged outside transient hook logging

  @slice-02 @driving_port @real-io @matcher-collision-spike @contract-shape:bounded-change
  Scenario: the spine-ledger PreToolUse hook and the pre-existing pre-bash execution-log guard COEXIST on the Bash matcher without interfering
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And the pre-existing pre-bash execution-log guard remains registered on the Bash matcher
    And a candidate commit message carrying the trailer "Slice-Id: synthetic-001" is staged on disk
    When the Claude Code session prepares to run the Bash command "git commit -F <candidate-commit-msg>"
    And the PreToolUse hook chain receives the Bash invocation event
    Then both hooks observe the Bash invocation event in registration order
    And the spine-ledger hook returns a block decision naming "block-ledger-evidence-missing"
    And the pre-bash execution-log guard does NOT mistakenly block the git-commit command
    And the matcher-coexistence semantics are recorded in the slice-02 scaffold notes
