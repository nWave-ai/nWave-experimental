@feature-mode-registry-single-locus @slice-03
# Feature: mode-registry-single-locus slice-03 — command frontmatter
#          `description:` is projected from `framework-catalog.yaml`; the
#          catalog↔frontmatter byte-match test degrades to a `docgen --check`
#          idempotency check (Slice Plan row slice-03, DESIGN decision
#          D-project).
#
# THE OPERATOR VALUE (Slice Plan row slice-03): "Eliminates one of the two
# hand-written copies (catalog = sole author); `test_command_frontmatter.py`
# flipped to call the idempotency check. The hotfix desync class becomes
# non-representable." The two probed guides ARE the 2026-06-10 hotfix victims:
# the execute guide's description and the distill guide's argument hint.
#
# Mechanism pin (DISTILL decision, recorded in the feature-delta): GENERATED
# HTML-comment markers cannot live inside YAML frontmatter — they would
# corrupt the host's frontmatter parse. The projection therefore REWRITES the
# `description:` / `argument-hint:` VALUES of every catalog-declared command
# guide from the catalog, and `--check` compares YAML-PARSED frontmatter
# values to catalog values, naming each stale guide. The catalog entry's
# existence IS the projection declaration (no marker); the key↔file rule is
# the retired test's own (underscore → hyphen); the equality contract is
# parsed-value equality (also the retired test's own comparison). Catalog
# entries with no guide file (update, workshopper) are skipped exactly as the
# retired test skipped them; guide files outside the catalog (forge,
# research) keep hand-authored frontmatter and stay guarded by docgen's
# existing missing-description refusal (DocgenError in extract_command).
#
# Driving port (the Driving-Port-Only Boundary mandate, SSOT
# `nw-test-design-mandates`): the REAL docgen CLI, Layer-3 subprocess —
# `python scripts/docgen.py [--check] --root <working-copy> --output-dir ...`
# — the slice-02 contract surface REUSED, no second mechanism. ZERO
# production imports in this slice's composition: the expected-side oracle is
# an independent YAML parse of the working catalog and guide frontmatter (the
# exact comparison the retired hand-sync test performed).
#
# Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared net-new seam
# this slice is the catalog→frontmatter projection reachable from the real
# docgen entry (D-project). It is witnessed through that real entry with
# observable effects: AT-01 (projection lands the edited catalog values in
# the guides, bounded change), AT-02 (the staleness check refuses each
# named desync vector), AT-03 (idempotent re-projection + the full-catalog
# agreement sweep that makes deleting the hand-sync test safe).
#
# Wiring witness shape (AT-01): the working catalog is EDITED to sentinel
# values that appear nowhere in the shipped assets, then re-projected. The
# guides carrying the sentinels afterwards proves the projection READ the
# catalog (never baked frontmatter); parsed-value equality with the EDITED
# catalog proves catalog-as-sole-author; the state delta proves the bounded
# change (projected fields only — bodies, the other guides, and the catalog
# itself untouched: the projection writes guides, never its own source).
#
# Byte-match degradation (AT-03, the deletion-safety pin): on one and the
# same working-copy state, the staleness check ACCEPTS, an independent YAML
# oracle confirms every catalog-declared guide agrees with the catalog on
# description and argument hint, and a second projection changes nothing
# (idempotency). Acceptance ⟹ agreement is exactly what the retired
# `test_command_frontmatter.py` guarded — with this pinned, the hand-sync
# test can be DELETED at GREEN (bloat-removal payoff).
#
# Working copy (Pillar 3, app as in production): byte-copies of the REAL
# framework catalog + ALL shipped command guides under tmp_path (plus the
# flavor registry and the empty asset dirs docgen's scan stage requires), so
# the full real entry (argparse → scan → extract → enrich → render →
# projection / check) runs exactly as in production, never mutating the live
# repo.
#
# Universe (Mandate 8, layer-3 FS acceptance): port-exposed observables only
# — YAML-parsed frontmatter values (what the host's parse yields), guide
# bodies outside the frontmatter, a fingerprint of every other guide, the
# catalog text. Every mutating step asserts via
# `assert_state_delta(before, after, universe, expected)`; the staleness
# check and the second projection assert the empty-expected preservation
# contract (fail-closed: they rewrite nothing).
#
# Treatment (Mandate 9 v2 OR-reduction): real filesystem + real subprocess in
# the driven set -> @real-io, example-based, zero PBT machinery (falsifier
# gate: closed-world finite domain — 28 catalog commands x 2 projected
# fields x 2 drift vectors; the AT-03 oracle sweep quantifies over the FULL
# catalog). Sad paths explicitly enumerated (Mandate 11).
#
# Carpaccio ceiling = 3 scenarios, @slice-03 (4 executable examples):
#   AT-01 — catalog edit → re-projection lands in the guides (sole author).
#   AT-02 (outline, 2 named desyncs) — the hotfix desync class is REFUSED.
#   AT-03 — acceptance ⟺ full catalog agreement + idempotency (the
#           byte-match degradation pin; hand-sync test deletable at GREEN).
# Error-path share: 2 of 4 executable examples (50% >= 40%).

Feature: The catalog is the sole author of every command guide's description and stale guides are refused
  As the maintainer of the framework catalog
  I want every command guide's description and argument hint projected from the catalog
  So that re-describing a command is one catalog edit followed by a re-projection,
  and a guide that drifted from the catalog is refused loudly instead of served stale

  Background:
    Given a working copy of the shipped command guides and the framework catalog

  @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: The catalog becomes the sole author of the command guides' descriptions and argument hints
    Given the catalog's description for the execute command is edited
    And the catalog's argument hint for the distill command is edited
    When the command guides are re-projected from the catalog
    Then the catalog projection completes without refusal
    And the execute guide's description is exactly what the edited catalog declares
    And the distill guide's argument hint is exactly what the edited catalog declares
    And nothing else about the command guides or the catalog changes

  @driving_port @real-io @slice-03 @error @contract-shape:unbounded-preservation
  Scenario Outline: A command guide that no longer matches its catalog is refused, never served stale
    Given the command guides have been freshly projected and accepted
    And <desync> behind the command guides' back
    When the staleness check inspects the command guides
    Then the staleness check refuses the command guides, naming the stale execute guide
    And the very same command guides were accepted before the desync
    And the staleness check leaves every command guide untouched

    Examples:
      | desync                                                    |
      | the catalog re-describes the execute command              |
      | the execute guide's projected description is hand-edited  |

  @driving_port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: What the retired hand-sync contract guarded, the staleness check now guards
    Given the catalog's description for the execute command is edited
    And the command guides have been freshly projected and accepted
    When the command guides are projected once more
    Then the freshly projected command guides were accepted by the staleness check
    And every command guide the catalog declares agrees with the catalog on description and argument hint
    And the second projection changes not a single command guide
