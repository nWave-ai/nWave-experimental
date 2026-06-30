@feature-sustainable-test-suite
Feature: A maintainer declares the sustainability work in a registered, structured section
  As an nWave maintainer authoring a feature's acceptance tests
  I want to declare the sustainability work I did (DSL extended, tests consolidated,
    prose improved) in a STRUCTURED, machine-readable feature-delta section that the
    methodology RECOGNISES as a first-class DISTILL output
  So that the declaration is a parseable section in the document model — not free prose —
    and the spine treats it as a declared output, the foundation a later gate validates

  # slice-02 of sustainable-test-suite — the SECTION SCHEMA + its output-contract
  # registration (DDD-3, DDD-11). The canonical section is
  # `## Test Reuse & Consolidation Analysis`, the mirror of `## Reuse Analysis`
  # (5 fixed columns: Existing Test/DSL-Step | File | Overlap | Decision | Justification;
  # decision tokens REUSE/EXTEND/CONSOLIDATE/CREATE_NEW). DDD-11: the section is
  # REGISTERED in the DISTILL output-contract SSOT `nWave/waves/distill.yaml`
  # output_contract.ref_sections, so a feature-delta declaring it under DISTILL is
  # recognised as a first-class DISTILL output rather than flagged undeclared.
  #
  # SCOPE BOUNDARY (HARD): slice-02 = the section SCHEMA + its output-contract
  # registration ONLY. The MECHANICAL CONTENT VALIDATION gate
  # (`validate_sustainability_content` + `--require-sustainability`) — which checks
  # the section's rows/decision-tokens/blind-add — is slice-03 and is NOT authored
  # here.
  #
  # DRIVING PORT (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
  # `des validate-feature-delta --require-registry-sections distill --format=json`
  # invoked as a real subprocess. The observable is the closed verdict token
  # (`accepted` / `undeclared-section`) on stdout + the process exit code. The
  # check runs against the REAL `nWave/waves/distill.yaml` registry (the default
  # --waves-dir). No production module is imported at the step boundary; the
  # feature-delta fixtures are written to a hermetic tmp_path; the subprocess IS the
  # SUT. `des`/`git` are never required by the assertions — Python + filesystem only.
  #
  # Active-RED (ADR-025/028, atdd_pure): at HEAD `nWave/waves/distill.yaml`
  # output_contract.ref_sections does NOT list `Test Reuse & Consolidation Analysis`
  # (verified: the 8 declared sections are Wave-Decision Reconciliation, Scenario
  # List with Tags, WS Strategy, Adapter Coverage Table, Scaffolds, Test Placement,
  # Driving Adapter Coverage, Pre-requisites). So a feature-delta declaring the new
  # section under DISTILL is REJECTED `undeclared-section` today; every scenario
  # below asserts `accepted` (the post-registration behaviour) and so fails for the
  # right reason (the section is not yet registered = MISSING_FUNCTIONALITY; clean
  # collection, not ImportError). DELIVER makes these GREEN by ADDING the
  # ref_section to distill.yaml (DDD-11, ADD-not-mutate) — it does NOT unskip
  # anything. slices 03-07 are ABSENT from disk.

  @slice-02 @walking_skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: A maintainer's declared sustainability section is a recognised DISTILL output
    Given a maintainer authors a feature-delta declaring the canonical sustainability section under DISTILL
    When the registry-section check runs against the live DISTILL registry
    Then the check accepts the feature-delta
    And the sustainability section is recognised as a declared DISTILL output

  @slice-02 @driving_port @real-io @contract-shape:pure-function
  Scenario: The new section composes with the existing declared DISTILL sections
    Given a maintainer authors a complete DISTILL feature-delta and adds the canonical sustainability section
    When the registry-section check runs against the live DISTILL registry
    Then the check accepts the feature-delta
    And the sustainability section is recognised as a declared DISTILL output

  @slice-02 @driving_port @real-io @contract-shape:pure-function
  Scenario: The recognised section uses the canonical heading, not a near-miss
    Given a maintainer authors a feature-delta declaring the canonical sustainability section under DISTILL
    When the registry-section check runs against the live DISTILL registry
    Then the live DISTILL registry declares the canonical sustainability section by its exact id
