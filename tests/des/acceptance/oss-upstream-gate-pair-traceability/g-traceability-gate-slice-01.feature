@feature-oss-upstream-gate-pair-traceability @slice-01
Feature: A decision-table clause that no acceptance test witnesses is warned at DISTILL-exit
  As an nWave operator running an atdd_pure feature hand-off
  I want the DISTILL->DELIVER transition to warn loudly when an upstream
    decision-table clause has no witnessing acceptance test
  So that an intent-unit declared in the feature-delta cannot silently reach
    DELIVER unwitnessed -- while the warning never blocks the move (OSS is
    hooks-only and non-halting)

  # slice-01 of oss-upstream-gate-pair-traceability -- the walking skeleton:
  # syntactic join (decision-table clauses <-> .feature comment clause-IDs),
  # warn-loud on a row with zero witnessing AT, non-halting. No behavioral
  # witness-check yet (DT-6/DT-6b/DT-7 land slice-03/04); a clause WITH a name
  # match is provisionally witnessed. DT-2 (comment parsing) is the enabling
  # mechanism exercised by DT-1/DT-3, authored as a step not a separate AT to
  # respect the <=3-ATs-per-slice ceiling.
  #
  # RED scaffold (ADR-025 + ADR-028): these ATs FAIL on master for the RIGHT
  # reason -- `_handle_distill_exit_gate` has no DecisionTableTraceabilityGate
  # branch yet, so the hook emits no traceability warning. The Then-steps that
  # assert the loud warning fail with a semantic AssertionError (never a
  # collection / import / setup error -- pre-DELIVER fail-for-right-reason gate).
  # They PASS once slice-01 lands the gate inside the D_DISTILL branch:
  # parse decision-table + parse comment clause-IDs + join + warn-loud-allow.
  #
  # HARD INVARIANT (non-halting): the gate only WARNS + ALLOWS. No scenario
  # asserts a block. The observable surface is the loud stderr warning, the
  # absence of a block decision on stdout, and exit code zero (slice-01 is
  # warn-only; the ledger record is slice-02, asserted there, not here).
  #
  # SUT join state model (C2): the gate evaluates a single D_DISTILL return and,
  # per clause, resolves to {witnessed-by-name, unwitnessed}. The materially
  # distinct decision-table rows (C5): a clause with zero AT refs -> warn; a
  # clause with >=1 AT ref -> silent (slice-01 provisional witnessed).
  #
  # Driving port (Mandate-13 / Mandate-9-v2): the real SubagentStop hook,
  # invoked over its JSON stdin protocol as a subprocess against a real git repo
  # carrying a real feature-delta decision-table and a real .feature comment
  # carrier (Layer 3/4 wiring_e2e). Example-only, no PBT (Mandate 9/11).
  #
  # TAG SCHEME (strict-markers safe -- mirrors the sibling suite
  # oss-hook-side-phase-injection): scenario @tags (@slice-01, @driving_port,
  # @real-io, @walking_skeleton, @contract-shape:*) are converted to dynamic
  # pytest marks by pytest-bdd's tag pipeline; the project's filterwarnings
  # (pyproject.toml) suppresses PytestUnknownMarkWarning so --strict-markers
  # does not reject them. This works ONLY when the binding goes through
  # pytest-bdd's scenario machinery the same way the sibling does (relative
  # `scenarios("../<feature>")` from the steps/ module). The immutable clause-ID
  # join-key + the production target ride in Gherkin COMMENTS (# clause:,
  # # target:) per the Published-Language carrier contract -- a comment, never a
  # tag, because the clause-ID carrier must be parseable without pytest marker
  # registration (DT-9).

  # clause: DT-1
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The gate reads the decision-table and names a clause that no test witnesses
    Given a feature whose decision-table declares a clause with no witnessing test
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate names the unwitnessed clause in its loud warning

  # clause: DT-3
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A decision-table row with no acceptance test warns while a witnessed row stays silent
    Given a feature whose decision-table declares one witnessed clause and one unwitnessed clause
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate warns loudly about the unwitnessed clause
    And the gate stays silent about the witnessed clause

  # clause: DT-5
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The traceability warning lets DISTILL proceed to DELIVER instead of blocking
    Given a feature whose decision-table declares a clause with no witnessing test
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate warns loudly about the unwitnessed clause
    And the gate lets the feature proceed to DELIVER
    And the hook exits with code zero
