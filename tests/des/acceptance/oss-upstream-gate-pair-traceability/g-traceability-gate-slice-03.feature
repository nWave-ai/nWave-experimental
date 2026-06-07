@feature-oss-upstream-gate-pair-traceability @slice-03
Feature: A named-but-vacuous test does not earn a clause its witness
  As an nWave operator running an atdd_pure feature hand-off
  I want a decision-table clause to count as witnessed only when an acceptance
    test GENUINELY asserts the clause's production behaviour -- not merely when
    a test names the clause-ID in a comment
  So that the one-line "name a clause, assert nothing" evasion cannot buy a
    clause a silent pass at DISTILL-exit -- while the gate stays hooks-only and
    non-halting

  # slice-03 of oss-upstream-gate-pair-traceability -- TARGET RESOLUTION +
  # BEHAVIORAL WITNESS CORE (ADR-001). The first HARD slice. slice-01 (shipped)
  # does a purely SYNTACTIC join: any clause whose ID appears in a `# clause:`
  # comment is provisionally `witnessed-by-name` and the gate stays SILENT about
  # it. slice-03 upgrades that provisional pass to an EARNED one for the positive
  # + unresolved cases: the gate must run the isolated-copy differential
  # perturbation and DOWNGRADE a name-matched-but-vacuous clause to unwitnessed.
  #
  # SCOPE (DT-7, DT-8, DT-12 -- @coupled, the witness-mechanism poles):
  #   DT-7  the positive + its non-vacuity guard -- a clause whose AT GENUINELY
  #         asserts its target -> `witnessed`; a clause whose AT merely
  #         names/imports the target without asserting -> NOT witnessed. The
  #         fixture carries BOTH so a coverage-equivalent gate (one that reports
  #         witnessed for any name-matched/executing AT) FAILS the contract.
  #   DT-8  the witness-check is git-free + tree-safe: perturbation happens in an
  #         isolated tmp copy; the real source file is byte-identical before and
  #         after; no `git` is invoked.
  #   DT-12 a clause whose `# target:` does not resolve in the source tree ->
  #         `unwitnessed: target-unresolved`, surfaced LOUD -- never a soft skip
  #         that lets the syntactic name-match pass.
  # @coupled: the witness mechanism is not meaningful without all three -- DT-7
  # is the positive pole, DT-8 its tree-safety invariant, DT-12 its
  # resolution precondition. Exactly 3 ATs (the slice-plan poles); no
  # @coupled-escape needed (slice-02 was the escape precedent; slice-03 fits the
  # ceiling). DT-6 / DT-6b (the two reason-discrimination evasion poles) are
  # slice-04, NOT here. DT-11 (the earned-trust probe degrade path) is slice-05.
  #
  # WHY RED-FOR-RIGHT-REASON NOW (the load-bearing slice-03 RED contract): the
  # `ClauseWitnessPort` + `PerturbationWitnessAdapter` (ADR-001 / architecture.md
  # sec.4) DO NOT EXIST yet (grep-confirmed: no src/des/ports/clause_witness_port
  # .py, no src/des/adapters/driven/witness/). The shipped slice-01 gate marks
  # EVERY name-matched clause `witnessed-by-name` and stays SILENT about it -- it
  # has no behavioral check, so it cannot tell a genuine AT from a vacuous one
  # and it cannot downgrade. Each slice-03 scenario therefore seeds a fixture
  # whose clause IS name-matched (slice-01 silent) but whose AT is behaviorally
  # the wrong kind (vacuous / unresolved). The Then-step asserts the gate
  # SURFACES that clause as unwitnessed -- which the current syntactic gate does
  # NOT do, so the assertion fails with a semantic AssertionError (the gate's
  # stderr carries no warning for the name-matched clause). NEVER a collection /
  # import / setup error: the suite collects cleanly (it imports only the shipped
  # AtCompletionLedger + test-local types) and the hook is driven as a
  # subprocess (pre-DELIVER fail-for-right-reason gate). It PASSES once DELIVER
  # slice-03 wires the witness-check into the D_DISTILL branch.
  #
  # NON-VACUITY (the whole point of this slice; DT-5 vacuity trap avoided):
  #   DT-7a/DT-7b seed THREE name-matched clauses in ONE feature-delta --
  #   DT-GENUINE (asserts the RETURN value), DT-VACUOUS (executes, asserts
  #   nothing), DT-EXEC-ASSERT-UNRELATED (executes + genuine assert independent of
  #   the return). DT-7a asserts the gate stays SILENT about DT-GENUINE; DT-7b
  #   asserts the gate SURFACES BOTH DT-VACUOUS and DT-EXEC-ASSERT-UNRELATED as
  #   `survived`. The litmus across gate classes:
  #     - coverage-equivalent (witnessed-iff-executes): warns about NEITHER
  #       non-asserting pole -> FAILS DT-7b surfacing.
  #     - warn-every-clause: warns about DT-GENUINE -> FAILS DT-7a silence.
  #     - syntactic-assert-shape (has-assert / has-assert-referencing-target):
  #       marks DT-EXEC-ASSERT-UNRELATED witnessed because an `assert` node is
  #       present -> stays silent about it -> FAILS DT-7b surfacing. (This is the
  #       gate the two-pole DT-7 could NOT catch; the keystone third pole closes
  #       it.)
  #     - coverage/crash-perturbation: the AT executes the target / a crash makes
  #       it RED -> marks DT-EXEC-ASSERT-UNRELATED witnessed -> stays silent ->
  #       FAILS DT-7b surfacing. (Forces wrong-RETURN over crash.)
  #   Only a genuine wrong-RETURN-perturbation-with-AssertionError-from-AT-body
  #   gate keeps DT-GENUINE silent AND surfaces both non-asserting poles survived.
  #   (slice-01's current syntactic gate stays silent about all three -> fails
  #   DT-7b surfacing -> the RED.)
  #   DT-8 asserts the REAL source file the `# target:` names is byte-identical
  #   before and after the witness-check (a true tree-safety observable), not the
  #   weaker "no git stash" -- a gate that perturbed the live tree would fail
  #   even if it produced a correct verdict.
  #   DT-12 names a `# target:` symbol absent from the tree and asserts the gate
  #   surfaces `target-unresolved` LOUD -- a gate that silently skips an
  #   un-targeted-but-name-matched clause (slice-01 does exactly this: silent)
  #   FAILS. This is the RED today.
  #
  # HARD INVARIANT (non-halting, inherited): the gate only WARNS + ALLOWS. No
  # slice-03 scenario asserts a block; all drive the same warn+allow surface as
  # slice-01/02. The fail-open hook wrapper still applies.
  #
  # Driving port (Mandate-13 / Mandate-9-v2): the real `handle_subagent_stop`
  # SubagentStop hook over its JSON stdin protocol as a subprocess (Layer 3/4
  # wiring_e2e), against a real git repo carrying a real feature-delta
  # decision-table, a real `.feature` comment carrier (# clause: + # target:),
  # and -- the slice-03 addition -- a real witnessing AT MODULE on disk that the
  # witness-check actually RUNS (baseline + perturbed) and a real production
  # source file the `# target:` resolves to + perturbs IN AN ISOLATED COPY. The
  # AtCompletionLedger writer is reused ONLY to seed the signed precondition
  # verdict so the orthogonal downstream verdict-completeness gate ALLOWS (the
  # S2 tolerable-variant; same as slice-01/02). Example-only, no PBT (Mandate
  # 9/11 -- layer 3/4, real subprocess + real I/O + real source perturbation).
  #
  # TAG SCHEME (strict-markers safe -- relative `scenarios("../<feature>")` from
  # the steps/ module, IDENTICAL to slice-01/02). The immutable clause-ID + the
  # production target ride in Gherkin COMMENTS (# clause:, # target:), never tags
  # (DT-9). The `# target:` here points at the REAL slice-03 production symbol
  # the witness mechanism perturbs: `ClauseWitnessPort.witness` -- the method
  # whose absence today IS the RED, and whose implementation in DELIVER turns the
  # behavioral verdict from absent to earned.

  # clause: DT-7
  # target: des.ports.clause_witness_port::ClauseWitnessPort
  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: A clause that genuinely asserts its target's outcome keeps its witness
    Given a feature with one test that asserts its target's outcome and two tests that exercise the target without asserting its outcome
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate stays silent about the test that asserts its target's outcome

  # clause: DT-7
  # target: des.ports.clause_witness_port::ClauseWitnessPort
  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: Every test that exercises but does not assert its target loses its witness
    Given a feature with one test that asserts its target's outcome and two tests that exercise the target without asserting its outcome
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate surfaces both tests that exercise but do not assert their target as unwitnessed

  # clause: DT-8
  # target: des.adapters.driven.witness.perturbation_witness_adapter::PerturbationWitnessAdapter
  @slice-03 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The witness-check leaves the real source untouched
    Given a feature whose clause is checked against a real production source file
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the real production source file is byte-identical after the witness-check
    And the witness-check uses no version-control to undo its perturbation

  # clause: DT-12
  # target: des.application.decision_table_traceability_gate::DecisionTableTraceabilityGate
  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: A clause whose target cannot be located is surfaced loudly, never silently skipped
    Given a feature whose clause names a production target that does not exist in the source tree
    When the acceptance designer returns and the DISTILL-exit gate evaluates the feature
    Then the gate surfaces the clause as unwitnessed because its target cannot be located
