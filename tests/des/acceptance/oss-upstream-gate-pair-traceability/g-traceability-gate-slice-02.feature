@feature-oss-upstream-gate-pair-traceability @slice-02
Feature: The traceability warning is comprehensible and auditable
  As an nWave operator reading a DISTILL-exit traceability warning
  I want every warned clause to name WHAT intent went unwitnessed (its summary),
    not just an opaque clause-ID, and the verdict to be recorded in the audit
    ledger
  So that the warning is actionable at a glance and the hand-off leaves a durable
    audit trail -- while the warning still never blocks the move (OSS is
    hooks-only and non-halting)

  # slice-02 of oss-upstream-gate-pair-traceability -- report quality + ledger
  # record. slice-01 (shipped) proved the syntactic join warns-loud + non-halting
  # and bound the clause-ID to an unwitnessed-semantics token. slice-02 tightens
  # the warning to resolve clause-ID -> summary on every report line (DT-4) and
  # records the verdict via the existing AtCompletionLedger (DT-10). DT-9
  # (strict-markers compatibility of the comment-carrier) is a meta-property
  # FOLDED as an enabling property of this suite, not a standalone scenario:
  # it is proven structurally by this .feature collecting EXIT=0 under the
  # project's canonical --strict-markers addopts (the comment-carrier # clause:
  # / # target: requires no pytest mark registration). See the DT-9 note below.
  #
  # SCOPE FINDING (2026-05-31, empirical-read-before-assumption): the dispatch
  # assumed BOTH DT-4 and DT-10 would be RED. The RED proof DISPROVED that for
  # DT-4: slice-01's gate ALREADY renders the ID->summary line
  # ("DT-ORPHAN (summary for DT-ORPHAN): unwitnessed-no-at ...",
  # decision_table_traceability_gate.py:130). So:
  #   * DT-4 ships as a GREEN REGRESSION-PIN -- it LOCKS the ID->summary
  #     co-location contract slice-01 happened to deliver, preventing a future
  #     refactor from regressing to bare-ID dumping. (Authoring it as a RED
  #     driver would fabricate feature debt that does not exist.)
  #   * DT-10 is the SOLE genuine RED driver: the gate appends NO ledger record
  #     today (grep-confirmed: zero append_gate_event in the gate module; the
  #     hook only emits to stderr). Its Then-step fails NOW with a semantic
  #     AssertionError (no DecisionTableTraceabilityWarned record read back from
  #     the ledger) -- never a collection / import / setup error (pre-DELIVER
  #     fail-for-right-reason gate). It PASSES once DELIVER (slice-02) adds the
  #     append_gate_event(event="DecisionTableTraceabilityWarned", slice_id="")
  #     call inside the D_DISTILL branch.
  #
  # NON-VACUITY (slice-01 DT-5 vacuity trap avoided): DT-4 does NOT assert a bare
  # substring -- it asserts the clause-ID and its DISTINCT summary text BOTH
  # appear AND are co-located on one warning line, so a gate that dumped bare IDs
  # or split ID/summary across lines WOULD fail (the regression-pin has teeth
  # even though slice-01 already satisfies it). DT-10 does NOT assert "the gate
  # ran" -- it reads the ledger back through the production AtCompletionLedger
  # reader and asserts the actual DecisionTableTraceabilityWarned record content
  # is present, so a gate that writes nothing FAILS (it fails NOW, the RED). Every
  # assertion binds to the SUT's behaviour, never to the seeded substrate alone.
  #
  # HARD INVARIANT (non-halting, inherited): the gate only WARNS + ALLOWS. No
  # slice-02 scenario asserts a block; both drive the same warn+allow surface as
  # slice-01.
  #
  # Driving port (Mandate-13 / Mandate-9-v2): the real SubagentStop hook, invoked
  # over its JSON stdin protocol as a subprocess against a real git repo carrying
  # a real feature-delta decision-table + a real .feature comment carrier (Layer
  # 3/4 wiring_e2e). The ledger read-back in DT-10 goes through the production
  # AtCompletionLedger reader (the S2 tolerable-variant: read precondition/outcome
  # state through the production reader, same class slice-01 seeds through).
  # Example-only, no PBT (Mandate 9/11 -- layer 3/4, real subprocess + real I/O).
  #
  # DT-9 NOTE (folded enabling meta-property, not a scenario): the immutable
  # clause-ID join-key + the production target ride in Gherkin COMMENTS
  # (# clause:, # target:) -- a comment, never a tag -- precisely so the carrier
  # is parseable WITHOUT pytest marker registration. The proof that this is
  # --strict-markers compatible is that THIS suite collects cleanly (EXIT=0)
  # under the canonical addopts (which already include --strict-markers): a tag
  # carrier would have produced a strict-collection-error. Folding it here
  # (rather than authoring a vacuous "Scenario: collection is clean") respects
  # the <=3-ATs/slice ceiling and mirrors slice-01's folding of DT-2.

  # clause: DT-4
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The warning resolves each unwitnessed clause to its summary, not a bare identifier
    Given a feature whose decision-table declares a clause with no witnessing test
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the warning names the unwitnessed clause together with its summary on one line

  # clause: DT-10
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The traceability verdict is recorded in the audit ledger
    Given a feature whose decision-table declares a clause with no witnessing test
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the audit ledger records the traceability warning verdict for the feature
    And the gate lets the feature proceed to DELIVER
