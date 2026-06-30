@feature-f-design-devops-review-gate @driving_port @real-io
Feature: A platform-architect's DEVOPS output is mechanically gated by the IDENTICAL review mechanism

  A platform-architect who returns a DEVOPS output has it gated by the SAME
  generic review-verdict mechanism the DESIGN wave uses -- only the wave name
  changes. This is the SSOT-not-duplication proof: the SAME generic core
  (ReviewVerdictGate) serves a SECOND wave with ZERO new verdict logic. The
  DEVOPS gate-out stack is authored ONCE in the canonical flavor-independent
  wave-contract registry (nWave/waves/devops.yaml) -- the registry HOME, NOT the
  flavor (brief §2/§3 slice-06 reconciliation: resolve_stack reads the registry
  as the SOLE gate-stack source, ADR-FLOW-006 D6). `verify-devops-review` reads
  the latest DevopsReviewVerdict ledger record, seals the feature-delta bytes
  (fail-closed default seal target, DDD-3), and REFUSES the return unless an
  artefact-current approved verdict exists.

  Driving surface (Mandate-13 driving-port-only): THREE real wired seams, no
  direct-domain import for business logic.
    * Layer 3 composition -- the REAL spine `wave_gate_stack_dispatch.resolve_stack`
      reading the SHIPPED `nWave/waves/devops.yaml` registry file (the entry the
      live SubagentStop gate-out caller uses, subagent_stop_service.py:311).
    * Layer 3 subprocess -- the REAL `des record-devops-review` / `des
      verify-devops-review` CLIs as black-box processes; the observable is the
      process exit code + the structured JSON verdict payload, nothing else.
    * Layer 3 composition (the literal-lift seam) -- the REAL
      `SubagentStopService.validate` built via the production composition root
      (`service_factory.create_subagent_stop_service`), driven with a `devops`
      wave-active floor; the observable is the service's HookDecision (allow vs
      block + reason). This is the brief slice-01 pt-4 deferral: the gate-out must
      fire via the REAL SubagentStop dispatch with the hardcoded "discuss" literal
      (subagent_stop_service.py:307/311/317) LIFTED to the active wave.

  Synthetic substrate (precondition state, NOT the SUT): a tmp work-tree carrying
  a `docs/feature/<id>/feature-delta.md` the verdict seals against + the
  AT-completion ledger the verdict is recorded into + a wave-active floor. No
  fixture authors the expected verdict -- the verdict, when present, is recorded
  through the REAL producer CLI.

  # AT-5: the SSOT-reuse proof -- the DEVOPS gate-out fact has ONE authoring locus
  #       (the canonical registry, mirroring DESIGN's design.yaml), and the WIRED
  #       spine resolves it FROM there to the same gate-id sequence. Two independent
  #       reads (registry-FILE-declared vs spine-resolved) agree, proving the
  #       registry -> dispatcher wiring for a SECOND wave with zero new dispatch code.
  @slice-02 @feature-f-design-devops-review-gate @AT-5 @contract-shape:bounded-change
  Scenario: The wired spine resolves the DEVOPS gate-out stack from the canonical registry
    Given the canonical wave-contract registry file for the DEVOPS wave is shipped in the repo
    When the dispatcher resolves the DEVOPS gate-out stack from the registry as the default source
    Then the resolved gate-id sequence equals the DEVOPS gate-out sequence the registry file declares
    And the resolved DEVOPS gate-out stack includes the verify-devops-review gate

  # AT-6 (error path): a DEVOPS return with NO recorded verdict -> the verify gate
  #       REFUSES it (INDETERMINATE "absent", exit 1). Same core as DESIGN,
  #       wave="devops". Absence reads as a veto, never as silent PASS.
  @slice-02 @feature-f-design-devops-review-gate @AT-6 @error @contract-shape:bounded-change
  Scenario: A DEVOPS output with no recorded review verdict is refused
    Given a DEVOPS feature with a feature-delta and no recorded review verdict
    When the DEVOPS review-verdict gate is verified for that feature
    Then the gate refuses the DEVOPS return with verdict indeterminate

  # AT-7 (happy path): after the platform-architect-reviewer's APPROVED verdict is
  #       recorded through the REAL producer CLI, the verify gate PASSES (exit 0,
  #       "no objection found") -- the record->verify loop closes end-to-end for a
  #       SECOND wave through the SAME core (the SSOT-reuse proof at the CLI surface).
  @slice-02 @feature-f-design-devops-review-gate @AT-7 @contract-shape:bounded-change
  Scenario: A DEVOPS output with an artefact-current approved verdict passes the gate
    Given a DEVOPS feature with a feature-delta and no recorded review verdict
    When the platform-architect-reviewer records an approved review verdict for that feature
    And the DEVOPS review-verdict gate is verified for that feature
    Then the gate passes the DEVOPS return with verdict pass

  # AT-8 (error path): a recorded needs-revision DEVOPS verdict -> the verify gate
  #       VETOES the return (exit 1, vetoed) -- a reviewer veto is mechanically honored.
  @slice-02 @feature-f-design-devops-review-gate @AT-8 @error @contract-shape:bounded-change
  Scenario: A DEVOPS output whose reviewer recorded needs-revision is vetoed
    Given a DEVOPS feature with a feature-delta and no recorded review verdict
    When the platform-architect-reviewer records a needs-revision review verdict for that feature
    And the DEVOPS review-verdict gate is verified for that feature
    Then the gate vetoes the DEVOPS return with verdict vetoed

  # AT-9 (the literal-lift seam, brief slice-01 pt-4 deferred to here): the DEVOPS
  #       gate-out fires via the REAL SubagentStop dispatch. A platform-architect
  #       returning a DEVOPS output (devops wave-active floor) with no recorded
  #       verdict is REFUSED by the live SubagentStopService -- which today keys on
  #       the hardcoded "discuss" literal and so lets a devops return pass. DELIVER
  #       must LIFT the literal to the active wave for this to go GREEN.
  #
  # NOTE (de-dup, carpaccio ceiling): the DISCUSS-regression safety of this same
  #       literal-lift (the lift must NOT break the DISCUSS gate-out) is ALREADY
  #       covered by the shipped DISCUSS gate-out ATs
  #       (tests/des/acceptance/oss_review_verdict_demotion/ +
  #       nwave_flow_v2_enforcement/), which run in this slice's regression check
  #       AND the feature-end full-suite -- a DISCUSS gate-out regression is caught
  #       there. AT-9 retains the UNIQUE coverage that the lift fires for DEVOPS;
  #       the DISCUSS-safety is the existing ATs' job, so no separate pin lives here.
  @slice-02 @feature-f-design-devops-review-gate @AT-9 @error @contract-shape:bounded-change
  Scenario: A DEVOPS return is mechanically gated by the live SubagentStop dispatch
    Given a DEVOPS wave-active floor and a feature-delta with no recorded review verdict
    When the platform-architect returns the DEVOPS output through the live SubagentStop gate
    Then the live gate blocks the DEVOPS return naming the absent devops review verdict
