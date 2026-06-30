@feature-fix-des-feature-id-marker-distinct
Feature: The carpaccio feature-id is its own DES-FEATURE-ID marker, not the overloaded DES-PROJECT-ID
  As a spine driver dispatching a carpaccio slice for a feature whose feature-id is
    not identical to the project-id
  I want the carpaccio feature-id to be resolved from a distinct DES-FEATURE-ID marker
    (falling back to DES-PROJECT-ID only when DES-FEATURE-ID is absent)
  So that the in-order guard reads the ledger keyed by the correct feature-id and my
    slice is not falsely blocked out-of-order (AD-61)

  # C5 of consolidation-for-wider-beta-testing (ARCH AD-61). Mode: atdd_pure,
  # cohort S, single slice-01.
  #
  # The defect: the carpaccio feature-id resolution OVERLOADS DES-PROJECT-ID --
  # `pre_tool_use_handler.py:165` does `feature_id = markers.project_id`. But
  # DES-PROJECT-ID is the project-ROOT identity (Earned-Trust intake + Task-Id
  # grep, subagent_stop_service:218), NOT the feature being delivered. On a fresh
  # feature whose DES-PROJECT-ID differs from its feature-id, the in-order guard
  # reads the AT-completion ledger keyed by the WRONG id -> a slice is falsely
  # blocked out-of-order.
  #
  # The fix, two seams:
  #   (1) des_marker_parser gains `_FEATURE_ID_PATTERN` + a `feature_id` field +
  #       the parse line, mirroring the shipped DES-PROJECT-ID parse (@232/138/254);
  #   (2) the carpaccio resolution (pre_tool_use_handler.py:165) becomes
  #       `feature_id = markers.feature_id or markers.project_id` -- prefer the
  #       distinct marker, fall back to the overload for back-compat.
  #
  # Driving ports (Mandate-13):
  #   * AC-1 / AC-4 -- the REAL `DesMarkerParser.parse` domain surface (pure, no I/O).
  #   * AC-2 / AC-3 -- the REAL carpaccio feature-id resolution
  #     `pre_tool_use_handler._evaluate_u1_intercept` (the production function
  #     carrying line 165). The resolved feature-id is observed at the production
  #     injectable seam -- the value the resolution feeds into
  #     `intercept_atdd_pure_dispatch(feature_id=...)`. Only that downstream
  #     boundary (the carpaccio CLI subprocess port) is stubbed; the resolution
  #     itself is the REAL production code.
  #
  # active-RED scaffold (atdd_pure -- NOT @skip):
  #   * AC-1 RED: no DES-FEATURE-ID pattern/field exists at HEAD -> the parsed
  #     result carries no feature_id == "feat-X"; the assertion RED-fails for the
  #     right reason (missing functionality), never a fixture/import error.
  #   * AC-2 RED: the resolution reads `markers.project_id` -> resolves "proj-Y",
  #     not "feat-X".
  #   * AC-3 / AC-4: live-green preservation guards (project-id-only already
  #     resolves to project_id; project_id parse is unchanged by adding feature_id).

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A distinct DES-FEATURE-ID marker is parsed into its own feature_id field
    Given a dispatch prompt carrying the distinct feature-id marker "feat-X"
    When the DES marker parser parses the dispatch prompt
    Then the parsed feature id is "feat-X"

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: The carpaccio resolution prefers the distinct feature-id over the project-id
    Given a carpaccio dispatch prompt carrying both a feature-id marker "feat-X" and a project-id marker "proj-Y"
    When the carpaccio dispatch resolution runs over the dispatch prompt
    Then the resolved carpaccio feature id is "feat-X"

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: The carpaccio resolution falls back to the project-id when no feature-id marker is present
    Given a carpaccio dispatch prompt carrying only a project-id marker "proj-Y"
    When the carpaccio dispatch resolution runs over the dispatch prompt
    Then the resolved carpaccio feature id is "proj-Y"

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: The DES-PROJECT-ID marker still populates project_id when a feature-id marker is also present
    Given a dispatch prompt carrying both a feature-id marker "feat-X" and a project-id marker "proj-Y"
    When the DES marker parser parses the dispatch prompt
    Then the parsed project id is "proj-Y"
