@feature-f-rust-test-runner-adapter @slice-03
Feature: The E2 contract gate routes a Rust target through cargo by convention, never pytest
  As an operator running the nWave spine against a Rust target
  I want the feature-scoped E2 contract gate to resolve the runner FIRST, derive the
    cargo binary() selector from the feature-id by convention, and run cargo feature-scoped
  So that a Rust slice clears the gate through the FULL spine (no DES-EXEMPT) -- a
    convention-following crate is zero-config, an OPTIONAL runner.json overrides the
    derived selector, and a Cargo target NEVER reaches the pytest collection worker

  # slice-03 of f-rust-test-runner-adapter (atdd_pure). Ships three net-new wiring
  # points (the SUT) -- ALL absent at HEAD:
  #   1. the _mode_feature_scoped runner-resolution short-circuit
  #      (run_contract_gate.py ~line 1229, BEFORE the pytest collection at ~1273):
  #      seed_runner_registry() -> resolve(repo) -> if cargo-test, DERIVE
  #      binary(/<snake_feature_id>/) by CONVENTION, read the OPTIONAL runner.json
  #      override, run the cargo facet, map exit -> verdict; else pytest UNCHANGED.
  #   2. the registry dispatch in RunnerAdapter.run (test_runner_port.py:89-93):
  #      GLOBAL_REGISTRY.lookup(name) instead of the hardcoded if name=="pytest".
  #   3. runner_json.py read_runner_json(feature_id, repo) -> dict | None (NEW):
  #      returns None on absence (the NORMAL zero-config case, NOT INDETERMINATE).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL operator-facing
  # contract gate `python -m des.cli.run_contract_gate --repo <target> --feature-id
  # <f> --entering-slice slice-NN` -- the EXACT subprocess
  # verify_slice_commit_completeness._run_contract_gate composes (a pure
  # pass-through). The OBSERVABLE is the JSON verdict the gate emits on stdout.
  # ZERO des.adapters.*/des.cli.*/des.domain.* import in the test process -- the SUT
  # is exercised ONLY across the subprocess boundary.
  #
  # FAKE-cargo determinism (no real Rust toolchain -- absent in CI): a planted REAL
  # chmod+x fake `cargo` on a controlled PATH LOGS its argv to a sentinel (so an AT
  # observes WHICH selector the gate drove -- the convention binary(/<snake>/) vs a
  # runner.json override token) then exits 0 (a green run -> the gate CLEARS). The
  # slice-03 wiring resolves the fake via the slice-01 resolve_tool PATH rung and
  # shells it -- the E2-routing is exercised end-to-end through the REAL gate.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam this slice declares is
  # the _mode_feature_scoped runner-resolution short-circuit -- resolve(repo)
  # consulted FIRST + the cargo facet driven BEFORE the pytest collection (today
  # _mode_feature_scoped has ZERO resolve/seed/cargo references -- the seam is
  # genuinely dormant). Every scenario names THAT exact seam as its driving port by
  # running the REAL gate over a Cargo target and asserting the observable verdict
  # (CLEARED, never the pytest-collection FeatureScopeMalformed/zero-collected) +
  # which selector the cargo facet drove. The runner.json reader seam is witnessed by
  # the override scenario observing the override selector drove the run.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # three wiring points are absent, so _mode_feature_scoped runs the pytest-bound
  # _collect_node_ids worker unconditionally; a Cargo target (no Python tests)
  # collects ZERO and the gate emits FeatureScopeMalformed/zero-collected (and the
  # fake cargo is NEVER invoked -> the sentinel stays empty). Each Then turns that
  # captured observable into a semantic AssertionError. GREEN once DELIVER ships the
  # three wiring points. No @skip, no collection/import error in the test process.

  @slice-03 @driving_port @real-io @walking_skeleton @us-e2-convention @contract-shape:bounded-change
  Scenario: A convention-following Rust target clears the gate through cargo, zero-config
    Given a convention-following Rust target shipping no runner.json
    When the operator runs the feature-scoped contract gate
    Then the gate clears the feature scope through cargo

  @slice-03 @driving_port @real-io @us-e2-convention @contract-shape:bounded-change
  Scenario: With no runner.json the gate derives and drives the convention binary selector
    Given a convention-following Rust target shipping no runner.json
    When the operator runs the feature-scoped contract gate
    Then the gate drove the convention-derived binary selector

  @slice-03 @driving_port @real-io @us-e2-override @contract-shape:bounded-change
  Scenario: An optional runner.json test_command overrides the convention selector
    Given a Rust target shipping a runner.json override
    When the operator runs the feature-scoped contract gate
    Then the gate drove the runner.json override command

  @slice-03 @driving_port @real-io @us-e2-short-circuit @error @contract-shape:bounded-change
  Scenario: A Rust target never reaches the pytest collection worker
    Given a convention-following Rust target shipping no runner.json
    When the operator runs the feature-scoped contract gate
    Then the gate does not emit a pytest collection failure
