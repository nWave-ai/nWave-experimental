@feature-des-gate-error-explain-and-guide @slice-02
Feature: The remaining three reason tokens each carry a non-empty token-specific explain-and-guide triad
  As an orchestrator running des run-contract-gate --feature-id on a malformed scope
  I want the FeatureScopeMalformed JSON to carry distinct what/why/next triads for
    collection-failed, arch-scope-zero-collected, and arch-invariant-failed reason codes
  So that I can identify the exact failure surface and apply the correct remediation
    without consulting the nWave source tree

  # slice-02 of des-gate-error-explain-and-guide -- COVERAGE PINS (F1 close).
  #
  # slice-01 exercised `zero-collected` and `empty-intersection`.
  # The deep-review F1 finding: the remaining 3 tokens have NO AT verifying
  # their _EXPLAIN_AND_GUIDE_TABLE entries are non-empty. A typo in those
  # entries would go undetected. slice-02 closes this gap.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess):
  #   `python -m des.cli.run_contract_gate --feature-id <id>
  #            --entering-slice <slice> --repo <tmp>`
  # The `_explain_and_guide` / `_EXPLAIN_AND_GUIDE_TABLE` seams are NEVER
  # imported-and-called at the step boundary -- that is a Layer-1 unit test
  # anti-pattern (Mandate-13 HARD invariant).
  #
  # ADDITIVE-ONLY INVARIANT (D-1): the enrichment must not change any of the
  # five pre-existing JSON fields or the exit code (2). Asserted in slice-01
  # for the zero-collected token; carried implicitly here via the `reason`
  # assertion that confirms the correct token was emitted.
  #
  # PURE-READ CONTRACT (Mandate-8, layer-3 universe guard):
  # run_contract_gate is a pure observer. capture_universe() snapshots the tmp
  # dir's file count before the When-step; the When-step asserts unchanged().
  #
  # GREEN-ON-AUTHOR (all three scenarios):
  # The `_EXPLAIN_AND_GUIDE_TABLE` entries for all five tokens are already
  # shipped (slice-01 DELIVER). Each scenario is GREEN because the table entry
  # is present and non-empty at HEAD. Non-vacuity: each scenario would FAIL if
  # the target token's table entry were emptied or turned into a constant
  # shared with another token -- see distinctness assertions per scenario.
  #
  # S1 STEP-TEXT UNIQUENESS: every step literal below is unique within this
  # feature directory -- no step text repeats across slice-01 and slice-02.
  #
  # PROVOKING EACH TOKEN (black-box, no direct imports):
  #
  # `collection-failed`:
  #   Substrate: a repo with a properly-tagged .feature file AND a broken Python
  #   step file (syntax error) in the feature scope directory. When the gate
  #   calls `_collect_node_ids(repo, paths=scope_dirs)` pytest raises a
  #   collection error -> `_CollectionError` -> reason="collection-failed".
  #
  # `arch-scope-zero-collected`:
  #   Substrate: a repo with a properly-tagged, correctly-sliced .feature file
  #   AND a valid conftest.py (so the feature scope collects ≥1 node), PLUS a
  #   tests/build/ dir that is empty. The arch-invariant worker exits 5
  #   (no tests collected) -> `_ArchVerdict(collected=0, passed=True)` ->
  #   reason="arch-scope-zero-collected".
  #
  # `arch-invariant-failed`:
  #   Substrate: same as arch-scope-zero-collected but tests/build/ has a
  #   failing pytest test marked `unit` (inside the contract marker set) ->
  #   `_ArchVerdict(collected=1, passed=False)` -> reason="arch-invariant-failed".

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A pytest-collection failure refusal carries a non-empty token-specific explain-and-guide triad
    Given a repository whose feature scope triggers a pytest collection failure
    When the operator runs des run-contract-gate on the collection-failed scope
    Then the gate refuses with a collection-failed explain-and-guide triad
    And the collection-failed triad why is distinct from the zero-collected triad why

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A vacuous architecture-invariant scope refusal carries a non-empty token-specific explain-and-guide triad
    Given a repository whose architecture-invariant tier collects zero tests
    When the operator runs des run-contract-gate on the vacuous arch scope
    Then the gate refuses with an arch-scope-zero-collected explain-and-guide triad
    And the arch-scope-zero-collected triad why is distinct from the collection-failed triad why

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A failing architecture invariant refusal carries a non-empty token-specific explain-and-guide triad
    Given a repository whose architecture-invariant tier has a failing test
    When the operator runs des run-contract-gate on the failing arch invariant scope
    Then the gate refuses with an arch-invariant-failed explain-and-guide triad
    And the arch-invariant-failed triad why is distinct from the arch-scope-zero-collected triad why
