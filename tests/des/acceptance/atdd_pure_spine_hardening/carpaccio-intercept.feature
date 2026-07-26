@feature-atdd-pure-spine-hardening @slice-01
Feature: The carpaccio entry gate is an unskippable PreToolUse intercept
  As the DES hook layer guarding atdd_pure carpaccio slice delivery
  I want a crafter dispatched into an A_GREEN_ATS slice intercepted at the
    PreToolUse boundary -- the carpaccio gate runs whether or not the
    orchestrating LLM chooses to run it
  So that a defective marker set, a rejected slice, an out-of-order slice, or a
    handler exception all fail closed as a blocked dispatch -- never a silent
    fall-through

  # slice-01 of F-DES-ATDD-PURE-HOOK-GATES (U1 -- ADR-030 D1).
  # Delivery order 00 -> 03 -> 01 -> 02 -> 04: slice-01 ships AFTER slice-03's
  # M7 ledger, so the M8 carpaccio-order check is load-bearing, not provisional.
  #
  # Driving port: the U1 intercept `evaluate_atdd_pure_dispatch`
  # (src/des/adapters/drivers/hooks/carpaccio_intercept.py) for focused
  # scenarios; the real `handle_pre_tool_use` PreToolUse hook entry, driven via
  # the Claude Code JSON stdin protocol, for the walking-skeleton scenario.
  #
  # U1 contract (the spec these ATs pin):
  #   * M3 positive recognition -- DES-MODE:atdd_pure absent => classic
  #     fall-through; present + valid markers => atdd_pure branch; present +
  #     incomplete => BLOCK AtddPureMarkerSetIncomplete (never fall-through).
  #   * carpaccio CLI invoked for A_GREEN_ATS; non-zero exit => block.
  #   * M8 order check -- entering slice-N (N>1) blocks CarpaccioSliceOutOfOrder
  #     when slice-(N-1) carries no SliceCommitVerified ledger record.
  #   * M1 handler-exception -- any exception in the U1 branch is an
  #     AtddPureHookInternalError block (decision:block + non-zero exit_code),
  #     never the bare exit-1 / status:error path.

  @wiring_e2e @walking_skeleton @slice-01 @driving_port @contract-shape:state-mutation
  Scenario: A defective atdd_pure crafter dispatch is blocked at the PreToolUse boundary
    Given an atdd_pure feature with an integrity-checked AT-completion ledger
    And a crafter dispatch into slice-01 carrying an atdd_pure dispatch missing its slice marker
    When the real PreToolUse hook processes the dispatch
    Then the dispatch is blocked
    And the block names the AtddPureMarkerSetIncomplete event

  @slice-01 @driving_port @property @contract-shape:state-mutation
  Scenario Outline: The U1 intercept classifies and gates an atdd_pure dispatch
    Given an atdd_pure feature with an integrity-checked AT-completion ledger
    And a crafter dispatch into slice-01 carrying <dispatch>
    And the carpaccio gate <carpaccio> the entering slice
    When the U1 carpaccio intercept evaluates the dispatch
    Then the dispatch is <verdict>
    And the carpaccio gate invocation <carpaccio_invocation>

    Examples:
      | dispatch                                          | carpaccio | verdict | carpaccio_invocation |
      | a dispatch with no mode marker                    | clears    | blocked | is skipped           |
      | a valid atdd_pure A_GREEN_ATS dispatch            | clears    | allowed | happens              |
      | a valid atdd_pure A_GREEN_ATS dispatch            | rejects   | blocked | happens              |
      | an atdd_pure dispatch missing its phase marker    | clears    | blocked | is skipped           |
      | an atdd_pure dispatch missing its slice marker    | clears    | blocked | is skipped           |

  @slice-01 @driving_port @error @contract-shape:state-mutation
  Scenario: An out-of-order carpaccio slice is blocked when its predecessor is unshipped
    Given an atdd_pure feature with an integrity-checked AT-completion ledger
    And a crafter dispatch into slice-02 carrying a valid atdd_pure A_GREEN_ATS dispatch
    And the carpaccio gate clears the entering slice
    When the U1 carpaccio intercept evaluates the dispatch
    Then the dispatch is blocked
    And the block names the CarpaccioSliceOutOfOrder event
    And the carpaccio gate invocation is skipped

  @slice-01 @driving_port @error @contract-shape:state-mutation
  Scenario: An out-of-order slice is allowed once its predecessor is verified
    Given an atdd_pure feature with an integrity-checked AT-completion ledger
    And slice-01 carries a verified slice commit in the ledger
    And a crafter dispatch into slice-02 carrying a valid atdd_pure A_GREEN_ATS dispatch
    And the carpaccio gate clears the entering slice
    When the U1 carpaccio intercept evaluates the dispatch
    Then the dispatch is allowed
    And the carpaccio gate invocation happens

  @slice-01 @driving_port @error @contract-shape:state-mutation
  Scenario: A U1 handler exception fails closed as a structured block
    Given an atdd_pure feature with an integrity-checked AT-completion ledger
    And a crafter dispatch into slice-01 carrying a valid atdd_pure A_GREEN_ATS dispatch
    And the U1 intercept body raises an internal exception
    When the U1 carpaccio intercept evaluates the dispatch
    Then the dispatch is blocked
    And the block names the AtddPureHookInternalError event
