@feature-des-gate-error-explain-and-guide @slice-01
Feature: The feature-scope gate enriches malformed-scope refusals with a what/why/next explain-and-guide triad
  As an orchestrator running des run-contract-gate --feature-id on a malformed scope
  I want the emitted FeatureScopeMalformed JSON to carry a what/why/next triad
  So that I can identify which check refused, understand the specific cause, and apply
    the concrete remediation without consulting the nWave source tree

  # slice-01 of des-gate-error-explain-and-guide -- THE WALKING SKELETON
  # (DISCUSS Slice Plan slice-01 + DESIGN [REF] §1 Driving Surface).
  # The thinnest honest end-to-end vertical: drive the real
  # `des run-contract-gate --feature-id` CLI against a synthetic tmp repo that
  # triggers `zero-collected` (no .feature file tagged @feature-<id>), parse
  # the stdout JSON, and assert the explain-and-guide triad is present.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess):
  #   `python -m des.cli.run_contract_gate --feature-id <id>
  #            --entering-slice <slice> --repo <tmp>`
  # The `_feature_scope_malformed` / `_explain_and_guide` seams are NEVER
  # imported-and-called at the step boundary -- that is a Layer-1 unit test
  # anti-pattern (Mandate-13 HARD invariant). The observable surface is:
  #   - stdout: one-line JSON object
  #   - exit code: 2
  #
  # ADDITIVE-ONLY INVARIANT (D-1, feature-delta.md Locked Decisions):
  # The enrichment MUST NOT change any of the five pre-existing JSON fields
  # (event / cause / feature_id / reason / error) or the exit code (2).
  # Scenario 2 guards this explicitly: it is the load-bearing canary AT --
  # if DELIVER touches an existing field or changes the exit code the scenario
  # goes RED even though it is expected GREEN-on-author.
  #
  # PURE-READ CONTRACT (Mandate-8, layer-3 universe guard):
  # run_contract_gate is a pure observer -- it reads the repo but MUST NOT
  # write to the tmp directory. capture_universe() snapshots the tmp dir's
  # file count before the When-step; the When-step asserts unchanged() for
  # every universe entry.
  #
  # RED-for-right-reason (ADR-025 + ADR-028):
  #   Scenario 1 (walking skeleton): at authorship HEAD the `_explain_and_guide`
  #     mapper does not exist and payload.update(...) is not called in
  #     `_feature_scope_malformed` -> the emitted JSON has no `what`/`why`/`next`
  #     -> the Then-step KeyErrors on `event["what"]` -> AssertionError. RED.
  #   Scenario 2 (additive-only invariant): the five existing fields ARE already
  #     present and exit code IS already 2 -> GREEN-on-author. This is intentional:
  #     the scenario is the load-bearing guard that DELIVER must not regress.
  #   Scenario 3 (per-token distinctness): same as Scenario 1 -- `what`/`why`/`next`
  #     absent at HEAD -> KeyError -> AssertionError. RED.
  #     Additionally asserts that the `why` for `empty-intersection` differs from
  #     the `why` for `zero-collected` (scenario 1's token) -- a constant-string
  #     stub mapper would pass scenario 1 but fail scenario 3.
  #
  # S3 CROSS-TABLE RECONCILIATION (DESIGN Driving Surface table, each seam
  # driven by at least one scenario from the real CLI):
  #   seam: _explain_and_guide(reason) pure mapper     -> scenarios 1, 2, 3
  #   seam: _feature_scope_malformed payload.update()  -> scenarios 1, 2, 3
  #   seam: _emit(payload) stdout                      -> scenarios 1, 2, 3
  #   reason token: zero-collected                     -> scenarios 1, 2
  #   reason token: empty-intersection                 -> scenario 3
  #
  # S1 STEP-TEXT UNIQUENESS: every step literal below is unique within this
  # feature directory (no duplicate step texts across scenarios).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A malformed feature-scope refusal carries a non-empty explain-and-guide triad
    Given a repository where no feature file carries the feature tag
    When the operator runs des run-contract-gate scoped to that feature
    Then the gate refuses with the explain-and-guide triad present
    And the gate does not write to the repository

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The existing FeatureScopeMalformed fields and exit code are unchanged by the enrichment
    Given a repository where no feature file carries the feature tag
    When the operator runs des run-contract-gate scoped to that feature
    Then the gate emits the canonical FeatureScopeMalformed event
    And the gate exits with the malformed-scope exit code

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The explain-and-guide triad content is token-specific not a constant stub
    Given a repository where a feature file exists but carries no slice tag
    When the operator runs des run-contract-gate scoped to that feature and slice
    Then the gate refuses with the explain-and-guide triad present for empty-intersection
    And the empty-intersection triad is distinct from the zero-collected triad
