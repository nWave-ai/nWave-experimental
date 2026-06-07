@feature-fix-distill-human-signoff
Feature: An acceptance designer renders a coverage map of the feature surface

  The DISTILL-exit human sign-off rests on a coverage map -- a Markdown
  document the human reads and signs. The acceptance designer authors the map
  as a human-readable synthesis of the 15-item completeness audit: the feature
  surface declared by the DESIGN component manifest is rendered on top, and
  every manifest domain that no scenario covers is surfaced below as explicit
  negative space the human must accept or refuse.

  This slice delivers that floor -- the rendering tool. Nothing downstream
  (anti-omission check, gate verdict, ledger record) can run until a coverage
  map exists in the canonical structure with the four mandatory dimension
  rows. It is the walking skeleton: a tagged scenario somewhere becomes a
  covered domain on the rendered page; a manifest domain with no tag becomes
  a negative-space row a human will read.

  # Driving port: the derive_coverage_map CLI (subprocess invocation).
  # Layer 3 (subprocess / FS acceptance) -- example-only sad paths (Mandate 11).
  # The parser-conformance outline is @property: every parser-edge equivalence
  # class is enumerated as a Scenario Outline row at layer 3, not a Hypothesis
  # @given (Mandate 9 -- this is layer 3; closed finite parser-edge domain).

  Background:
    Given a feature whose design wave has produced a component manifest

  @slice-01 @walking_skeleton @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: A fully-covered manifest renders a coverage map with four none rows
    Given every manifest domain is covered by an acceptance scenario tag
    When the acceptance designer renders the coverage map
    Then a coverage map is written to the feature distill directory
    And the coverage map carries the four mandatory dimension rows each marked none
    And the coverage map carries the feature surface declared section in order

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A manifest domain with no covering scenario appears on the correct dimension row
    Given a manifest domain is left uncovered by every acceptance scenario tag
    When the acceptance designer renders the coverage map
    Then the uncovered manifest domain appears on the not covered table
    And the not covered table places the domain on the dimension row matching its category

  @slice-01 @property @driving_port @contract-shape:pure-function
  Scenario Outline: The covers tag binding respects placement multiplicity and identifier shape
    Given an acceptance scenario authored where <parser_edge>
    When the acceptance designer renders the coverage map
    Then the rendered coverage matches the parser edge expectation for <parser_edge>

    Examples:
      | parser_edge                                                                 |
      | the tag line carries two covers tags for two distinct manifest domains      |
      | a scenario outline carries one covers tag with three Examples rows          |
      | the covers tag sits on the Feature line instead of the Scenario tag line    |
      | the scenario carries no covers tag at all                                   |
      | the covers tag names a domain identifier that is not lowercase kebab case   |
