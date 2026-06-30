@feature-f-spine-runs-tests-not-git-hooks
Feature: The spine genuinely RUNS only the entering slice's tests at commit
  As a developer (human or LLM) committing a slice
  I want the spine itself to RUN only the entering slice's acceptance tests
    at the slice gate -- a real execution, not a collect-only walk -- so a
    broken slice is VETOED at commit with no git test-hook present
  So that every commit is fast (slice-proportional, not whole-tree) AND a RED
    slice can never commit clean

  # slice-01 of f-spine-runs-tests-not-git-hooks (THE ACCELERATION + the genuine
  # RUN). The thinnest end-to-end vertical that DELIVERS the acceleration AND
  # fails on RED. REUSE `run_contract_gate.run_slice_ats` for the SCOPE
  # (collect-only node-id set); BUILD the slice-scoped EXECUTOR + the
  # `RunnerAdapter.run()` run-facet + a `pytest_runner` adapter + the
  # `des run-slice-ats` CLI subcommand (CRITICAL-1/CRITICAL-2 -- genuinely NEW
  # machinery, not pure wiring).
  #
  # DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the REAL in-tree executor
  #   `python -m des.cli.run_slice_ats`, driven via --repo-root / --entering-slice.
  #   observable = the process EXIT CODE (PASS=0 / FAIL=1) + the one JSON line on
  #   stdout {event, entering_slice, verdict, runner, ran_node_ids, ran_whole_tree,
  #   out_of_slice_ran}. No executor logic re-implemented in step bodies (the AT
  #   drives the real shipped gate -- protocol-driver contract).
  #
  # DORMANT-SEAM (D11 / Mandate-15): the net-new load-bearing seams this slice
  #   declares are (a) `des.cli.run_slice_ats` (resolve->scope->RUN->verdict),
  #   (b) `RunnerAdapter.run(scoped_node_ids) -> verdict` on the `name`-only
  #   frozen dataclass, (c) `des.adapters.driven.runner.pytest_runner` (the
  #   package does NOT exist at HEAD). Each scenario drives THAT seam through the
  #   REAL entry point + asserts the exit-code observable effect, never a claim a
  #   symbol "exists".
  #
  # DISTINCT FIXTURE PER VERDICT (§22.0): green-slice-AT / RED-slice-AT are
  #   GENUINELY different planted preconditions (a green vs a RED `then` step in
  #   the planted slice suite), never one payload re-asserted with different Thens.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD `des.cli.run_slice_ats` does not
  #   exist (`__main__.py` registers no `run-slice-ats` row), so the subprocess
  #   exits non-zero on module-absence -- NEITHER the expected PASS (0) nor BLOCK
  #   FAIL (1). Each scenario observes a semantic AssertionError against the
  #   expected verdict (the AT imports nothing from the absent SUT; it shells out).
  #   GREEN once DELIVER ships the executor + run-facet + pytest adapter + the
  #   `run-slice-ats` subcommand row.

  # ---- CT-1: the gate RUNS ONLY the entering slice's ATs (proportional) -------

  @slice-01 @walking_skeleton @driving_port @real-io @us-the-acceleration @contract-shape:bounded-change
  Scenario: A green slice passes and only its own tests run
    Given a developer commits the entering slice
    And the entering slice has a green acceptance test
    When the spine slice-AT gate runs
    Then the spine slice-AT gate passes the commit
    And the spine slice-AT gate ran only the entering slice's tests

  # ---- CT-2: a RED slice AT genuinely RUNS and VETOES (no git hook) -----------

  @slice-01 @driving_port @real-io @us-the-acceleration @error @contract-shape:bounded-change
  Scenario: A broken slice is vetoed because the spine RUNS its tests
    Given a developer commits the entering slice
    And the entering slice has a broken acceptance test
    When the spine slice-AT gate runs
    Then the spine slice-AT gate refuses the commit
