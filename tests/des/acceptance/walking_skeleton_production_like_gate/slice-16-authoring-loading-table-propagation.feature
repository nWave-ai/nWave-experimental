@feature-walking-skeleton-production-like-gate
Feature: The authoring agents load the tier discipline at their authoring phase
  As an nWave framework maintainer
  I want every authoring agent's skill-loading table to reference the tier
    discipline, verified by an arch test
  So that the tier discipline is the operative dispatch contract, not an
    invisible frontmatter declaration

  # carpaccio slice-16 (DESIGN slice-09). Authoring-side methodology
  # propagation -- agent loading tables + verification. The Skill Loading
  # Strategy tables of the acceptance-designer, the crafters, and the reviewers
  # are updated to load the tier-discipline skill at the authoring phase, and
  # an arch test asserts every named agent's loading table references it.
  # Per feedback_update_skill_loading_table_with_skill_changes_2026_05_19: a
  # skill's applies_to frontmatter is a declaration; the operative dispatch
  # contract is the agent loading table. Depends on slice-15 (the skill content
  # must exist before a table can reference it meaningfully).
  #
  # Layer 4 (integration): example-pinned, traditional assertions (Mandate 8).
  #
  # Driving port: a `pytest` arch test over the agent skill-loading tables.

  @slice-16 @contract-shape:bounded-change
  Scenario: An authoring agent's loading table references the tier-discipline skill
    Given an authoring agent's skill-loading table carries the tier-discipline skill
    When the propagation check reads the authoring agent's skill-loading table
    Then the propagation check confirms the loading table references the tier-discipline skill

  @slice-16 @error @contract-shape:bounded-change
  Scenario: The propagation check fails when an agent loading table omits the tier-discipline skill
    Given an authoring agent's skill-loading table omits the tier-discipline skill
    When the propagation check reads the authoring agent's skill-loading table
    Then the propagation check fails naming the authoring artifact that omits the discipline

  @slice-16 @contract-shape:bounded-change
  Scenario: The propagation arch test passes when every authoring artifact is updated
    Given every authoring agent's skill-loading table carries the tier-discipline skill
    When the propagation check reads every authoring agent's skill-loading table
    Then the propagation arch test passes
