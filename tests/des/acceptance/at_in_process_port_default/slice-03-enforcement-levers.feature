@feature-at-in-process-port-default
Feature: A gate mechanically flags a non-walking-skeleton acceptance test that spawns an interpreter

  Mara, an nWave maintainer, can no longer rely on prose discipline alone to keep
  the acceptance layer fast. Slice-01 proved the in-process active-RED pattern is
  executable; slice-02 flipped the methodology default to in-process-port. But a
  documented default that no machine enforces silently regresses the first time a
  maintainer forgets it (the des_spawn lesson). This slice ships the enforcement:
  AXIS-B levers, added to the EXISTING gates (logic intact), that mechanically
  FLAG a non-walking-skeleton acceptance test which forks an interpreter, an entry
  reached by no real dispatch, a production path the test claims to drive but never
  executes, and a slice with no sad-path coverage. The levers are
  language-agnostic and generic to the target project: the spawn-detector is
  per-language, AST-based, git-free, and degrades LOUD (NOT_APPLICABLE on an
  unrecognized language, INDETERMINATE on an unparseable file) -- never a false
  flag, never a silent pass.

  # DISCUSS US-03 (Metà-B, code): a gate FLAGS a non-@walking_skeleton AT that
  # spawns an interpreter, so the subprocess-overuse cannot silently regress.
  # DESIGN §3 (the 6 levels -> 6 mechanical gates), the 3 L2 anti-theater/speed
  # levers, the subprocess-overuse gate, the L3/L4 enumeration procedure (F3),
  # DDD-1 (degrade-LOUD), DDD-2b/F4 (target-aware F821 NOT_APPLICABLE), DDD-9
  # (per-language, git-free, pytest-NEVER-hardcoded).
  #
  # Q3 RESOLUTION (pinned by these ATs): advisory->gated progression -- the gate
  # FLAGS with a STRUCTURED EVENT (machine-readable token on captured output),
  # never a bare exit code. lever-1 wiring / L3 integration-per-adapter / L4
  # contract-per-port live as NEW invariants in `verify_readiness_pre_dispatch.main`
  # (REFUSED verdict). lever-2 F821 lives in pre-commit (target-aware
  # NOT_APPLICABLE on non-Python). ZOMBIES-zero lives in
  # `carpaccio_slice_gate.main`.
  # The spawn-overuse detector is per-language, AST/CodeFactPort-based, git-free,
  # degrade-LOUD.
  #
  # Driving port (Architecture-of-Reference / Infra Policy "Driving", the inverted
  # default this very feature ships): the REAL gate entries
  # `verify_readiness_pre_dispatch.main(argv)` / `carpaccio_slice_gate.main(argv)`
  # driven IN-PROCESS with stdout/stderr captured
  # -- NOT a `python -m` subprocess. These slice-03 ATs are themselves the proof
  # that the enforcement levers can be driven in-process (eating the feature's own
  # dog food: subprocess-e2e is reserved for @walking_skeleton; everything else
  # drives in-process). Mandate-13 (driving-port-only) is satisfied in-process.
  #
  # Layer 3 (in-process composition acceptance) -- example-only, no PBT
  # (Mandate 9/11): each lever pins a single closed observable (the structured
  # flag the gate emits). Sad paths (non-Python target, unrecognized language)
  # enumerated explicitly (Mandate 11), never PBT-generated.
  #
  # active-RED mechanism (DESIGN P1-P4): the step modules import ONLY the stable
  # `main` entries of the three gates at module top (P1) -- never an absent lever
  # helper / a not-yet-created detector callable (importing an absent name at
  # module top => collection ImportError => BROKEN, the escalation trap). Each
  # lever's not-yet-built invariant is reached at RUNTIME inside the in-process
  # `main()` call (P2/P3): at HEAD the new invariant simply is not in the gate's
  # invariant chain, so the gate clears where it should refuse -- a runtime
  # absence surfaced as a verdict, not a collection error. The Then asserts the
  # captured structured flag (the lever flagged the violation), which it does NOT
  # at HEAD, so the assertion is a NAMED semantic AssertionError (P4). Collection
  # succeeds (only the three `main` entries imported); every scenario RED-fails
  # for the right reason.
  #
  # Principle (a): these levers EXTEND existing gates; DELIVER UPDATEs each gate's
  # existing test. A genuinely-NEW AT is authored here ONLY because each lever is
  # genuinely-new behaviour that did not previously exist (per the feature-delta
  # principle-(a) traceability table, F5).

  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: The wiring lever flags a produced entry reached by no real dispatch
    Given the maintainer has a real repo the enforcement gates can run against
    When the maintainer drives the wiring lever for an entry with no callers and no readers in-process
    Then the wiring lever flags the unwired entry
    And the wiring lever emits its structured flag event on the captured output
    And the wiring lever carries the code-fact confidence label with its flag
    And the wiring lever drove the gate without forking an interpreter

  @slice-03 @coupled @driving_port @real-io @adapter-integration @contract-shape:unbounded-preservation
  Scenario: The integration-per-adapter lever flags a driven adapter with no real-io test
    Given the maintainer has a real repo the enforcement gates can run against
    When the maintainer drives the integration-per-adapter lever in-process
    Then the integration-per-adapter lever flags the untested adapter
    And the integration-per-adapter lever emits its structured flag event on the captured output
    And the integration-per-adapter lever drove the gate without forking an interpreter

  @slice-03 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The contract-per-port lever flags a port with no contract test
    Given the maintainer has a real repo the enforcement gates can run against
    When the maintainer drives the contract-per-port lever in-process
    Then the contract-per-port lever flags the uncontracted port
    And the contract-per-port lever emits its structured flag event on the captured output
    And the contract-per-port lever drove the gate without forking an interpreter

  @slice-03 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The sad-path-floor lever flags a slice with zero error-path acceptance tests
    Given the maintainer has a real repo the enforcement gates can run against
    When the maintainer drives the sad-path-floor lever for a slice with no error-path test in-process
    Then the sad-path-floor lever flags the missing sad-path coverage
    And the sad-path-floor lever emits its structured flag event on the captured output
    And the sad-path-floor lever drove the gate without forking an interpreter

  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: The spawn-overuse detector flags a non-walking-skeleton test that forks an interpreter
    Given the maintainer has a real repo the enforcement gates can run against
    And the target project is written in "python"
    When the maintainer drives the spawn-overuse detector for a non-walking-skeleton test that spawns a process in-process
    Then the spawn-overuse detector flags the non-walking-skeleton spawn
    And the spawn-overuse detector drove the gate without forking an interpreter
    And the spawn-overuse detector did not invoke git

  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: The spawn-overuse detector exempts a walking-skeleton test that legitimately forks an interpreter
    Given the maintainer has a real repo the enforcement gates can run against
    And the target project is written in "python"
    When the maintainer drives the spawn-overuse detector for a walking-skeleton test that spawns a process in-process
    Then the spawn-overuse detector exempts the walking-skeleton spawn from flagging

  @slice-03 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The spawn-overuse detector reports NOT_APPLICABLE for an unrecognized target language
    Given the maintainer has a real repo the enforcement gates can run against
    And the target project is written in "haskell"
    When the maintainer drives the spawn-overuse detector for a non-walking-skeleton test that spawns a process in-process
    Then the spawn-overuse detector reports the lever as not applicable for the unrecognized language
    And the spawn-overuse detector does not raise a false flag on the unrecognized language

  @slice-03 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The undefined-name lever reports NOT_APPLICABLE on a non-python target
    Given the maintainer has a real repo the enforcement gates can run against
    And the target project is written in "rust"
    When the maintainer drives the undefined-name lever in-process
    Then the undefined-name lever reports the lever as not applicable for the non-python target
    And the undefined-name lever does not raise a false flag on the non-python target
