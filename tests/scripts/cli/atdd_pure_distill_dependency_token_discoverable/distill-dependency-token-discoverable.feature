@feature-parallel-by-default-distill-slicing
Feature: The dependency token is discoverable from the DISTILL authoring surface

  Row 1 (feature parallel-by-default-slice-plan) documented `depends-on {slice-id}`
  and its flipped default (silence = parallel-safe) on the two surfaces a PO reads
  while authoring in DISCUSS. This slice is the SIBLING half: an acceptance-designer
  who originates a Slice Plan directly in DISTILL (DISCUSS skipped) never opens
  nw-discuss -- so the same vocabulary must be discoverable from within his OWN
  trigger-loaded skill surface, the `nw-distill` skill FAMILY (core + composed
  modules). Per D-4 (SSOT/DRY) the family must POINT at nw-discuss's vocabulary
  reference, never carry a second, independently-worded copy that could drift.

  # docs/feature/parallel-by-default-distill-slicing/feature-delta.md slice-02.
  # No driving port exists for "is this documented" (same posture as the row-1
  # sibling suite tests/scripts/cli/atdd_pure_slice_dependency_annotation_discoverable/
  # and as tests/des/unit/cli/test_carpaccio_ceiling_15_and_coupled_affordance.py
  # AT-d). These scenarios read the nw-distill family files directly, locus-scoped
  # (a window around the token), never file-scoped substring matching.
  # Layer 3 (FS acceptance) -- example-only, no PBT (Mandate 9/11): the family is a
  # finite, enumerable closed set (source + installed trees), so a Scenario Outline
  # over that set is the correct paradigm.

  @slice-02 @driving_port @contract-shape:pure-function
  Scenario Outline: The token, its default flip, and the nw-discuss cross-link are discoverable in the family
    Given the <tree> nw-distill skill family
    When an acceptance-designer reads the family for the dependency-token vocabulary
    Then the family documents the depends-on slice-id token
    And the token locus states the flipped default in plain language
    And the token locus points at nw-discuss's Slice Plan annotation vocabulary reference
    And the family never tells an empty annotation it owes a justification
    And the family never reads silence as assume-serial

    # the source tree is a hard requirement; the installed tree (this machine's
    # ~/.claude dogfood copy) is SKIPPED, not failed, when absent -- a fresh
    # clone / CI checkout has no local nWave install.
    Examples: family trees
      | tree                          |
      | nw-distill family (source)    |
      | nw-distill family (installed) |

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A restated copy with no nw-discuss cross-link is rejected as an SSOT drift risk
    Given a fabricated family that restates the rule but omits the nw-discuss pointer
    When an acceptance-designer reads the family for the dependency-token vocabulary
    Then the family documents the depends-on slice-id token
    But the token locus does not point at nw-discuss's Slice Plan annotation vocabulary reference

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A bare token mention with no default-flip statement is rejected
    Given a fabricated family that names the token but never states the default flip
    When an acceptance-designer reads the family for the dependency-token vocabulary
    Then the family documents the depends-on slice-id token
    But the token locus does not state the flipped default in plain language

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A family that makes an empty annotation owe a justification is caught
    Given a fabricated family that makes an empty annotation owe a justification
    When an acceptance-designer reads the family for the dependency-token vocabulary
    Then the family tells an empty annotation it owes a justification

  @slice-02 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A family that reads silence as assume-serial is caught
    Given a fabricated family that reads silence as assume-serial
    When an acceptance-designer reads the family for the dependency-token vocabulary
    Then the family reads silence as assume-serial
