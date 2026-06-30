@feature-fix-whole-tree-contract-gate-runner-aware
Feature: A polyglot root declares its whole-tree runner via .nwave/runner.json

  As nWave's genericity / target-machine-agnosticism mandate AND the
    consumer-driven field-proof (sister-Tsunami's real Rust+JS repo, 2026-06-27)
  I want a polyglot repository root -- one with BOTH a Cargo.toml AND a
    package.json at the root, which the whole-tree gate cannot disambiguate on its
    own -- to be able to DECLARE its whole-tree runner in a committed, reviewable
    repo-level `.nwave/runner.json` `{"runner": "<key>"}`, consulted by `resolve`
    only when there is no feature context (whole-tree), BEFORE the lockfile-scan
  So that `des run-contract-gate --repo .` on Tsunami's polyglot crate RESOLVES the
    declared runner and is unblocked at feature-end -- while an UNKNOWN or MALFORMED
    declaration degrades LOUD INDETERMINATE (never guessed, never crashed), and a
    root with NO declaration keeps today's behaviour byte-for-byte (polyglot ->
    loud-INDETERMINATE, single-lockfile -> zero-config resolved).

  # ---------------------------------------------------------------------------
  # slice-03 (the LAST slice). DESIGN D8 + ADR-FLOW-011 D8 (amendment 2026-06-27).
  #
  # Driving port (Mandate-13, Layer-3 subprocess e2e): each scenario drives the
  # REAL installed gate via `python -m des.cli.run_contract_gate --repo <fixture>`
  # against a SYNTHETIC fixture root -- REUSING the slice-01/02 `WholeTreeGateComposition`
  # driving port (the combined-channel `GateOutcome` event parse), EXTENDED only
  # with polyglot-root staging + a `.nwave/runner.json` writer. Zero new driving
  # surface. The observable is the gate's emitted single-line-JSON events + exit
  # code (a shipped artifact, never a value the test fabricates).
  #
  # minimize-e2e: the keystone (scenario 1, the Tsunami unblock) is the justified
  # subprocess; the degrade-LOUD sad-paths (2-4) and the zero-config witness (5)
  # REUSE the SAME proven subprocess port -- run_contract_gate is not OutputPort-
  # wired (slice-01/02 confirm subprocess is the only working driving surface), so
  # an in-process route would be a fragile NEW harness buying no isolation (the
  # gate spawns child workers regardless). Reuse-of-the-proven-port IS the
  # minimize-e2e call here (the same decision slice-02 documented).
  #
  # NOT a @walking_skeleton (slice-01 owns the one terminal-wiring keystone).
  #
  # cargo-availability robustness: `cargo` / `cargo-nextest` are ABSENT in CI. The
  # keystone reads the `WholeTreeRunnerResolved` PREAMBLE event (emitted at the
  # resolution layer, BEFORE any run/list leg) and asserts the override RESOLVED
  # cargo + ESCAPED the polyglot INDETERMINATE -- NOT that a cargo build is green.
  # cargo-absent -> the RUN leg degrades LOUD INDETERMINATE naming the cargo runner,
  # which STILL proves the declaration was honoured (the resolution layer no longer
  # refuses the polyglot root).
  #
  # active-RED (atdd_pure -- NOT @skip). At HEAD `_repo_runner_override` +
  # `read_repo_runner_json` are ABSENT and `resolve(repo, None)` never consults
  # `.nwave/runner.json`: a polyglot root (declared or not) hits
  # `_disambiguate(matched, None)`, skips the `if feature is not None` block, and
  # degrades to `Indeterminate` naming the competing lockfiles + the FEATURE-scoped
  # `docs/feature/<id>/runner.json`. So:
  #   * scenario 1 (declared cargo)   -> RED: no `WholeTreeRunnerResolved` preamble,
  #                                       the LOUD "polyglot target" refusal fires.
  #   * scenario 2 (unknown key)      -> RED: the reason names the lockfiles, NOT
  #                                       `bogus-runner` / `.nwave/runner.json`.
  #   * scenario 3 (malformed)        -> RED: the reason names the lockfiles, NOT
  #                                       the malformed `.nwave/runner.json`.
  #   * scenario 4 (no override)      -> GREEN-by-construction: D2 polyglot
  #                                       INDETERMINATE naming both lockfiles is the
  #                                       SAME at HEAD and wired (no-regression).
  #   * scenario 5 (single, no override) -> GREEN-by-construction: the single-lockfile
  #                                       fast-path resolves pytest, unchanged by the
  #                                       D8 `feature is None` pre-check (no-regression).
  # DELIVER ships `read_repo_runner_json` + `_repo_runner_override` + the
  # `feature is None` pre-check in `resolve` to turn scenarios 1-3 GREEN. The
  # composition imports ONLY stdlib + subprocess, so the suite COLLECTS cleanly
  # (RED, not BROKEN).
  #
  # Mandate-9/11 (example-only at Layer-3): the override state space is a finite
  # closed set {declared-valid, unknown-key, malformed, absent} x {polyglot,
  # single} -- enumerated examples, no paired PBT (a property over a constant
  # fixture is vacuous).
  #
  # DELIVER observable contract (declared by DISTILL -- see the [REF] section in
  # feature-delta.md):
  #   * declared VALID key   -> `WholeTreeRunnerResolved(runner=<key>, routed=...)`
  #     at the preamble; the resolution layer no longer emits the polyglot
  #     INDETERMINATE marker (the override BYPASSED the scan).
  #   * declared UNKNOWN key -> `health.gate.whole-tree-runner.indeterminate` whose
  #     `reason` names the unregistered runner key AND `.nwave/runner.json`; NEVER
  #     a `WholeTreeRunnerResolved` (never guessed).
  #   * MALFORMED declaration-> `health.gate.whole-tree-runner.indeterminate` whose
  #     `reason` names the malformed `.nwave/runner.json`; exit 3, NO Python
  #     traceback (JSONDecodeError caught, never a crash).
  #   * NO declaration       -> behaviour byte-identical to today: polyglot ->
  #     INDETERMINATE naming both lockfiles; single-lockfile -> pytest resolved.
  # ---------------------------------------------------------------------------

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A polyglot root declares cargo and the gate honours the declaration
    Given a polyglot repository root the contract gate cannot disambiguate on its own
    And the maintainer declares the whole-tree runner as cargo in the repository
    When the maintainer runs the whole-tree contract gate against the root
    Then the gate honours the declared cargo runner and routes the whole-tree run through it
    And the gate never refuses the declared polyglot root as an ambiguous lockfile set

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A declaration naming an unregistered runner is refused, never guessed
    Given a polyglot repository root the contract gate cannot disambiguate on its own
    And the maintainer declares an unregistered whole-tree runner in the repository
    When the maintainer runs the whole-tree contract gate against the root
    Then the gate refuses indeterminate and names the unregistered runner declaration
    And the gate never resolves a runner for the unrecognised declaration

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A malformed runner declaration degrades loud, never crashes the gate
    Given a polyglot repository root the contract gate cannot disambiguate on its own
    And the maintainer leaves a malformed whole-tree runner declaration in the repository
    When the maintainer runs the whole-tree contract gate against the root
    Then the gate refuses indeterminate and names the malformed runner declaration
    And the gate never crashes on the malformed declaration

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A polyglot root with no declaration stays loud-indeterminate, never a silent pick
    Given a polyglot repository root the contract gate cannot disambiguate on its own
    When the maintainer runs the whole-tree contract gate against the root
    Then the gate refuses indeterminate and names the competing lockfiles
    And the gate never silently picks one of the competing runners

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A single-lockfile root with no declaration still resolves zero-config
    Given a single-lockfile Python target the contract gate can run against
    When the maintainer runs the whole-tree contract gate against the target
    Then the gate resolves the target's runner to pytest with no declaration needed
