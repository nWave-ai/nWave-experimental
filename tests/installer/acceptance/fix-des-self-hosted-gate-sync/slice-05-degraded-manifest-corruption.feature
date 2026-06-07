@feature-fix-des-self-hosted-gate-sync @slice-05
# DISTILL slice-05 ATs — malformed `_install_manifest.json` REFUSES as
# DEGRADED with a per-corruption-kind reason substring on stderr.
#
# Story: a malformed `_install_manifest.json` REFUSES with state DEGRADED
# and a per-corruption-kind reason substring (§1.3 DEGRADED row + §1.4
# manifest schema + DDD-6 four-state truth table).
#
# Design SSOT: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md
#              §1.3 + §1.4 + DDD-6. Slice plan §5 row `slice-05`.
#
# SPLIT 2026-05-23 (DISTILL): this file isolates AT-03-C (architect's
# original corruption AT) into its own carpaccio slice. The slice carries
# `@coupled` on every scenario AND a justification row in the slice plan
# per ADR-028 D2-bis — 4 enumerated corruption kinds exceed the carpaccio
# ceiling 3 only as a cohesive Scenario-Outline group exercising the same
# SUT method (`RepoSourceProbe._read_install_manifest` returning DEGRADED
# verdict on malformed input) with enumerable bounded-change inputs.
#
# Layer: 3 (integration / subprocess) — example-based per Mandate 11.
# Architect's nominal `@given(corruption_kind)` PBT framing was downgraded
# at DISTILL: corruption shapes are a closed enumerable set; PBT runtime
# cost on a real-I/O subprocess test buys no signal.

Feature: DES freshness gate refuses malformed install manifest as DEGRADED
  As an operator running DES gates against an installed tree with a
  corrupted `_install_manifest.json`
  I want the gate to REFUSE with state DEGRADED and a reason citing the
  corruption shape
  So that operators see an actionable diagnostic instead of a silent failure
  or a wrong-state PROCEED

  @slice-05 @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario Outline: A malformed install manifest is REFUSED as DEGRADED per kind
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has a malformed manifest of kind <corruption>
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate REFUSES the invocation with exit code 78
    And the gate reports state DEGRADED
    And the refusal reason includes the substring <reason_substring>

    Examples:
      | corruption               | reason_substring |
      | unknown_schema_version   | schema_version   |
      | missing_required_field   | required field   |
      | non_json_content         | parse            |
      | empty_file               | parse            |
