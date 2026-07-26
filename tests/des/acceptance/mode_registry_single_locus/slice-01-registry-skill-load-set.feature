@feature-mode-registry-single-locus @slice-01
# Feature: mode-registry-single-locus slice-01 (@walking-skeleton per the Slice
#          Plan; executable tag `@walking_skeleton` per suite convention).
#
# THE OPERATOR VALUE (Slice Plan row slice-01): "One asset
# (`nw-software-crafter.md`) reads its conditional skills from the flavor
# `skill_load_set` instead of its inline table; dispatch behaviour
# byte-identical." Face (c) of the mode 4-tuple — the skill-load set per mode —
# gains its single locus of truth: the flavor registry (`nWave/flavors/*.yaml`),
# per DESIGN D-extend + D-inject (feature-delta, SSOT: analysis §2.2-§2.3).
#
# Driving port (the Driving-Port-Only Boundary mandate, SSOT
# `nw-test-design-mandates`): `des.application.flavor_dispatcher.
# resolve_skill_load_set(agent_id, flavor_id, *, flavors_dir)` — the
# DESIGN-declared D-inject seam, Layer-3 composition entry of the flavor
# dispatcher SUT, same surface class as `dispatch_lifecycle_event` (precedent
# attestation: tests/des/acceptance/d4_phase_3_flavor_dispatcher/conftest.py).
# NEVER prose inspection of the agent markdown; NEVER a hand-rolled YAML read
# at the test boundary.
#
# Dormant-Seam Reconciliation (D11 / S3): the AT-oracle target IS the
# DESIGN-declared seam (registry -> conditional-skill resolution), not the new
# component in isolation. All three ATs name and drive that exact seam. The
# asset-side reference line in `nw-software-crafter.md` and the dispatch-prompt
# injection call-site are DELIVER slice-01 GREEN scope; the registry-edit
# refusal gates are slice-05.
#
# Byte-equivalence witness shape (DISTILL open item, now pinned): the resolved
# conditional-skill set for (nw-software-crafter, atdd_pure) must equal EXACTLY
# {"nw-crafter-discipline-atdd-pure"} — the one skill the agent spec's inline
# table (`nw-software-crafter.md:74`) carries today. For classic the registry
# must DECLARE the crafter with the empty set (declared-empty, never an
# absent-key fallback — pinned by the refusal contract below). Set-equality
# against the typed constant in `steps/domain_types_slice_01.py` IS the
# byte-equivalence witness; the inline table is then safe to retire.
#
# Universe (Mandate 8 note): resolution is a READ — no observable state is
# mutated, so no `assert_state_delta` universe applies. Observables at the
# port: the resolved skill tuple OR the typed refusal (ValueError). Internal
# parser structures never appear in assertions.
#
# Treatment (Mandate 9 v2 OR-reduction): the driven set includes the REAL
# filesystem adapter reading the shipped `nWave/flavors/*.yaml` (AT-01/02) or
# a tmp_path-authored registry fixture (AT-03) -> @real-io, example-based,
# zero PBT machinery. Sad paths are explicitly enumerated (Mandate 11).
#
# Carpaccio ceiling = 3 scenarios, @slice-01:
#   AT-01 (@walking_skeleton) — atdd_pure: registry answer == retired inline table.
#   AT-02 — classic: registry's own declared-empty answer.
#   AT-03 (outline, 2 named defects) — declaration defects are REFUSED, never improvised.
# Error-path share: 2 of 4 executable examples (50% >= 40%).

Feature: The mode registry is the single home of the crafter's conditional skills
  As the dispatch orchestrator preparing a crafter dispatch
  I want the crafter's conditional skills answered by the active flavor's registry entry
  So that changing a mode's skill set is one registry edit instead of a hand-sync
  across agent specs, while today's dispatch behaviour stays byte-identical

  Background:
    Given the shipped mode registry declares the atdd_pure flavor

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:pure-function
  Scenario: Under atdd_pure the registry directs the crafter to its discipline skill exactly as the retired inline table did
    When the dispatch asks the registry for the crafter's conditional skills under the "atdd_pure" flavor
    Then the crafter is directed to load exactly "nw-crafter-discipline-atdd-pure"
    And no other conditional skill is injected for the crafter

  # Converted with the removal. This pinned the registry's own DECLARED-EMPTY
  # answer for classic -- valuable while classic was a mode one could ask about.
  # It is not one any more, so the registry does not answer: it refuses. Kept
  # rather than deleted so the refusal stays pinned where the answer used to be.
  @driving_port @real-io @slice-01 @error @contract-shape:pure-function
  Scenario: The registry refuses to answer for the retired classic flavor
    When the dispatch asks the registry for the crafter's conditional skills under the "classic" flavor
    Then the registry refuses the retired flavor instead of answering

  @driving_port @real-io @slice-01 @error @contract-shape:pure-function
  Scenario Outline: The registry refuses to improvise an answer it does not properly declare
    Given a mode registry whose crafter entry is <defect>
    When the dispatch asks that registry for the crafter's conditional skills
    Then the request is refused as a declaration defect
    And no conditional skills are improvised for the crafter

    Examples:
      | defect                                     |
      | written as one bare word instead of a list |
      | missing from the flavor entirely           |
