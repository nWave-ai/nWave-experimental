@feature-f-nonbypassable-attestation @slice-04
Feature: A catalogued gate that no live hook fires is flagged unless declared dormant
  As a maintainer adding a gate to the gate catalog
  I want a mechanical coherence check that flags a catalogued gate no live hook
    fires, unless I explicitly mark it dormant with a rationale
  So that the authored-but-unwired class (a gate shipped green but never fired)
    cannot reach "done" silently -- the gate-G / self-attest / runner-port hole

  # slice-04 of f-nonbypassable-attestation (KPI-4, DDD-6). The coherence check is
  # an ARCH-TIER pure function over (catalog, firing-surfaces): every gate-id in
  # nWave/gates/_catalog.yaml is EITHER wired into a live firing surface (a flavor
  # gate stack row, a live-hook module reference, OR operator-direct cli/git-hook
  # invocation) OR carries an explicit `dormant: <rationale>`. A gate that is
  # NEITHER is FLAGGED + NAMED (veto-able). The permanent CI guard is the arch test
  # tests/build/f_nonbypassable_attestation/test_arch_catalog_gate_wiring.py; THIS
  # .feature is the readable Gherkin companion driving the SAME shipped reducer.
  #
  # DRIVING SURFACE (Mandate-13 pure-function carve-out): the SUT is the pure
  #   coherence reducer `coherence_offenders(catalog, firing, host_visibility)` +
  #   the catalog `_schema.yaml`. The "driving port" for a pure-function slice IS
  #   the pure function. Step bodies delegate to the composition root, which drives
  #   the SAME reducer the arch test pins (single SSOT, no reimplementation) over
  #   the REAL shipped artifacts and over distinct synthetic fixtures.
  #   observable = the offender set (catalogued gate-ids neither wired nor dormant).
  #
  # INDIRECT WIRING COUNTS (S3 / Mandate-15 framing-attack): operator-direct CLI
  #   gates (`des doctor`, `des commit-slice`), git-hook gates, and live-hook
  #   module references are all valid wiring -- a naive "appears as a flavor
  #   gate_id row" match would FALSE-POSITIVE ~19 legitimate operator-CLI gates.
  #
  # DISTINCT FIXTURE PER VERDICT: coherent / flagged / excused / empty-rationale
  #   are produced by GENUINELY DIFFERENT catalogues, never a re-assertion over one.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): the schema-permits-dormant scenario is RED
  #   at HEAD -- `_schema.yaml` GateContract is `additionalProperties: false` with
  #   no `dormant` property, so a `dormant:` value is schema-REJECTED. GREEN once
  #   DELIVER adds optional `dormant: {type: string, minLength: 10}` (CRITICAL-2).
  #   The other scenarios are GREEN behaviour proofs over the reducer + live catalog.

  @slice-04 @driving_port @real-io @us-catalog-coherence @contract-shape:pure-function
  Scenario: Every catalogued gate is wired or dormant so the catalog is coherent
    Given the real gate catalog and the live hook firing surfaces
    When the catalog coherence check runs
    Then no gate is flagged as unwired

  @slice-04 @driving_port @us-catalog-coherence @error @contract-shape:pure-function
  Scenario: A catalogued gate no live hook fires and not dormant is flagged by name
    Given a catalogue with a wired gate and an orphan gate that no hook fires
    When the catalog coherence check runs
    Then the orphan gate is flagged and named

  @slice-04 @driving_port @us-catalog-coherence @contract-shape:pure-function
  Scenario: An unwired gate declared dormant with a rationale is excused
    Given an unwired catalogued gate declared dormant with the rationale "intentionally unwired pending the SF-tier dispatch layer"
    When the catalog coherence check runs
    Then the dormant gate is excused

  @slice-04 @driving_port @us-catalog-coherence @error @contract-shape:pure-function
  Scenario: An unwired gate declared dormant with an empty rationale is still flagged
    Given an unwired catalogued gate declared dormant with an empty rationale
    When the catalog coherence check runs
    Then the unwired gate is still flagged

  @slice-04 @driving_port @real-io @us-catalog-coherence @error @contract-shape:pure-function
  Scenario: The catalog schema permits an explicit dormant rationale on a gate
    Given a catalogued gate contract carrying a dormant rationale
    When the gate contract is validated against the shipped catalog schema
    Then the catalog schema accepts the dormant rationale
