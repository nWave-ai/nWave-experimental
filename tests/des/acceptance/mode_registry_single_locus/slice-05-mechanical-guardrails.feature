@feature-mode-registry-single-locus @slice-05
# Feature: mode-registry-single-locus slice-05 — the THREE orthogonal,
#          Python-only, git-free mechanical gates that make the NEXT mode
#          shotgun-surgery STRUCTURALLY IMPOSSIBLE (Slice Plan row slice-05;
#          analysis §3.1-§3.4). This is the guardrail; everything before it
#          (slices 01-04, shipped) is convention until these gates exist.
#
# THE OPERATOR VALUE (Slice Plan row slice-05): "A hand-edit that re-introduces
# a mode copy is REFUSED mechanically: Layer A (mode_locus_gate) + Layer B
# (mode_registry_completeness) + Layer C (resolver<->registry agreement) wired
# as DES gates + pre-commit." Each gate answers a different question, and a
# one-layer bypass is caught by >=1 of the others (analysis §3.4):
#   A — no naked mode literal outside a GENERATED region / allow-marker;
#   B — the registry is the single, complete home for the mode 4-tuple;
#   C — every projection equals its source AND the resolver-default equals the
#       flavor-default AND the registry deliver_phase_shape equals the runtime
#       canonical DELIVER phases (the registry<->runtime parity that CLOSES the
#       KEEP-row-10 open leg of atdd_pure_phase_count_slice03).
#
# THE LOAD-BEARING DECISION pinned AS DATA (the bare-`classic` disambiguation,
# routed here from slice-04): Layer A flags `classic` ONLY in a
# config/declaration shape (workflow.mode == classic / mode: classic /
# --mode classic / flavor vocabulary: flavor_id: classic, classic.yaml),
# NEVER the bare English word (classic Scenario / classic TDD / classic
# 3-phase) NOR descriptive prose (classic mode / classic-mode — 17 legitimate
# documentation lines, slice-04 KEEP). `atdd_pure` and `workflow.mode` stay
# unconditionally flagged. Empirical corpus anchor (2026-06-11, restated under
# this rule): 31 files carry `classic`; only config/declaration shapes flag —
# bare English + descriptive prose MUST pass, shipped tree accepted clean.
# The rule lives in domain_types_slice_05.py:BARE_CLASSIC_RULE; the AT-01
# accept BASELINE exercises its accept side (an allow-marked literal +
# benign-classic prose ACCEPTED before the naked literal is planted).
#
# THE TWO TEETH PER GATE in 3 scenarios (Pillar-2 chaining, the slice-02/03/04
# accepted-before-drift pattern): each scenario's Given runs the gate against
# the CLEAN copy as a baseline (accept teeth), THEN the When introduces the
# defect and re-runs (refuse teeth). One scenario per orthogonal layer; AT-02
# is an outline over the three named Layer-B registry defects.
#
# Driving port (the Driving-Port-Only Boundary mandate, SSOT
# `nw-test-design-mandates`): each gate driven through its REAL entry —
# Layer A/B via `python -m des.cli <gate-id> --root <working-copy>` (the REAL
# `des` dispatcher, Layer-3 subprocess); Layer C via the already-shipped
# `python scripts/docgen.py --check --root <working-copy>`. ZERO production
# import in the slice-05 step surface (S2 PASS): the gates are subprocesses,
# the gate catalog is read as a data artifact (the wiring-witness oracle).
#
# Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared net-new seams
# are the two new gate CLIs + the elevated docgen agreement check. EACH is
# witnessed THROUGH its real entry with an observable effect (accept baseline +
# refuse-on-defect). PLUS the explicit anti-dormancy witness: Layer A/B are
# reachable as `des` subcommands (dispatcher-registry membership = INDIRECT
# wiring, valid per S3) AND declared in the gate catalog (1:1 mirror) — so
# neither ships as a dormant CLI. Mandate-7 RED scaffolds ship additively for
# the two new gate CLIs (the dispatcher does not yet route them, so the
# real-entry invocation surfaces the missing capability as a semantic refusal
# asserted in Then — active-RED, never an import/setup error). Layer C's entry
# exists but does not yet assert the two agreement legs.
#
# Working copy (Pillar 3, app as in production): byte-copies of the shipped
# nWave/{agents,tasks,skills,flavors} families + the gate catalog under
# tmp_path + a self-contained clean locus probe (allow-marked literal +
# benign-classic prose) — because the family copies ARE the shipped bytes, the
# accept baseline witnesses the REAL registry's completeness at GREEN.
#
# Universe (Mandate 8, layer-3 FS acceptance): port-exposed observables only —
# the two registry file texts, the locus-probe asset text, the catalog text,
# and each gate's exit/output. Every gate is a pure read; the empty-expected
# delta proves the guardrail rewrites nothing.
#
# Treatment (Mandate 9 v2 OR-reduction): real filesystem + real subprocess in
# the driven set -> @real-io, example-based, zero PBT machinery (falsifier
# gate: closed-world finite domain — three gates, a fixed defect set, a fixed
# clean corpus). Sad paths explicitly enumerated (Mandate 11): Layer A naked
# literal, Layer B three named registry defects, Layer C the agreement check.
#
# Carpaccio ceiling = 3 scenarios, @slice-05 (one per orthogonal layer; AT-02
# is an outline over the three named registry defects = 5 executable examples).
# Error-path share: AT-01 + AT-02's three examples carry the refuse teeth in
# the When (4 of 5 executable examples are @error >= 40%).

Feature: The mechanical guardrails make the next mode shotgun-surgery structurally impossible
  As the maintainer of the mode registry
  I want three orthogonal, Python-only, git-free gates wired as reachable DES gates
  So that a hand-edit re-introducing a mode copy, a half-declared mode, or a
  drifted projection is REFUSED mechanically — never merely discouraged

  Background:
    Given a working copy of the mode registry, its asset families, and the gate catalog

  @driving_port @real-io @slice-05 @error @contract-shape:unbounded-preservation
  Scenario: Layer A accepts marked references then refuses a hand-restated mode literal
    Given the no-naked-mode-literal gate stands watch over the working copy
    And the guardrail has already accepted the clean working copy as a baseline
    And a mode literal is re-stated by hand outside any generated region or marker
    When the guardrail inspects the working copy carrying the defect
    Then the guardrail refuses the working copy, naming the offending defect
    And the guardrail accepted the clean working copy before the defect
    And the guardrail itself rewrites nothing
    And the guardrail is wired as a reachable gate the catalog declares

  @driving_port @real-io @slice-05 @error @contract-shape:unbounded-preservation
  Scenario Outline: Layer B accepts the shipped registry then refuses a half-declared mode
    Given the registry-completeness gate stands watch over the working copy
    And the guardrail has already accepted the clean working copy as a baseline
    And the working registry is half-declared so that <defect>
    When the guardrail inspects the working copy carrying the defect
    Then the guardrail refuses the working copy, naming the offending defect
    And the guardrail accepted the clean working copy before the defect
    And the guardrail is wired as a reachable gate the catalog declares

    Examples:
      | defect                                          |
      | a flavor is missing a required mode field       |
      | two flavors both claim to be the default        |
      | a flavor directs an agent that does not exist   |

  @driving_port @real-io @slice-05 @error @contract-shape:unbounded-preservation
  Scenario: Layer C accepts agreeing registry then refuses a registry whose phase shape drifts from the runtime
    Given the projection-and-resolver-agreement gate stands watch over the working copy
    And the guardrail has already accepted the clean working copy as a baseline
    And the registry's declared delivery phase shape drifts from the running system
    When the guardrail inspects the working copy carrying the defect
    Then the guardrail refuses the working copy, naming the offending defect
    And the guardrail accepted the clean working copy before the defect
    And the guardrail is wired as a reachable gate the catalog declares
