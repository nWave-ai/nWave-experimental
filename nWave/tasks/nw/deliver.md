---
description: "Orchestrates the full DELIVER wave end-to-end (roadmap > execute-all > finalize). Use when all prior waves are complete and the feature is ready for implementation."
argument-hint: '[feature-description] - Example: "Implement user authentication with JWT"'
---

<!-- gates-ref: deliver -->
<!-- outputs-ref: deliver -->

The DELIVER gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/deliver.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This prose does not re-enumerate the gate stack inline; it POINTS at the registry.

# NW-DELIVER: Complete DELIVER Wave Orchestrator

**Wave**: DELIVER (wave 6 of 6)|**Agent**: Main Instance (orchestrator)|**Command**: `/nw-deliver "{feature-description}"`

## Overview

Orchestrates complete DELIVER wave: feature description → production-ready code with mandatory quality gates. You (main Claude instance) coordinate by delegating to specialized agents via Task tool. Final wave (DISCOVER > DIVERGE > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER).

Sub-agents cannot use Skill tool or `/nw:*` commands. You MUST:
- Read the relevant command file and embed instructions in the Task prompt
- Remind the crafter to load its skills as needed for the task (skill files are at `~/.claude/skills/nw/{agent-name}/`)

## CRITICAL BOUNDARY RULES

1. **NEVER implement steps directly.** ALL implementation MUST be delegated to the selected crafter (@nw-software-crafter or @nw-functional-software-crafter per step 1.5) via Task tool with DES markers. You are ORCHESTRATOR — coordinate, not implement.
2. **NEVER write phase entries to execution-log.json.** Only the crafter subagent that performed TDD work may append entries.
3. **Extract step context from roadmap.json ONLY for Task prompt.** Grep roadmap for step_id ~50 lines context, extract (name|criteria|files_to_modify) per `nWave/templates/roadmap-schema.json`, pass in DES template.

**DES monitoring is non-negotiable.** Circumventing DES — faking step IDs, omitting markers, or writing log entries manually — is a **violation that invalidates the delivery**. DES detects unmonitored steps and flags them; finalize **blocks** until every flagged step is re-executed through a properly instrumented Task. There is no workaround: unverified steps cannot pass integrity verification, and the delivery cannot be finalized. Without DES monitoring, nWave cannot **verify** TDD phase compliance. For non-deliver tasks (docs, research, one-off edits): `<!-- DES-ENFORCEMENT : exempt -->`.

## Workflow Mode Dispatch (classic vs atdd_pure) <!-- mode-ref-ok -->

Before any phase work, read `.nwave/config.yaml` key `workflow.mode`. Two execution paths — per-mode descriptor + DELIVER phase shape projected from the mode registry, never hand-written here: <!-- mode-ref-ok -->

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
- `classic` — Roadmap-driven 3-phase TDD canon (ADR-025); roadmap.json + execution-log.json are the audit. DEPRECATED per ADR-028 D6 — fallback under explicit per-instance authorization only.
  Deliver phase shape: `RED -> GREEN -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

Read precedence: `.nwave/config.yaml:workflow.mode` → if missing, fall back to `classic`. Mid-feature mode switch is forbidden (a feature is born in one mode and dies in it). On the per-slice spine, the classic 3-phase orchestration in §Orchestration Flow Phase 2 is REPLACED by the per-slice sequence below; all other phases (refactor, review, mutation, integrity, finalize) still run as written. <!-- mode-ref-ok -->

## ATDD-Pure 7-Phase Sequence (A→G) — invoked when workflow.mode = atdd_pure <!-- mode-ref-ok -->

Reference: ADR-027 §Decision · plan v3 §4 §7 · domain types `src/des/domain/atdd_pure_phases.py`.

Replace the per-step `RED→GREEN→COMMIT` dispatch (Phase 2 step c2) with the following per-step A→G sequence. One Agent invocation per phase per step (separation-of-concerns enforced).

| Phase | Owner | Action | Gate |
|-------|-------|--------|------|
| A_GREEN_ATS | crafter (instance #1) | Make all DISTILL-authored ATs pass, NO defensive code beyond AT-driven need | All ATs green |
| B_COVERAGE_CLEANUP | same crafter instance | Coverage-driven dead-code elimination | ≥90% line+branch OR justified misses documented in commit body |
| C_REVIEWER_AUDIT | reviewer | 15-item AT-completeness audit via `nw-at-completeness-check` | `PhaseCReviewerVerdict` emitted; verdict_hash optional |
| D_GAP_ROUTING | orchestrator | Route per `ATGapKind` (see §Phase D Routing below) | exactly one Routing decision recorded |
| E_BATCH_REFACTOR | **crafter-B (separate instance, distinct agent_instance_id)** | L1-L6 batch refactor per `feedback_refactor_batch_when_test_suite_slow_2026_05_19` | Tests stay green |
| F_FINAL_REVIEW | reviewer | Code review + refactor green check | `PhaseFReviewerVerdict` with MANDATORY verdict_hash (keyless content seal) |
| G_COMMIT | crafter | Conventional commit with `Step-Id:` + `Reviewed-by:` trailers (Reviewed-by carries verdict_hash) | Ledger record present and audited via verify-commit-trailers |

### Crafter-matches-design gate-OUT (D2 review-rubric leg)

Gate-IN: the A_GREEN_ATS dispatch consumes the bundle (AT + `[REF] Code-Design` contract + architecture + the DISTILL AT review) — the crafter implements MATCHING the declared design, not a re-invented structure that merely passes the ATs.

Gate-OUT adds the matches-design review-rubric leg to F_FINAL_REVIEW: the crafter-matches-design gate compares the implementation public surface against the design declared public contract and emits a §17 verdict. The verdict map (reuses the five-verdict GateVerdict SSOT — no sixth verdict):

- **PASS** — the implementation public symbol-set is equal to the design's declared public contract → proceed (no-veto, not authorize).
- **FAIL → redo-in-wave** — an undeclared public symbol or a missing declared one fails the gate at gate-OUT and is routed to redo in-wave (privatize/remove the undeclared symbol, or implement the missing declared one). Private structure is out of scope: a new private symbol or Extract-Method refactor below the public boundary is never a conformance violation (C4).
- **UNVERIFIED** — the design contract is prose-only and the rubric suspects a drift it cannot mechanically confirm: NAME the suspected drift, propose `/nw-design`, LOUD advisory, then escalate fail-closed. Never silent-pass.
- **NOT_APPLICABLE** — a removal-only slice with no public contract to diff: proceed and record the N/A explicitly (not a FAIL).
- **INDETERMINATE** — the crafter-matches-design mechanism that cannot run degrades LOUD as INDETERMINATE never a silent pass (the per-language AST adapter absent for the target language, or the `[REF] Code-Design` heading malformed / the impl modules unparseable). Degrade-LOUD and escalate now.

The mechanical public-surface diff (the `CodeFactPort AstAdapter`-backed form) is DESIGNED-NOT-BUILT here — feature 6 swaps it in behind this same review-rubric seam without re-authoring; the interim form is the prose review-rubric diffing against the `[REF] Code-Design` contract.

### Phase D Routing (orchestrator decision rules)

Source of truth: plan v3 §7.2. Implementation outline:

1. **BLOCKER severity in any gap** → emit `DeliverBlocker`, halt sequencer exit 42 `ARCHITECTURE_GAP_ESCALATION`, return `HUMAN_ESCALATION`.
2. **Cycle exhaustion** (`ctx.phase_d_cycle_count > 2`) → emit `DeliverCycleExhausted`, halt exit 42 `CYCLE_EXHAUSTION`, return `HUMAN_ESCALATION`.
3. **Wall-clock timeout** (`ctx.wall_clock_s > 14400` i.e. 4h) → emit `DeliverTimeoutExceeded`, checkpoint state, halt exit 42 `DELIVER_TIMEOUT`, return `CHECKPOINT_TIMEOUT`. Resume via `/nw-resume-deliver`.
4. **Second-order architecture-scope-miss** (≥2 gaps sharing a `scenario_class` mapping to a component absent from DESIGN) → emit `ArchitectureScopeMissDetected`, return `REROUTE_DESIGN`.
   - **Crafter-matches-design DESIGN-DEFECT bump** (K5, OB-2 named-contradiction witness): when a slice cannot pass because a named contract self-contradiction routes a recorded DESIGN-DEFECT bump to DESIGN that the human disposes instead of being patched in place — this EXTENDS the existing `REROUTE_DESIGN` substrate, NOT a new routing primitive nor a sixth verdict. The witness names the contradiction (e.g. an error-encoding requiring a field the declared return-type never declares); the orchestrator emits the recorded `DESIGN-DEFECT`, returns `REROUTE_DESIGN`, and the human disposes the bump (Invariant 1: a control only vetoes, the human authorizes). Distinct from redo-in-wave: a divergence the crafter can fix in-wave (undeclared/missing public symbol) is FAIL→redo; a contract the crafter CANNOT satisfy because it self-contradicts is the bump.
5. **`SPECIFICATION_AMBIGUITY` gaps** → emit `SpecificationAmbiguityDetected`, derive upstream wave from gap kind (C2→DISCUSS state-machine, C5→DESIGN mode-flags, C7→DEVOPS env contract), return `REROUTE_DISCUSS` | `REROUTE_DESIGN` | `REROUTE_DEVOPS` accordingly.
6. **`AT_GAP_IN_DELIVERY_SCOPE` only** → emit `AcceptanceTestGapIdentified`, increment `phase_d_cycle_count`, return `RELOOP_A` (re-enter Phase A with refined ATs from acceptance-designer).
7. **No gaps** → return `PROCEED_TO_E_BATCH_REFACTOR`.

Sentinel values map to `PhaseExit` enum in `src/des/domain/atdd_pure_phases.py`. Use those names verbatim in audit-log events.

### Separation Enforcement (Phase A vs Phase E)

Phase E dispatch MUST use a SEPARATE crafter instance from Phase A (Ale 2026-05-19 mandate). Enforcement:

1. Emit `Phase E dispatch` event with `agent_instance_id` distinct from the Phase A dispatch's id.
2. Pre-flight check: orchestrator refuses to dispatch Phase E with the same `agent_instance_id` as the Phase A entry recorded in `execution-log.json`.
3. Rationale: review independence — refactor by the original implementer rubber-stamps their own bias; a fresh crafter exposes structural smells.

### Verdict-Hash Trailer (Phase F → G)

Reference: plan v3 §8. Phase F reviewer verdict MUST be paired with a `Reviewed-by: <agent>:<verdict-hash>` trailer. Phase G commit message embeds this trailer verbatim. The verdict-hash is the keyless content seal produced by `des.domain.at_review_signing.canonical_at_review_json`. Verification: `src/des/cli/verify_commit_trailers.py` audits the slice's ledger record (exit 45 on refusal).

### Telemetry per Phase Boundary (atdd_pure mode) <!-- mode-ref-ok -->

Each phase A-G emits one JSONL event at PhaseEntered and PhaseCompleted to `nWave/telemetry/wave-time-token-telemetry/pilot/{feature_id}.jsonl`:

```json
{
  "telemetry_schema_version": "1.0.0",
  "source": "des_sequencer",
  "event": "PhaseEntered",
  "feature": "{feature_id}",
  "phase": "C_REVIEWER_AUDIT",
  "wall_clock_s": 42.3,
  "token_cost": 8421,
  "reviewer_findings": 3,
  "cycle_n": 1,
  "verdict_hash": "ab12cd34...",
  "timestamp": "2026-05-19T18:42:13Z"
}
```

Fields `reviewer_findings`, `cycle_n`, `verdict_hash` are null outside their respective phases. Validator: `scripts/validation/validate_atdd_pure_telemetry.py`.

### Phase G Post-Commit: Falsifier-Gate Hook

After Phase G commit completes, invoke `python scripts/automation/atdd_pure_falsifier_gate.py` (Phase 5 deliverable per plan v3 §4.5). Behavior:

- Reads N=3 latest pilot JSONL records.
- ANY threshold breach (median wall-clock > 1.3× target | reviewer findings median > 12 | post-deploy defect rate > 2× classic | Phase D cycle rate median ≥ 2.0) → patch `.nwave/config.yaml:workflow.mode = classic`, emit `FalsifierGateTripped`, exit 42. <!-- mode-ref-ok -->
- Otherwise → emit `FalsifierGateHealthy`, exit 0.

Falsifier-gate exit 42 blocks subsequent CI release steps; operator review required before next pilot feature.

## Skill Loading (ATDD-pure additions)

When `workflow.mode = atdd_pure`, the orchestrator MUST embed skill-load directives in every crafter and reviewer dispatch prompt. <!-- mode-ref-ok -->
The mode-conditional skill set per agent is declared by the mode registry `skill_load_set` (projected into each agent spec's GENERATED skill-load region — the registry, never this guide, is the author): embed a directive to load every skill the registry declares for the dispatched agent at its phase entry.
| E | `nw-refactor` | `~/.claude/skills/nw-refactor/SKILL.md` |
| F | `nw-review` | `~/.claude/skills/nw-review/SKILL.md` |

Classic mode skill loading is unchanged (per existing Task Invocation Pattern below).

## Rigor Profile Integration

Before dispatching any agent, read the rigor profile from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

**How rigor affects deliver phases:**

| Setting | Effect |
|---------|--------|
| `agent_model` | Pass as `model` parameter to all Task tool invocations for crafter agents. If `"inherit"`, omit `model` parameter (Task tool inherits from session). |
| `reviewer_model` | Pass as `model` parameter to reviewer Task invocations. If `"skip"`, skip Phase 4 entirely. |
| `review_enabled` | If `false`, skip Phase 4 (Adversarial Review). |
| `double_review` | If `true`, run Phase 4 twice with separate review scopes. |
| `tdd_phases` | Pass to crafter in DES template. Replace `# TDD_PHASES` section with the configured phases. The 3-phase canon (ADR-025) is `[RED, GREEN, COMMIT]`; legacy 5-phase contract is `[PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]`. If lean profile (`[RED_UNIT, GREEN]` legacy or `[RED, GREEN]` canon), omit setup/commit instructions accordingly. |
| `refactor_pass` | If `false`, skip Phase 3 (Complete Refactoring). |
| `mutation_enabled` | If `false`, skip Phase 5 regardless of mutation strategy in CLAUDE.md. |

**Task invocation with rigor model:**
```python
Agent(
    subagent_type="{agent}",
    model=rigor_agent_model,  # omit this line entirely if "inherit"
    max_turns=45,
    prompt=...,
)
```

## Prior Wave Consultation

Before beginning DELIVER work, read targeted prior wave artifacts. DISTILL is the major synthesis point — its acceptance tests encode all prior wave decisions into executable specifications.

1. **DISCOVER** (skip): Synthesized into DISCUSS, then into DISTILL acceptance tests.
2. **DISCUSS** (skip): Synthesized into DISTILL acceptance tests. If needed during implementation, read specific files on demand.
3. **DESIGN** (structural context): Read from `docs/feature/{feature-id}/design/`:
   - `architecture-design.md` — component structure and C4 diagrams guide implementation
   - `component-boundaries.md` — dependency-inversion boundaries
   - `wave-decisions.md` — paradigm, tech stack, upstream changes
4. **DEVOPS** (skip): Infrastructure setup is independent of implementation. Read `wave-decisions.md` only if test environment issues arise.
5. **DISTILL** (primary input): Read all files in `docs/feature/{feature-id}/distill/` — test scenarios, walking skeleton, acceptance review are the authoritative specification for implementation.

**READING ENFORCEMENT**: You MUST read every file listed in Prior Wave Consultation above using the Read tool before proceeding. After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes implementation disconnected from architecture and acceptance tests.

Additionally, check for `upstream-changes.md` and `upstream-issues.md` in DESIGN and DISTILL directories. If unresolved issues exist, flag them to the user before starting implementation. Do not implement against contradictory specifications.

**On-demand escalation**: If during implementation a crafter encounters ambiguity not resolved by DISTILL tests or DESIGN architecture, the orchestrator reads the specific prior wave file referenced in wave-decisions.md — never re-reads entire directories.

## Document Update (Back-Propagation)

When DELIVER implementation reveals gaps or contradictions in prior waves:
1. Document findings in `docs/feature/{feature-id}/deliver/upstream-issues.md`
2. Reference the original prior-wave document and describe the issue
3. If implementation requires deviating from architecture or requirements, document the deviation and rationale
4. Resolve with user before continuing past the affected step

## Orchestration Flow

```
INPUT: "{feature-description}"
  |
  0. Read rigor profile from .nwave/des-config.json (default: standard)
     Store: agent_model|reviewer_model|tdd_phases|review_enabled|double_review|mutation_enabled|refactor_pass
  |
  0.5. Prior Wave Consultation (see section above)
     Read DISTILL (all) + DESIGN (architecture + boundaries + wave-decisions)|flag contradictions|resolve before proceeding
     Summarize key design decisions into a reusable DESIGN_CONTEXT block for crafter dispatch (component structure, boundaries, tech choices, data models). This summary is injected into every crafter's DES template so sub-agents make implementation decisions aligned with the architecture.
  |
  1. Parse input|derive feature-id (kebab-case)|create docs/feature/{feature-id}/deliver/
     a. Create execution-log.json if missing via CLI:
        des init-log --project-dir docs/feature/{feature-id}/deliver --feature-id {feature-id}
        Do NOT create execution-log.json directly with Write — use the CLI only.
     b. Create deliver session marker: .nwave/des/deliver-session.json
  |
  1.5. Detect development paradigm
     a. Read project CLAUDE.md (project root, NOT ~/.claude/CLAUDE.md)
     b. Search "## Development Paradigm"
     c. Found → extract paradigm: "functional"/@nw-functional-software-crafter or "object-oriented"/@nw-software-crafter (default)
     d. Not found → ask user "OOP or Functional?"|offer to write to CLAUDE.md
     e. Store selected crafter for all Phase 2 dispatches
     f. Functional → property-based testing default|@property tags signal PBT|example-based = fallback
  |
  1.6. Detect mutation testing strategy
     a. Same CLAUDE.md|search "## Mutation Testing Strategy"
     b. Found → extract: per-feature|nightly-delta|pre-release|disabled
     c. Not found → default "per-feature"
     d. Log strategy for traceability
     Note: Strategy locks at deliver start. CLAUDE.md edits during delivery take effect next run.
  |
  2. Phase 1 — Roadmap Creation + Review
     a. Skip if docs/feature/{feature-id}/deliver/roadmap.json exists with validation.status == "approved"
        IMPORTANT: Only check the deliver/ subdirectory. If roadmap.json is found in design/ instead,
        MOVE it to deliver/ and log warning: "Roadmap relocated from design/ to deliver/ — was created in wrong wave."
     b. @nw-solution-architect creates roadmap.json (read ~/.claude/skills/nw-roadmap/SKILL.md)
        Step IDs: NN-NN format (01-01, 01-02, 02-01). 01-A or 1-1 = invalid.
        DISTILL LINKAGE: If docs/feature/{feature-id}/distill/ exists, the architect MUST populate
        test_file and scenario_name fields in each roadmap step from the distilled acceptance tests.
        Each step maps to one acceptance scenario (1 Step = 1 Scenario = 1 TDD Cycle).
     c. Automated quality gate (see below)
     d. @nw-software-crafter-reviewer reviews (read ~/.claude/skills/nw-review/SKILL.md)
     e. Retry once on rejection → stop for manual intervention
  |
  3. Phase 2 — Execute All Steps (ATOMIC DISPATCH)
     **INVARIANT: 1 Agent invocation = 1 roadmap step. No exceptions.**
     A single Agent MUST NEVER execute more than one step. Each step gets its own
     Agent invocation with exactly one DES-STEP-ID. Batching multiple steps into
     one Agent prompt is a VIOLATION — DES integrity verification will reject it.
     a. Extract steps from roadmap.json in dependency order (respect `depends_on` fields).
        PREREQUISITE: Phase 1 roadmap quality gate validates the dependency graph (no cycles,
        all `depends_on` references resolve to existing step IDs). Phase 2 assumes validation passed.
     b. Check execution-log.json for prior completion — skip steps with COMMIT/PASS
     c. **Dispatch loop** — for EACH pending step:
        c1. Extract step context from roadmap (grep step_id ~50 lines, extract fields)
        c2. Dispatch ONE Agent with ONE DES-STEP-ID using DES Prompt Template from execute.md
            Use crafter from step 1.5|@nw-functional-software-crafter → PBT default|@property tags signal PBT
            Include DES markers (DES-VALIDATION|DES-PROJECT-ID|DES-STEP-ID) + all mandatory sections
            OUTCOME_RECORDING: agents use DES CLI (des log-phase)|CLI bypass → SubagentStop hook corrects timestamps
        c3. WAIT for Agent to complete before dispatching next step
        c4. Verify COMMIT/PASS in execution-log.json for THIS step
        c5. Missing phase → RE-DISPATCH a NEW agent for the SAME step. NEVER write entries yourself.
        c6. Wiring smoke check: verify every new function defined in production files
            has at least one call site in production code (not just tests).
            Flag "function X defined but only called from tests" → re-dispatch crafter.
        c7. Acceptance test gate (two levels):
            - Step-scoped: run the acceptance test for THIS step (from `test_file` + `scenario_name` in roadmap).
              If it fails, fix before proceeding.
            - Feature-scoped regression: run ALL feature acceptance tests (tests/acceptance/{feature-id}/).
              If a test unrelated to this step fails, it means this step introduced a regression — fix before proceeding.
            Do NOT skip or defer failing tests at either level.
        c8. On failure → STOP. Do not proceed to next step.
     d. **Parallel dispatch** — BLOCKED until DES CLI implements file locking.
        The DES CLI (log_phase) uses read/modify/write on execution-log.json without serialization.
        Concurrent agents cause last-write-wins data loss. Sequential dispatch (c1-c8) is
        the ONLY safe mode. When file locking is implemented, parallel rules will be:
        d1. Steps with disjoint `depends_on` chains AND disjoint `files_to_modify` may run concurrently
        d2. Launch one Agent per step (never batch) using run_in_background=true
        d3. Wait for ALL agents in the group to complete
        d4. Run verification (c4-c7) for each step in the group
        d5. On ANY failure in the group → STOP. Do not proceed to next group.
        d6. Parallel group timeout: if ANY agent times out → wait for remaining agents to
            finish or timeout → check execution-log.json for partial progress → re-dispatch
            only timed-out steps individually. Do NOT re-run completed steps in the group.
     e. Timeout recovery: GREEN completed → resume (~5 turns)|GREEN partial → resume|Otherwise → restart higher max_turns
  |
  4. Phase 3 — Complete Refactoring (L1-L4) [SKIP if rigor.refactor_pass = false]
     a. Collect modified files: git diff --name-only {base-commit}..HEAD -- '*.py' | sort -u
        Split: PRODUCTION_FILES (src/) | TEST_FILES (tests/)
     b. /nw-refactor {files} --levels L1-L4 via {selected-crafter} with DES orchestrator markers:
        <!-- DES-VALIDATION : required -->|<!-- DES-PROJECT-ID : {feature-id} -->|<!-- DES-MODE : orchestrator -->|<!-- DES-WAVE: deliver -->
     c. All tests green after each module
  |
  5. Phase 4 — Adversarial Review [SKIP if rigor.review_enabled = false]
     a. If rigor.reviewer_model = "skip" → SKIP phase entirely
     b. /nw-review @nw-software-crafter-reviewer implementation "{execution-log-path}"
        Use model=rigor.reviewer_model for reviewer Task invocation
        Include DES orchestrator markers (same as Phase 3)
     c. If rigor.double_review = true → run review a second time with different scope focus
     d. Scope: ALL files modified during feature|includes Testing Theater 7-pattern detection
     e. One revision pass on rejection → proceed
  |
  6. Phase 5 — Mutation Testing [SKIP if rigor.mutation_enabled = false]
     If rigor.mutation_enabled = false → SKIP regardless of CLAUDE.md strategy
     Otherwise, apply CLAUDE.md strategy:
     per-feature → gate ≥80% kill rate (read ~/.claude/skills/nw-mutation-test/SKILL.md)
     nightly-delta → SKIP|log "handled by CI nightly pipeline"
     pre-release → SKIP|log "handled at release boundary"
     disabled → SKIP|log "disabled per project configuration"
  |
  7. Phase 6 — Deliver Integrity Verification
     a. des verify-integrity docs/feature/{feature-id}/deliver/
     b. Exit 0 → proceed|Exit 1 → STOP, read output
     c. No entries = not executed through DES|Partial = incomplete TDD
     d. Violations → re-execute via Task with DES markers|Only proceed after pass
  |
  8. Phase 7 — Finalize
     a. @nw-platform-architect archives to docs/evolution/ (read ~/.claude/skills/nw-finalize/SKILL.md)
     b. Commit + push|rm -f .nwave/des/deliver-session.json .nwave/des/des-task-active
  |
  9. Phase 8 — Retrospective (conditional)
     Skip if clean execution|@nw-troubleshooter 5 Whys on issues found
  |
  10. Phase 9 — Report Completion
      Display summary: phases|steps|reviews|artifacts|Return to DISCOVER for next iteration
```

## Orchestrator Responsibilities

Follow this flow directly. Do not delegate orchestration.

Per phase:
1. Read the relevant command file (paths listed above)
2. Extract instructions and embed them in the Task prompt
3. Include task boundary instructions to prevent workflow continuation
4. Verify output artifacts exist after each Task completes
5. Update .develop-progress.json for resume capability

## Task Invocation Pattern

DES markers required for step execution. Without markers → unmonitored. Full DES Prompt Template in `~/.claude/skills/nw-execute/SKILL.md`.

When dispatching steps via Agent tool, use the COMPLETE DES template from execute.md verbatim. Fill all `{placeholders}` from roadmap step context. The DES hook validates the prompt BEFORE the sub-agent starts — abbreviated prompts that delegate template reading to the sub-agent will be BLOCKED.

Copy the template from the code block in `~/.claude/skills/nw-execute/SKILL.md` (between ``` markers), fill placeholders, and pass as the Agent prompt. The template sections are defined in execute.md — do not hardcode the list here.

```python
Agent(
    subagent_type="{agent}",
    model=rigor_agent_model,  # omit if "inherit"
    prompt=f'''
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {project_id} -->
<!-- DES-STEP-ID : {step_id} -->
<!-- DES-WAVE: deliver -->

# DES_METADATA
Step: {step_id}
Feature: {project_id}
Command: /nw-execute

# AGENT_IDENTITY
Agent: {agent}

# SKILL_LOADING
Before starting TDD phases, read your skill files for methodology guidance.
Skills path: ~/.claude/skills/nw/{agent-name}/
Always load at PREPARE: tdd-methodology.md, quality-framework.md
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{step context extracted from roadmap - name|criteria|test_file|scenario_name|implementation_notes|deps|files_to_modify (per nWave/templates/roadmap-schema.json)}

# DESIGN_CONTEXT
{Summarize key architectural decisions from design wave artifacts read at step 0.5.
Include: component structure, dependency-inversion boundaries, technology choices,
data models, and any design constraints relevant to this step.
Source files: architecture-design.md, component-boundaries.md, wave-decisions.md.
If no design artifacts exist, write "No design artifacts available — use project conventions."}

# TDD_PHASES
... (copy remaining sections from execute.md template verbatim)

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching limit, COMMIT current progress.
''',
    description="{phase description}"
)
```

## Roadmap Quality Gate (Automated, Zero Token Cost)

After roadmap creation, before reviewer:
1. AC coupling: flag AC referencing private methods (`_method()`)
2. Decomposition ratio: flag steps/files > 2.5
3. Identical patterns: flag 3+ steps with same AC structure (batch them)
4. Validation-only: flag steps with no files_to_modify
5. Step ID format: flag non-matching `^\d{2}-\d{2}$`
6. DISTILL linkage: if docs/feature/{feature-id}/distill/ exists, flag steps missing test_file/scenario_name

HIGH findings → return to architect for one revision.

## Skip and Resume

- Check `.develop-progress.json` on start for resume
- Skip if file exists with validation.status == "approved"
- Skip completed steps via execution-log.json COMMIT/PASS
- Max 2 retry per review rejection → stop for manual intervention

## Input

- `feature-description` (string, required, min 10 chars)
- feature-id: strip prefixes (implement|add|create)|remove stop words|kebab-case|max 5 words

## Output Artifacts

```
docs/feature/{feature-id}/deliver/
  roadmap.json|execution-log.json|.develop-progress.json
docs/evolution/
  {feature-id}-evolution.md
```

## Quality Gates

Roadmap review (1 review, max 2 attempts)|Per-step TDD cycle (3-phase canon RED→GREEN→COMMIT per ADR-025, or legacy 5-phase PREPARE→RED_ACCEPTANCE→RED_UNIT→GREEN→COMMIT for pre-2026-05-07 audit-log replay)|Paradigm-appropriate crafter|L1-L4 refactoring (Phase 3)|Adversarial review + Testing Theater detection (Phase 4)|Mutation ≥80% if per-feature (Phase 5)|Integrity verification (Phase 6)|All tests passing per phase

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Roadmap created and approved
- [ ] All steps COMMIT/PASS (3-phase TDD canon per ADR-025, or legacy 5-phase for pre-2026-05-07 logs)
- [ ] L1-L4 refactoring complete (Phase 3)
- [ ] Adversarial review passed (Phase 4)
- [ ] Mutation gate ≥80% or skipped per strategy (Phase 5)
- [ ] Integrity verification passed (Phase 6)
- [ ] Evolution archived (Phase 7)
- [ ] Retrospective or clean execution noted (Phase 8)
- [ ] Completion report (Phase 9)

## Examples

### 1: Fresh Feature
`/nw-deliver "Implement user authentication with JWT"` → roadmap → review → TDD all steps → mutation → finalize → report

### 2: Resume After Failure
Same command → loads .develop-progress.json → skips completed → resumes from failure

### 3: Single Step Alternative
For manual granular control, use individual commands:
```
/nw-roadmap @nw-solution-architect "goal"
/nw-execute {selected-crafter} "feature-id" "01-01"
/nw-finalize @nw-platform-architect "feature-id"
```

## Completion

DELIVER is final wave. After completion → DISCOVER for next feature or mark project complete.
