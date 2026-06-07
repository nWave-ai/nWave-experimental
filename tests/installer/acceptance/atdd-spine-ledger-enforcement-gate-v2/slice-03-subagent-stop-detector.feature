@feature-atdd-spine-ledger-enforcement-gate-v2
Feature: spine-ledger SubagentStop soft-escalation detector — surface Agent-dispatched code-shipping that bypassed the spine

  As the nWave orchestrator who occasionally dispatches code-shipping work via Agent (sub-agent) without DES markers
  I want a SubagentStop hook that inspects the returning sub-agent transcript for code-shipping signals (Edit on src/des/* or Bash `git commit`)
  And, when those signals are present WITHOUT a preceding CarpaccioGateCleared event for the current session, emits a structured `SpineBypassDetected` audit event
  And I want a read-only sub-agent return (only Read/Grep/Glob tool uses) to leave NO audit event and NO escalation noise
  And I want a sub-agent return that DID go through the spine (a preceding `CarpaccioGateCleared` event exists in the current session ledger) to be silently honoured — NO `SpineBypassDetected` emitted
  So that the Gap C marker-less Agent-dispatch class surfaced by RCA 2026-05-28 (430 marker-less transcripts in a single day) becomes observable post-hoc — every Agent-dispatched code-shipping is either spine-gated OR audited, never invisible.

  Background:
    Given the operator is inside a Claude Code session with the spine-ledger SubagentStop hook installed
    And the spine-ledger SubagentStop hook entry point is the script "subagent_stop_spine_detector"
    And the hook speaks the Claude Code SubagentStop protocol — JSON stdin, audit-log side-effect, exit code as soft signal
    And the hook writes audit events to ".nwave/des/logs/audit-{today}.jsonl" in JSONL format

  @slice-03 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: an Agent-dispatched code-shipping transcript with NO preceding spine-cleared event emits one SpineBypassDetected audit event
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the current Claude Code session has NO preceding "CarpaccioGateCleared" event in the spine-telemetry directory
    And an Agent sub-agent has returned with a transcript containing an Edit tool use on "src/des/example_module.py"
    When the Claude Code session emits the SubagentStop event for the returning Agent
    And the SubagentStop hook receives the Agent return event
    Then the audit log carries exactly one new "SpineBypassDetected" event for this Agent return
    And the new audit event names the cause as "no-spine-event-in-session"
    And the new audit event names at least one transcript-evidence entry containing "Edit src/des/"
    And the new audit event carries the transcript path of the returning Agent
    And the hook returns a soft-pass decision to Claude Code

  @slice-03 @driving_port @real-io @fast-path @contract-shape:unbounded-preservation
  Scenario: an Agent-dispatched read-only transcript (only Read/Grep/Glob) leaves the audit log unchanged
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the current Claude Code session has NO preceding "CarpaccioGateCleared" event in the spine-telemetry directory
    And an Agent sub-agent has returned with a transcript containing ONLY Read and Grep and Glob tool uses
    When the Claude Code session emits the SubagentStop event for the returning Agent
    And the SubagentStop hook receives the Agent return event
    Then the audit log carries zero new "SpineBypassDetected" events for this Agent return
    And the hook returns a soft-pass decision to Claude Code
    And the target machine filesystem is unchanged outside transient hook logging

  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: an Agent-dispatched code-shipping transcript WITH a preceding spine-cleared event is silently honoured
    Given a target machine with a spine-telemetry directory containing one verified slice under feature "atdd-spine-ledger-enforcement-gate-v2" slice "slice-99"
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the current Claude Code session has a preceding "CarpaccioGateCleared" event for slice "slice-99" recorded in the spine-telemetry directory
    And an Agent sub-agent has returned with a transcript containing an Edit tool use on "src/des/example_module.py"
    When the Claude Code session emits the SubagentStop event for the returning Agent
    And the SubagentStop hook receives the Agent return event
    Then the audit log carries zero new "SpineBypassDetected" events for this Agent return
    And the hook returns a soft-pass decision to Claude Code
