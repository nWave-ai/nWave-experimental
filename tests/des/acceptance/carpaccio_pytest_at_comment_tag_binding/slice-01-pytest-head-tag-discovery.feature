@feature-carpaccio-pytest-at-comment-tag-binding
Feature: A pytest test file binds to its feature via a head-comment tag

  The carpaccio slice gate discovers a feature's ``.feature`` files via a
  file-level ``@feature-{id}`` tag (``feature_tag_files``). An infra/CLI
  feature whose DISTILL wave correctly authored plain pytest ATs (not
  Gherkin -- the right format for infra/CLI behavior) owns zero ``.feature``
  files, so it is structurally invisible to that discovery and the gate
  wrongly rejects it ``no-scenarios-for-slice``. This slice generalizes the
  SAME ``@feature-{id}`` head-tag idiom to ANY test file via a new, separate
  resolver -- ``feature_tag_files`` and its 2 production consumers stay
  byte-unchanged (ADD-not-mutate).

  # docs/feature/carpaccio-pytest-at-comment-tag-binding/feature-delta.md
  # [REF] Slice Plan slice-01 (@walking-skeleton, Elephant-Carpaccio thin
  # vertical) + EXP-carpaccio-pytest-at-comment-tag-binding-1.
  #
  # Driving surface (Layer 3 composition, Mandate 13): the NEW
  # `feature_tagged_test_files` resolver (src/des/application/feature_at_files.py)
  # IS the shared application-layer entry point future CLIs (slice-04's
  # carpaccio-slice-gate auto-discovery) will consume -- driving it directly via
  # a composition root mirrors the sibling `carpaccio_slice_plan_parser` slice's
  # treatment of the shared parser entry point, not a direct-domain bypass.
  #
  # @real-io (Architecture of Reference): the composition root writes real
  # pytest test files onto a real filesystem under pytest tmp_path -- no fake.
  # Example-only, no PBT machinery (Mandate 9/11): slice-01 pins the two closed
  # cases (head-tagged file discovered; untagged file excluded / empty-set
  # guardrail), not a property.
  #
  # This feature's OWN ATs are authored as Gherkin (not pytest) so they clear
  # the EXISTING Gherkin-only carpaccio gate today -- the chicken-and-egg this
  # feature exists to fix.

  @slice-01 @covers-R1 @real-io @contract-shape:bounded-change
  Scenario: A head-tagged pytest test file is discovered as belonging to the feature
    Given a scratch repository containing a pytest test file head-tagged "@feature-test-binding-1"
    And the repository also contains an untagged pytest test file
    When the maintainer resolves the feature's tagged test files
    Then the head-tagged test file is included in the resolved file set
    And the untagged test file is excluded from the resolved file set

  @slice-01 @covers-R1 @real-io @contract-shape:bounded-change
  Scenario: A repository with no head-tagged test file resolves an empty set
    Given a scratch repository containing an untagged pytest test file
    When the maintainer resolves the feature's tagged test files
    Then the resolved file set is empty
