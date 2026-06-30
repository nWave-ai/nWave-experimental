@feature-algebra-projections-enforced
Feature: The DELIVER-entry contract-freeze gate keeps its observable contract after the registry migration

  The DELIVER-entry contract-freeze gate (`des verify-deliver-entry-contract`)
  decides whether a feature-delta has every locked section before it freezes the
  contract. Today it reads a hard-coded 4-section list; this feature migrates it
  to the registry-backed reader (ADR-001 ADD-not-mutate). The migration MUST be
  byte-stable: a maintainer entering DELIVER sees EXACTLY the same verdict and the
  SAME diagnostic — naming the same four locked sections — before and after the
  swap. These scenarios are the un-gameable regression witness of that
  byte-stability: they pass at HEAD (the pre-migration gate) and MUST stay green
  through the DELIVER swap, proving the migration changed the implementation
  without changing the observable contract.

  # DISCUSS WD-2 (LOCKED_REF_SECTIONS is a substrate consumed by N callers — ADD a
  # registry-backed reader + migrate the 1 caller explicitly, byte-stable; an
  # in-place swap silently mutates the DELIVER-entry contract). DESIGN DA-3 / DD-A3
  # (the migration is byte-stable: the FAIL diagnostic text + the PASS/FAIL/
  # INDETERMINATE verdict mapping are preserved VERBATIM). ADR-001 D2.
  # Driving port: the REAL DELIVER-entry gate `des verify-deliver-entry-contract
  # --feature-id <id> --repo-root <tmp> --format=json` (NOT the validate-feature-
  # delta surface — the migration's whole point is that THIS gate's contract is
  # unchanged). Layer 3 (subprocess/FS acceptance) — example-only, no PBT (Mandate
  # 9/11). @contract-shape:bounded-change per DA-3 (declared mutation set = the 1
  # call site at verify_deliver_entry_contract.py:172; the observable contract is
  # the invariant the witness pins). @regression-witness: this is a guardrail that
  # is GREEN at HEAD and must remain GREEN across the DELIVER migration — the
  # un-gameable proof of ADD-not-mutate.

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change @regression-witness
  Scenario: A DELIVER-entry contract missing a locked section is refused, naming the same four locked sections after the migration
    Given a DELIVER-entry contract missing one of its locked sections
    When the contract-freeze gate runs at the DELIVER gate-IN
    Then the freeze gate refuses the contract for a missing locked section
    And the refusal names the four locked sections of the DELIVER-entry contract
    And the freeze gate leaves the contract unfrozen

  @slice-02 @driving_port @real-io @contract-shape:bounded-change @regression-witness
  Scenario: A structurally-complete DELIVER-entry contract is still frozen after the migration
    Given a DELIVER-entry contract that carries every locked section and a valid slice plan backed by an authored slice
    When the contract-freeze gate runs at the DELIVER gate-IN
    Then the freeze gate freezes the contract
    And the freeze gate emits no diagnostic
