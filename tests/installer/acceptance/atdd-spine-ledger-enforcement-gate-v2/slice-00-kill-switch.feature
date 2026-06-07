@feature-atdd-spine-ledger-enforcement-gate-v2
Feature: spine-ledger gate kill-switch — operator bypass + dormant-mode safety

  As a nWave operator paged at 3am because the spine-ledger gate is mis-refusing
  I want a single environment variable OR a single repo-local file to immediately bypass the gate
  And I want every bypass to leave an audit trail naming WHO bypassed and WHY
  So that I can unblock production without `--no-verify` AND so that bypasses are accountable.

  As the installer of nWave on a target machine without spine telemetry
  I want the gate to behave as dormant (PASS without error) when no `.nwave/telemetry/atdd-pure/` exists
  So that customers who have not adopted the spine are not blocked by a gate they have no telemetry for.

  Background:
    Given the operator's target machine has nWave installed
    And the spine-ledger gate entry point is the script "spine_ledger_gate"
    And the gate writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format

  @slice-00 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: operator bypasses the gate via the documented environment variable and the bypass is audited
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment carries "NWAVE_SPINE_LEDGER_GATE_BYPASS=1"
    And a candidate commit message carrying the trailer "Slice-Id: slice-99"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-allowed"
    And the gate's stdout reports the bypass cause as "operator-env-bypass"
    And the audit log carries exactly one new "SpineBypassUsed" event for this invocation
    And the audit event names the bypass source as "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the audit event names the candidate slice as "slice-99"

  @slice-00 @driving_port @real-io @contract-shape:bounded-change
  Scenario: operator bypasses the gate via the repo-local disabled-gates file and the bypass is audited
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries a ".nwave/disabled-gates" file listing "spine-ledger-gate" on its own line
    And a candidate commit message carrying the trailer "Slice-Id: slice-99"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-allowed"
    And the gate's stdout reports the bypass cause as "operator-file-bypass"
    And the audit log carries exactly one new "SpineBypassUsed" event for this invocation
    And the audit event names the bypass source as ".nwave/disabled-gates"
    And the audit event names the candidate slice as "slice-99"

  @slice-00 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: a target machine without spine telemetry sees the gate as dormant — no error, no block, no audited bypass
    Given a target machine that has NOT adopted the spine (no ".nwave/telemetry/atdd-pure/" directory exists)
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And a candidate commit message carrying the trailer "Slice-Id: slice-99"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-allowed"
    And the gate's stdout reports the dormant-mode cause as "spine-telemetry-absent"
    And the audit log carries zero new "SpineBypassUsed" events for this invocation
    And the target machine filesystem is unchanged outside the audit log
