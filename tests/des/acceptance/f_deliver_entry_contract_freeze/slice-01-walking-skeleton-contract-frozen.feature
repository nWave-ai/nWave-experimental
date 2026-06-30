@feature-f-deliver-entry-contract-freeze
Feature: DELIVER-entry contract freeze (walking skeleton)

  A developer entering DELIVER (first gate-IN) with a structurally-complete
  contract -- every locked feature-delta section present-and-valid AND every
  planned Slice-Plan row backed by an authored AT module -- has that contract
  mechanically attested complete and a ContractFrozen record written. A missing
  locked section, a planned-slice-with-no-AT-module, or an unreadable contract is
  REFUSED (no false freeze).

  # The thinnest end-to-end vertical: read feature-delta -> validate locked
  # sections -> assert AT-module-per-slice -> write ContractFrozen -> PASS, on the
  # real DELIVER gate-IN driving port (`des verify-deliver-entry-contract`).

  @slice-01 @walking-skeleton @driving_port @contract-shape:unbounded-preservation @CT-1 @CT-7
  Scenario: A structurally-complete contract is frozen at the first DELIVER gate-IN
    Given a DELIVER-entry contract that is complete
    When the contract-freeze gate runs at the first DELIVER gate-IN
    Then the freeze gate returns a pass verdict
    And the contract is frozen in the completion ledger

  @slice-01 @driving_port @contract-shape:unbounded-preservation @error @CT-2b
  Scenario: A contract missing a locked section is refused
    Given a DELIVER-entry contract that is missing_section
    When the contract-freeze gate runs at the first DELIVER gate-IN
    Then the freeze gate returns a fail verdict
    And no contract is frozen in the completion ledger

  @slice-01 @driving_port @contract-shape:unbounded-preservation @error @CT-3
  Scenario: A planned slice with no authored AT module is refused
    Given a DELIVER-entry contract that is slice_without_at
    When the contract-freeze gate runs at the first DELIVER gate-IN
    Then the freeze gate returns a fail verdict
    And no contract is frozen in the completion ledger

  @slice-01 @driving_port @contract-shape:unbounded-preservation @error @CT-6
  Scenario: An unreadable contract degrades loud to indeterminate, never a false freeze
    Given a DELIVER-entry contract that is unreadable
    When the contract-freeze gate runs at the first DELIVER gate-IN
    Then the freeze gate returns an indeterminate verdict
    And no contract is frozen in the completion ledger
