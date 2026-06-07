@feature-d4-phase-3-flavor-dispatcher
Feature: LogPersistencePort sinks gate events through a sink-agnostic adapter

  As D4 Phase 3 slice-04 author of the LogPersistencePort foundation
  I want every gate to emit `GateLogEvent` through `LogPersistencePort.emit`
  so the destination path is an adapter concern (per INV-3 gate emits log via
  adapter port; gate does NOT know where the log goes), and the shipped
  `JsonlLogAdapter` with fanout writes BOTH per-feature ledger AND singleton
  common-log atomically — closing friction #36 (common-log walking-skel
  partial-ship) STRUCTURALLY because a gate cannot "forget" to write the
  common log when the adapter does it

  Background:
    Given the log persistence composition is available

  @walking_skeleton @driving_port @real-io @slice-04 @contract-shape:bounded-change
  Scenario: A gate emits a log event through the jsonl adapter with fanout enabled and both ledgers receive it
    Given the jsonl log adapter is configured with fanout enabled for feature "f-x"
    And a gate log event named "gate.carpaccio.slice-cleared" carrying payload "{slice_id=slice-04}"
    When the gate emits the event through the log persistence port
    Then the per-feature ledger for "f-x" contains exactly one event named "gate.carpaccio.slice-cleared"
    And the common audit log contains exactly one event named "gate.carpaccio.slice-cleared"

  @driving_port @real-io @slice-04 @error @contract-shape:unbounded-preservation
  Scenario: A jsonl adapter write failure leaves the gate verdict unchanged and surfaces a stderr diagnostic
    Given the jsonl log adapter is configured with fanout enabled for feature "f-y"
    And the per-feature ledger destination is not writeable
    And a gate log event named "gate.carpaccio.slice-cleared" carrying payload "{slice_id=slice-05}"
    When the gate emits the event through the log persistence port
    Then the log persistence port does not raise
    And a stderr diagnostic mentions the failing destination

  @driving_port @real-io @slice-04 @contract-shape:bounded-change
  Scenario: The silent adapter captures emitted events in memory for fixture introspection
    Given the silent log adapter is configured with capture in memory enabled
    And a gate log event named "gate.contract.tree-cleared" carrying payload "{digest=abc123}"
    And a gate log event named "gate.scope.completeness-cleared" carrying payload "{at_count=3}"
    When the gate emits each event through the log persistence port
    Then the silent adapter captured exactly two events
    And the first captured event is named "gate.contract.tree-cleared"
    And the second captured event is named "gate.scope.completeness-cleared"
