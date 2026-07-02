---
name: nw-discuss-story-mapping
description: "DISCUSS Phase 2.5 user story mapping procedure — backbone, walking-skeleton slice, elephant-carpaccio slicing with taste tests, slice briefs, and prioritization, with artifact paths. Run when decomposing the feature into a story map + thin vertical slices."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Phase 2.5: User Story Mapping (PROCEDURE)

**Kind**: PROCEDURE | **One job**: decompose the feature into a story map + elephant-carpaccio slices | **One trigger**: Phase 2.5 — the journey is designed and the feature must be decomposed into slices.

Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Phase 2.5: User Story Mapping

Luna loads `user-story-mapping` skill before this phase.

1. **Load Skill** — Load `user-story-mapping` skill. Gate: skill loaded.
2. **Backbone** — Map user activities (big steps) horizontally across the top of the story map. Gate: all major activities identified and ordered.
3. **Walking Skeleton** — Identify minimum slice that delivers end-to-end value. Gate: walking skeleton slice defined.
4. **Elephant Carpaccio Slicing** — Decompose stories into **thin vertical slices**, each shipping end-to-end in ≤1 day (≤6 hours of crafter dispatch), each with a named learning hypothesis. This supersedes the old "group into at least two releases" gate. The discipline and its rationale are documented below. Gate: every slice has (a) end-to-end value, (b) ≤1 day ship estimate, (c) a named learning hypothesis of the form "disproves X if it fails", (d) production data (not synthetic), (e) a dogfood moment within the same day, (f) explicit IN/OUT scope lists.
5. **Slice Taste Tests** — Apply the carpaccio taste tests to each slice before committing:
   - If a slice lists "ship 4+ new components" → it is NOT thin. Split further.
   - If every slice depends on a new abstraction → ship the abstraction FIRST as its own slice (or postpone it).
   - If no slice disproves any pre-commitment → the slicing is decoration, not discipline. Rethink.
   - If a slice uses only synthetic data → it proves plumbing, not value. Require a production-data acceptance criterion.
   - If 2+ slices are identical except for scale → merge them.
   Gate: all taste tests pass OR the failures are documented with a reason.
6. **Slice Briefs** — Produce one brief per slice at `docs/feature/{feature-id}/slices/slice-NN-name.md` with: goal (one sentence), IN scope, OUT scope, learning hypothesis (what this disproves if it fails, what it confirms if it succeeds), acceptance criteria, dependencies, effort estimate, reference class, pre-slice SPIKE if uncertainty is high. Each brief is ≤100 lines. Gate: brief exists for each slice listed in the story map.
7. **Prioritization** — Suggest slice execution order based on (a) learning leverage (highest-uncertainty slices first, so failures cost less), (b) dependency chain, (c) dogfood cadence. Gate: prioritization rationale documented per slice, NOT just per release bucket.

| Artifact | Path |
|----------|------|
| Story Map | `docs/feature/{feature-id}/discuss/story-map.md` |
| Prioritization | `docs/feature/{feature-id}/discuss/prioritization.md` |
| Slice Briefs | `docs/feature/{feature-id}/slices/slice-NN-*.md` (one per slice) |
