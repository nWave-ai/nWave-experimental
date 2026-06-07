# Feature: Skill Restructuring Walking Skeleton
# Based on: story-map.md Walking Skeleton (nw-troubleshooter, 3 skills, zero collisions)
# Proves: source restructure -> installer copies -> Claude Code auto-loads
# Date: 2026-03-14

Feature: Skill Restructuring Walking Skeleton
  As a framework maintainer
  I want skills installed to the auto-loading path
  So that agents start with skills injected without manual Read calls

  Background:
    Given the nWave source tree contains skill directories
    And the installer plugin is available

  @walking_skeleton @priority-critical
  Scenario: Maintainer installs skills and agent receives them automatically
    Given 3 troubleshooter skills exist in the source tree as nw-prefixed directories
    And each skill directory contains a SKILL.md file
    And the troubleshooter agent lists these skills in its frontmatter
    And a clean installation directory exists

    When the skills plugin installs all skills
    Then "nw-five-whys-methodology" is installed with its SKILL.md
    And "nw-investigation-techniques" is installed with its SKILL.md
    And "nw-post-mortem-framework" is installed with its SKILL.md
    And the installation reports 3 skill files installed
    And verification confirms all 3 skills are present

  @walking_skeleton @priority-critical
  Scenario: Existing user upgrades and old skill structure is cleaned up
    Given the user has skills installed in the old "nw/" namespace directory
    And the old directory contains agent-grouped skill files
    And a clean installation directory exists

    When the skills plugin installs all skills
    Then the old "nw/" namespace directory no longer exists
    And skills are installed in the flat nw-prefixed layout
    And the installation completes successfully

  @walking_skeleton @priority-critical
  Scenario: User's custom skills are preserved during installation
    Given the user has a custom skill "my-prompt-patterns" in the skills directory
    And a clean installation directory exists

    When the skills plugin installs all skills
    Then the custom skill "my-prompt-patterns" is still present
    And nWave skills are installed alongside the custom skill

  @walking_skeleton @priority-critical
  Scenario: Installer detects and handles both old and new skill layouts
    Given skills exist in both old "nw/" namespace AND new nw-prefixed directories
    And a clean installation directory exists
    When the skills plugin installs all skills
    Then all skills from both layouts are installed correctly
    And the old "nw/" directory is cleaned up after installation
