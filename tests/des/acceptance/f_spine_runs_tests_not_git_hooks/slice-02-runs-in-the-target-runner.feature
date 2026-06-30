@feature-f-spine-runs-tests-not-git-hooks
Feature: The slice RUN executes in the target project's own resolved runner
  As a developer on any target project (Python, Node, Go, Rust, or unrecognized)
  I want the slice RUN to execute in the runner the target itself resolves to,
    with the resolution consulted FIRST so an unrecognized runner degrades LOUD
    BEFORE any pytest-bound collection, never a silent pass and never a pytest
    fallback
  So that a non-Python target gets an honest INDETERMINATE rather than a vacuous
    verdict, and an empty slice with no real test is NOT_APPLICABLE rather than a
    fabricated always-green pass

  # slice-02 of f-spine-runs-tests-not-git-hooks. Closes the agnosticism gap
  # (KPI-3) + the HIGH-1 silent-pass vector + the HIGH-2 collection-leak. Reuses
  # `TestRunnerPort.resolve` + `Indeterminate` verbatim. NEW: (a) consult
  # `resolve()` FIRST and short-circuit on `Indeterminate` BEFORE the pytest-bound
  # `_collect_scope_worker` is reached (HIGH-2); (b) guard the live gate off
  # `_materialize_representative_slice_at` -> no-real-AT returns NOT_APPLICABLE
  # (HIGH-1, DDD-8); (c) convert `Indeterminate` into the slice-gate INDETERMINATE
  # verdict + a degrade-LOUD reason. No hardcoded pytest in the RUN path.
  #
  # DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the same REAL in-tree
  #   executor `python -m des.cli.run_slice_ats` (slice-01), driven via
  #   --repo-root / --entering-slice over tmp workspaces carrying different target
  #   manifests. observable = exit code (PASS=0 / INDETERMINATE != {0,1} /
  #   NOT_APPLICABLE=0) + the JSON line {verdict, runner, reason}.
  #
  # DORMANT-SEAM (D11 / Mandate-15): the net-new load-bearing seam this slice
  #   declares is `resolve()` consulted FIRST on the executor's path (before any
  #   collection) + the `Indeterminate`->INDETERMINATE mapping + the no-real-AT
  #   NOT_APPLICABLE guard. Each scenario drives THAT seam through the REAL entry
  #   point + asserts the resolved-runner / INDETERMINATE / NOT_APPLICABLE exit
  #   observable.
  #
  # DISTINCT FIXTURE PER VERDICT (§22.0): a pyproject.toml target, a bare
  #   no-lockfile target, and a no-`.feature` workspace are GENUINELY different
  #   on-disk states (different planted manifests / planted ATs), never one
  #   payload re-asserted.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the executor module is absent, so
  #   every scenario observes a module-absent non-zero exit -- semantic
  #   AssertionErrors against the expected verdict. GREEN once DELIVER ships the
  #   resolve()-first executor + the `pytest_runner` adapter (DDD-2/DDD-7/DDD-8).

  # ---- CT-3: the RUN executes in the runner resolve() returns ----------------

  @slice-02 @driving_port @real-io @us-agnostic-run @contract-shape:bounded-change
  Scenario: The slice tests run in the target's resolved pytest runner
    Given a developer commits the entering slice
    And the target project resolves to the "pytest" runner
    And the entering slice has a green acceptance test
    When the spine slice-AT gate runs
    Then the spine slice-AT gate passes the commit
    And the slice tests ran in the resolved "pytest" runner

  # ---- CT-4: an unrecognized runner degrades LOUD to INDETERMINATE ------------

  @slice-02 @driving_port @real-io @us-agnostic-run @error @contract-shape:bounded-change
  Scenario: An unrecognized-runner target degrades loud, never a silent pass
    Given a developer commits the entering slice
    And the target project resolves to no recognized runner
    And the entering slice has a green acceptance test
    When the spine slice-AT gate runs
    Then the spine slice-AT gate reports indeterminate
    And the indeterminate reason names the unresolved runner

  # ---- CT-8: a no-real-AT slice is NOT_APPLICABLE, never a fabricated pass -----

  @slice-02 @driving_port @real-io @us-no-fabricated-at @contract-shape:bounded-change
  Scenario: An entering slice with no real test is not-applicable
    Given a developer commits the entering slice
    And the target project resolves to the "pytest" runner
    And the entering slice has no real acceptance test
    When the spine slice-AT gate runs
    Then the spine slice-AT gate reports not-applicable
