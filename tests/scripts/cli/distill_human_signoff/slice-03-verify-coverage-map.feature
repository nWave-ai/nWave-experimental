@feature-fix-distill-human-signoff @slice-03
Feature: The verify coverage map gate refuses a coverage map that has gone stale or lost its shape

  The acceptance designer authors and signs the coverage map (slices 01-02);
  the verify gate is the read-side. A reviewer (or the DELIVER-exit re-check)
  asks the gate "is this coverage map still trustworthy?" and the gate
  answers with a verdict -- accepted, structurally incomplete, stale,
  malformed.

  The structural verdict catches a coverage map missing a mandatory section
  or carrying the four dimension rows out of order. The stale verdict
  catches a coverage map whose signed content body was edited after the
  human signed (the canonical-content digest no longer matches). The
  malformed verdict catches a coverage map / manifest / ledger that is not
  even parseable.

  # Driving port: verify_coverage_map verify. Layer 3 (subprocess / FS
  # acceptance) -- example-only sad paths (Mandate 11). The @property-tagged
  # AT3 outline enumerates the four signed sections (each one's tamper case)
  # plus the malformed + cross-tree canonicalization conformance fixtures.

  Background:
    Given a feature whose design wave has produced a component manifest
    And a coverage map has been authored and signed by a human

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: A coverage map whose signed content has not been touched is accepted
    When the reviewer verifies the coverage map
    Then the verify gate accepts the coverage map

  @slice-03 @driving_port @error @contract-shape:pure-function
  Scenario: A coverage map missing a mandatory section is refused as structurally incomplete
    Given the acceptance designer has removed a mandatory section from the coverage map
    When the reviewer verifies the coverage map
    Then the verify gate refuses for a structurally incomplete coverage map

  @slice-03 @property @driving_port @contract-shape:pure-function
  Scenario Outline: Post-signoff tampering, malformation, and canonicalization conformance
    Given <tamper_or_input>
    When the reviewer verifies the coverage map
    Then the verify gate responds with <verdict>

    Examples:
      | tamper_or_input                                                                              | verdict                                            |
      | the acceptance designer has edited the feature surface declared section after signoff       | the verify gate refuses for a stale signoff        |
      | the acceptance designer has edited the not covered table after signoff                       | the verify gate refuses for a stale signoff        |
      | the acceptance designer has edited the known residues carried forward section after signoff | the verify gate refuses for a stale signoff        |
      | the acceptance designer has edited the negative space completeness statement after signoff  | the verify gate refuses for a stale signoff        |
      | the manifest or coverage map cannot be parsed                                                | the verify gate refuses for a malformed input      |
      | the canonical content of a golden fixture is digested by the local implementation           | the verify gate produces the golden fixture digest |
