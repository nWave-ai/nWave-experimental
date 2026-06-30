@feature-go-test-runner-adapter
Feature: The Go run-facet shells the declared go test command and maps go exit-semantics
  As an operator running the nWave spine against a Go target
  I want the Go run-facet to resolve the target's go binary, shell the declared
    go test command at the target root, and map its exit code to PASS / FAIL /
    INDETERMINATE
  So that a Go spine runs through the port like Python and Rust -- a green run
    PASSes, a real failure FAILs (never swallowed), and an unresolvable go is a
    LOUD INDETERMINATE (never a silent pass, never a pytest fallback), with the
    feature's declared subcommand shelled as-is at cwd=target_root

  # slice-01 of go-test-runner-adapter (atdd_pure). Ships ONE net-new seam:
  #   the Go run-facet run_go_scope (go_runner.py) -- mirrors run_cargo_scope:
  #   resolves the target's go via the shared resolve_tool scale, shells the
  #   declared `go test` command at cwd=target_root, maps exit 0 -> PASS /
  #   non-zero -> FAIL / unresolvable -> INDETERMINATE (RunnerAdapterUnavailable).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_go_scope) imported + invoked in a CHILD interpreter. ZERO des.adapters.*
  # import in the test process -- the SUT is only ever imported in the child.
  #
  # FAKE-go determinism (AC-1/2/4 -- explicit fixture approach): the exit-semantics
  # ATs drive run_go_scope over a planted REAL chmod+x fake `go` on a controlled
  # PATH that emits a controlled exit code/output (GREEN exit 0 / RED exit non-zero)
  # AND records its argv + cwd. The run-facet resolves the fake via resolve_tool's
  # PATH rung and shells it exactly like a real go -- so the exit-semantics + the
  # declared-command-shelled contract are exercised end-to-end through the REAL
  # run-facet, DETERMINISTICALLY in CI, with NO real Go toolchain. AC-3 drives
  # run_go_scope over a go-absent fixture (PATH empty, known-locations empty).
  #
  # GO-vs-cargo: `go test` exits 0 even with NO tests (prints "no test files") --
  # there is NO cargo-style exit-4 NO_MATCH empty-scope. So GoExitScenario has only
  # GREEN (0) and RED (non-zero); there is NO "go ran no tests -> INDETERMINATE"
  # scenario (OUT-OF-SCOPE per the feature-delta). INDETERMINATE is reached ONLY via
  # an unresolvable go (AC-3).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # go_runner module is absent, so the child import raises ModuleNotFoundError
  # (rc != 0, no VERDICT:/ARGV: marker). Each Then turns a captured observable into
  # a semantic AssertionError. GREEN once DELIVER ships go_runner.run_go_scope.
  # No @skip, no import / collection error in the test process.

  @slice-01 @driving_port @real-io @us-go-exit-semantics @contract-shape:bounded-change
  Scenario: A green go run yields a PASS verdict
    Given a Go target whose go test exits zero with all tests passing
    When the go run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-go-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing go run yields a FAIL verdict, not indeterminate
    Given a Go target whose go test exits non-zero after executing tests
    When the go run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-go-exit-semantics @error @contract-shape:bounded-change
  Scenario: A Go target whose go is unresolvable yields a loud indeterminate naming the remediation
    Given a Go target whose go is absent from PATH and every known location
    When the go run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @real-io @us-declared-command-shelled @contract-shape:bounded-change
  Scenario: The Go run-facet shells the feature's declared subcommand as-is at the target root
    Given a Go target whose go records the argv and working directory it is shelled with
    When the go run-facet runs the declared command
    Then the go binary was invoked with the declared subcommand as-is
    And the go binary was invoked with the working directory set to the target root
