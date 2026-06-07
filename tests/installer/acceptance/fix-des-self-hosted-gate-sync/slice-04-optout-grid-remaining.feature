@feature-fix-des-self-hosted-gate-sync @slice-04
# DISTILL slice-04 ATs — NWAVE_FRESHNESS opt-out grid remaining values
# (verbose, enforce, empty, garbage) × {fresh, stale} install topology.
# The `skip` row already shipped in slice-01 AT-01-C (F3 bootstrap-blind
# closure for repo dev usage). This slice closes the §1.8 + DDD-10
# contract for every legal opt-out value AND the unrecognised-value
# REFUSE-as-DEGRADED leg.
#
# Design SSOT: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md
#              §1.8 (opt-out values), §1.3 (truth table), DDD-10
# Slice plan: §5 slice-04 — ADR-028 D2-bis coupled Scenario Outline
#             (7 ATs over carpaccio ceiling 3, justified by single SUT
#             method `assert_fresh_or_explain` honoring NWAVE_FRESHNESS
#             with bounded-change varying inputs; splitting would defeat
#             Mandate-12 parametrize-collapse density).
#
# Layer: 3 (integration / subprocess) — example-based + parametrize per
# Mandate 11 (sad paths at layer 3+ are enumerated examples, never PBT).

Feature: DES freshness gate honours NWAVE_FRESHNESS values per §1.8
  As an operator running DES gates against either a fresh or a stale install
  I want NWAVE_FRESHNESS={verbose,enforce,empty,garbage} to behave per §1.8
  So that the opt-out contract is exercised at every legal value (skip is
  already covered by slice-01 AT-01-C — the F3 bootstrap-blind closure)

  @slice-04 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario Outline: NWAVE_FRESHNESS opt-out grid behaviour matches §1.8
    Given a synthetic installed DES tree at the standard install path
    And the installed tree is in install state <install_state>
    And the environment variable NWAVE_FRESHNESS is set to <opt_out>
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate verdict is <verdict>
    And the gate reports state <observed_state>

    Examples: opt-out grid (3 × 2 = 6 cells — skip row already in slice-01 AT-01-C)
      | install_state | opt_out  | verdict | observed_state |
      | fresh         | enforce  | proceed | C              |
      | fresh         | verbose  | proceed | C              |
      | fresh         | empty    | proceed | C              |
      | stale         | enforce  | refuse  | D              |
      | stale         | verbose  | refuse  | D              |
      | stale         | empty    | refuse  | D              |

  @slice-04 @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: NWAVE_FRESHNESS with an unknown value is REFUSED as DEGRADED
    Given a synthetic installed DES tree at the standard install path
    And the installed tree is in install state fresh
    And the environment variable NWAVE_FRESHNESS is set to garbage
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate REFUSES the invocation with exit code 78
    And the gate reports state DEGRADED
    And the refusal reason cites the unrecognised opt-out value
