@feature-f-attest-bundled-slice @slice-04
Feature: Bundled-slice attestation runs the real gates and records the outcome honestly
  As a maintainer recovering a bundle-delivered slice the closure scorecard counts partial
  I want `des attest-bundled-slice` to run the SAME real gates the strong gate runs and, only
    when they pass, emit the SAME origin-blind verification record the scorecard counts -- plus a
    loud provenance trail of the bundle attestation and my stated reason
  So that a genuinely-complete bundled slice becomes countable as delivered, while a slice whose
    acceptance tests do not pass is blocked and never attested -- the anti-theater guarantee

  # slice-04 of f-attest-bundled-slice (classic spine; engine CLI, no LLM in path) -- the FINAL
  # slice. slice-04 DELIVER replaces the post-A2 `BundledSliceAttestPreconditionsCleared`
  # placeholder in attest_bundled_slice.main() with the gate composition + ledger emit, mirroring
  # reverify_slice_commit.main():
  #   SUCCESS (both gates pass) -> append a genuine `SliceCommitVerified` (the origin-blind,
  #     scorecard-counted record) THEN the adjacent `SliceAttestedFromBundle` provenance record
  #     carrying {slice_id, bundle_commit, reason, timestamp}; emit `SliceAttestedFromBundle`, exit 0.
  #   BLOCK (a gate fails) -> append one `SliceCommitBlocked`, emit `SliceAttestBlocked` naming the
  #     failing gate, exit 1, and -- the anti-theater guarantee -- NO `SliceCommitVerified`.
  # E1 (`check_slice_at_completeness`) + E2 (`run_contract_gate`) are the REUSED `_compose_gates`,
  # run for REAL against the commit -- never a flag, never a stub (invariant I-2). The fixtures
  # carry a REAL contract-marked test that genuinely goes green (success) or red (block) so E2's
  # whole-tree suite run reflects the slice's actual state -- the load-bearing realism.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL `des` dispatcher via
  # `python <src/des/cli/__main__.py> attest-bundled-slice ...` against a crafted TEMP git repo
  # (its own .git/ + .nwave/ ledger), REUSING the slices 02/03 harness (`_run_des` by-path
  # dispatch + git-fixture builders) verbatim. The ledger assertions READ the ledger `.jsonl`
  # FILE AS DATA (the same shape the closure scorecard reads), NEVER importing `AtCompletionLedger`
  # or any des.adapters.* (slice-02 RC-2 / F-005 boundary). The countability assertion applies the
  # scorecard's OWN predicate (`_slice_commits_verified`) against that file.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seams this slice wires are the gate
  # composition (`_compose_gates` E1+E2) and the ledger emit (`_record_outcome` -> the
  # SliceCommitVerified + SliceAttestedFromBundle / SliceCommitBlocked records) inside main(). Each
  # scenario drives that seam through the REAL dispatcher subprocess and asserts the observable
  # effect -- the emitted terminal event AND the ledger-file state delta -- not an import-shape check.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD main() is the
  # slice-03 shape -- it runs P1, A2, P3, P5, P6 then emits the
  # `BundledSliceAttestPreconditionsCleared` placeholder (exit 0), running NO gates and touching
  # NO ledger. So:
  #   * the RED-suite fixture: main() stops at the placeholder (exit 0) before E2 -> the block
  #     terminal `SliceAttestBlocked` is never emitted -> the block assertion fires (active-RED).
  #   * the GREEN fixture: main() stops at the placeholder (exit 0) without the ledger emit -> NO
  #     SliceCommitVerified / SliceAttestedFromBundle line is appended -> the success + provenance +
  #     countability assertions all fire (active-RED).
  # Each Then turns a captured subprocess observable OR a ledger-file read into a semantic
  # AssertionError. No @skip, no import / collection error. GREEN once slice-04 DELIVER wires the
  # gate composition + ledger emit into main().

  @slice-04 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A bundled slice whose acceptance tests do not pass is blocked and never attested
    Given a bundle commit whose contract suite is red on HEAD
    When the maintainer attests the bundled slice
    Then the attestation is blocked and the slice gains no verification record

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Attesting a green bundled slice records the slice's verification in the ledger
    Given a bundle commit carrying the slice's green acceptance test and production work
    When the maintainer attests the bundled slice
    Then the slice gains a verification record in the completion ledger

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Attesting a green bundled slice records the bundle provenance and the maintainer's reason
    Given a bundle commit carrying the slice's green acceptance test and production work
    When the maintainer attests the bundled slice
    Then the bundle attestation is recorded with the maintainer's reason and the bundle commit

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A successfully attested bundled slice is counted as delivered
    Given a bundle commit carrying the slice's green acceptance test and production work
    When the maintainer attests the bundled slice
    Then the closure scorecard counts the slice as delivered
