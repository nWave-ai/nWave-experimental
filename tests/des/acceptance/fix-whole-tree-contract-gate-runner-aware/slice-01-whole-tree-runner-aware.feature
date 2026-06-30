@feature-fix-whole-tree-contract-gate-runner-aware
Feature: The whole-tree contract gate resolves the target's runner, never hardcoded pytest

  As nWave's genericity / target-machine-agnosticism mandate
    (the contract gate must run on ANY single-lockfile target, degrade-LOUD
    never silent-pass) and the WIRING of ADR-FLOW-008 into the whole-tree path
  I want the whole-tree contract gate (`des run-contract-gate --repo .`, no
    --feature-id) to RESOLVE the target's runner from its lockfile and route the
    whole-tree run through it -- exactly as the feature-scoped path already does
  So that a non-Python target (Tsunami's Rust crate, #73) runs `cargo nextest
    run` instead of crashing on `InterpreterUnavailable` at the hardcoded pytest
    seam, and feature-end finalize is unblocked.

  # ---------------------------------------------------------------------------
  # slice-01 (walking-skeleton-first carpaccio). DESIGN D3/D4/D6 + ADR-FLOW-011.
  #
  # Driving port (Mandate-13, Layer-3 subprocess e2e): each scenario drives the
  # REAL installed gate via `python -m des.cli.run_contract_gate --repo <fixture>`
  # against a SYNTHETIC single-lockfile fixture repo (a Cargo.toml / pyproject.toml
  # tmp tree). The observable is the gate's PROCESS output + exit code -- a
  # shipped artifact (emitted single-line-JSON events on the captured channels),
  # never a value the test fabricates (Mandate-13 protocol-driver contract).
  #
  # The @walking_skeleton scenario is the ONE subprocess-e2e proof that the
  # installed artifact is wired end-to-end (terminal-wiring facet). The two
  # sibling slice-01 scenarios share its subprocess driving surface because the
  # whole-tree gate's behaviour IS its process verdict (gate-CLI nature).
  #
  # cargo-availability robustness (DESIGN + dispatch): `cargo-nextest` need NOT
  # be installed. The keystone asserts the gate RESOLVES + ROUTES to cargo and
  # never reaches the pytest seam -- NOT that a cargo build is green. When cargo
  # is absent the run leg yields a degrade-LOUD INDETERMINATE naming the cargo
  # runner (RunnerAdapterUnavailable), which STILL proves #73 fixed: the gate
  # resolved cargo and refused, it did NOT crash on pytest's InterpreterUnavailable.
  #
  # active-RED (atdd_pure -- NOT @skip). At HEAD the whole-tree modes hardcode
  # pytest (`_collect_scope` / `_run_contract_suite` -> `pytest_interpreter()`),
  # so the net-new `WholeTreeRunnerResolved` resolution event is ABSENT from the
  # gate's output. Every observable assertion below reads that absent event and
  # RED-fails for the right reason (missing functionality: the whole-tree runner
  # router does not exist yet). DELIVER ships `_maybe_route_through_runner_whole_tree`
  # to turn these GREEN. The composition imports ONLY stdlib + subprocess (no
  # not-yet-implemented module), so the suite COLLECTS cleanly (RED, not BROKEN).
  #
  # Mandate-9/11 (example-only at Layer-3): the target space is a finite closed
  # set {Rust single-lockfile, Python single-lockfile} -- enumerated examples,
  # no paired PBT (a property over a constant fixture would be vacuous).
  #
  # DELIVER observable contract (the events DELIVER MUST emit, declared by DISTILL):
  #   * `WholeTreeRunnerResolved` -- a single-line-JSON event emitted at
  #     resolution time (the mode preamble, BEFORE any run/digest leg, so it is
  #     present regardless of cargo availability), carrying:
  #       - `runner`         : the resolved runner identity ("cargo-test"|"pytest")
  #       - `routed`         : true when dispatched to a non-pytest runner;
  #                            false when pytest resolved -> router returned None
  #                            -> the EXISTING pytest path runs unchanged
  #       - `digest_degraded`: true on a non-pytest target where the enumerate
  #                            facet is absent (D6 slice-01) -> gate_scope_digest=None
  #   * the gate NEVER emits `InterpreterUnavailable` on a non-Python target.
  # ---------------------------------------------------------------------------

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A Rust target runs the whole-tree gate through its own resolved runner
    Given a single-lockfile Rust target the contract gate can run against
    When the maintainer runs the whole-tree contract gate against the target
    Then the gate resolves the target's runner to cargo and routes the whole-tree run through it
    And the gate never falls through to the pytest interpreter on the non-Python target

  @slice-01 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: The Rust target's digest leg degrades loud to no-digest, never a fabricated pytest digest
    Given a single-lockfile Rust target the contract gate can run against
    When the maintainer runs the whole-tree contract gate against the target
    Then the gate stamps no gate-scope digest and announces the degrade on the captured output
    And the gate never fabricates a pytest node-id digest over the non-Python tree

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A Python target runs the whole-tree gate byte-identically through the resolved pytest path
    Given a single-lockfile Python target the contract gate can run against
    When the maintainer runs the whole-tree contract gate against the target
    Then the gate resolves the target's runner to pytest and runs the existing pytest path unchanged
