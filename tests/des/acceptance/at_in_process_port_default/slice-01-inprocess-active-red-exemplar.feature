@feature-at-in-process-port-default
Feature: The in-process active-RED pattern is proven by one converted exemplar

  Mara, an nWave maintainer, pays the wall-clock tax of a subprocess-heavy
  acceptance layer: every non-walking-skeleton acceptance test today forks an
  interpreter to make an absent SUT module active-RED, so the full contract
  suite she must run before every commit grows slower with every feature
  shipped. The methodology now tells her to drive the real CLI entry IN-PROCESS
  for everything that is not a walking-skeleton — but prose alone is not proof.

  This slice ships the proof: ONE converted exemplar acceptance test that drives
  the real run-contract-gate entry `main(argv)` directly in-process — no
  `subprocess.run([sys.executable, ...])` fork — and is active-RED at HEAD
  because the in-process-port exemplar route the maintainer asks for is not yet
  built. The exemplar is the executable reference the methodology points at:
  the in-process active-RED pattern is demonstrably runnable, not just
  documented.

  # DISCUSS US-02 (Metà-B, code): the in-process active-RED pattern is proven by
  # one converted exemplar that drives the real entry in-process and is active-RED
  # at HEAD with no interpreter fork. DESIGN §1 (P1-P4 invariants) + §2 (OutputPort
  # capture contract) + the F1 collection-semantics premise.
  #
  # Driving port (Architecture-of-Reference / Infra Policy "Driving"): the real CLI
  # entry `des.cli.run_contract_gate.main(argv)` driven IN-PROCESS with stdout/stderr
  # captured (NOT a `python -m` subprocess) — this is the whole point of the feature
  # (the bleeding-stop exemplar). Mandate-13 (driving-port-only) is satisfied
  # in-process; the WS annotation marks this as the keystone slice that proves the
  # real entry is wired in-process.
  #
  # Layer 3 (in-process composition acceptance) — example-only, no PBT (Mandate 9/11):
  # the exemplar pins a single closed observable (the in-process exemplar route is
  # recognised + emits its in-process-routed verdict). Sad path enumerated explicitly
  # (Mandate 11), never PBT-generated.
  #
  # active-RED mechanism (DESIGN P1-P4): the step module imports ONLY the stable
  # `main` entry at module top (P1) — never the not-yet-created OutputPort /
  # CapturingOutput (importing an absent name at module top => collection ImportError
  # => BROKEN, the escalation trap). The exemplar route is reached at RUNTIME inside
  # the in-process `main()` call (P2/P3): at HEAD `--inprocess-exemplar` is an
  # unrecognised flag, so argparse rejects it WITHIN the call (a runtime SystemExit,
  # not a collection error). The Then asserts the captured observable — the route is
  # recognised and emits an in-process-routed verdict — which it does NOT at HEAD, so
  # the assertion is a NAMED semantic AssertionError (P4). Collection succeeds
  # (only `main` imported); every scenario RED-fails for the right reason.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: The in-process exemplar drives the real gate entry without forking an interpreter
    Given the maintainer has a real repo the contract gate can run against
    When the maintainer drives the real contract-gate entry in-process for the in-process exemplar
    Then the gate recognises the in-process exemplar route
    And the gate emits an in-process-routed verdict on the captured output
    And the exemplar drove the entry without forking an interpreter
    And the maintainer's repo is left unchanged by the in-process exemplar run
