Feature: Marco gets lean wave output by default after one-time install choice
  As Marco, a solo developer running ten features per quarter
  I want a one-time density choice at install plus lean output by default
  So that every wave I run stays under my token budget without per-wave friction

  @walking_skeleton @real-io @driving_adapter @adapter-integration @US-1 @US-3 @US-5
  Scenario: Marco installs nWave and a lean wave produces only [REF] sections with telemetry recorded
    Given Marco is installing nWave for the first time on a host with no nWave global configuration
    When Marco completes the install accepting the lean density choice
    And Marco runs a lean DISCUSS wave on a small feature called "small-feat-x"
    Then Marco's nWave global configuration records lean as the default density and ask as the expansion prompt
    And the feature-delta.md for "small-feat-x" contains only sections labelled [REF]
    And every Tier-1 field downstream waves require is present in the feature-delta.md
    And Marco's audit trail records a documentation-density event for that wave
    And the nw-discuss wave skill encodes density-aware emission instructions
