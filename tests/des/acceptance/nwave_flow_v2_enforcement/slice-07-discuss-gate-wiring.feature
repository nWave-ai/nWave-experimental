@feature-nwave-flow-v2-enforcement @slice-07
Feature: Running the discuss wave is gated on entry and exit and the exit check re-earns its verdict
  As an nWave maintainer who trusts the spine to be deterministic
  I want a discuss wave to be blocked on ENTRY when its product preconditions are
    not met, and blocked on EXIT when its slice plan is not value-bearing, with the
    exit check re-runnable so a later wave re-earns the same verdict
  So that drift / unmet-preconditions / non-cohesive slice plans are caught
    MECHANICALLY at the wave boundaries, never on the LLM remembering to cooperate,
    and an ad-hoc agent call outside a wave is never interfered with

  # slice-07 of nwave-flow-v2-enforcement -- DISCUSS gate-IN (PreToolUse) +
  # structural gate-OUT (SubagentStop) + the §21.2.4 idempotent seam callable,
  # WIRED onto the slice-04 wave-active anchor. Follows the DESIGN slice-07
  # code-design verbatim (flow-v2 thesis: ATs FOLLOW the design SHAPE).
  #
  # DRIVING PORTS (Mandate-13 driving-port-only):
  #   * gate-IN  -> Layer 3 composition: the REAL PreToolUseService.validate via
  #     the production composition root, with a ProductSsotReader over a tmp
  #     project_root and a `discuss` wave-active floor armed under tmp_path.
  #   * gate-OUT -> Layer 3 composition: the REAL SubagentStopService.validate via
  #     the production composition root, with a FeatureDeltaReader over a tmp
  #     feature-delta. Observable = the HookDecision (allow vs block) + reason token.
  #   * seam     -> Layer 1 in-process pure callable DiscussGateOut.evaluate; the
  #     idempotence property (same content -> same token) IS the §21.2.4 re-earn
  #     contract, driven through the production composition root the same way the
  #     gate-OUT host invokes it (no direct-domain function-boundary test --
  #     it is driven via the SubagentStopService gate-OUT surface that calls it,
  #     and re-run via the SAME service path on identical content).
  #
  # The net-new domain VOs (DiscussGateInResult / DiscussGateOutResult), the
  # DiscussGateInToken / DiscussGateOutToken enums, the ProductSsotReader /
  # FeatureDeltaReader ports are NEVER imported-and-called at the step boundary --
  # the assertions are on the SERVICE's observable HookDecision (allow vs block +
  # the DISCUSS_GATE_IN_* / DISCUSS_GATE_OUT_* reason token).
  #
  # CONTRACT SHAPES (Mandate-14):
  #   gate-IN / gate-OUT scenarios are @real-io (real filesystem reads of SSOT
  #   docs / the feature-delta via real capability adapters) ->
  #   @contract-shape:bounded-change is wrong (no mutation); the gate is a
  #   DECISION over read state -> @contract-shape:unbounded-preservation (the gate
  #   VETOES or allows; it preserves the product/artefact, mutating nothing).
  #   The seam-idempotence property is a pure-function invariant ->
  #   @contract-shape:pure-function.
  #
  # DORMANT-SEAM RECONCILIATION (D11 / S3) -- net-new DESIGN driving-surface seams
  # each named + driven through the real entry point + observable-effect asserted:
  #   * `DiscussGateIn.evaluate` + `ProductSsotReader.ssot_present` threaded into
  #     the PreToolUseService gate-IN branch -> witnessed by AT-1 (REAL
  #     PreToolUseService.validate denies an entering discuss dispatch when SSOT
  #     preconditions are unmet; the deny + DISCUSS_GATE_IN_* reason is the effect).
  #   * `DiscussGateOut.evaluate` + `FeatureDeltaReader.read` threaded into the
  #     SubagentStopService gate-OUT branch -> witnessed by AT-2 (REAL
  #     SubagentStopService.validate blocks a discuss-wave return over a non-
  #     value-bearing slice plan; the block + DISCUSS_GATE_OUT_* reason is the
  #     effect) and AT-4 (an unreadable delta -> INDETERMINATE degrade-LOUD block).
  #   * the §21.2.4 seam re-earn property -> witnessed by AT-3 (the SAME gate-OUT
  #     service path re-run on identical feature-delta content yields the IDENTICAL
  #     verdict token -- idempotent, re-runnable).
  #
  # RED-for-right-reason (pre-DELIVER fail-for-right-reason gate): the net-new
  # `discuss_gate.py` cores + the two capability ports + their wiring into
  # PreToolUseService / SubagentStopService do NOT exist at HEAD. The production
  # factories build the services WITHOUT a DISCUSS gate-IN / gate-OUT branch, so:
  #   - AT-1: the entering discuss dispatch is ALLOWED where a gate-IN DENY is
  #     expected (unmet SSOT preconditions) -> semantic AssertionError.
  #   - AT-2: the discuss-wave return is ALLOWED where a gate-OUT BLOCK is expected
  #     (infra-only slice plan) -> semantic AssertionError.
  #   - AT-3: with no gate-OUT branch, the two runs do not produce a
  #     DISCUSS_GATE_OUT_* verdict to compare -> semantic AssertionError.
  #   - AT-4: an unreadable delta is not degraded-LOUD (no gate-OUT branch) ->
  #     semantic AssertionError.
  # No @skip, no import / collection / setup error. GREEN once DELIVER ships the
  # cores + capability adapters + the two service branches.
  #
  # SUT STATE MACHINE (C2 -- documented in the AT module docstring):
  #   gate-IN states  = {DISCUSS_ENTERING}. event product-model-absent
  #     (MIGRATION_UNMET) -> ADVISORY (allow, soft-gate, slice-05 declass);
  #     event required-doc-missing (MISSING_SSOT) -> VETO (block); event
  #     no-wave-armed -> S1 allow (non-interference, AT-5 illegal-event-from-
  #     no-wave: the gate-IN must NOT fire when no discuss wave is active).
  #   gate-OUT states = {DISCUSS_RETURNING}. event slice-plan-rejected -> VETO;
  #     event delta-unreadable -> INDETERMINATE (degrade-LOUD); event value-bearing
  #     -> PASS (no objection found, NOT a GO).

  # ---- gate-IN (DISCUSS entry) ------------------------------------------------

  # AT-1 -- the gate-IN greenfield ADVISORY (slice-05 declass: ADR-FLOW-002 Q4).
  # Net-new seam: DiscussGateIn.evaluate + ProductSsotReader.ssot_present threaded
  # into PreToolUseService. A greenfield entry (docs/product/ absent ->
  # MIGRATION_UNMET) is a DECLASSED veto: the gate ALLOWS the entry and surfaces a
  # soft advisory rather than hard-blocking (wave-optionality model -- DISCUSS is
  # optional, greenfield bootstraps via DIVERGE / on user ratification). This is
  # the ONLY gate-IN case that flips BLOCK->ADVISORY; MISSING_SSOT (AT-8) and
  # INDETERMINATE still hard-veto (Invariant 2, §17 no-silent-pass).
  @slice-07 @driving_port @real-io @us-gate-in @contract-shape:unbounded-preservation
  Scenario: Entering the discuss wave is allowed with an advisory when the product model is absent
    Given the discuss wave is active in a project whose product preconditions are unmet
    When the wave-entering dispatch is checked by the gate
    Then the entry is allowed as a greenfield advisory rather than vetoed

  # AT-5 -- the gate-IN non-interference complement (§22.0 / K2). Illegal-event-
  # from-no-wave: an ad-hoc dispatch when NO wave is armed must NOT trigger the
  # discuss gate-IN even though the same project preconditions are unmet. This is
  # the same scenario FAMILY as AT-1 (the gate-IN decision surface), kept thin to
  # respect the carpaccio ceiling -- it pins the consent-gate (D-nonintf).
  @slice-07 @driving_port @real-io @us-gate-in @contract-shape:unbounded-preservation
  Scenario: An ad-hoc dispatch is never blocked by the discuss gate when no wave is active
    Given no wave is active in a project whose product preconditions are unmet
    When a bare non-wave dispatch is checked by the discuss gate-in
    Then the entry is allowed and left completely untouched

  # AT-7 -- the jobs-slot-is-YAML correctness fix. The JOB registry in this repo
  # is the STRUCTURED docs/product/jobs.yaml (wired into validate_ssot_propagation
  # + the discuss/diverge/product-owner skills+agents); forcing the gate to demand
  # jobs.md is pure churn. The gate-IN jobs slot MUST be satisfied by jobs.yaml.
  # Net-new seam witnessing: the REAL PreToolUseService gate-IN branch reads the
  # product SSOT via the production ProductSsotFilesystemReader; with vision+
  # backlog+glossary as .md AND jobs as jobs.yaml (NO jobs.md), the gate-IN finds
  # NO missing SSOT and ALLOWS the entering discuss dispatch.
  #
  # RED-for-right-reason (active-RED now): at HEAD the adapter's _REQUIRED_DOCS
  # hard-codes "jobs.md" and reports jobs=present["jobs.md"], so a docs/product/
  # holding jobs.yaml (and no jobs.md) yields jobs=False -> missing_docs() = a
  # jobs entry -> DiscussGateIn.evaluate -> MISSING_SSOT -> the service BLOCKS the
  # entry. This scenario asserts ALLOW, so it fails NOW with a semantic
  # AssertionError ("gate-IN must ALLOW ... jobs satisfied by jobs.yaml ... it
  # returned 'block'"). GREEN once the crafter points the adapter's jobs slot at
  # jobs.yaml. No @skip, no import/collection/setup error.
  @slice-07 @driving_port @real-io @us-gate-in @contract-shape:unbounded-preservation
  Scenario: Entering the discuss wave is allowed when the jobs registry is YAML rather than markdown
    Given the discuss wave is active in a project whose jobs registry is provided as YAML
    When the wave-entering dispatch is checked by the gate
    Then the entry is allowed because the product preconditions are satisfied

  # AT-8 -- the entirely-absent-jobs regression (the gate must not silently pass).
  # vision+backlog+glossary present, but NO jobs doc at all (neither .md nor
  # .yaml). The gate-IN MUST still VETO with a named precondition reason -- the
  # jobs-format correctness fix must not weaken the gate into ignoring an absent
  # jobs registry. This stays GREEN at HEAD (the absent jobs slot already vetoes)
  # and MUST stay GREEN after the crafter's fix (post-fix the gate names the
  # missing jobs.yaml instead of jobs.md; the BLOCK + named token are invariant).
  @slice-07 @driving_port @real-io @us-gate-in @error @contract-shape:unbounded-preservation
  Scenario: Entering the discuss wave is still blocked when the jobs registry is absent entirely
    Given the discuss wave is active in a project whose jobs registry is missing entirely
    When the wave-entering dispatch is checked by the gate
    Then the entry is blocked
    And the block names the unmet discuss precondition so it cannot pass as a silent success

  # ---- gate-OUT (DISCUSS exit) ------------------------------------------------

  # AT-2 -- the gate-OUT structural VETO. Net-new seam: DiscussGateOut.evaluate +
  # FeatureDeltaReader.read threaded into SubagentStopService. The MECC floor
  # (validate_slice_plan_content != accepted, incl. slice-06 infra-only cohesion)
  # is reused verbatim; the AT seeds an infra-only slice plan and asserts the
  # DISCUSS_GATE_OUT_SLICE_PLAN_REJECTED veto.
  @slice-07 @driving_port @real-io @us-gate-out @error @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave is blocked when the slice plan carries no user-visible value
    Given a discuss-wave return whose feature-delta slice plan is infrastructure-only
    When the discuss-wave return is checked by the gate
    Then the handoff is blocked
    And the block names the rejected slice plan so it cannot pass as a silent success

  # AT-6 -- the gate-OUT PASS complement. A value-bearing slice plan WITH an
  # approved product-owner review -> PASS ("no objection found", NOT a GO --
  # §22.0 asymmetric authority). Same scenario FAMILY as AT-2 (the gate-OUT
  # decision surface); pins that the MECC floor only vetoes the structurally-
  # certain case and otherwise allows the wave to exit.
  #
  # ARRANGEMENT HARDENED (oss-review-verdict-demotion S3, 2026-06-11): the
  # legal discuss exit path requires BOTH a value-bearing slice plan AND a
  # recorded approved product-owner review. Pre-S3 this scenario passed ONLY
  # through the now-deleted unarmed-gate escape (no record + no key -> silent
  # allow); post-S3 the review gate is always armed, so the approved review is
  # an explicit precondition of the legal exit -- which is truer to the
  # production contract and is documented here as a first-class Given.
  @slice-07 @driving_port @real-io @us-gate-out @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave is allowed when the slice plan carries user-visible value
    Given a discuss-wave return whose feature-delta slice plan is value-bearing
    And the product owner has recorded an approved review of the current artefact
    When the discuss-wave return is checked by the gate
    Then the handoff is allowed as no objection found

  # AT-4 -- the gate-OUT INDETERMINATE degrade-LOUD floor (§17 no-silent-pass).
  # An absent / unreadable feature-delta is NEVER coerced to PASS -- it blocks
  # degrade-LOUD. Net-new seam witnessing: the FeatureDeltaReader returns None ->
  # DiscussGateOut.evaluate decides INDETERMINATE -> the service blocks.
  @slice-07 @driving_port @real-io @us-gate-out @error @contract-shape:unbounded-preservation
  Scenario: Exiting the discuss wave blocks degrade-loud when the feature-delta cannot be read
    Given a discuss-wave return whose feature-delta cannot be read
    When the discuss-wave return is checked by the gate
    Then the handoff is blocked degrade-loud rather than passed silently

  # ---- seam re-earn (§21.2.4 idempotence) -------------------------------------

  # AT-3 -- the §21.2.4 seam re-earnability property. The gate-OUT verdict is
  # RE-EARNED, never inherited: re-running the SAME gate-OUT service path on
  # IDENTICAL feature-delta content yields the IDENTICAL verdict token. This is a
  # pure-function invariant over the artefact content; it is the empirical anchor
  # for "a future DESIGN gate-IN consumes the same callable and re-earns the
  # verdict from the sealed artefact". Driven through the same SubagentStopService
  # gate-OUT surface (NOT a direct-domain function-boundary call).
  @slice-07 @driving_port @real-io @us-seam @property @contract-shape:pure-function
  Scenario: The discuss gate-out verdict is re-earned identically when re-run on the same artefact
    Given a discuss-wave return whose feature-delta slice plan is infrastructure-only
    When the discuss-wave return is checked by the gate twice on the identical artefact
    Then both checks yield the identical gate-out verdict
