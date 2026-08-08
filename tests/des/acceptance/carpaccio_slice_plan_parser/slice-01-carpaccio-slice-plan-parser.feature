@feature-fix-carpaccio-slice-plan-parser-unify
Feature: One tolerant slice-plan parser for the carpaccio entry gate
  As a spine driver whose feature-delta carries a well-formed slice plan
  I want the carpaccio entry gate to parse the supported markdown forms
  So that a 3-column / H3-heading / escaped-pipe plan is not falsely rejected

  # C10 of consolidation-for-wider-beta-testing. The CLI carpaccio_slice_gate
  # reads the artifact through the public parser
  # (src/des/cli/carpaccio_format.py::parse_slice_plan), which was strict -- H2-only
  # heading, raw-| split, requires exactly 5 columns -- and REJECTS a 3-column
  # plan. An H3
  # heading yields SectionMissing and a GFM-escaped `\|` in a cell is miscounted as
  # a column boundary (MalformedInput). The fix provides one tolerant
  # `parse_slice_plan_rows(text)` in carpaccio_format (H2-H4 heading-tolerant,
  # escaped-`\|` un-escaping, column-tolerant: slice-id col + value next col,
  # extra columns ignored).
  #
  # atdd_pure: AC-1/2/3 are ACTIVE-RED (they RUN and raise AssertionError -- the
  # shared tolerant parser does not exist; the public parser miscounts /
  # SectionMissing at HEAD). AC-4 is a live-green preservation guard (the 5-col H2
  # plan the shipped deltas use already parses; the fix must not break it). The
  # scenarios drive the REAL public carpaccio_slice_gate parser
  # over hermetic feature-delta texts crafted under pytest tmp_path -- never this
  # repo's own deltas.

  @slice-01 @US-01 @contract-shape:bounded-change
  Scenario: A 3-column slice plan parses through the entry gate
    Given a feature-delta whose slice plan is a 3-column table with columns "Slice", "Value statement" and "Status"
    And the plan declares slices "slice-01" and "slice-02"
    When the carpaccio entry-gate parser reads the plan
    Then the parser extracts the slice-id set "slice-01, slice-02"
    And the parser accepts the 3-column plan

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
