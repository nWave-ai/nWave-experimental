@feature-f-wave-contract-coherence @driving_port @real-io @contract-shape:bounded-change
Feature: The DISCUSS greenfield triangle is dissolved

  The "greenfield triangle" is the three-source contradiction that made DISCUSS
  de-facto mandatory and self-contradictory on a greenfield project (ADR-FLOW-002
  Q4, retired into this slice; brief §6):

    (1) the DISCUSS gate-IN MIGRATION_UNMET token (docs/product/ absent) is treated
        as a HARD VETO by the spine -- so a greenfield project cannot enter DISCUSS
        at all, contradicting the "DISCUSS is optional, DELIVER/DISTILL are the only
        floor" methodology model;
    (2) bootstrap-ownership disagrees across the shipped DISCUSS prose -- the
        `nw-discuss` SKILL and the `/nw-discuss` command both say "DISCUSS will
        bootstrap docs/product", while the canonical DISCOVER -> DIVERGE -> DISCUSS
        order makes DIVERGE the bootstrap owner;
    (3) the legacy multi-file `discuss/*.md` output form survives in the command
        prose's produced-output list, contradicting the inline `## Wave: DISCUSS /
        [REF] <Section>` feature-delta form the layout validator now enforces.

  This slice dissolves all three. The cure is idempotency-guarded: each scenario
  asserts the END-STATE (not a delta) so a prior ADR-FLOW-002 Q4 ship that already
  reconciled part of this is green either way (brief §6 "assert the desired
  end-state, which a prior Q4 ship already satisfies").

  Driving surface (Mandate-13 driving-port-only):
    * AT-12 drives the REAL shipped DISCUSS gate-IN seam -- the production
      `DiscussGateIn.evaluate` pure core (the §22.0 token authority) over a
      greenfield `SsotPresence`, AND the REAL spine veto-classifier
      (`PreToolUseService._discuss_gate_in_invoker`, the seam that today routes the
      token to a block) -- the exact loci ADR-FLOW-002 Q4 declasses. Observable: the
      gate-IN decision the spine emits for a greenfield project (a §17 veto stdout vs
      a non-blocking pass/advisory).
    * AT-13 + AT-14 drive the REAL shipped prose over the filesystem (TextSearch
      floor, ADR-LA-001 tier-3, git-free) -- the actual `nWave/tasks/nw/discuss.md`
      + `nWave/skills/nw-discuss/SKILL.md` the maintainer edits, and (AT-14) the REAL
      shipped layout validator `scripts/validation/validate_feature_layout.py`. The
      AT fails if any shipped artifact is absent (Critical Rule 7: no fixture
      theater -- the prose + validator are the real shipped artifacts).

  # AT-12: on a greenfield project (docs/product/ absent), the DISCUSS gate-IN no
  #        longer HARD-BLOCKS -- MIGRATION_UNMET is declassed veto -> advisory
  #        (ADR-FLOW-002 Q4, scope = MIGRATION_UNMET only; INDETERMINATE / MISSING_SSOT
  #        untouched). Driven through the REAL shipped gate-IN spine seam.
  @slice-05 @feature-f-wave-contract-coherence @AT-12 @error
  Scenario: A greenfield DISCUSS entry is not hard-blocked by the migration gate
    Given a greenfield project where docs/product is absent
    When the DISCUSS gate-in is evaluated for the greenfield project
    Then the DISCUSS gate-in does not hard-block the wave entry
    And the INDETERMINATE degrade-loud veto is left intact for an unreadable root

  # AT-13: bootstrap-ownership is reconciled and consistent -- BOTH shipped DISCUSS
  #        prose loci (command + skill) agree that DIVERGE owns the greenfield
  #        bootstrap, and neither carries the stale "DISCUSS bootstraps / creates
  #        docs/product" contradiction. End-state assertion (idempotent).
  @slice-05 @feature-f-wave-contract-coherence @AT-13
  Scenario Outline: The shipped DISCUSS prose agrees DIVERGE owns greenfield bootstrap
    Given the shipped DISCUSS <locus> bootstrap-ownership prose
    Then the shipped DISCUSS prose carries no stale DISCUSS-bootstraps-docs-product claim
    And the shipped DISCUSS prose attributes greenfield bootstrap to DIVERGE

    Examples:
      | locus   |
      | command |
      | skill   |

  # AT-14: the legacy multi-file `discuss/*.md` output form is retired -- the shipped
  #        layout validator REJECTS a `discuss/*.md` companion file, and the shipped
  #        command prose no longer ENUMERATES `discuss/*.md` files as its produced
  #        outputs (the inline `## Wave: DISCUSS / [REF] <Section>` form is the SSOT).
  @slice-05 @feature-f-wave-contract-coherence @AT-14
  Scenario: The legacy discuss multi-file output form is retired
    Given the shipped layout validator and the shipped DISCUSS command prose
    Then the layout validator rejects a legacy discuss multi-file output
    And the shipped DISCUSS command prose enumerates no legacy discuss multi-file outputs
