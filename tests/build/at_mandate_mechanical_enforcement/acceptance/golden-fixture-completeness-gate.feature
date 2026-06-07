# slice-11 — the Tier-M golden-fixture-completeness meta-gate, the Earned-Trust
# self-application over the 9 Tier-S gates (ADR-TEST-002 D-D: Tier-S = the static
# AST/import gates shipped in slices 01-10, Tier-M = THIS meta-tier, Tier-J =
# agent-audit).
#
# The methodology-maintainer's contract: every shipped gate must carry its OWN
# golden fixtures + a self-AT, or it is untrustworthy — a gate with no recall
# (violation_) fixture has never been PROVEN to catch its violation; a gate with
# no precision (clean_) near-miss has never been PROVEN not to false-positive.
# This meta-gate catches the STRUCTURAL ABSENCE that the per-gate ATs structurally
# cannot see: a per-gate AT proves the gate WORKS; only the meta-gate proves the
# gate is COVERED.
#
# Honest tagging: an in-process pure filesystem-PRESENCE walk — @component
# (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no AST,
# no git, no real I/O beyond reading directory entries. The meta-gate practises
# the honesty its sibling gates enforce. Its own self-AT (this .feature) lives at
# acceptance/ root, NOT under fixtures/, so the meta-gate never enumerates itself
# as a gate to check (it has no fixtures/golden_fixture_completeness/ subdir).

@feature-at-mandate-mechanical-enforcement @slice-11 @component
Feature: Every shipped gate carries its own golden fixtures and self-AT

  As the methodology maintainer who must trust the mechanical gate suite
  I want each shipped Tier-S gate mechanically confirmed to carry its full
  golden-fixture triad — a recall fixture, a precision near-miss, and a self-AT —
  so that no gate is ever shipped unproven, and the Earned-Trust self-application
  contract is enforced, not merely conventional

  Background:
    Given the golden-fixture-completeness meta-gate

  @slice-11 @driving_port @contract-shape:bounded-change
  Scenario: The meta-gate flags a gate missing its golden fixtures
    When the meta-gate judges a gate that ships a violation fixture but no clean near-miss and no self-AT
    Then the meta-gate rules that gate incomplete

  @slice-11 @contract-shape:bounded-change
  Scenario: The meta-gate clears a gate carrying its full golden triad
    When the meta-gate judges a gate that ships a violation fixture, a clean near-miss, and a self-AT
    Then the meta-gate rules that gate complete

  @slice-11 @contract-shape:bounded-change
  Scenario: The meta-gate clears every gate the feature has shipped
    When the meta-gate judges every gate the feature has shipped
    Then the meta-gate rules every shipped gate complete
    And the meta-gate finds at least one shipped gate to judge
