@feature-java-test-runner-adapter
Feature: The Java run-facet shells the declared mvn test command, maps Maven exit-semantics, and discovers @Test-attributed ATs
  As an operator running the nWave spine against a Java target
  I want the Java run-facet to resolve the target's mvn binary, shell the
    declared mvn test command at the target root, map its exit code to
    PASS / FAIL / INDETERMINATE, and discover the @Test-attributed AT
    identities a Java regression file carries
  So that a Java (Maven) spine runs through the port like Python/Rust/Go -- a
    green run PASSes, a real failure FAILs (never swallowed), an unresolvable
    mvn is a LOUD INDETERMINATE (never a silent pass), and the AT-discovery
    facet seals a regression file's real @Test methods with a content hash

  # slice-01 of java-test-runner-adapter (atdd_pure). Ships TWO net-new seams
  # in one module (mirrors cargo_runner.py's run+discover pair):
  #   - the Java run-facet run_java_scope (java_runner.py) -- mirrors
  #     run_go_scope/run_cargo_scope: resolves the target's mvn via the
  #     shared resolve_tool scale, shells the declared `mvn test` command at
  #     cwd=target_root, maps exit 0 -> PASS / non-zero -> FAIL /
  #     unresolvable -> INDETERMINATE (RunnerAdapterUnavailable).
  #   - the Java AT-discovery facet discover_java_ats (java_runner.py) --
  #     mirrors discover_pytest_ats/discover_cargo_ats: scans a regression
  #     file's raw bytes for @Test-attributed method names and returns them
  #     alongside a sha256 content seal.
  # The test fixture (tests/polyglot-pilot/java/) carries ONLY a pom.xml (no
  # build.gradle) -- Maven is the target's declared build tool -- so the
  # runner token is "maven-test" (test_runner_port.py _REGISTRY row
  # pom.xml -> maven-test), NOT a Gradle token.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_java_scope / discover_java_ats) imported + invoked in a CHILD
  # interpreter. ZERO des.adapters.* import in the test process -- the SUT is
  # only ever imported in the child. Required (not the Layer-2 in-process
  # default) because at HEAD java_runner.py does not exist: a plain in-process
  # import would raise ModuleNotFoundError at COLLECTION time (a BROKEN test),
  # never active-RED; the child interpreter makes the absent module a
  # CAPTURED observable each Then turns into a semantic AssertionError
  # (mirrors go_test_runner_adapter's identical rationale).
  #
  # FAKE-mvn determinism (AC-1/2/4 -- explicit fixture approach): the
  # exit-semantics ATs drive run_java_scope over a planted REAL chmod+x fake
  # `mvn` on a controlled PATH that emits a controlled exit code/output
  # (GREEN exit 0 / RED exit non-zero) AND records its argv + cwd. The
  # run-facet resolves the fake via resolve_tool's PATH rung and shells it
  # exactly like a real mvn -- so the exit-semantics + the
  # declared-command-shelled contract are exercised end-to-end through the
  # REAL run-facet, DETERMINISTICALLY in CI, with NO real Maven/JDK
  # toolchain. AC-3 drives run_java_scope over an mvn-absent fixture (PATH
  # empty, known-locations empty).
  #
  # JAVA-vs-cargo: `mvn test` exits 0 even with NO test files (like `go
  # test`) -- there is NO cargo-style exit-4 NO_MATCH empty-scope. So
  # MavenExitScenario has only GREEN (0) and RED (non-zero); INDETERMINATE is
  # reached ONLY via an unresolvable mvn (AC-3), never via an exit code.
  #
  # AT-DISCOVERY (AC-5/6): discover_java_ats is driven over a REAL, controlled
  # Java fixture file (never the shared polyglot-pilot fixture -- a
  # self-contained, ephemeral regression file so the discovery contract is
  # pinned independent of the pilot's own evolution). AC-5 proves BOTH a bare
  # `@Test` method and a `@Test` + `@DisplayName`-annotated method are
  # discovered with the real sha256 content seal (mirrors
  # discover_cargo_ats's two-function fixture). AC-6 proves a Java file with
  # ZERO @Test methods degrades LOUD (RunnerAdapterUnavailable), never a
  # silent empty discovery (mirrors discover_cargo_ats's zero-#[test] row).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at
  # HEAD the java_runner module is absent, so the child import raises
  # ModuleNotFoundError (rc != 0, no marker). Each Then turns a captured
  # observable into a semantic AssertionError. GREEN once DELIVER ships
  # java_runner.run_java_scope + java_runner.discover_java_ats. No @skip, no
  # import / collection error in the test process.

  @slice-01 @driving_port @real-io @us-java-exit-semantics @contract-shape:bounded-change
  Scenario: A green mvn run yields a PASS verdict
    Given a Java target whose mvn test exits zero with all tests passing
    When the java run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-java-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing mvn run yields a FAIL verdict, not indeterminate
    Given a Java target whose mvn test exits non-zero after executing tests
    When the java run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-java-exit-semantics @error @contract-shape:bounded-change
  Scenario: A Java target whose mvn is unresolvable yields a loud indeterminate naming the remediation
    Given a Java target whose mvn is absent from PATH and every known location
    When the java run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @real-io @us-declared-command-shelled @contract-shape:bounded-change
  Scenario: The Java run-facet shells the feature's declared subcommand as-is at the target root
    Given a Java target whose mvn records the argv and working directory it is shelled with
    When the java run-facet runs the declared command
    Then the mvn binary was invoked with the declared subcommand as-is
    And the mvn binary was invoked with the working directory set to the target root

  @slice-01 @driving_port @real-io @us-java-at-discovery @contract-shape:pure-function
  Scenario: The Java AT-discovery facet discovers @Test-attributed methods and seals the real content
    Given a Java regression file with a plain @Test method and a @Test method annotated with @DisplayName
    When the java AT-discovery facet discovers the file's acceptance tests
    Then the discovered AT identities are "userSignsUpAndIsRegistered" and "duplicateSignupIsRejected"
    And the content hash seals the regression file's real bytes

  @slice-01 @driving_port @real-io @us-java-at-discovery @error @contract-shape:pure-function
  Scenario: The Java AT-discovery facet refuses a regression file with zero @Test methods
    Given a Java regression file with zero @Test methods
    When the java AT-discovery facet discovers the file's acceptance tests
    Then the discovery is refused naming the zero-test condition
