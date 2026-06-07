@feature-atdd-pure-spine-hardening @slice-00
Feature: An atdd_pure crafter dispatch is recognised by its three DES markers
  As the DES hook layer that must intercept an atdd_pure crafter dispatch
  I want every atdd_pure dispatch prompt to carry, and the marker parser to
    value-validate, the DES-MODE, DES-PHASE and DES-SLICE markers
  So that a hook can recognise an atdd_pure dispatch (U1/U2 key on it) and a
    defective dispatch is named as defective instead of silently mistaken for
    a classic one

  # hg-slice-00 of F-DES-ATDD-PURE-HOOK-GATES (U0 -- ADR-030 D8).
  # The recognition substrate that precedes U1-U4: a PreToolUse / SubagentStop
  # intercept can only fire on a dispatch it can RECOGNISE. Today the parser
  # (src/des/domain/des_marker_parser.py) has no atdd_pure vocabulary. U0 is the
  # design item that makes U1-U4 possible.
  #
  # SUT recognition state model (the contract these ATs pin):
  #   the marker set resolves to one of THREE states --
  #     ABSENT   -- no DES-MODE:atdd_pure marker -> a classic dispatch, fall through
  #     VALID    -- DES-MODE:atdd_pure present AND DES-PHASE in ATDDPurePhase
  #                 AND DES-SLICE matches the anchored slice-\d+ shape
  #     DEFECTIVE -- DES-MODE:atdd_pure present BUT a remaining marker is
  #                 absent, malformed, or carries an out-of-vocabulary value
  #   A DEFECTIVE set is recognised AS defective -- never silently treated as a
  #   classic dispatch, never silently dropped to None (M3/M14).
  #
  # Driving port: the DesMarkerParser domain class (a pure, no-I/O parser) and
  # its dispatch-classification surface -- the same production surface the
  # /nw-deliver phase-entry diagnostic consumes to refuse a defective dispatch.
  # Layer 1-2 (pure domain, no real I/O) -> the parametrized recognition AT may
  # use PBT; the walking-skeleton AT is example-only (Mandate 9).
  #
  # Regression / RED contract: every scenario FAILS on master -- DesMarkerParser
  # carries no DES-PHASE/DES-SLICE pattern, no atdd_pure DesMarkers fields, and
  # no dispatch-classification surface; the RED scaffolds raise AssertionError
  # (MISSING_FUNCTIONALITY). They PASS once hg-slice-00 lands.

  @component @walking_skeleton @slice-00 @driving_port @contract-shape:pure-function
  Scenario: A real nw-deliver atdd_pure dispatch prompt is recognised as a valid dispatch
    Given the production nw-deliver atdd_pure dispatch prompt
    When the DES marker parser parses the dispatch prompt
    Then the walking-skeleton dispatch is recognised as a valid atdd_pure dispatch
    And the parsed mode is atdd_pure
    And the parsed phase is a member of the ATDD-pure phase vocabulary
    And the parsed slice id matches the anchored slice shape

  @slice-00 @driving_port @property @contract-shape:pure-function
  Scenario Outline: A marker set is classified absent, valid or defective from its three markers
    Given a dispatch prompt whose mode marker is <mode_marker>
    And whose phase marker is <phase_marker>
    And whose slice marker is <slice_marker>
    When the DES marker parser classifies the dispatch prompt
    Then the dispatch is recognised as <recognition>

    Examples:
      | mode_marker | phase_marker  | slice_marker | recognition |
      | absent      | absent        | absent       | absent      |
      | orchestrator| absent        | absent       | absent      |
      | atdd_pure   | A_GREEN_ATS   | slice-01     | valid       |
      | atdd_pure   | G_COMMIT      | slice-12     | valid       |
      | atdd-pure   | a_green_ats   | slice-03     | valid       |
      | atdd_pure   | absent        | slice-01     | defective   |
      | atdd_pure   | A_GREEN_ATS   | absent       | defective   |
      | atdd_pure   | NOT_A_PHASE   | slice-01     | defective   |
      | atdd_pure   | A_GREEN_ATS   | slice1       | defective   |
      | atdd_pure   | A_GREEN_ATS   | slice-3-->   | defective   |

  @slice-00 @driving_port @error @contract-shape:pure-function
  Scenario Outline: The phase-entry diagnostic refuses an atdd_pure dispatch missing a marker
    Given a dispatch prompt whose mode marker is atdd_pure
    And whose phase marker is <phase_marker>
    And whose slice marker is <slice_marker>
    When the nw-deliver phase-entry diagnostic checks the dispatch prompt
    Then the dispatch is refused for the missing <missing_marker> marker

    Examples:
      | phase_marker | slice_marker | missing_marker |
      | absent       | slice-01     | des-phase      |
      | A_GREEN_ATS  | absent       | des-slice      |
