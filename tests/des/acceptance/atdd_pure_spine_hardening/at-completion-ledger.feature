@feature-atdd-pure-spine-hardening @slice-03
Feature: The AT-completion ledger is an integrity-checked atdd_pure audit substrate
  As the DES hook layer that records and later reconstructs carpaccio gate state
  I want every ledger record to carry a gap-free monotonic sequence number and a
    record hash, appended under an OS file lock, with a fail-closed integrity read
  So that the U1 carpaccio-order check and the U4 feature-end gate read a
    trustworthy machine SSOT -- a corrupt ledger blocks loud, never undercounts

  # slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 -- ADR-030 D3 / M7).
  # Delivery order 00 -> 03 -> 01 -> 02 -> 04: slice-03 (the M7 ledger) lands
  # BEFORE slice-01, so slice-01's M8 carpaccio-order check ships load-bearing.
  #
  # Driving port: the AtCompletionLedger writer/reader module
  # (src/des/adapters/driven/logging/at_completion_ledger.py) -- the production
  # substrate the U1/U2/U4 hook intercepts emit into and read from.
  #
  # Ledger substrate contract (M7, the spec these ATs pin):
  #   * append-only JSONL at .nwave/telemetry/atdd-pure/{feature_id}.jsonl
  #   * every appended record carries a gap-free monotonic per-feature `seq`
  #     and a `record_hash` over the record's own fields
  #   * the append acquires an advisory fcntl.flock for the write duration
  #   * the integrity read fails closed (LedgerIntegrityViolation) on a
  #     malformed line, a truncated final line, a record_hash mismatch, or a
  #     seq gap -- never a silent undercount
  #   * the ledger directory is provisioned mkdir(parents=True, exist_ok=True);
  #     writability is checked EAFP via the append itself, not an os.access probe

  @wiring_e2e @walking_skeleton @slice-03 @driving_port @contract-shape:state-mutation
  Scenario: An operator reconstructs which slices' gates passed from the ledger
    Given a fresh AT-completion ledger for an atdd_pure feature
    When a cleared carpaccio gate is recorded for slice-01
    And a verified slice commit is recorded for slice-01
    And a cleared carpaccio gate is recorded for slice-02
    Then the integrity-checked read of the ledger succeeds
    And the ledger reports a verified slice commit for slice-01
    And the ledger does not report a verified slice commit for slice-02
    And every ledger record carries a gap-free monotonic sequence number
    And every ledger record carries a record hash over its own fields

  @slice-03 @driving_port @property @error @contract-shape:state-mutation
  Scenario Outline: An integrity-checked ledger read fails closed on corruption
    Given an AT-completion ledger with three recorded gate events
    And the ledger has been corrupted with <corruption>
    When the ledger is read under the integrity contract
    Then the integrity-checked read verdict is <verdict>

    Examples:
      | corruption             | verdict   |
      | well-formed            | succeeds  |
      | a malformed line       | is blocked|
      | a truncated final line | is blocked|
      | a tampered record hash | is blocked|
      | a gap in the sequence  | is blocked|

  @slice-03 @driving_port @error @contract-shape:state-mutation
  Scenario: The ledger directory is provisioned on the first append
    Given an atdd_pure feature whose ledger directory does not yet exist
    When a cleared carpaccio gate is recorded for slice-01
    Then the ledger directory is provisioned and the record is appended
    And the integrity-checked read of the ledger succeeds
