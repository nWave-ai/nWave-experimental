@feature-cpp-test-runner-adapter
Feature: The C++ run-facet shells the declared make test command and maps make exit-semantics
  As an operator running the nWave spine against a C++/Make target
  I want the C++ run-facet to resolve the target's make binary, shell the declared
    make test command, and map its exit code to PASS / FAIL / INDETERMINATE, and
    the AT-discovery facet to discover the TEST("...")-declared identities a C++
    regression file carries
  So that a C++ spine runs through the port like Go, Kotlin, and C# -- a green run
    PASSes, a real failure FAILs (never swallowed), an unresolvable make is a LOUD
    INDETERMINATE (never a silent pass, never a pytest fallback), and a regression
    file's TEST("...") identities are discovered and content-sealed rather than
    silently reported empty

  # slice-01 of cpp-test-runner-adapter (atdd_pure). Ships TWO net-new seams,
  # mirroring go-test-runner-adapter (ADR-RTR-001 C1) + kotlin/csharp-test-runner-
  # adapter's AT-discovery facet pair (fix-rust-regression-at-kind-wiring):
  #   1. the C++ run-facet run_cpp_scope (cpp_runner.py) -- resolves the target's
  #      make via the shared resolve_tool scale, shells the declared `make test`
  #      command, maps exit 0 -> PASS / non-zero -> FAIL / unresolvable ->
  #      INDETERMINATE (RunnerAdapterUnavailable).
  #   2. the C++ AT-discovery facet discover_cpp_ats (cpp_runner.py) -- discovers
  #      TEST("...")-declared identities a C++ regression file carries (the
  #      hand-rolled common/testkit/testkit.hpp runner's self-registration macro),
  #      mirroring discover_kotlin_ats / discover_csharp_ats.
  #
  # NO auto-detection registry row for a bare "Makefile" manifest is added by this
  # feature (see feature-delta's Manifest-Detection Decision): unlike go.mod /
  # Cargo.toml / pom.xml / build.gradle.kts / *.csproj -- each a language-
  # unambiguous manifest -- a bare Makefile is used across many non-C++ purposes,
  # so auto-detecting on it would silently misclassify unrelated targets. C++
  # target scoping stays explicit-declaration-only; there is deliberately NO
  # "routing" scenario in this feature (unlike kotlin-test-runner-adapter's AC-6).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_cpp_scope / discover_cpp_ats) imported + invoked in a CHILD interpreter.
  # ZERO des.adapters.* import in the test process -- the SUT is only ever
  # imported in the child. The AT constructs RunnerAdapter(name="cpp-make-test")
  # directly and calls the facets directly, bypassing resolve()/_REGISTRY
  # entirely -- exactly the pattern go/kotlin/csharp's slice-01 ATs already use.
  #
  # FAKE-make determinism (AC-1/2/3 -- explicit fixture approach, mirrors go/
  # kotlin): the exit-semantics ATs drive run_cpp_scope over a planted REAL
  # chmod+x fake `make` on a controlled PATH that emits a controlled exit code
  # (GREEN exit 0 / RED exit non-zero AFTER emitting test-shaped output). The
  # run-facet resolves the fake via resolve_tool's PATH rung and shells it
  # exactly like a real make -- so the exit-semantics are exercised end-to-end
  # through the REAL run-facet, DETERMINISTICALLY in CI, with NO real g++/make
  # toolchain build required for these three rows.
  #
  # CPP-vs-cargo (verified by a real fake-Makefile probe during this DISTILL, not
  # assumed): GNU make wraps a failing recipe line's exit code into its OWN
  # non-zero exit (`make: *** [Makefile:N: test] Error N`) -- there is NO
  # cargo-style exit-4 NO_MATCH empty-scope row. So MakeExitScenario has only
  # GREEN (0) and RED (non-zero); INDETERMINATE is reached ONLY via an
  # unresolvable make (AC-3).
  #
  # REAL-FIXTURE AT-discovery (AC-4/AC-5 -- no synthetic fixture needed): the
  # already-verified-working polyglot pilot at tests/polyglot-pilot/cpp/ already
  # carries a genuine two-TEST file (feature/feature_scenarios_test.cpp) and a
  # genuine zero-TEST file (common/testkit/test_main.cpp, which only calls
  # testkit::run_all()) -- AC-4/AC-5 read these REAL on-disk files directly.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # the cpp_runner module is absent, so the child import raises
  # ModuleNotFoundError (rc != 0, no marker). Each Then turns a captured
  # observable into a semantic AssertionError. GREEN once DELIVER ships
  # cpp_runner.run_cpp_scope + cpp_runner.discover_cpp_ats. No @skip, no
  # import / collection error in the test process.

  @slice-01 @driving_port @real-io @us-cpp-exit-semantics @contract-shape:bounded-change
  Scenario: A green make run yields a PASS verdict
    Given a C++ target whose make test exits zero with all tests passing
    When the C++ run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-cpp-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing make run yields a FAIL verdict, not indeterminate
    Given a C++ target whose make test exits non-zero after executing tests
    When the C++ run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-cpp-exit-semantics @error @contract-shape:bounded-change
  Scenario: A C++ target whose make is unresolvable yields a loud indeterminate naming the remediation
    Given a C++ target whose make is absent from PATH and every known location
    When the C++ run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @us-cpp-at-discovery @contract-shape:bounded-change
  Scenario: The C++ AT-discovery facet discovers the TEST identities a real regression file carries
    Given the real polyglot pilot regression file declaring two TEST cases
    When the C++ AT-discovery facet discovers the file's acceptance tests
    Then the discovered AT identities match the declared TEST cases
    And the discovery result carries a content seal over the regression file's bytes

  @slice-01 @driving_port @us-cpp-at-discovery @error @contract-shape:bounded-change
  Scenario: The C++ AT-discovery facet degrades loud when the regression file declares zero TEST cases
    Given the real polyglot pilot regression file declaring zero TEST cases
    When the C++ AT-discovery facet discovers the file's acceptance tests
    Then the discovery degrades to a loud indeterminate naming the malformed file
