@feature-fix-oss-environmental-e2e-gate
Feature: The environmental e2e gate degrades honestly and detects mis-scoped features
  As an nWave framework developer
  I want the gate to defer with a marker when no tier can be provisioned, to
    detect a mis-scoped feature, and to report every verdict through its frozen
    exit-code and stdout-token contract
  So that the gate never silently passes and never silently exempts

  # carpaccio slice-03 (DESIGN [REF] Slice Plan). FAIL-MODE-D fail-closed +
  # mis-scoped detector + the verdict-mode grid.
  #
  # CONTRACT SOURCE: NORMATIVE-FROZEN L1.4. The verdict universe and exit-code
  # grid are FINITE and ENUMERABLE -> parametrize-collapse, NOT PBT
  # (nw-property-based-testing falsifier-gate; feedback_ats_max_pbt_parametrize
  # _density). Frozen L1.4 grid:
  #   exit 0  PASS  -- verdict pass / authored+genuine / present+genuine /
  #                    merge-ready / no stale pairs
  #   exit 1  CHECK FAILED -- verdict fail / flaky / broken / stale-xfail-XPASS
  #                    / JSON absent / stale-digest / xfail-still-on / stale pair
  #   exit 2  PARSE/IO -- parse failure / marker not registered / build-install
  #                    failure / hermeticity-probe failure
  #   exit 3  MISSCOPED -- no `## Environmental E2E` block (work mis-scoped as
  #                    a feature)
  # stdout token verdict field closed enum: pass | fail | flaky | broken |
  #   misscoped | xpass-stale.
  #
  # FAIL-MODE-D: when no tier can be provisioned the gate exits 2 (parse/IO ->
  # hermeticity-probe failure / build-install failure) and writes a deferral
  # marker. Marker-write failure itself fails closed. A hand-removed marker
  # still leaves the done-gate blocked (no positive proof record).
  #
  # Layer 3+ (subprocess / FS acceptance): example-based per Mandate 11 --
  # each sad path enumerated, no PBT explosion on real-I/O tests.
  #
  # Driving port: `verify_environmental_e2e` CLI as a `python -m` subprocess.

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: The gate reports each verdict through its frozen exit-code contract
    Given a feature whose environmental e2e is in the "<situation>" condition
    When the developer runs the environmental e2e gate in run mode
    Then the gate verdict token reads "<verdict>"
    And the gate exit status is "<exit_meaning>"

    Examples:
      | situation                          | verdict   | exit_meaning  |
      | green against the installed artifact | pass      | success       |
      | red against the installed artifact   | fail      | check failed  |
      | unstable across reruns               | flaky     | check failed  |
      | uncollectable at the declared path   | broken    | check failed  |
      | declared on a feature with no environmental e2e block | misscoped | mis-scoped |

  # C7b interruption coverage (Sentinel slice-03 revision). The two fail-closed
  # conditions below share one invariant: a gate run that does NOT complete a
  # trusted positive-verification record leaves the feature not-done. The
  # second row is the interruption case -- a run killed mid build-install can
  # leave a TRUNCATED `EnvironmentalE2eVerified` record; the done-gate must
  # treat a truncated record as ABSENT (no trusted proof), not as proof.
  #
  # FROZEN-CONTRACT GAP (cross-tree raise): L1.4 (gate-family-implementation-
  # 2026-05-21.md, lines 207-317) is SILENT on results-JSON / ledger-record
  # write atomicity -- it specifies the results-JSON schema but mandates no
  # atomic write-then-rename. L1.7.3a line 698 lists "partial-write" only as a
  # human-signoff omission class to attest, not a CLI-contract clause. This AT
  # asserts the BEHAVIOUR (truncated record => done blocks); the mechanism
  # (atomic write-then-rename) should be added to frozen L1.4 by a coordinated
  # DEV<->SF amendment. See the DISTILL report's L1.4 atomicity finding.
  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario Outline: A gate run that never completes its proof leaves the feature not-done
    Given a feature whose environmental e2e gate run "<fail_condition>"
    When the developer runs the environmental e2e gate in run mode
    Then the feature-end ledger holds no trusted positive verification record
    And evaluating the feature-end done-gate blocks the feature from being declared done

    Examples:
      | fail_condition                                          |
      | cannot provision any clean prefix to install into       |
      | is interrupted mid build-install before the verdict     |

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A feature declared without an environmental e2e block is flagged as mis-scoped
    Given a feature whose delta carries no environmental e2e declaration block
    When the developer runs the environmental e2e gate in verify-authored mode
    Then the gate reports the feature as mis-scoped
    And the gate exit status indicates a mis-scoped feature
    And the gate diagnostic names the absent environmental e2e declaration as the re-scope trigger
