@feature-mode-registry-single-locus @slice-04
# Feature: mode-registry-single-locus slice-04 — the BULK application of the
#          proven slice-01/02/03 patterns to every remaining mode-aware asset
#          family, plus the removal debt (Slice Plan row slice-04,
#          depends-on slice-02/03 — both SHIPPED: b4359ef35 / 9972dbe2d).
#
# THE OPERATOR VALUE (Slice Plan row slice-04): "The remaining 15 skills + 6
# agents reference the registry (skill-load injection + generated descriptor
# regions); the ~12 presence-assertion test dirs and the duplicated mode
# prose are DELETED — the codebase shrinks." Verified current-tree inventory
# (2026-06-11, supersedes the analysis estimate): 35 asset files carry 277
# naked `atdd_pure` / `workflow.mode` literals outside GENERATED regions
# (20 remaining skill dirs + 1 checklist yaml + 6 remaining agent specs + 6
# task guides); 11 prose-watcher test locations enumerated (8 DELETE / 3
# KEEP), per the deletion-safety ledger in `domain_types_slice_04.py` and
# the feature-delta DISTILL slice-04 section.
#
# THE BULK PROPERTY, not per-asset re-testing: slice-02 already proved
# region rendering == seam output for ONE agent; slice-04 pins (i) the two
# rendering cardinalities that slice-02 explicitly routed here (C1a empty
# conditional set / C3 many-skills list — the registry's answer for an
# agent may be silence or a chorus, and BOTH must land verbatim), (ii) the
# Layer-A precondition AS DATA: after the bulk migration no naked mode
# literal survives outside a GENERATED region or a `<!-- mode-ref-ok -->`
# allow-marker anywhere in the three migrated families (the sweep logic
# lives in the test composition; the `mode_locus_gate` CLI itself is
# slice-05 scope), and (iii) the deletion-safety equivalence: what each
# retired prose-watcher guarded is named, mapped to its replacement, and
# the watcher's absence + the replacement's teeth are both observable
# (the slice-03 AT-03 pattern, applied to the watcher ledger).
#
# Driving port (the Driving-Port-Only Boundary mandate, SSOT
# `nw-test-design-mandates`): the REAL docgen CLI, Layer-3 subprocess —
# `python scripts/docgen.py [--check] --root <working-copy>` — the
# slice-02/03 contract surface REUSED, no second mechanism. The ONLY other
# production import is the slice-01 seam
# `des.application.flavor_dispatcher.resolve_skill_load_set`, the
# EXPECTED-side read API ("region content equals seam output"). The
# watcher-ledger assertions read the live repository test tree — the
# legitimate structural-gate driving surface for a removal-debt contract
# (precedent: tests/methodology/test_code_design_skill_dedup.py).
#
# Dormant-Seam Reconciliation (D11 / S3): slice-04 declares NO net-new
# production seam — the projection, the regions, and the staleness check
# shipped with slices 02-03. The DESIGN-declared net-new SURFACE is data
# reach: (i) registry `skill_load_set` rows for the remaining agents,
# including the declared-EMPTY cardinality, rendered through the real
# entry (AT-01); (ii) region coverage across the bulk families + the
# zero-naked-literal end state (AT-02); (iii) the watcher deletion with
# replacement teeth (AT-03). No Mandate-7 scaffold needed: the entry and
# both region ids exist (slice-02 GREEN).
#
# Working copy (Pillar 3, app as in production): byte-copies of the ENTIRE
# shipped nWave/{agents,tasks,skills,flavors,templates} trees + the
# framework catalog under tmp_path — because the copies ARE the shipped
# bytes, the assertions witness the REAL assets' migrated state at GREEN.
#
# Universe (Mandate 8, layer-3 FS acceptance): port-exposed observables
# only — generated-region bodies, asset text outside regions, per-family
# content fingerprints, CLI exit/output. The sweep and the staleness check
# assert the empty-expected preservation contract (they rewrite nothing).
#
# Treatment (Mandate 9 v2 OR-reduction): real filesystem + real subprocess
# in the driven set -> @real-io, example-based, zero PBT machinery
# (falsifier gate: closed-world finite domain — a fixed asset tree, two
# rendering cardinalities, a fixed watcher ledger). Sad paths explicitly
# enumerated (Mandate 11). Literal set pinned to the unambiguous pair
# `atdd_pure` + `workflow.mode`; bare-`classic` token disambiguation is
# the slice-05 `mode_locus_gate` design call (routed, see feature-delta).
#
# Carpaccio ceiling = 3 scenarios, @slice-04 (5 executable examples):
#   AT-01 (outline, 2 cardinalities) — empty-set + many-skills rendering.
#   AT-02 — the bulk sweep: zero naked mode literals in the families.
#   AT-03 (outline, 2 watchers) — watcher gone + replacement has teeth.
# Error-path share: 2 of 5 executable examples (40% >= 40%).

Feature: The bulk migration makes the registry the sole author across every mode-aware asset family
  As the maintainer of the mode registry
  I want every remaining mode-aware skill, agent spec, and task guide to reference the registry
  So that no asset re-states a mode by hand, the retired prose-watchers are gone,
  and the staleness check now guards what each of them used to guard

  Background:
    Given a working copy of every shipped mode-aware asset family and the mode registry

  @driving_port @real-io @slice-04 @contract-shape:bounded-change
  Scenario Outline: The registry's answer for every agent lands in that agent's spec, whether silence or a chorus
    Given the working registry is edited to declare <render case>
    When the bulk migration re-renders every migrated asset
    Then the bulk re-render completes without refusal
    And the <agent> spec's generated skill-load region declares exactly what the registry resolution seam answers
    And the <agent> spec outside its generated region is untouched

    Examples:
      | render case                                                        | agent               |
      | no conditional skills for the product owner                        | product owner       |
      | two freshly minted conditional skills for the acceptance designer | acceptance designer |

  @driving_port @real-io @slice-04 @contract-shape:unbounded-preservation
  Scenario: After the bulk migration no asset re-states the mode by hand
    Given the migrated families have been freshly re-rendered and accepted
    When the sweep audits every migrated asset family for hand-written mode statements
    Then no hand-written mode statement survives outside a generated region or a marked reference
    And the sweep itself rewrites nothing

  @driving_port @real-io @slice-04 @error @contract-shape:unbounded-preservation
  Scenario Outline: What each retired prose-watcher guarded, the staleness check now guards, and the watcher is gone
    Given the migrated families have been freshly re-rendered and accepted
    And the <guarded asset>'s generated region is hand-edited behind the bulk migration's back
    When the staleness check audits the migrated families
    Then the <watcher> is gone from the test tree
    And the prose-watchers ruled keepers still stand watch
    And the staleness check refuses the migrated families, naming the <guarded asset>
    And the migrated families were accepted before the hand-edit

    Examples:
      | watcher                    | guarded asset                  |
      | bugfix mode watcher        | bugfix guide                   |
      | review methodology watcher | software-crafter reviewer spec |
