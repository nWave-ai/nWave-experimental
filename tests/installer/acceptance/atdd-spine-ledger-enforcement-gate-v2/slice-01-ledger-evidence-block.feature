@feature-atdd-spine-ledger-enforcement-gate-v2
Feature: spine-ledger gate ledger-evidence block — refuse Slice-Id commits without verified ledger evidence

  As a nWave operator on a target machine that has adopted the spine
  I want the spine-ledger gate to refuse a commit carrying a Slice-Id trailer whose slice has no matching SliceCommitVerified ledger record
  And I want the gate to ALLOW a commit whose slice DOES have a matching SliceCommitVerified ledger record
  So that operator-bypass-free production commits MECHANICALLY guarantee the carpaccio spine ran for every shipped slice (the F1 seam-rot defect of `verify_slice_ledger_record.py` shipped 2026-05-22 never invoked is finally closed).

  As a nWave operator on a target machine whose spine telemetry directory carries a pre-M7 legacy ledger alongside one or more healthy M7-shape ledgers
  I want the gate to skip the malformed ledger with an audited LedgerSkipped event and continue scanning the healthy ledgers
  So that one legacy file does not fail-stuck-refuse every Slice-Id commit on the target machine (Phase 0 audit Gap B fix option 2 — partial-failure tolerance over operational quarantine).

  Background:
    Given the operator's target machine has nWave installed
    And the spine-ledger gate entry point is the script "spine_ledger_gate"
    And the gate reads ledger records through the SINGLE source of truth "AtCompletionLedger.read_records"
    And the gate writes audit events to ".nwave/des/logs/audit-{today}.log" in JSONL format

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: a Slice-Id commit with NO matching ledger record is refused with a structured verdict
    Given a target machine with a spine-telemetry directory containing zero verified slices
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And a candidate commit message carrying the trailer "Slice-Id: synthetic-001"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-refused"
    And the gate's stdout reports the refusal cause as "block-ledger-evidence-missing"
    And the gate's stdout names the unverified slice as "synthetic-001"
    And the audit log carries zero new "SpineBypassUsed" events for this invocation

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: a Slice-Id commit with a matching SliceCommitVerified ledger record is allowed
    Given a target machine with a spine-telemetry directory containing a verified slice record for slice "synthetic-001" under feature ledger "synthetic-feature"
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And a candidate commit message carrying the trailer "Slice-Id: synthetic-001"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-allowed"
    And the gate's stdout reports the allow cause as "ledger-evidence-present"
    And the gate's stdout names the verified slice as "synthetic-001"
    And the audit log carries zero new "SpineBypassUsed" events for this invocation

  @slice-01 @driving_port @real-io @partial-failure-tolerance @contract-shape:bounded-change
  Scenario: a Slice-Id commit is allowed when one ledger is malformed but a HEALTHY ledger carries the matching verified slice
    Given a target machine with a spine-telemetry directory containing a verified slice record for slice "synthetic-001" under feature ledger "synthetic-feature"
    And the spine-telemetry directory ALSO contains a legacy pre-M7 ledger file named "legacy-broken.jsonl" carrying a record with no "seq" field
    And the operator's environment does NOT carry "NWAVE_SPINE_LEDGER_GATE_BYPASS"
    And the repo carries NO ".nwave/disabled-gates" file
    And a candidate commit message carrying the trailer "Slice-Id: synthetic-001"
    When the operator runs the spine-ledger gate against the candidate commit message
    Then the gate exits with verdict "commit-allowed"
    And the gate's stdout reports the allow cause as "ledger-evidence-present"
    And the gate's stdout lists the skipped ledger file as containing "legacy-broken.jsonl"
    And the audit log carries exactly one new "LedgerSkipped" event for this invocation
    And the audit event names the skipped ledger path as containing "legacy-broken.jsonl"
    And the audit event names the skip cause as "ledger-integrity-violation"
