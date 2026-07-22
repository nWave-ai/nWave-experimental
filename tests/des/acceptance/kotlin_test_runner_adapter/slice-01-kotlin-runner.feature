@feature-kotlin-test-runner-adapter
Feature: The Kotlin run-facet shells the declared gradlew test command and maps gradle exit-semantics
  As an operator running the nWave spine against a Kotlin/Gradle target
  I want the Kotlin run-facet to resolve the target's gradlew binary, shell the
    declared gradlew test command, and map its exit code to PASS / FAIL /
    INDETERMINATE, and the AT-discovery facet to discover the @Test-annotated
    identities a Kotlin regression file carries
  So that a Kotlin spine runs through the port like Go and Rust -- a green run
    PASSes, a real failure FAILs (never swallowed), an unresolvable gradlew is a
    LOUD INDETERMINATE (never a silent pass), and a build.gradle.kts target routes
    to the gradle-test runner instead of degrading to an unrecognized target

  # slice-01 of kotlin-test-runner-adapter (atdd_pure). Ships TWO net-new seams,
  # mirroring go-test-runner-adapter (ADR-RTR-001 C1) + the pytest/cargo
  # AT-discovery facet pair (fix-rust-regression-at-kind-wiring):
  #   1. the Kotlin run-facet run_kotlin_scope (kotlin_runner.py) -- resolves the
  #      target's gradlew via the shared resolve_tool scale, shells the declared
  #      `gradlew test` command, maps exit 0 -> PASS / non-zero -> FAIL /
  #      unresolvable -> INDETERMINATE (RunnerAdapterUnavailable).
  #   2. the Kotlin AT-discovery facet discover_kotlin_ats (kotlin_runner.py) --
  #      discovers @Test-annotated `fun` identities a Kotlin regression file
  #      carries, mirroring discover_pytest_ats / discover_cargo_ats.
  #   PLUS the routing gap this feature closes: test_runner_port.py's resolve()
  #   registry gains a build.gradle.kts / build.gradle -> gradle-test row (AC-6)
  #   so a Kotlin target is recognized at all, not just runnable once recognized.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_kotlin_scope / discover_kotlin_ats / resolve) imported + invoked in a
  # CHILD interpreter. ZERO des.adapters.* import in the test process -- the SUT
  # is only ever imported in the child.
  #
  # FAKE-gradlew determinism (AC-1/2/3 -- explicit fixture approach, mirrors go):
  # the exit-semantics ATs drive run_kotlin_scope over a planted REAL chmod+x
  # fake `gradlew` on a controlled PATH that emits a controlled exit code
  # (GREEN exit 0 / RED exit non-zero). The run-facet resolves the fake via
  # resolve_tool's PATH rung and shells it exactly like a real gradlew -- so the
  # exit-semantics are exercised end-to-end through the REAL run-facet,
  # DETERMINISTICALLY in CI, with NO real Gradle/JDK toolchain.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # the kotlin_runner module is absent, so the child import raises
  # ModuleNotFoundError (rc != 0, no marker). Each Then turns a captured
  # observable into a semantic AssertionError. GREEN once DELIVER ships
  # kotlin_runner.run_kotlin_scope + discover_kotlin_ats. AC-6 (the resolve()
  # registry row) is authored by THIS feature directly (a small, surgical
  # routing-table addition, not a run-facet) and is therefore LIVE-GREEN at HEAD.

  @slice-01 @driving_port @real-io @us-kotlin-exit-semantics @contract-shape:bounded-change
  Scenario: A green gradlew run yields a PASS verdict
    Given a Kotlin target whose gradlew test exits zero with all tests passing
    When the Kotlin run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-kotlin-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing gradlew run yields a FAIL verdict, not indeterminate
    Given a Kotlin target whose gradlew test exits non-zero after executing tests
    When the Kotlin run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-kotlin-exit-semantics @error @contract-shape:bounded-change
  Scenario: A Kotlin target whose gradlew is unresolvable yields a loud indeterminate naming the remediation
    Given a Kotlin target whose gradlew is absent from PATH and every known location
    When the Kotlin run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @us-kotlin-at-discovery @contract-shape:bounded-change
  Scenario: The Kotlin AT-discovery facet discovers the @Test identities a regression file carries
    Given a Kotlin regression file declaring two @Test functions
    When the Kotlin AT-discovery facet discovers the file's acceptance tests
    Then the discovered AT identities match the declared @Test functions
    And the discovery result carries a content seal over the regression file's bytes

  @slice-01 @driving_port @us-kotlin-at-discovery @error @contract-shape:bounded-change
  Scenario: The Kotlin AT-discovery facet degrades loud when the regression file declares zero @Test functions
    Given a Kotlin regression file declaring zero @Test functions
    When the Kotlin AT-discovery facet discovers the file's acceptance tests
    Then the discovery degrades to a loud indeterminate naming the malformed file

  @slice-01 @driving_port @us-kotlin-runner-routing @contract-shape:bounded-change
  Scenario: A build.gradle.kts target routes to the gradle-test runner
    Given a target carrying only a build.gradle.kts manifest
    When the target's test runner is resolved
    Then the resolved runner is gradle-test
