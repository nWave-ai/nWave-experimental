@feature-skill-normative-content-gate @slice-04 @real-io @driving_port
Feature: A discriminating multi-word phrase is accepted — discrimination is word count, not length
  # Slice-04 (DESIGN §9): the positive-acceptance side of the discrimination
  # rule that slice-02 introduces. AC-05 proves a discriminating multi-word
  # phrase loads and is enforceable; AC-09 pins the boundary — the three-word
  # phrase "zero is an obligation" is shorter in characters than markers the rule
  # already accepts, yet it loads cleanly, proving the discrimination predicate
  # (ADR-SNCG-004) is word-count >= 2, never raw string length. Sequenced after
  # slice-02 (which introduces the LOUD-rejection side of the same rule).
  #
  # Driven through the real `des` dispatcher (@real-io -> example-based).

  @contract-shape:bounded-change @ac-05 @slice-04
  Scenario: A discriminating multi-word phrase loads and is enforceable
    Given a manifest registering clause "protocol-driver:assert-shipped-artifact" against the real shipped skill
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the clause was included in the checked set

  @contract-shape:bounded-change @ac-09 @slice-04
  Scenario: A three-word marker shorter than accepted markers still loads
    Given a manifest clause whose marker is the three-word phrase "zero is an obligation"
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the manifest loads without a discrimination error
    And no INDETERMINATE is emitted for this clause
