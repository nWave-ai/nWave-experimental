@feature-parallel-by-default-distill-slicing
Feature: A DISTILL-originated Slice Plan reads exactly like a DISCUSS-originated one

  An acceptance-designer originating a Slice Plan directly inside DISTILL -- because DISCUSS
  never ran for this feature -- writes the SAME `depends-on {slice-id}` grammar and default-flip
  (silence = parallel-safe, a declared dependency owes its one-line why) a Product Owner would
  have written during DISCUSS. `des validate-feature-delta --require-slice-plan --format=json`
  must return the IDENTICAL verdict for a DISTILL-originated Slice Plan and a DISCUSS-originated
  one carrying equivalent Annotation/Justification cell content -- the validator classifies the
  TABLE, never who wrote the document around it, and never what else that document does or does
  not carry above or below the table.

  # docs/feature/parallel-by-default-distill-slicing/feature-delta.md D-1..D-6, Domain Examples 1-3.
  # Driving port: `des validate-feature-delta --require-slice-plan --format=json`, run TWICE per
  # scenario -- once against a DISCUSS-shaped fixture (Job & Intent / Locked Decisions / Slice Plan
  # / Guardrails / Out-of-Scope / Outcome KPIs sections, a Product Owner's authoring shape), once
  # against a DISTILL-shaped fixture (only the Slice Plan section, no other DISCUSS heading at
  # all) -- with byte-identical Slice Plan table content, so every scenario is a PARITY assertion
  # between the two authoring paths, not a standalone verdict pin (that pin already exists, shipped
  # by the sibling parallel-by-default-slice-plan feature's own AT suite).
  # Layer 3 (subprocess/FS acceptance) -- example-only, no PBT: the annotation vocabulary under
  # test is a finite, enumerable closed set of three combinations, mirroring the paradigm choice
  # parallel-by-default-slice-plan slice-01 already made for the same grammar (Mandate 9/11).

  Background:
    Given a feature-delta authored for an atdd_pure feature

  @slice-01 @driving_port @walking_skeleton @contract-shape:pure-function
  Scenario: A DISTILL-originated slice with no declared dependency reads parallel-safe, just like a DISCUSS-originated one
    Given a DISCUSS-shaped fixture and a DISTILL-shaped fixture whose second row carries no annotation and an empty Justification
    When the acceptance-designer runs the slice-plan check on both fixtures
    Then both fixtures are accepted
    And the two verdicts are identical
    And the check leaves both feature-deltas unchanged

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario: A DISTILL-originated dependency with a one-line Justification is accepted, just like a DISCUSS-originated one
    Given a DISCUSS-shaped fixture and a DISTILL-shaped fixture whose second row declares depends-on slice-01 with a non-empty Justification
    When the acceptance-designer runs the slice-plan check on both fixtures
    Then both fixtures are accepted
    And the two verdicts are identical
    And the check leaves both feature-deltas unchanged

  @slice-01 @driving_port @error @negative @contract-shape:pure-function
  Scenario: A DISTILL-originated dependency with an empty Justification is rejected, never diverging from what a DISCUSS-originated plan would get for the identical mistake
    Given a DISCUSS-shaped fixture and a DISTILL-shaped fixture whose second row declares depends-on slice-01 with an empty Justification
    When the acceptance-designer runs the slice-plan check on both fixtures
    Then both fixtures are rejected for an unjustified slice dependency
    And the two verdicts are identical
    And both rejections name row 2 as the offending row
    And the check leaves both feature-deltas unchanged
