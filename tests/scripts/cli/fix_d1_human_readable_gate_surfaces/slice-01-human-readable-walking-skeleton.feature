@feature-fix-d1-human-readable-gate-surfaces @slice-01
Feature: An operator sees a colored verdict line alongside the structured event on every gate

  The D1 spine exit criterion: every gate CLI emits BOTH a single-line JSON
  event (for machine consumers) AND a short colored human-readable summary
  line (for the operator) on stderr. The slice-01 walking skeleton wires the
  shared helper to ONE gate (the contract gate) as proof-of-pattern;
  subsequent slices extend the same helper to the remaining gates without
  revisiting it.

  When the operator runs the gate inside a real terminal, the summary line
  carries ANSI color escapes — green for ✅ PASS, red for ❌ FAIL, yellow
  for ⚠️ DEGRADED. When the gate runs in CI or under a pipe, the escapes are
  stripped so the line stays plain-readable; the JSON event byte-content is
  unchanged either way.

  # Driving port: ``des run-contract-gate --repo <tmp_path>``
  # (subprocess). Layer 3 (subprocess / FS acceptance) — example-only sad
  # paths (Mandate 11). The composition spawns a real subprocess against a
  # tmp_path repo carrying a minimal pytest suite the gate can collect and
  # run; stderr is captured and inspected for both surfaces.

  Background:
    Given a tmp_path repository carrying a minimal pytest suite the contract gate can run

  @slice-01 @walking-skeleton @driving_port @contract-shape:bounded-change
  Scenario: The operator sees a green PASS line alongside the structured event when the suite passes
    Given the minimal pytest suite is configured to pass
    When the operator runs the contract gate against the repository inside a real terminal
    Then the stderr carries a single-line JSON ContractGateResult event with passed true
    And the stderr carries a green colored PASS line summarising the contract gate outcome
    And the gate exits zero

  @slice-01 @driving_port @error @contract-shape:bounded-change
  Scenario: The operator sees a red FAIL line alongside the structured event when the suite fails
    Given the minimal pytest suite is configured to fail
    When the operator runs the contract gate against the repository inside a real terminal
    Then the stderr carries a single-line JSON ContractGateResult event with passed false
    And the stderr carries a red colored FAIL line summarising the contract gate outcome
    And the gate exits with a failure code

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: The operator running the gate under a pipe sees a plain readable line and the JSON event remains byte identical
    Given the minimal pytest suite is configured to pass
    When the operator runs the contract gate against the repository under a non terminal stderr
    Then the stderr carries a single-line JSON ContractGateResult event with passed true
    And the stderr carries a plain readable PASS line summarising the contract gate outcome with no ANSI escapes
    And the JSON event byte content equals the JSON event observed when stderr is a real terminal
