@feature-algebra-projections-enforced
Feature: The DELIVER-entry gate refuses a contract missing a mandatory locked section, naming it

  Direction (b) of the registry-section cross-check — "every mandatory section is
  PRESENT" — is a COMPLETENESS assertion, and completeness is only required where
  the whole contract must be FROZEN: at the DELIVER-entry gate
  (`des verify-deliver-entry-contract`), NOT on the standalone
  `validate-feature-delta --require-registry-sections` flag (ADR-002 D1). The flag
  stays direction-(a)-only and ACCEPTS partial deltas, because its sole wiring
  (`discuss.yaml gate-out`) legitimately carries a mid-authoring partial delta. The
  DELIVER-entry gate is where a missing mandatory section IS a FAIL — that is the
  surface these two scenarios drive.

  The DELIVER-entry mandatory contract is the four LOCKED `[REF]` sections
  (Architecture & Contract Tests / ADR Refs / Reuse Analysis / Slice Plan), read
  via `missing_registry_sections(content, _DELIVER_LOCKED_CONTRACT)`
  (verify_deliver_entry_contract.py:193). Scenario one drives the completeness
  oracle: a delta omitting ONE locked section is REFUSED, the verdict naming THAT
  section so the maintainer knows what to author. Scenario two is the presence
  discriminator (the structural analogue of WD-5 at the DELIVER-entry surface):
  presence is heading-based, so a locked section whose heading is PRESENT but whose
  body is empty SATISFIES the completeness check — an honest-empty section is NOT a
  missing-mandatory failure, and the contract still freezes.

  # ADR-002 (REROUTE_DESIGN): direction (b) completeness lives at the DELIVER-entry
  # gate, not on the standalone flag. DISCUSS WD-3 direction (b) (a mandatory section
  # not in the delta -> REJECT) + WD-5 (a present-but-honestly-empty section is NOT a
  # missing-mandatory failure) are REALISED here against the four LOCKED sections,
  # the only mandatory contract this gate freezes. DESIGN DD-A4 (revised by ADR-002).
  # Driving port: `des verify-deliver-entry-contract --feature-id <id> --repo-root
  # <tmp> --format=json` (the §17 GateVerdict envelope; read the structured token,
  # never a free-text stdout substring). Layer 3 (subprocess/FS acceptance) —
  # example-only, no PBT (Mandate 9/11): the locked-section presence cross-check is a
  # closed-world finite classification; sad paths enumerated explicitly (Mandate 11).
  # @contract-shape:pure-function per DA-2 (return-only, zero I/O — the gate reads the
  # feature-delta and returns a verdict without mutating it).
  #
  # NOTE on classification (honest, NOT active-RED): the DELIVER-entry gate ALREADY
  # calls missing_registry_sections at :193 against _DELIVER_LOCKED_CONTRACT and
  # ALREADY names the missing section in its FAIL diagnostic; presence is ALREADY
  # heading-based (an empty-body locked section ALREADY freezes). Both scenarios are
  # therefore PRESERVATION-GUARDS, GREEN at HEAD — the direction-(b) completeness
  # surface was always THIS gate (ADR-002: the byte-stable migration IS direction-(b)
  # realised; the call site at :193 pre-exists). They go RED only if a future change
  # regresses the completeness oracle. This is the un-gameable distinction from the
  # two byte-stable witnesses: those pin that the migration names ALL FOUR sections;
  # these pin the direction-(b) SEMANTICS (the specific missing section is named; an
  # honest-empty section is not a failure).
  #
  # NOTE on greenfield_degradation: the standalone-flag scenarios' greenfield-
  # degradable discriminator (Wave-Decision Reconciliation, a DISCUSS ref_section)
  # is NOT expressible at the DELIVER-entry surface — _DELIVER_LOCKED_CONTRACT is the
  # four LOCKED sections, all grade=mandatory, ZERO greenfield-degradable
  # (verify_deliver_entry_contract.py:98-112). WD-5's intent (a section satisfiable
  # without a substantive body) is honoured here by the heading-based presence rule
  # (scenario two), the only honest analogue this gate carries. Documented in
  # distill/at-completeness-audit.md — not a specification gap.

  @slice-02 @walking_skeleton @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A DELIVER-entry contract omitting a mandatory locked section is refused, naming the missing section
    Given a DELIVER-entry contract omitting a mandatory locked section
    When the contract-freeze gate runs at the DELIVER gate-IN
    Then the freeze gate refuses the contract for a missing mandatory section
    And the refusal names the omitted locked section
    And the freeze gate leaves the contract unchanged

  @slice-02 @driving_port @real-io @contract-shape:pure-function
  Scenario: A DELIVER-entry contract whose only deficiency is an empty-body locked section still freezes
    Given a DELIVER-entry contract carrying every locked section heading with one section left honestly empty
    When the contract-freeze gate runs at the DELIVER gate-IN
    Then the freeze gate freezes the contract
    And the freeze gate emits no diagnostic
    And the freeze gate leaves the contract unchanged
