@feature-fix-design-reuse-first-gate
Feature: The DESIGN skill emits the gate's canonical shape and the reviewer vetoes weak reuse

  A gate that consumes an upstream-wave artifact must scope the upstream skill
  that produces it, or it degrades to a vacuous no-op (memory:
  feedback_seam_design_two_learnings). slice-01 and slice-02 built the gate;
  this slice closes the seam at both ends.

  At the producing end: the nw-design skill is the human-facing copy that
  tells an architect how to write the Reuse Analysis table. Its template must
  emit exactly the canonical heading and the five-column constant the gate
  parses, and it must spell the new-path decision `CREATE_NEW`, not the legacy
  `CREATE NEW` -- so the artifact the architect produces and the artifact the
  gate consumes are one shape, defined once.

  At the judging end: no parser can decide whether a CREATE_NEW was honest or
  whether an overlapping component was silently omitted from the table. That
  irreducible judgment is the solution-architect reviewer's veto -- this slice
  adds the critique dimension that makes the reviewer flag a hand-waving
  CREATE_NEW justification and a missing overlapping component as high issues.

  # DDD-8 (R1 normative source: skill template == REUSE_ANALYSIS_COLUMNS
  # constant), DDD-4 (reviewer veto over judgment). Driving ports: the
  # nw-design skill template text + the nw-solution-architect-reviewer YAML.
  # Layer 3 (cross-artifact / framework-asset acceptance) -- example-only, no
  # PBT (Mandate 9/11): these are single normative-source identity checks.

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: The DESIGN skill template matches the gate's canonical heading and columns
    Given the nw-design skill and the validate-feature-delta module
    When the architect compares the skill's Reuse Analysis template to the gate constant
    Then the skill template heading equals the canonical Reuse Analysis heading
    And the skill template columns equal the REUSE_ANALYSIS_COLUMNS constant

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: The DESIGN skill template spells the new-path decision CREATE_NEW
    Given the nw-design skill and the validate-feature-delta module
    When the architect inspects the skill's Reuse Analysis decision token
    Then the skill template uses the CREATE_NEW token
    And the skill template does not produce the legacy CREATE NEW spelling

  @slice-03 @error @driving_port @contract-shape:bounded-change
  Scenario: The reviewer vetoes a hand-waving CREATE_NEW and a silently omitted overlap
    Given the nw-solution-architect-reviewer carries the reuse-first critique dimension
    When a feature-delta presents an unjustified CREATE_NEW and a silently omitted overlapping component
    Then the reviewer flags the unjustified CREATE_NEW as a high issue
    And the reviewer flags the silently omitted overlapping component as a high issue
