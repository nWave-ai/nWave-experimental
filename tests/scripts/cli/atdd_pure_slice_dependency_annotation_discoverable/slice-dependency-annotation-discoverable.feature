@feature-parallel-by-default-slice-plan
Feature: The dependency token is discoverable at the point of authoring a Slice Plan

  Slice-01 taught the validator to require a Justification on any Slice Plan row
  declaring `depends-on {slice-id}` -- a REACTIVE gate that fires only after a PO
  has already written the row. This slice is the PROACTIVE half (GDP-2): the
  `depends-on {slice-id}` token and its flipped default (silence = parallel-safe)
  must be documented on the two surfaces a PO is actually looking at while
  authoring a Slice Plan -- alongside `@walking_skeleton`/`@infrastructure`/
  `@coupled`, in the SAME section, never merely somewhere in the file.

  # docs/feature/parallel-by-default-slice-plan/feature-delta.md slice-02.
  # No driving port exists for "is this documented" (same posture as
  # tests/des/unit/cli/test_carpaccio_ceiling_7_and_coupled_affordance.py
  # AT-d for the sibling `@coupled` affordance) -- these scenarios read the
  # two authoring-surface files directly, section-scoped (fence-aware
  # extraction keyed to the exact H2 heading), never file-scoped substring
  # matching.
  # Layer 3 (FS acceptance) -- example-only, no PBT (Mandate 9/11): the
  # surface set is a finite, enumerable closed set (4 files), so a Scenario
  # Outline over that set is the correct paradigm.

  @slice-02 @driving_port @contract-shape:pure-function
  Scenario Outline: The dependency token and its default flip are documented in the vocabulary section
    Given the <surface> authoring surface
    When a PO reads that surface's annotation-vocabulary section
    Then the section documents the depends-on slice-id token
    And the section states the flipped default in plain language
    And the section still documents its pre-existing annotation tokens

    # source copies are hard requirements; installed copies (this machine's
    # ~/.claude dogfood tree) are SKIPPED, not failed, when absent -- a
    # fresh clone/CI checkout has no local nWave install (composition
    # docstring explains why).
    Examples: authoring surfaces
      | surface                             |
      | nw-discuss skill (source)           |
      | nw-discuss skill (installed)        |
      | nw-product-owner agent (source)     |
      | nw-product-owner agent (installed)  |

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A token documented outside the vocabulary section is not recognized as documented
    Given a fabricated surface with the token pasted into an unrelated appendix
    When a PO reads that surface's annotation-vocabulary section
    Then the section does not document the depends-on slice-id token

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A bare token mention with no default-flip statement is rejected
    Given a fabricated surface that names the token without stating the default flip
    When a PO reads that surface's annotation-vocabulary section
    Then the section documents the depends-on slice-id token
    But the section does not state the flipped default in plain language

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: An edit that documents the new token but drops an existing one is rejected as a regression
    Given a fabricated surface that documents the new token but drops an existing annotation token
    When a PO reads that surface's annotation-vocabulary section
    Then the section no longer documents its pre-existing annotation tokens
