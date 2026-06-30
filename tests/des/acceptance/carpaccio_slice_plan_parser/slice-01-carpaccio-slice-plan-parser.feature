@feature-fix-carpaccio-slice-plan-parser-unify
Feature: One tolerant slice-plan parser shared by the carpaccio entry gate and the hook
  As a spine driver whose feature-delta carries a well-formed slice plan
  I want the carpaccio entry gate and the subagent-stop hook to parse it identically
    through ONE tolerant parser
  So that a 3-column / H3-heading / escaped-pipe plan is not falsely rejected by one
    path while accepted by the other

  # C10 of consolidation-for-wider-beta-testing. Two divergent slice-plan
  # parsers split the SAME artifact: the CLI carpaccio_slice_gate parser
  # (src/des/cli/carpaccio_format.py::parse_slice_plan) is strict -- H2-only
  # heading, raw-| split, requires exactly 5 columns -- and REJECTS a 3-column
  # plan that the hook parser
  # (src/des/adapters/drivers/hooks/subagent_stop_handler.py::_parse_slice_plan_rows
  # :1299, len(cells) >= 3) ACCEPTS. The entry gate is thus non-functional for the
  # canonical plan while the exit gate (hook) accepts it. Both are GFM-naive: an H3
  # heading yields SectionMissing and a GFM-escaped `\|` in a cell is miscounted as
  # a column boundary (MalformedInput). The fix replaces both with ONE tolerant
  # `parse_slice_plan_rows(text)` in carpaccio_format (H2-H4 heading-tolerant,
  # escaped-`\|` un-escaping, column-tolerant: slice-id col + value next col,
  # extra columns ignored), to which BOTH paths delegate.
  #
  # atdd_pure: AC-1/2/3 are ACTIVE-RED (they RUN and raise AssertionError -- the
  # shared tolerant parser does not exist; both real parsers diverge / miscount /
  # SectionMissing at HEAD). AC-4 is a live-green preservation guard (the 5-col H2
  # plan the shipped deltas use already parses; the fix must not break it). The
  # scenarios drive the REAL carpaccio_slice_gate parser and the REAL hook parser
  # over hermetic feature-delta texts crafted under pytest tmp_path -- never this
  # repo's own deltas.

  @slice-01 @US-01 @contract-shape:bounded-change
  Scenario: A 3-column slice plan parses identically through the entry gate and the hook
    Given a feature-delta whose slice plan is a 3-column table with columns "Slice", "Value statement" and "Status"
    And the plan declares slices "slice-01" and "slice-02"
    When the carpaccio entry-gate parser and the subagent-stop hook parser each read the plan
    Then both parsers extract the slice-id set "slice-01, slice-02"
    And neither parser rejects the 3-column plan

  @slice-01 @US-01 @contract-shape:bounded-change
  Scenario: A slice-plan cell containing an escaped pipe keeps its slice-id and value intact
    Given a feature-delta whose slice plan has a value cell containing a GFM-escaped pipe
    And the plan declares slice "slice-01" with a value statement that mentions a piped alternative
    When the shared slice-plan parser reads the plan
    Then the parser extracts slice-id "slice-01" with its full value statement
    And the escaped pipe is treated as literal text, not a column boundary

  @slice-01 @US-01 @contract-shape:bounded-change
  Scenario: A slice plan under a level-3 heading is parsed, not reported missing
    Given a feature-delta whose slice plan sits under a level-3 "Slice Plan" heading
    And the plan declares slices "slice-01" and "slice-02"
    When the shared slice-plan parser reads the plan
    Then the parser extracts the slice-id set "slice-01, slice-02"
    And the parser does not report the slice-plan section as missing

  @slice-01 @US-01 @contract-shape:unbounded-preservation
  Scenario: A 5-column slice plan under a level-2 heading still parses the same slice-ids
    Given a feature-delta whose slice plan is a 5-column table under a level-2 "Slice Plan" heading
    And the plan declares slices "slice-01" and "slice-02"
    When the carpaccio entry-gate parser reads the plan
    Then the parser extracts the slice-id set "slice-01, slice-02"
