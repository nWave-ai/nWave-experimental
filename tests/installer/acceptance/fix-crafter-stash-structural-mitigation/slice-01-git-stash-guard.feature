@feature-fix-crafter-stash-structural-mitigation
Feature: git-stash guard PreToolUse hook on Bash — block mutating git stash, allow worktree + read-only inspection

  As a nWave operator working inside a Claude Code session where a sub-agent has been dispatched
  I want the git-stash guard to refuse a Bash `git stash` (push/pop/apply/drop/clear/save) invocation and point me at the safe `git worktree add /tmp/probe HEAD` alternative
  And I want an explicit kill-switch so a deliberate, audited bypass is possible when I genuinely need it
  And I want read-only stash inspection (`git stash list`, `git stash show`), `git worktree`, and every other git command to pass through untouched
  So that the STANDING "no git stash, use worktree" rule becomes mechanically binding (an 11th violation is impossible without the explicit audited bypass) rather than a text rule that has failed ten times.

  Background:
    Given the operator is inside a Claude Code session with the git-stash guard PreToolUse hook installed on Bash
    And the git-stash guard PreToolUse hook entry point is the script "git_stash_guard"
    And the hook speaks the Claude Code PreToolUse protocol — JSON stdin, JSON stdout, exit code as decision signal
    And the hook writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: a Bash git-stash invocation is refused with a block decision pointing at the worktree alternative
    Given the operator's environment does NOT carry "NWAVE_GIT_STASH_ALLOW"
    When the Claude Code session prepares to run the Bash command "git stash push -m work-in-progress"
    And the git-stash guard receives the Bash invocation event
    Then the hook returns a block decision to Claude Code
    And the hook's decision reason names the safe alternative "git worktree add /tmp/probe HEAD"
    And the hook's decision reason names the bypass mechanism "NWAVE_GIT_STASH_ALLOW"
    And the Bash invocation is refused before the git stash subprocess is spawned

  @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: the operator deliberately bypasses the guard and the bypass is recorded in the audit log
    Given the operator's environment carries "NWAVE_GIT_STASH_ALLOW" set to "1"
    When the Claude Code session prepares to run the Bash command "git stash"
    And the git-stash guard receives the Bash invocation event
    Then the hook approves the Bash invocation
    And the audit log gains exactly one new "GitStashBypassUsed" event for this invocation
    And the new bypass event names the git-stash command "git stash"

  @driving_port @real-io @slice-01 @contract-shape:unbounded-preservation
  Scenario Outline: a safe Bash command passes the guard untouched without any block or audit side effect
    Given the operator's environment does NOT carry "NWAVE_GIT_STASH_ALLOW"
    When the Claude Code session prepares to run the Bash command "<command>"
    And the git-stash guard receives the Bash invocation event
    Then the hook approves the Bash invocation
    And the audit log carries zero new "GitStashBypassUsed" events for this invocation
    And the target machine filesystem is unchanged outside transient hook logging

    Examples: clean-tree regression-isolation alternative + read-only inspection + help + unrelated git
      | command                          |
      | git worktree add /tmp/probe HEAD |
      | git stash list                   |
      | git stash show                   |
      | git stash --help                 |
      | git status                       |
