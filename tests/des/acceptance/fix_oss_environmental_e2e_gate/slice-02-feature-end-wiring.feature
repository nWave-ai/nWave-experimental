@feature-fix-oss-environmental-e2e-gate
Feature: The environmental e2e gate is wired into the feature-end done-gate
  As an nWave framework developer
  I want the feature-end cycle to invoke the environmental e2e gate and the
    done-gate to require positive proof it ran and passed
  So that a feature cannot be declared done without its environmental e2e
    being verified against the installed artifact

  # carpaccio slice-02 (DESIGN [REF] Slice Plan). CREATE-wiring, not EXTEND:
  # the feature-end orchestration service is shipped-but-unwired (RES-2/RES-3,
  # grep-verified zero callers). This slice creates the invocation from the
  # DELIVER feature-end orchestration step to the gate, adds the gate's
  # heartbeat record to the U4 enforcer required-record frozenset, and extends
  # the done-gate with the presence-of-proof check.
  #
  # CONTRACT SOURCE: NORMATIVE-FROZEN L1.4. The done-gate trusts
  # presence-of-proof (principle 13): it passes only when (a) no unverified
  # marker exists AND (b) a positive verification record exists. A
  # hand-deleted marker satisfies (a) but not (b) -- done still blocks.
  #
  # The U4 enforcer (subagent_stop_handler._missing_feature_end_cycle_records)
  # is the real mechanical enforcement point (DESIGN RES-2): a skipped
  # sub-step produces a missing-record block in the separate U4 subprocess,
  # independent of whether the gate itself ran. This is Claude-Code-harness
  # coupled (honest asymmetry, DESIGN [REF] Harness Parity).
  #
  # Layer 2 (in-memory acceptance): the done-gate logic over the
  # record-presence universe is layer-1/2 -- PBT example-pinned permitted
  # (Mandate 9). The wiring proof itself is example-based at layer 3+.
  #
  # Driving port: the feature-end done-gate (des-verify-integrity extension)
  # invoked in-process; the U4 SubagentStop hook branch via hook JSON payload.

  # Mandate 9 + 11: at layer 2 (in-memory acceptance) the done-gate decision
  # table is finite (2^2 cells of {HEARTBEAT, VERIFIED}). The universe-sweep is
  # example-pinned via parametrize-collapse, one row per cell -- never
  # PBT-generated. The `<verdict>` column carries the typed DoneGateVerdict
  # token so each Then asserts the gate's diagnostic shape, not just go/no-go.
  @slice-02 @driving_port @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The done-gate verdict for ledger holding <records> is <verdict>
    Given a feature whose feature-end ledger holds <records>
    When the feature-end done-gate evaluates whether the feature may be declared done
    Then the done-gate verdict is <verdict>

    Examples:
      | records            | verdict                       |
      | heartbeat+verified | permitted                     |
      | heartbeat only     | blocked-missing-verification  |
      | verified only      | blocked-missing-heartbeat     |
      | none               | blocked-missing-both          |

  @slice-02 @driving_port @wiring_e2e @real-io @contract-shape:bounded-change
  Scenario: A feature with a passing environmental e2e proceeds past the done-gate
    Given a feature whose feature-end cycle ran the environmental e2e gate to a passing verdict
    When the feature-end done-gate evaluates whether the feature may be declared done
    Then the feature is permitted to be declared done
    And the feature-end ledger carries the environmental e2e heartbeat recorded before the verdict

  @slice-02 @driving_port @wiring_e2e @real-io @error @contract-shape:bounded-change
  Scenario: A skipped environmental e2e sub-step is caught as a missing feature-end record
    Given a feature whose feature-end cycle never ran the environmental e2e gate
    When the feature-end completion enforcer checks the required feature-end records
    Then the enforcer reports the environmental e2e heartbeat as a missing required record
    And the feature is not permitted to be declared done
