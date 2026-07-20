@feature-pista1v2-phase225-bypasscause
Feature: BypassCause value object — eliminate Primitive Obsession on `_CAUSE_*` string constants

  As the maintainer of `scripts/hooks/spine_ledger_gate.py`
  I want the seven `_CAUSE_*` module-level string constants collapsed into a single `BypassCause` `StrEnum` value object
  And I want the `_emit_allowed(cause)` + `_dispatch_block_path` consumers to take a `BypassCause` parameter type
  So that future cause additions are caught at type-check time
  And typos on cause literals fail loudly instead of silently mis-labelling audit events
  Because the RPP L4 Abstraction Refinement clause names Primitive Obsession on cause vocabulary as a smell that accelerates change-cost on every future slice that touches the bypass branches.

  Background:
    Given the spine-ledger gate ships seven cause vocabulary constants
    And every constant value participates in either a stdout verdict or an audit event payload
    And the predecessor feature `atdd-spine-ledger-enforcement-gate-v2` shipped 15 acceptance tests pinning the existing cause vocabulary

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:byte-identical-parity
  Scenario Outline: gate stdout is byte-identical across cause branches before vs after the refactor
    Given a target machine wired to exercise the "<branch>" cause branch of the gate
    When the operator runs the spine-ledger gate against the staged invocation inputs
    Then the gate's stdout JSON carries cause "<expected_cause>"
    And the gate's stdout is a valid single-line JSON verdict
    And the gate's exit code matches the documented branch contract

    Examples:
      | branch        | expected_cause                  |
      | env-bypass    | operator-env-bypass             |
      | file-bypass   | operator-file-bypass            |
      | dormant       | spine-telemetry-absent          |
      | block-refused | block-ledger-evidence-missing   |
      | block-allowed | ledger-evidence-present         |

  @slice-01 @driving_port @contract-shape:type-safe-enum-extraction
  Scenario: BypassCause is a StrEnum carrying every cause literal as a typed member
    Given the spine-ledger gate module exposes a value object named "BypassCause"
    When the maintainer inspects the value object's type and members
    Then BypassCause is a subclass of StrEnum
    And BypassCause carries a member "OPERATOR_ENV_BYPASS" whose value is "operator-env-bypass"
    And BypassCause carries a member "OPERATOR_FILE_BYPASS" whose value is "operator-file-bypass"
    And BypassCause carries a member "SPINE_TELEMETRY_ABSENT" whose value is "spine-telemetry-absent"
    And BypassCause carries a member "NO_SLICE_TRAILER" whose value is "no-slice-trailer"
    And BypassCause carries a member "BLOCK_LEDGER_EVIDENCE_MISSING" whose value is "block-ledger-evidence-missing"
    And BypassCause carries a member "LEDGER_EVIDENCE_PRESENT" whose value is "ledger-evidence-present"
    And BypassCause carries a member "LEDGER_INTEGRITY_VIOLATION" whose value is "ledger-integrity-violation"
