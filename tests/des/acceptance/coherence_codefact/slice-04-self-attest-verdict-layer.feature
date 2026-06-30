@feature-f-coherence-and-attestation @slice-04
Feature: A self-attest layer makes a machine YES never authorize a gate verdict
  As a maintainer reading any gate verdict
  I want a PASS to mean a mechanical control found no objection
    -- a bare-LLM verdict with no mechanical evidence is UNVERIFIED (a NO floor),
    and two sources that disagree are INDETERMINATE
  So that a machine YES never authorizes and only the human GO advances the flow

  # slice-04 of f-coherence-and-attestation (JOB-028). The self-attest verdict
  # layer (D9 / ADR-CA-001 D1): EXTENDS the keyless content-seal
  # (`src/des/domain/at_review_signing.py` -- SIGNED_FIELDS, canonical_signed_json;
  # HMAC removed 2026-06-11) into the dual-source classifier. It CONSUMES the
  # 5-verdict GateVerdict SSOT unchanged (C6, no sixth) -- gate-G (slice-03) and the
  # runner port (slice-05) are mechanical-evidence SOURCES it reads. Builds ON the
  # PARTIAL substrate; the slice 01/02/03 ATs stay GREEN.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition -- the REAL src/des seam):
  #   the self-attest classifier is driven at the COMPOSITION ROOT (a real
  #   classifier callable over a real dual-source verdict record) -- NOT a
  #   subprocess `des self-attest` dispatch: the `des` dispatcher has no self-attest
  #   row at HEAD, so a subprocess dispatch would be a collection-stage failure, not
  #   a semantic RED (mirrors slice-03's composition-root ASSUMPTION). The observable
  #   is the classified §17 GateVerdict + the reason the classifier names -- NEVER a
  #   line number.
  #
  #   AT-12 -> a record carrying mechanical evidence where the mechanical source and
  #            the LLM source AGREE -> classified PASS (a mechanically-grounded
  #            verdict -- a control found no objection).
  #   AT-13 -> a record with an LLM say-so but NO mechanical evidence reference ->
  #            classified UNVERIFIED (a NO floor -- the bare-LLM YES never
  #            authorizes, Invariant 1).
  #   AT-14 -> the mechanical source and the LLM source DISAGREE -> classified
  #            INDETERMINATE (two sources that disagree).
  #   AT-15 -> the mechanical leg did not complete within the watchdog window ->
  #            classified INDETERMINATE (the mechanism could not run -- degrade LOUD).
  #
  # §17 verdict map (ADR-GV-001, FIVE verdicts -- CONSUMED unchanged, no sixth, C6):
  #   mechanical evidence present AND sources agree    -> PASS
  #   bare-LLM say-so, no mechanical evidence           -> UNVERIFIED (NO floor)
  #   mechanical and LLM sources disagree               -> INDETERMINATE
  #   watchdog timeout before the mechanical leg set    -> INDETERMINATE
  #
  # FIXTURE DISTINCTNESS: each AttestationCase builds a CONTENT-DISTINCT verdict
  # record (the {mechanical_verdict, llm_verdict, mechanical_evidence_ref, watchdog}
  # 4-tuple differs per case) so a deterministic classifier maps each distinct
  # record to its distinct verdict. The two INDETERMINATE-producing cases
  # (DUAL_SOURCE_DIVERGENCE vs WATCHDOG_TIMEOUT) carry GENUINELY distinct records
  # (FAIL/PASS/<ref>/False vs None/PASS/None/True). See composition `_build_record`.
  #
  # active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the self-attest classifier
  # is ABSENT -- `src/des/domain/self_attest.py` does not exist (verified: no
  # self_attest module, no mechanical_verdict/llm_verdict classifier in src/des --
  # only docstring mentions of the memory anchor). Each scenario RED-fails with a
  # semantic AssertionError naming the missing classifier, never a collection /
  # import / setup error. GREEN once DELIVER lands the classifier EXTENDING the
  # keyless content-seal (ADR-CA-001 D1 -- never HMAC, never self-signed).
  #
  # DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (in the composition docstring --
  # the SEAM, never a line number): A1 the classifier entry (composition-root
  # callable `classify` / `classify_verdict` / `SelfAttest().evaluate`); A2 the
  # record shape ({mechanical_verdict, llm_verdict, mechanical_evidence_ref} +
  # watchdog signal, modelled `watchdog_timed_out: bool`); A3 the verdict envelope
  # (a §17 GateVerdict + reason); A4 seal-projection is the spine's concern -- NOT
  # asserted at this layer. DELIVER MUST wire these to whatever real seam it ships.

  # AT-12 -- the mechanically-grounded PASS: mechanical evidence present AND the
  # mechanical source and the LLM source agree -> a control found no objection ->
  # §17 PASS.
  @slice-04 @driving_port @real-io @us-self-attest-grounded-pass @contract-shape:bounded-change
  Scenario: A verdict with mechanical evidence where both sources agree is mechanically grounded
    Given a gate verdict carrying mechanical evidence where the mechanical and reviewer sources agree
    When the self-attest layer classifies the gate verdict
    Then the self-attest layer returns a passing verdict

  # AT-13, AT-14, AT-15 -- the NO-floor / degrade cases: a machine YES never
  # authorizes. A bare-LLM say-so floors to UNVERIFIED; two sources that disagree
  # and a watchdog timeout each degrade LOUD to INDETERMINATE. Each case carries a
  # NON-EMPTY reason that NAMES ITS CAUSE (Invariant 2 -- no silent degrade) ->
  # the <cause_fragment> column pins a DISCRIMINATING phrase per row, so the two
  # INDETERMINATE causes (divergence vs watchdog) are NOT conflatable: a hollow
  # classifier returning INDETERMINATE with ONE constant reason for both RED-fails
  # the divergence-names-"disagree" / watchdog-names-"watchdog" assertion. The
  # three fragments ("evidence" / "disagree" / "watchdog") are MUTUALLY EXCLUSIVE
  # (none a substring of another's reason) so the cause-in-reason is forced, not
  # just the verdict token -- this closes the "INDETERMINATE-for-the-wrong-reason
  # still passes" hole (the slice-03 fixture-distinctness lesson at the verdict-
  # CAUSE level). PBT-shaped over the NO-floor cases -> Scenario Outline. Each
  # row's record is CONTENT-DISTINCT.
  @slice-04 @driving_port @real-io @us-self-attest-no-floor @property @contract-shape:bounded-change
  Scenario Outline: A <attestation> gate verdict floors the self-attest layer to <verdict>
    Given a gate verdict that is <attestation>
    When the self-attest layer classifies the gate verdict
    Then the self-attest layer returns a <verdict> verdict
    And the self-attest layer names the floor as <cause_fragment> in the reason

    Examples:
      | attestation                                     | verdict       | cause_fragment |
      | a bare reviewer say-so with no mechanical evidence | unverified    | evidence       |
      | a disagreement between the mechanical and reviewer sources | indeterminate | disagree       |
      | a mechanical leg that timed out before it completed | indeterminate | watchdog       |
