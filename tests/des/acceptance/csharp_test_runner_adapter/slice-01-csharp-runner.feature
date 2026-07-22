@feature-csharp-test-runner-adapter
Feature: The C# run-facet shells the declared dotnet test command and maps dotnet exit-semantics
  As an operator running the nWave spine against a C#/.NET target
  I want the C# run-facet to resolve the target's dotnet binary, shell the
    declared dotnet test command, and map its exit code to PASS / FAIL /
    INDETERMINATE, and the AT-discovery facet to discover the [Fact]/[Test]
    identities a C# regression file carries
  So that a C# spine runs through the port like Go and Rust -- a green run
    PASSes, a real failure FAILs (never swallowed), an unresolvable dotnet is a
    LOUD INDETERMINATE (never a silent pass), and a .csproj/.sln target routes
    to the dotnet-test runner instead of degrading to an unrecognized target

  # slice-01 of csharp-test-runner-adapter (atdd_pure). Ships TWO net-new seams,
  # mirroring go-test-runner-adapter (ADR-RTR-001 C1) + the pytest/cargo
  # AT-discovery facet pair (fix-rust-regression-at-kind-wiring):
  #   1. the C# run-facet run_csharp_scope (csharp_runner.py) -- resolves the
  #      target's dotnet via the shared resolve_tool scale, shells the declared
  #      `dotnet test` command, maps exit 0 -> PASS / non-zero -> FAIL /
  #      unresolvable -> INDETERMINATE (RunnerAdapterUnavailable).
  #   2. the C# AT-discovery facet discover_csharp_ats (csharp_runner.py) --
  #      discovers [Fact]/[Test]-attributed method identities a C# regression
  #      file carries, mirroring discover_pytest_ats / discover_cargo_ats.
  #   PLUS the routing gap this feature closes: test_runner_port.py's resolve()
  #   registry gains *.csproj / *.sln -> dotnet-test rows (AC-6) so a C# target
  #   is recognized at all, not just runnable once recognized. Unlike every
  #   prior registry row, a .csproj/.sln filename is the PROJECT'S OWN name
  #   (never a fixed lockfile name), so the registry now resolves a GLOB pattern
  #   against the target root, not only an exact filename.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production SUT
  # (run_csharp_scope / discover_csharp_ats / resolve) imported + invoked in a
  # CHILD interpreter. ZERO des.adapters.* import in the test process -- the SUT
  # is only ever imported in the child.
  #
  # FAKE-dotnet determinism (AC-1/2/3 -- explicit fixture approach, mirrors go):
  # the exit-semantics ATs drive run_csharp_scope over a planted REAL chmod+x
  # fake `dotnet` on a controlled PATH that emits a controlled exit code
  # (GREEN exit 0 / RED exit non-zero). The run-facet resolves the fake via
  # resolve_tool's PATH rung and shells it exactly like a real dotnet -- so the
  # exit-semantics are exercised end-to-end through the REAL run-facet,
  # DETERMINISTICALLY in CI, with NO real .NET SDK.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # the csharp_runner module is absent, so the child import raises
  # ModuleNotFoundError (rc != 0, no marker). Each Then turns a captured
  # observable into a semantic AssertionError. GREEN once DELIVER ships
  # csharp_runner.run_csharp_scope + discover_csharp_ats. AC-6 (the resolve()
  # glob-registry rows) is authored by THIS feature directly (a small, surgical
  # routing-table addition, not a run-facet) and is therefore LIVE-GREEN at HEAD.

  @slice-01 @driving_port @real-io @us-csharp-exit-semantics @contract-shape:bounded-change
  Scenario: A green dotnet run yields a PASS verdict
    Given a C# target whose dotnet test exits zero with all tests passing
    When the C# run-facet runs the declared command
    Then the run verdict is pass

  @slice-01 @driving_port @real-io @us-csharp-exit-semantics @error @contract-shape:bounded-change
  Scenario: A failing dotnet run yields a FAIL verdict, not indeterminate
    Given a C# target whose dotnet test exits non-zero after executing tests
    When the C# run-facet runs the declared command
    Then the run verdict is fail

  @slice-01 @driving_port @real-io @us-csharp-exit-semantics @error @contract-shape:bounded-change
  Scenario: A C# target whose dotnet is unresolvable yields a loud indeterminate naming the remediation
    Given a C# target whose dotnet is absent from PATH and every known location
    When the C# run-facet runs the declared command
    Then the run verdict is indeterminate
    And the indeterminate result names the remediation

  @slice-01 @driving_port @us-csharp-at-discovery @contract-shape:bounded-change
  Scenario: The C# AT-discovery facet discovers the [Fact] identities a regression file carries
    Given a C# regression file declaring two [Fact] test methods
    When the C# AT-discovery facet discovers the file's acceptance tests
    Then the discovered AT identities match the declared [Fact] methods
    And the discovery result carries a content seal over the regression file's bytes

  @slice-01 @driving_port @us-csharp-at-discovery @error @contract-shape:bounded-change
  Scenario: The C# AT-discovery facet degrades loud when the regression file declares zero [Fact] methods
    Given a C# regression file declaring zero [Fact] test methods
    When the C# AT-discovery facet discovers the file's acceptance tests
    Then the discovery degrades to a loud indeterminate naming the malformed file

  @slice-01 @driving_port @us-csharp-runner-routing @contract-shape:bounded-change
  Scenario Outline: A .NET project manifest routes to the dotnet-test runner
    Given a target carrying only a <manifest> manifest
    When the target's test runner is resolved
    Then the resolved runner is dotnet-test

    Examples:
      | manifest       |
      | .csproj        |
      | .sln           |
