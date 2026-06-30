@feature-f-spine-runs-tests-not-git-hooks
Feature: The certainty the git-hook removal is gated on is a tested property
  As a maintainer about to drop the git pre-push net (a later, separate step)
  I want the precondition for that removal to be MECHANICAL -- the spine genuinely
    RUNS the entering slice's ATs and vetoes on RED with no git hook present, AND
    the full suite runs at feature-end emitting FullSuiteLegRan ONLY when green
  So that "be CERTAIN" is a property the build proves, not a claim a maintainer
    makes -- the net cannot be silently dropped before the certainty exists

  # slice-04 of f-spine-runs-tests-not-git-hooks (CERTAINTY made mechanical).
  # Self-applies Principle 13 (a probe that the spine genuinely RUNS the tests).
  # Closes KPI-2/KPI-4. Lands at the carpaccio ceiling (4 < 5). The arch-tier
  # coherence assertions + the integration veto-probe are authored as pytest
  # modules (tests/build/ + tests/des/integration/) NOT counted toward the
  # carpaccio Scenario ceiling; the Gherkin scenarios below frame the CT-7
  # feature-end-certainty contract through the real feature-end driving surface.
  #
  # DRIVING SURFACE (Mandate-13): CT-7 drives the REAL feature-end full-suite leg
  #   (`des.cli.run_contract_gate` default mode, invoked by the feature-end
  #   cycle) -- the observable is the FullSuiteLegRan ledger record emitted ONLY
  #   when the suite is green (a PRESENT-but-RED suite -> CycleRefusal, no
  #   record). The companion arch ATs (AT-A1 wired, CT-7-coherence) read the
  #   shipped __main__ subcommand registry + the required-set SSOT as DATA
  #   (@contract-shape:pure-function). The companion integration probe (AT-A5)
  #   drives the REAL `python -m des.cli.run_slice_ats` over a temp repo with git
  #   test-hooks ABSENT and a RED slice AT, asserting the spine genuinely vetoes.
  #
  # DORMANT-SEAM (D11 / Mandate-15): the net-new load-bearing seam this slice
  #   witnesses is the WIRING of the slice executor into the commit path (the
  #   `run-slice-ats` subcommand registry row -- AT-A1, the dead-code regression
  #   guard) + the CT-7 feature-end full-suite certainty. Each witnessing test
  #   drives THAT seam through its real surface (the shipped registry / the real
  #   feature-end cycle / the real executor subprocess) and asserts an observable
  #   effect (registry row present / FullSuiteLegRan emitted-only-when-green /
  #   exit-code veto), never a claim a symbol "exists".
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the `run-slice-ats` subcommand
  #   row is absent from `__main__.py` (the executor is unwired -- dead code), so
  #   AT-A1 RED-fails; the executor module is absent, so the AT-A5 veto-probe
  #   exits non-zero (NEITHER PASS nor the expected veto) and the CT-7 feature-end
  #   contract is observed against the (already-built) leg with the executor
  #   wiring not yet present. Every failure is a semantic AssertionError. GREEN
  #   once DELIVER wires the `run-slice-ats` subcommand (slice-01) -- CT-7's leg
  #   is reused from f-nonbypassable-attestation (already built).

  # ---- CT-7: the full suite runs at feature-end; FullSuiteLegRan only when green

  @slice-04 @driving_port @real-io @us-feature-end-certainty @contract-shape:bounded-change
  Scenario: A green feature-end full suite is attested by the leg record
    Given a feature-end cycle over a repository whose full suite is green
    When the feature-end cycle runs the full suite once
    Then the full-suite leg record attests the green run

  @slice-04 @driving_port @real-io @us-feature-end-certainty @error @contract-shape:bounded-change
  Scenario: A red feature-end full suite is refused with no attestation
    Given a feature-end cycle over a repository whose full suite is red
    When the feature-end cycle runs the full suite once
    Then the feature-end cycle is refused with no full-suite leg record
