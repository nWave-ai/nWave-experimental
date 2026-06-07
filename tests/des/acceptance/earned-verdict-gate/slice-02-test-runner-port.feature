@feature-oss-earned-verdict-gate
Feature: The test-runner port emits an honest run result from a real test run
  As the earned-verdict gate that must compare a baseline run against a
    perturbed run
  I want a per-language test-runner adapter that invokes a REAL test run and
    reports its counts through the frozen JSON contract -- never by scraping the
    runner's human-readable stdout
  So that the verdict CORE is fed counts that are byte-faithful to what actually
    ran, and a missing or unrunnable runner is reported as a fail-safe abstain
    rather than a fabricated green

  # carpaccio slice-02 (DISCUSS [REF] Slice Plan). Builds on the slice-01 CORE:
  # the CORE rules a verdict over two `nwave.test_result.v1` envelopes; THIS
  # slice produces those envelopes from a real test run. Exactly THREE ATs
  # (carpaccio_slice_max=3): AT-1 a passing target -> a faithful green
  # `test_result.v1`; AT-2 a failing target -> a faithful `test_result.v1` whose
  # failed>0 (proving the counts come from the RUN, not from a hard-coded
  # template); AT-3 the owned residue R-1 -- an absent/unnameable runner ->
  # fail-safe ABSTAIN reason=runner-absent, NEVER a fabricated green run.
  #
  # CONTRACT SOURCE: authored against the FROZEN contracts
  #   nWave/schemas/nwave.test_result.v1.schema.json    (the RUN -- output here)
  #   nWave/schemas/nwave.earned_verdict.v1.schema.json (the ABSTAIN envelope
  #                                                       for runner-absent)
  # Counts contract (HARD INVARIANT -- never stdout parsing): the emitted
  # `nwave.test_result.v1` carries `passed` / `failed` / `collected` / `exit_code`
  # read from a structured JSON emission of the run (a runner plugin / json
  # report), NOT a regex over the runner's textual summary line. The existing
  # `run_contract_gate.py` scrapes stdout via `_COLLECTED_COUNT_RE` -- this slice
  # deliberately does NOT do that.
  #
  # Driving port (Mandate-13): the test-runner CLI invoked as a
  # `python -m des.cli.run_tests` subprocess (Layer 3 subprocess + JSON
  # assertion). It runs a real pytest target staged on a tmp path and emits one
  # `nwave.test_result.v1` JSON. ZERO direct domain import; example-only, no PBT
  # machinery (Mandate 9/11). The emitted envelope's port-exposed fields are the
  # universe (Mandate 8).
  #
  # R-1 ENVELOPE CHOICE (design note, see feature-delta R-1): `test_result.v1`
  # has no status/reason field -- ABSTAIN(runner-absent) is a `earned_verdict.v1`
  # concept. So "runner-absent" is NOT a malformed `test_result.v1`; it is the
  # gate-level ABSTAIN signal emitted in place of a run. AT-3 asserts the CLI
  # emits an ABSTAIN-shaped envelope (status=ABSTAIN, reason=runner-absent) and
  # crucially does NOT emit a passing `test_result.v1` -- a fabricated green is
  # the exact theater the whole gate exists to prevent. The concrete envelope
  # the CLI emits for runner-absent is flagged for DESIGN confirmation.
  #
  # adapter-integration note: TestRunnerPort is LANGUAGE_BOUND (catalog #1) and
  # the pytest adapter spawns a real subprocess (process-spawning predicate).
  # Whether the (TestRunnerPort, pytest-adapter) pair is CRITICAL -- and thus
  # owes a 10-property adapter-integration slice -- is flagged for DESIGN; this
  # slice authors the FEATURE-level acceptance ATs only.

  # AT-1 -- a target whose tests all pass yields a faithful green run.
  @driving_port @real-io @slice-02 @contract-shape:unbounded-preservation
  Scenario: A test target that all passes is reported as a faithful green run
    Given a test target whose tests all pass
    When the test-runner port runs the target
    Then the emitted run result conforms to the test-result contract
    And the emitted run result reports at least one passing test
    And the emitted run result reports no failing tests
    And the emitted run result reports a zero exit code

  # AT-2 -- a target with a failing test yields a run whose failed>0. This is the
  # proof the counts come from the RUN, not a hard-coded green template: a
  # genuinely-failing target MUST surface failed>0 through the JSON contract.
  @driving_port @real-io @slice-02 @error @contract-shape:unbounded-preservation
  Scenario: A test target with a failing test is reported with a faithful failure count
    Given a test target with at least one failing test
    When the test-runner port runs the target
    Then the emitted run result conforms to the test-result contract
    And the emitted run result reports at least one failing test
    And the emitted run result reports a nonzero exit code

  # AT-3 -- R-1 fail-safe (verdict class ABSTAIN, reason runner-absent): the
  # named runner cannot be invoked. The port MUST NOT fabricate a green run; it
  # emits a fail-safe abstain so the gate never trusts a run that never happened.
  @driving_port @real-io @slice-02 @error @contract-shape:bounded-change
  Scenario: An absent runner yields a fail-safe abstain instead of a fabricated green
    Given a test target whose runner cannot be invoked
    When the test-runner port runs the target
    Then the emitted result is a fail-safe abstain
    And the abstain reason is "runner-absent"
    And no passing run result is fabricated
