@feature-skill-normative-content-gate @slice-03 @real-io @driving_port
Feature: Loud absence and the hook-spine veto on a skill edit
  # Slice-03 (DESIGN §9): INDETERMINATE on a missing / undecodable asset
  # (AC-06, AC-10) + hook-spine wiring with a blocking exit (AC-07).
  #
  # Two driving ports: the real `des` dispatcher (AC-06/AC-10) AND the real
  # `pre_write` hook handler driven as a subprocess with a real JSON payload
  # whose tool_input.file_path is under `nWave/skills/**` (AC-07).
  #
  # F-1 (DESIGN §8): the hook AT drives `pre_write` (PreToolUse Write/Edit),
  # NOT SubagentStop — a maintainer's skill edit never produces a SubagentStop
  # transcript.
  #
  # H-1 (ADR-SNCG-002 §Placement rule, NORMATIVE): the AC-07 hook AT injects a
  # fault into the gate-subprocess spawn and asserts the intercept's OWN
  # try/except emits {"decision":"block"} + exit 2 — proving the outer
  # fail-OPEN catch-all (pre_write_handler.py:177-186) is unreachable from the
  # intercept. Without the local wrap a spawn failure would silently allow the
  # skill write, contradicting no-silent-pass.
  #
  # @real-io -> example-based (Mandate 11); no PBT machinery.

  @contract-shape:unbounded-preservation @ac-06 @slice-03
  Scenario: A manifest-referenced asset that is absent yields INDETERMINATE, not PASS
    Given a manifest that references a skill asset path that does not exist on disk
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is INDETERMINATE with exit code 4
    And the verdict names the missing asset path and is not PASS

  @contract-shape:unbounded-preservation @ac-10 @slice-03
  Scenario: A non-UTF-8 referenced asset yields INDETERMINATE, not PASS
    Given a manifest that references a skill asset that exists but is not UTF-8 text
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is INDETERMINATE with exit code 4
    And the verdict names the asset path and the read failure and is not PASS

  @contract-shape:bounded-change @ac-07 @hook-spine @fault-injection @slice-03
  Scenario: The pre_write hook fails closed to a block when the gate intercept faults
    Given a maintainer edit to a skill file under the nWave skills tree
    And the skill-normative gate intercept is forced to raise during the edit
    When the pre_write hook evaluates the skill edit
    Then the hook decision is block with exit code 2
    And the block reason carries the skill-normative gate intercept error
