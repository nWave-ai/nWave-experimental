@feature-mode-registry-single-locus @slice-02
# Feature: mode-registry-single-locus slice-02 — registry projections land in
#          REAL assets via docgen GENERATED regions (Slice Plan row slice-02,
#          wiring-witness for the slice-01 seam).
#
# THE OPERATOR VALUE (Slice Plan row slice-02): "(a) `nw-deliver`
# mode-descriptor prose; (b) the `nw-software-crafter.md:74` conditional-skill
# row rendered from `skill_load_set` via the slice-01 seam, inline row RETIRED
# — the registry-read → projection → prompt-surface wiring witness." Per
# D-inject AMENDED there is no runtime prompt-assembly locus in the hook path:
# the agent-spec markdown IS the prompt the host loads, so the docgen
# projection landing the GENERATED region in it IS the prompt-surface step.
#
# Driving port (the Driving-Port-Only Boundary mandate, SSOT
# `nw-test-design-mandates`): the REAL docgen CLI, Layer-3 subprocess —
# `python scripts/docgen.py [--check] --root <working-copy> --output-dir ...`.
# The `--root` override is part of the slice-02 contract surface (analogous to
# the existing `--output-dir`): it rebases the asset tree docgen scans and
# projects, so the ATs drive the FULL real entry (argparse → pipeline →
# projection / check) against a working copy, never mutating the live repo.
# NEVER a hand-rolled markdown rewrite at the test boundary; the ONLY other
# production import is the slice-01 driving-port seam
# `des.application.flavor_dispatcher.resolve_skill_load_set`, used as the
# expected-side read API per the slice plan ("region content equals seam
# output" — one registry-read SSOT, two consumers: gates + docgen).
#
# Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared net-new seams
# this slice are (i) the docgen projection consuming `resolve_skill_load_set`
# (this RESOLVES the slice-01 owned-dormancy — named owner slice-02, named
# witness AT-01), (ii) the `GENERATED:mode-descriptor` render from the new
# `descriptor` + `deliver_phase_shape` registry fields (AT-02), (iii) the
# Layer-C staleness check reachable from the real docgen entry (AT-03). Each
# is driven through the real CLI entry point with an observable effect
# (bounded file delta / refusal verdict).
#
# Wiring witness shape (AT-01): the working registry is EDITED to a sentinel
# skill that appears nowhere in the shipped assets, then re-rendered. The
# generated region following the EDIT proves docgen reads the registry (never
# a baked constant); region content agreeing with the seam answer proves the
# one-SSOT read API; the retired `:74` row is detected mechanically as any
# surviving line pairing the retired skill name with its CONDITIONAL marker
# outside the freshly rendered region. Prose-content assertions here are
# sanctioned because the projected region content IS the observable contract.
#
# Working copy (Pillar 3, app as in production): byte-copies of the REAL
# shipped `nw-software-crafter.md`, `nw-deliver` guide, both flavor files and
# the framework catalog under tmp_path, plus minimal stubs for the agent's
# referenced skills + the registry-directed agents so the real docgen
# pipeline scans/enriches/renders exactly as in production AND the copy is a
# LEGAL registry-bearing tree the slice-05 Layer-B gate accepts. Sentinel
# authoring is REPLACE-IN-PLACE (post-review amendment 2026-06-11: each field
# declared exactly once — the append-pattern's duplicate-key shadowing was
# the illegal state Layer B refuses). The phase-shape sentinel targets the
# CLASSIC flavor only; the DEFAULT flavor's `deliver_phase_shape` keeps the
# shipped runtime-canonical value the Layer-C agreement leg cross-checks —
# read-through for the field is proven via the classic row (one renderer
# code path, per-flavor data).
#
# Universe (Mandate 8, layer-3 FS acceptance): port-exposed observables only —
# generated-region bodies, asset text outside the regions, registry file
# texts, CLI exit/output. Every mutating step asserts via
# `assert_state_delta(before, after, universe, expected)`; the staleness
# check asserts the empty-expected preservation contract (rewrites nothing).
#
# Treatment (Mandate 9 v2 OR-reduction): real filesystem + real subprocess in
# the driven set -> @real-io, example-based, zero PBT machinery (falsifier
# gate: closed-world finite domain — 2 assets x 2 regions x 2 drift vectors).
# Sad paths explicitly enumerated (Mandate 11).
#
# Carpaccio ceiling = 3 scenarios, @slice-02 (4 executable examples):
#   AT-01 — skill-load render + inline-row retirement (the wiring witness).
#   AT-02 — mode-descriptor render from the new registry fields.
#   AT-03 (outline, 2 named drifts) — stale projection REFUSED, never served.
# Error-path share: 2 of 4 executable examples (50% >= 40%).

Feature: Registry projections land in the real assets and stale projections are refused
  As the maintainer of the mode registry
  I want every asset's mode prose rendered from the registry into a generated region
  So that changing a mode is one registry edit followed by a re-render,
  and a projection that drifted from the registry is refused loudly instead of served stale

  Background:
    Given a working copy of the shipped crafter spec, deliver guide, and mode registry
    And the working registry declares the mode descriptors authored for this test

  @driving_port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: The registry becomes the sole author of the crafter's conditional-skill directive
    Given the working registry is edited to direct the crafter to a different conditional skill
    When the projection re-renders the working copy
    Then the re-render completes without refusal
    And the crafter spec's generated skill-load region directs exactly what the registry resolution seam answers
    And no hand-written copy of the retired conditional-skill row survives in the crafter spec
    And the crafter spec outside its generated region is untouched

  @driving_port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: The deliver guide's mode description is spoken by the registry, not hand-written
    When the projection re-renders the working copy
    Then the re-render completes without refusal
    And the deliver guide's generated mode-descriptor region carries the registry's descriptor for every declared mode
    And the deliver guide's generated mode-descriptor region carries the registry's deliver phase shape
    And the deliver guide outside its generated region is untouched

  @driving_port @real-io @slice-02 @error @contract-shape:unbounded-preservation
  Scenario Outline: A projection that no longer matches its registry is refused, never served stale
    Given the working copy has been freshly projected and accepted
    And <drift> behind the projection's back
    When the staleness check inspects the working copy
    Then the staleness check refuses the working copy, naming the stale crafter spec
    And the very same working copy was accepted before the drift
    And the staleness check itself rewrites nothing

    Examples:
      | drift                                          |
      | the registry's crafter skills are edited       |
      | the generated skill-load region is hand-edited |
