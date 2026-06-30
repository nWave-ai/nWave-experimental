@feature-f-attest-bundled-slice @slice-02
Feature: Bundled-slice attestation enforces reverify's reused preconditions before attesting
  As a maintainer recovering a bundle-delivered slice the closure scorecard counts partial
  I want `des attest-bundled-slice` to enforce reverify's proven preconditions P1/P3/P5/P6
    verbatim before it ever evaluates the bundle evidence
  So that attestation is fail-closed on a non-ancestor, already-verified, still-HEAD, or
    out-of-order slice -- the same disjoint-domain discipline reverify enforces, reused
    without a parallel path

  # slice-02 of f-attest-bundled-slice (classic spine; engine CLI, no LLM in path).
  # slice-02 DELIVER wires the REUSED preconditions from `des.cli._reverify_core`
  # into `attest_bundled_slice.main()`: P1 ancestor, P3 not-already-verified, P5
  # orphan/buried-state, P6 predecessor-verified. P4 + A2 land in slice-03; gate
  # composition + ledger mutation in slice-04 -- NOT exercised here. A present,
  # non-empty `--reason` (the slice-01 A0 human-GO gate) is supplied so each run
  # reaches the slice-02 preconditions.
  #
  # P3's corrupt-ledger -> LedgerIntegrityViolation branch is INHERITED VERBATIM
  # from `_reverify_core` and is already covered by reverify's own acceptance suite
  # (tests/des/acceptance/test_reverify_slice_commit.py) -- so it is NOT re-tested
  # at attest slice-02 (no duplication; same code, same coverage). slice-02 ATs =
  # P1 / P3-already-verified / P5 / P6 / all-clear (5, within the carpaccio ceiling).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL `des` dispatcher via
  # `python <src/des/cli/__main__.py> attest-bundled-slice ...` against a crafted
  # TEMP git repo (its own .git/ + .nwave/ ledger), mirroring reverify's own
  # precondition ATs (tests/des/acceptance/test_reverify_slice_commit.py). The
  # observables = process exit code + the terminal attest JSON event on stdout
  # (the freshness autoskip prefix line a developer-checkout temp repo emits is
  # parsed past).
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam this slice wires is
  # the precondition group composed from the shared `_reverify_core` helpers
  # (P1/P3/P5/P6) inside `attest_bundled_slice.main()`. Each scenario drives that
  # seam through the REAL dispatcher subprocess and asserts the observable refusal
  # (SliceAttestRefused, exit 1) or the proceed-past effect -- not an import-shape
  # check.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # slice-01 SCAFFOLD's `main` only parses args + emits
  # `BundledSliceAttestNotApplicable` (exit 0); it never imports or runs the
  # precondition group. So a fixture that MUST refuse currently gets the
  # NotApplicable marker exit 0, and each refusal Then turns that captured
  # observable into a semantic AssertionError (expected SliceAttestRefused exit 1,
  # got NotApplicable exit 0). GREEN once slice-02 DELIVER wires P1/P3/P5/P6 into
  # main(). No @skip, no import / collection error.

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a bundle commit that is not on the branch's history is refused
    Given a bundle commit that is not an ancestor of the current head
    When the maintainer attests the bundled slice
    Then the attestation is refused on a reused precondition

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a slice that already carries a verification is refused
    Given a slice that already carries a completion verification
    When the maintainer attests the bundled slice
    Then the attestation is refused on a reused precondition

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a bundle commit that is still the head is refused
    Given a bundle commit that is still the head with nothing burying it
    When the maintainer attests the bundled slice
    Then the attestation is refused on a reused precondition

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a later slice whose predecessor is unverified is refused
    Given a later slice whose predecessor carries no completion verification
    When the maintainer attests the bundled slice
    Then the attestation is refused on a reused precondition

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A bundle whose preconditions all hold proceeds past them
    Given a bundle slice whose preconditions all hold
    When the maintainer attests the bundled slice
    Then the attestation proceeds past the reused preconditions
