@feature-fix-whole-tree-contract-gate-runner-aware
Feature: The whole-tree contract gate's digest is derived from the target's own runner

  As nWave's genericity / target-machine-agnosticism mandate
    (the `Gate-Scope:` trailer must be a REAL cross-runner digest on ANY
    single-lockfile target, never a pytest-shaped fabrication and never the
    slice-01 no-digest placeholder)
  I want the whole-tree digest modes (`des run-contract-gate --committed-scope-digest`
    / `--verify-gate-scope` / `--collect-only --print-digest`, no --feature-id) to
    ENUMERATE the target's test scope through the resolved runner's own enumerate
    facet -- `cargo nextest list` on a Cargo target, `_collect_scope` on a pytest
    target -- and digest THAT set
  So that a non-Python target's `Gate-Scope:` trailer is a meaningful digest of its
    own tests (or a degrade-LOUD INDETERMINATE when the runner is absent), and the
    slice-01 D6 `digest_degraded=True` placeholder is retired for the digest modes.

  # ---------------------------------------------------------------------------
  # slice-02 (carpaccio: RUN routing shipped in slice-01; this slice ships the
  # ENUMERATE facet). DESIGN D5 + ADR-FLOW-011 D5/D6.
  #
  # Driving port (Mandate-13, Layer-3 subprocess e2e): each scenario drives the
  # REAL installed gate via `python -m des.cli.run_contract_gate <digest-mode>
  # --repo <fixture>` against a SYNTHETIC single-lockfile fixture repo (the SAME
  # Cargo.toml / pyproject.toml tmp-tree fixtures + GateOutcome combined-channel
  # event parse the slice-01 keystone established -- REUSE, not a new driving
  # surface). The observable is the gate's emitted single-line-JSON events + exit
  # code (a shipped artifact, never a value the test fabricates).
  #
  # NOT a @walking_skeleton (slice-01 owned the terminal-wiring keystone). The
  # digest modes' behaviour IS their process output (a bare-stdout digest line +
  # stderr JSON events + a spawned collection child); the proven combined-channel
  # GateOutcome subprocess parse is the robust driving port -- in-process capture
  # of the mixed channels buys no isolation (the gate spawns child workers
  # regardless) and is fragile, so all three reuse the established subprocess port.
  #
  # cargo-availability robustness (DESIGN WS strategy + dispatch): `cargo` /
  # `cargo-nextest` are ABSENT in CI. The two Rust scenarios assert the digest
  # mode RESOLVES cargo and routes the digest leg through cargo's ENUMERATE facet
  # (the `WholeTreeRunnerResolved` preamble event names cargo and NO LONGER
  # degrades the digest), NOT that a real cargo digest is produced. When cargo is
  # absent the enumerate facet degrades-LOUD INDETERMINATE -- which STILL proves
  # the digest leg is runner-aware (it routed to the cargo list facet, never
  # fabricated a pytest digest, never crashed on InterpreterUnavailable).
  #
  # active-RED (atdd_pure -- NOT @skip). At HEAD the whole-tree router is
  # mode-AGNOSTIC: for a Cargo target EVERY mode (run AND the 3 digest modes)
  # routes through the slice-01 RUN leg and emits the D6 placeholder
  # `WholeTreeRunnerResolved(cargo, routed=True, digest_degraded=True)` (the
  # enumerate facet does not exist yet). Each Rust scenario below reads that
  # preamble event and asserts `digest_degraded` is NOT True -- which RED-fails
  # for the right reason (missing functionality: the runner-aware digest /
  # enumerate facet). DELIVER ships `RunnerAdapter.list_scope` + `list_cargo_scope`
  # + `list_pytest_scope` + the digest-mode wiring to turn these GREEN. The
  # composition imports ONLY stdlib + subprocess, so the suite COLLECTS cleanly
  # (RED, not BROKEN).
  #
  # Mandate-9/11 (example-only at Layer-3): the target space is a finite closed
  # set {Rust single-lockfile, Python single-lockfile} x {digest modes} --
  # enumerated examples, no paired PBT (a property over a constant fixture is
  # vacuous).
  #
  # DELIVER observable contract (declared by DISTILL -- the events DELIVER MUST
  # emit; see the [REF] DELIVER observable contract section in feature-delta.md):
  #   * In a DIGEST mode on a non-pytest target the `WholeTreeRunnerResolved`
  #     preamble event carries `digest_degraded=False` (the enumerate facet IS
  #     wired -- the slice-01 D6 placeholder True is retired for the digest modes).
  #   * cargo present  -> a digest event with `runner="cargo-test"` provenance +
  #     a real `gate_scope_digest`; `--verify-gate-scope` re-derives it.
  #   * cargo absent   -> a degrade-LOUD INDETERMINATE naming the cargo ENUMERATE
  #     facet (`cargo nextest list`) -- NEVER a fabricated pytest digest, NEVER
  #     `InterpreterUnavailable`.
  #   * A pytest target's digest mode stays runner-aware-but-unchanged: router ->
  #     None, a real pytest node-id digest, `digest_degraded` not True.
  # ---------------------------------------------------------------------------

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A Rust target's committed-scope digest is derived through its own runner's enumerate facet
    Given a single-lockfile Rust target the contract gate can run against
    When the maintainer prints the committed-scope digest for the target
    Then the gate derives the digest through the target's cargo enumerate facet, not the no-digest placeholder
    And the gate never fabricates a pytest node-id digest over the non-Python tree

  @slice-02 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A Rust target's gate-scope verification re-derives through the runner-aware enumerate facet
    Given a single-lockfile Rust target the contract gate can run against
    When the maintainer verifies the target's gate-scope trailer
    Then the gate re-derives the digest through the target's cargo enumerate facet, not the no-digest placeholder
    And the gate never verifies against a fabricated pytest node-id digest over the non-Python tree

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A Python target's working-tree digest stays a real pytest-derived digest (no regression)
    Given a single-lockfile Python target the contract gate can run against
    When the maintainer prints the working-tree digest for the target
    Then the gate derives a real pytest node-id digest through the resolved pytest enumerate facet
    And the gate never degrades the Python digest to the no-digest placeholder
