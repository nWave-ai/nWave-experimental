@feature-feature-delta-section-schema @slice-03
Feature: The Architecture and Contract Tests section is an additive Composite
  As an nWave maintainer converging the feature-delta form with the SF tier
  I want the new Architecture and Contract Tests section validated as a Composite of
    two byte-locked Table sub-blocks, added WITHOUT touching any existing section
  So that the cross-tier column form is enforced while the Slice Plan stays five columns

  # slice-03 of feature-delta-section-schema -- ADR-FLOW-007 §S.5. The only
  # genuinely-new validator: the Composite-of-two-Tables convergence section.
  # DRIVING PORT (Mandate-13, Layer 3 subprocess): `des feature-delta-schema verify`
  # for the Composite checks; `des validate-feature-delta --require-slice-plan` for the
  # additivity-preservation check (the EXISTING 5-column gate must stay green).
  # Cross-tier column lock (byte-identical with SF, do NOT change):
  #   Contract-Tests:     Component/AT-target | Contract-shape | Universe | Assertion-mechanism | Consumed-by
  #   Architecture-Tests: Invariant | AST-query-or-probe | Enforcement-layer | Consumed-by
  # Active-RED: at HEAD the scaffold raises; the Composite validator does not exist yet.

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The convergence section is validated as a Composite of two tables
    Given a feature-delta carrying a well-formed Architecture and Contract Tests section
    When the schema gate verifies the document
    Then the verdict is pass

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: The Contract-Tests sub-table columns are byte-locked
    Given a feature-delta whose Contract-Tests sub-table header is reordered
    When the schema gate verifies the document
    Then the verdict is fail naming the architecture-and-contract-tests section

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: The Architecture-Tests sub-table columns are byte-locked
    Given a feature-delta whose Architecture-Tests sub-table header is reordered
    When the schema gate verifies the document
    Then the verdict is fail naming the architecture-and-contract-tests section

  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The convergence section is additive and the slice plan stays five columns
    Given a feature-delta carrying both the slice plan and the convergence section
    When the existing slice-plan gate runs on the document
    Then the five-column slice plan is still accepted
