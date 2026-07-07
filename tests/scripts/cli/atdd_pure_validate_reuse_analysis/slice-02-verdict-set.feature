@feature-fix-design-reuse-first-gate
Feature: The Reuse Analysis gate classifies every verdict in its closed set

  slice-01 proved the gate runs end-to-end on the two extreme cases -- a
  well-formed table and an absent section. This slice delivers the full closed
  verdict set: a table whose Decision token does not normalise is rejected as
  malformed; a CREATE_NEW row with no justification is rejected as unjustified;
  and the three accepted verdicts a feature can legitimately reach -- a
  space-spelled CREATE_NEW that normalises cleanly, a methodology-exempt
  marker, and a no-overlap marker -- each reach their accepted verdict.

  A gate that cannot classify its own exempt inputs is the vacuous no-op the
  gate-or-residue policy forbids: methodology-only features and features that
  genuinely overlap nothing are first-class accepted verdicts the gate itself
  classifies (DDD-9), not a downstream waiver.

  # DDD-2 (closed verdict set), DDD-3 (well-formedness checks), DDD-7
  # (Decision-token normalization), DDD-9 (exemption verdicts), DDD-11 (parser
  # hardening). Driving port: validate-feature-delta CLI --require-reuse-analysis.
  # Layer 3 (subprocess/FS acceptance) -- example-only, no PBT (Mandate 9/11).
  # The DDD-7 normalization universe and DDD-11 parser-hardening universe are
  # enumerated as Scenario Outline rows, not a Hypothesis @given: both are
  # finite closed sets, so the falsifier-gate selects example-based outlines.

  Background:
    Given a feature-delta authored for a code feature

  @slice-02 @error @driving_port @contract-shape:pure-function
  Scenario: A component row with an un-normalisable Decision is rejected as malformed
    Given the feature-delta carries a component row with an un-normalisable Decision
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is rejected for a malformed Reuse Analysis
    And the check leaves the feature-delta unchanged

  @slice-02 @error @driving_port @contract-shape:pure-function
  Scenario: A CREATE_NEW row with an empty Justification is rejected as unjustified
    Given the feature-delta carries a CREATE_NEW row with an empty Justification
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is rejected for an unjustified CREATE_NEW
    And the check leaves the feature-delta unchanged

  # F-fix-reuse-analysis-content-grounding (WS-9) regression lock: a
  # structurally well-formed row is still rejected when its `Existing
  # Component | File` citation is a phantom -- it does not resolve through
  # the CodeFactPort chain. Catches a table that "looks right" but names a
  # component that does not exist.
  @slice-02 @error @driving_port @contract-shape:pure-function
  Scenario: A component row citing a phantom component is rejected as ungrounded
    Given the feature-delta carries a component row citing a phantom component absent from its file
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is rejected for an ungrounded reuse analysis
    And the check leaves the feature-delta unchanged

  @slice-02 @driving_port @contract-shape:pure-function
  Scenario Outline: A feature-delta reaches its accepted verdict
    Given the feature-delta carries <reuse section>
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is <verdict>
    And the check leaves the feature-delta unchanged

    # DDD-7: `CREATE NEW` (space) normalises -- strip -> upper -> collapse
    # internal whitespace runs to `_` -> CREATE_NEW; with a non-empty
    # justification it is accepted. DDD-9: the two exemption markers are
    # first-class accepted verdicts the gate classifies itself. C5 (mode-flag
    # / decision-table: the three materially-distinct accepted paths), C6
    # (the normalization is robustness -- lenient input, explicit verdict).
    Examples: legitimately accepted feature-deltas
      | reuse section                            | verdict                            |
      | a CREATE NEW row spelled with a space    | structurally accepted              |
      | a CREATE_NEW row with a trailing parenthetical qualifier | structurally accepted |
      | a methodology-exempt marker              | accepted as methodology-exempt     |
      | a no-overlap marker                      | accepted as declaring no overlap   |
