@feature-slice-dependency-declared
Feature: A declared slice dependency redirects the carpaccio order check
  As the DES hook layer guarding carpaccio slice delivery order (M8)
  I want a crafter dispatch entering slice-N checked against the PREDECESSOR
    its OWN Slice-Plan row DECLARES (`depends-on {slice-id}`) instead of
    blindly `slice-(N-1)`
  So that two genuinely independent slices that both depend on the same
    earlier slice are no longer forced serial by row position alone, while a
    plan that declares nothing keeps behaving exactly as it does today, and a
    malformed declaration blocks LOUD rather than silently readmitting the
    old default

  # slice-01 of `slice-dependency-declared` (mikado node D94, ADR-CARPACCIO-
  # DEPENDENCY-001, DDD-1/DDD-2/DDD-3). The walking skeleton of the whole
  # feature: new domain grammar + `resolve_predecessor_slice` +
  # `DeclaredDependencyMalformed` + the M8 call-site swap, all through ONE
  # gate (`_carpaccio_order_block`).
  #
  # Driving port: the M8 order check via `intercept_atdd_pure_dispatch`
  # (src/des/adapters/drivers/hooks/carpaccio_intercept.py) for focused
  # scenarios; the real `handle_pre_tool_use` PreToolUse hook entry, driven
  # via the Claude Code JSON stdin protocol, for the walking-skeleton
  # scenario.
  #
  # Contract these ATs pin (DDD-1/DDD-2/DDD-3, CT-1..CT-7, CT-2b):
  #   * declared-first  -- a well-formed, strictly-backward `depends-on
  #     {slice-id}` on the entering slice's OWN row makes that target the
  #     predecessor the order check consults, even when the true positional
  #     `slice-(N-1)` has no verified record (CT-2).
  #   * positional fallback, unconditional on silence -- an absent, unreadable
  #     or malformed plan, an absent row, or an empty/silent Annotation cell
  #     ALL resolve to EXACTLY `slice-(N-1)`, byte-identical to pre-feature
  #     behaviour (CT-1, CT-7).
  #   * malformed blocks LOUD, never a silent fallback -- more than one
  #     token, a non-`slice-NN` shaped target, a target absent from the plan,
  #     or a self-/forward-reference all BLOCK, even when the true positional
  #     predecessor IS verified (CT-3, CT-4, CT-5, CT-6).
  #   * the message earns its GDP-3 HOW -- a block on an unresolved SILENT
  #     row names both the rebuild-predecessor remedy and the declare-
  #     depends-on alternative (CT-2b).

  @wiring_e2e @walking_skeleton @slice-01 @driving_port @contract-shape:pure-function @covers-R1
  Scenario: A declared predecessor permits a dispatch the positional default would have blocked
    Given a crafter dispatch enters slice-04
    And a Slice Plan where slice-04 declares "depends-on slice-01"
    And slice-01 carries a verified slice commit in the ledger
    And slice-03 carries no verified slice commit in the ledger
    When the real PreToolUse hook processes the dispatch
    Then the dispatch is allowed

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R1
  Scenario Outline: A well-formed declared predecessor is honored by the order check
    Given a crafter dispatch enters <entering_slice>
    And a Slice Plan where <entering_slice> declares "depends-on <declared_predecessor>"
    And <declared_predecessor> carries a verified slice commit in the ledger
    When the M8 carpaccio order check evaluates the dispatch
    Then the dispatch is allowed

    Examples:
      | entering_slice | declared_predecessor |
      | slice-03       | slice-02              |
      | slice-04       | slice-01              |

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R2 @covers-R7
  Scenario Outline: A slice with no resolvable declaration falls back to the pre-existing positional predecessor
    Given a crafter dispatch enters slice-03
    And the Slice Plan is <plan_shape>
    And slice-02 carries <predecessor_ledger_state>
    When the M8 carpaccio order check evaluates the dispatch
    Then the dispatch is <verdict>

    Examples:
      | plan_shape                                 | predecessor_ledger_state             | verdict |
      | absent (no feature-delta.md at all)        | no verified slice commit in the ledger | blocked |
      | absent (no feature-delta.md at all)        | a verified slice commit in the ledger  | allowed |
      | present but has no Slice Plan section       | no verified slice commit in the ledger | blocked |
      | present with a malformed Slice Plan table   | no verified slice commit in the ledger | blocked |
      | unreadable (the path is a directory)        | no verified slice commit in the ledger | blocked |
      | missing the entering slice's own row        | no verified slice commit in the ledger | blocked |
      | silent on the entering slice's own row      | no verified slice commit in the ledger | blocked |

  @slice-01 @driving_port @error @negative @contract-shape:pure-function @covers-R3 @covers-R4 @covers-R5 @covers-R6
  Scenario Outline: A malformed declared dependency always blocks the dispatch, never a silent fallback
    Given a crafter dispatch enters <entering_slice>
    And a Slice Plan where <entering_slice> declares "<declared_annotation>"
    And <true_predecessor> carries a verified slice commit in the ledger
    When the M8 carpaccio order check evaluates the dispatch
    Then the dispatch is blocked
    And the block names the CarpaccioDeclaredDependencyMalformed event

    Examples:
      | entering_slice | declared_annotation                       | true_predecessor |
      | slice-04       | depends-on slice-01 depends-on slice-02   | slice-03         |
      | slice-03       | depends-on foo                            | slice-02         |
      | slice-03       | depends-on slice-04a                      | slice-02         |
      | slice-04       | depends-on slice-99                       | slice-03         |
      | slice-03       | depends-on slice-03                       | slice-02         |
      | slice-03       | depends-on slice-05                       | slice-02         |

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R8
  Scenario: The block on an unresolved silent predecessor names both remedies
    Given a crafter dispatch enters slice-03
    And slice-02 carries no verified slice commit in the ledger
    When the M8 carpaccio order check evaluates the dispatch
    Then the dispatch is blocked
    And the block names the CarpaccioSliceOutOfOrder event
    And the block explains both the rebuild remedy and the declare-depends-on alternative
