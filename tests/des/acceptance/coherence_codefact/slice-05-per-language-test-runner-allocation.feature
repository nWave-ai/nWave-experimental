@feature-f-coherence-and-attestation @slice-05
Feature: The slice's tests run in the target's own runner, allocated ATs@slice / full-suite-once@feature-end
  As a maintainer on any target (TypeScript, Go, Rust, Python...)
  I want the slice's tests run in the TARGET's own runner -- never hardcoded pytest --
    allocated ATs@slice (fast) / full-suite-once@feature-end, with an unrecognized
    runner degrading LOUD as INDETERMINATE
  So that I trust the verdict was earned by running the right tests in the right runner,
    not the ~40-min full-suite-every-commit, and not a hardcoded pytest on a non-Python project

  # slice-05 of f-coherence-and-attestation (JOB-028 -- the LAST slice / OB-RUNNER).
  # The per-language TestRunnerPort resolved from the installed env by FILESYSTEM
  # lockfile inspection (never hardcoded pytest, C3) + the §V.B ATs@slice /
  # full-suite-once@feature-end re-allocation + the removal-of-obsolete (C10: the
  # hardcoded-pytest-over-whole-tree at every commit-slice is SUPERSEDED). It
  # CONSUMES the 5-verdict GateVerdict SSOT unchanged (C6, no sixth) for the
  # unrecognized-runner INDETERMINATE degrade. Builds on slices 01-04 (which stay
  # GREEN -- they are DELIVERed at HEAD).
  #
  # DRIVING SURFACES (Mandate-13 -- the REAL src/des seams):
  #   AT-16 / AT-17 -> Layer 3 composition: the REAL TestRunnerPort.resolve over a
  #     REAL tmp_path target carrying a real lockfile (filesystem inspection of the
  #     installed target, §V.A). The resolution-registry seam is driven at the
  #     COMPOSITION ROOT (a real resolve callable) -- the `des` dispatcher has no
  #     resolution-registry row at HEAD, so a subprocess dispatch would be a
  #     collection-stage failure, not a semantic RED (mirrors slice-04).
  #   AT-18 -> Layer 3 subprocess: the REAL `des run-contract-gate` (a real
  #     dispatcher _REGISTRY row) scoped to ONE slice -- the observable is WHICH
  #     tests the gate RAN (the slice's ATs only), never a line number.
  #   AT-19 -> Layer 3 composition: the REAL feature-end cycle full-suite leg
  #     (feature_end_cycle_service.run_feature_end_cycle) + the removal-absence of
  #     the obsolete whole-tree-every-commit-slice pytest (the discriminating
  #     phrase "unit or integration or acceptance" over the WHOLE tree, read from
  #     the SHIPPED slice-gate surface -- Mandate-13 prose-surface rule).
  #
  #   AT-16 -> resolve the TARGET runner from lockfile inspection (domain example 2
  #            `acme-web` -> vitest via package.json; go.mod -> go test;
  #            Cargo.toml -> cargo; pyproject -> pytest) -- the per-language port
  #            resolved from the installed env by FILESYSTEM inspection (never
  #            hardcoded). Scenario Outline over the LOCKED (lockfile -> runner) map.
  #   AT-17 -> an unrecognized runner / unsupported language -> INDETERMINATE
  #            (degrade-LOUD, N=0) -- NEVER a hardcoded-pytest fallback, never silent.
  #   AT-18 -> the slice-gate runs the SLICE's ATs ONLY (ATs@slice allocation) --
  #            the current whole-tree hardcoded-pytest at every commit-slice is
  #            SUPERSEDED (fast, proportional).
  #   AT-19 -> the full-suite-once leg added at feature-end + the removal-of-obsolete
  #            (the hardcoded-pytest-over-whole-tree assertion is GONE).
  #
  # CRITICAL DELIVER CARE (the slice-gate boundary -- flagged, the SEAM not a line
  # number): the slice-AT re-allocation (AT-18) MUST NOT break the EXISTING
  # `run-contract-gate --verify-gate-scope` DIGEST mechanism. --verify-gate-scope is
  # COLLECT-ONLY (the gate_scope_digest over collected node-ids vs a commit's
  # Gate-Scope: trailer); the hardcoded-pytest is the EXECUTION leg. AT-18/AT-19
  # drive the EXECUTION-allocation (WHICH tests RUN), DISTINCT from the gate-scope
  # DIGEST -- DELIVER re-scopes the RUN WITHOUT touching the collect-only digest path.
  #
  # FIXTURE DISTINCTNESS: each AT-16 row writes a CONTENT-DISTINCT lockfile (a real
  # pyproject.toml / package.json+vitest / go.mod / Cargo.toml body) into a fresh
  # tmp target, so a deterministic resolver cannot map two distinct inputs to one
  # runner -- a resolver that always returns pytest RED-fails the vitest/go/cargo
  # rows. AT-17's target carries an UNRECOGNIZED manifest (mix.exs / elixir -- the
  # domain-example-2 counter-case), content-distinct from every recognized row. The
  # removal-AT (AT-19) keys on the discriminating phrase
  # "unit or integration or acceptance" over the WHOLE tree -- a multi-word phrase
  # unique to the obsolete run, never a common substring.
  #
  # active-RED scaffold (atdd_pure -- NOT @skip): at HEAD all three seams are
  # absent/unbuilt -- src/des/ports/test_runner_port.py + src/des/adapters/driven/
  # runner/ do NOT exist (the RESOLUTION REGISTRY -- NB run_tests.py (ADR-042) is a
  # per-runner ADAPTER taking --runner, not the resolver); run_contract_gate has no
  # slice-AT RUN mode (--feature-id is collect-only + arch RUN; the only RUN is
  # whole-tree _mode_run_suite); feature_end_cycle_service runs env-e2e + coverage-map
  # but NO full-suite leg, and the obsolete whole-tree pytest is still present. Each
  # scenario RED-fails with a semantic AssertionError naming the missing seam, never
  # a collection / import / setup error. GREEN once DELIVER builds the runner port +
  # the slice-AT RUN re-scope + the feature-end full-suite leg (+ the C10 removal).
  #
  # DESIGN AMBIGUITY flagged to DELIVER (in the composition docstring -- the SEAM,
  # never a line number): A1 the resolution entry (composition-root callable
  # resolve / TestRunnerPort().resolve) + the Indeterminate VO path correction
  # (DESIGN mis-cites des.cli.committed_scope_port; CORRECT is
  # des.ports.driven_ports.committed_scope_port); A2 the resolved-runner observable;
  # A3 the INDETERMINATE degrade envelope; A4 the slice-AT RUN observable; A5 the
  # feature-end full-suite leg + removal-absence. DELIVER MUST wire these to whatever
  # real seam it ships. Also flagged: the ADR-042 run_tests.py / slice-05 resolution
  # registry relationship (adapter vs resolver -- DESIGN does not reconcile them).

  # AT-16 -- resolve the TARGET runner from lockfile inspection of the installed
  # target (§V.A). PBT/parametrize-shaped over the LOCKED (lockfile -> runner) map
  # -> Scenario Outline. Each row's lockfile is CONTENT-DISTINCT (a real manifest
  # body) so a deterministic resolver maps each distinct input to its distinct
  # runner: pytest is one row among equals, NEVER the universal executor (C3).
  @slice-05 @driving_port @real-io @us-runner-resolution @property @contract-shape:bounded-change
  Scenario Outline: A target carrying a <lockfile> resolves to the <runner> test runner
    Given a target project carrying a <lockfile> build manifest
    When the test-runner port resolves the runner for the target
    Then the test-runner port resolves the <runner> test runner

    Examples:
      | lockfile         | runner     |
      | pyproject.toml   | pytest     |
      | package.json     | vitest     |
      | go.mod           | go-test    |
      | Cargo.toml       | cargo-test |

  # AT-17 -- an unrecognized runner / unsupported language degrades LOUD to
  # INDETERMINATE (N=0), NEVER a hardcoded-pytest fallback (C3 / §17). The reason
  # NAMES the degrade (Invariant 2 -- no silent-pass) and the resolver does NOT
  # silently resolve pytest for the non-pytest target.
  @slice-05 @driving_port @real-io @us-runner-unrecognized @error @contract-shape:bounded-change
  Scenario: A target with an unrecognized build manifest degrades loud to indeterminate
    Given a target project carrying an unrecognized build manifest
    When the test-runner port resolves the runner for the target
    Then the test-runner port degrades loud to an indeterminate verdict
    And the test-runner port does not silently fall back to the pytest runner

  # AT-18 -- the slice-gate runs the SLICE's ATs ONLY (the §V.B ATs@slice
  # allocation, fast / proportional). The whole-tree hardcoded-pytest at every
  # commit-slice is SUPERSEDED: the gate must NOT run the whole tree, and must not
  # leak past the entering slice's scope. Drives the REAL `des run-contract-gate`
  # subprocess scoped to one slice.
  @slice-05 @driving_port @real-io @us-slice-allocation @contract-shape:unbounded-preservation
  Scenario: The slice gate runs only the entering slice's acceptance tests
    Given a target repository entering a single slice
    When the contract gate runs scoped to the entering slice
    Then the contract gate runs only the entering slice's acceptance tests
    And the contract gate does not run the whole tree

  # AT-19 -- the full-suite-once leg added at feature-end + the removal-of-obsolete
  # (C10). A distinct clean full-suite leg runs ONCE at feature-end (the cycle today
  # runs env-e2e + coverage-map but NO full-suite leg); the hardcoded-pytest-over-
  # whole-tree at every commit-slice is GONE (the discriminating-phrase absence,
  # read from the SHIPPED slice-gate surface). Two CONTENT-DISTINCT observables
  # (full-suite-leg presence vs obsolete-marker absence) so a one-sided
  # implementation RED-fails the half it skipped.
  @slice-05 @driving_port @real-io @us-feature-end-allocation @infrastructure @contract-shape:unbounded-preservation
  Scenario: The full suite runs once at feature-end and the obsolete whole-tree run is removed
    Given a feature reaching its feature-end cycle
    When the feature-end allocation is inspected
    Then a distinct full suite runs once at feature-end
    And the obsolete whole-tree run at every commit-slice is removed
