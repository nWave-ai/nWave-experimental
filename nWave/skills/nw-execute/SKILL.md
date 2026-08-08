---
name: nw-execute
description: "Dispatches one unit of DELIVER work to a specialized agent for executable-AT delivery. Use to run one carpaccio slice of the ATDD-pure workflow."
user-invocable: true
argument-hint: '[agent] [feature-id] [slice-id] - Example: @nw-software-crafter "auth-upgrade" "slice-01"'
---

> **Code facts** — resolve structural facts about code (who-calls / defs-reads / never-wired / call-graph / atoms-in-file) through the `nw-code-analysis-port` skill: graphify-first (`graphify explain <symbol>`), declared fallback (AST, then grep), degrade-LOUD. Never ad-hoc grep for a structural fact.

# NW-EXECUTE: Atomic Task Execution

**Wave**: EXECUTION_WAVE | **Agent**: Dispatched agent (specified by caller)

## Overview


> **Do NOT invoke `/nw-execute` directly to deliver a FEATURE.** It is ONE unit of DELIVER work, not the wave. Deliver a feature through **`/nw-deliver`** — it owns the multi-slice loop, the finalize, and the feature-end cycle, and drives `/nw-execute` internally per slice. The ONLY sanctioned standalone use is a single-slice **bugfix**, driven by **`/nw-bugfix`** (its atdd_pure lane runs `/nw-execute` for the one regression slice). Calling `/nw-execute` standalone for feature work skips the deliver-cycle orchestration (slice plan, the loop, feature-end) — exactly the reverse-engineering trap a clean instance falls into. Route: feature → `/nw-deliver`; bug → `/nw-bugfix`; unsure → `/nw-buddy`. <!-- mode-ref-ok -->

## Workflow Mode

`/nw-execute` reads `workflow.mode` from `.nwave/config.yaml` and branches on it before doing anything else. <!-- mode-ref-ok -->
Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **`atdd_pure` is the sole active workflow**. Resolve it through `des.application.workflow_mode.resolve_workflow_mode`. <!-- mode-ref-ok -->
- **`atdd_pure`** — `/nw-execute` IS the **per-slice lean cycle**: it executes ONE carpaccio slice. See "ATDD-Pure Per-Slice Lean Cycle" below. <!-- mode-ref-ok -->

### ATDD-Pure Per-Slice Lean Cycle

Under `workflow.mode: atdd_pure`, `/nw-execute` runs one carpaccio slice through the per-slice lean cycle (ADR-028 D6). It uses the active `[REF] Slice Plan` row in the Feature Delta as the slice authority and does not emit a parallel execution record. The unit of work is a carpaccio slice. The cycle, in order: <!-- mode-ref-ok -->

1. **Carpaccio entry gate** — confirm the slice's acceptance tests exist and are correctly skip-scaffolded; reject the slice if the carpaccio gate fails. Entry evidence for the gate's AT-attestation leg (assertion 5): a pytest-regression slice (`at_kind: pytest-regression`, the `/nw-bugfix` mode — the regression test IS the slice's AT) clears by DEFAULT on the mechanical pair — fresh `RedObserved` seal (`des verify-red-green --record-red --test-file <f>`) + negative-AT pass (`des verify-negative-at --test-file <f> --all-critical`) — recorded as `SliceCleared at_evidence: mechanical-seal`, no AT-review LLM dispatch (evolution-plan P1.1). A recorded `ATReviewVerdict` (reviewer dispatch + `des record-at-review-verdict`) is the optional rigor-profile alternative on that path. Gherkin slices keep the reviewer-verdict route unchanged — the seal path is not yet wired for Gherkin (tracked follow-up).
3. **`B_COVERAGE_CLEANUP`** — coverage-driven dead-code elimination for the slice. **DEPRECATED (FR-2/FR-3, velocity-v2)**: absorbed into A_GREEN as AT-driven minimalism (no `pytest --cov` gate, no ≥90% target) — see the Phase B DEPRECATED banner in `nw-crafter-discipline-atdd-pure`.
4. **Light slice review** — confirm the implementation satisfies the slice's ATs. This is a light pass, not the deep adversarial review (the deep `C`+`F` review belongs to `/nw-deliver`'s feature-end cycle, not here).
5. **Terminating focused run** — execute the project-declared focused test command. Do not invent a language-specific subset; if no command is declared, report that limitation rather than guessing. The whole-tree contract suite is not run per slice.
6. **EXAMINE — the Definition of DONE (hard-gated, ADR P1.2).** For a VALUE slice, dispatch `nw-user-examiner` (Vera) against the slice's charter (`docs/product/expectations/{feature-id}/*.md` — the one whose `Spec rows: slice-NN` names this slice), have her observe the outcome end-to-end through the REAL user surface, then record the verdict: `des record-examine-verdict --repo . --feature-id {feature-id} --slice {slice-NN} --charter <path> --verdict PASS --observations <text> --examiner nw-user-examiner`. **EXAMINE is the true DoD** — green tests verify the CODE, EXAMINE verifies the running SYSTEM (isolated-green ≠ assembled-green; a stale process can serve old code while tests pass on fresh source). This is NOT optional: G_COMMIT's `des verify-slice-commit` runs **E3 (`check_examine_verdict`)** and refuses `SliceCommitVerified` fail-closed for an ARMED feature (a charter dir exists) that lacks a fresh PASS verdict whose `charter_seal` matches the charter's current bytes. **EXEMPTION** — a behaviour-preserving **prefactoring/refactoring** slice changes no behaviour, carries no charter → the gate is UNARMED → green-to-green (tests pass before AND after) suffices; prefactorings run through a SEPARATE path (Mikado / the prefactoring-lane), not this cycle. **Slicing test**: if a value slice cannot be EXAMINE'd (no observable surface), that is a horizontal-slicing smell — re-slice it VERTICAL; the gate records `ExamineVerdictIndeterminate` = "an unexaminable slice carries no observable value — it was not a slice", never a silent pass.
7. **`G_COMMIT`** — stage and conventional-commit, then run the exit gate EXPLICITLY: `des verify-slice-commit --repo . --commit HEAD --feature-id {feature-id}` (the verify-then-record path — E1 completeness + E2 feature-scoped contract gate + E3 examine-verdict — which RECORDS `SliceCommitVerified` to the AT-completion ledger IFF all three clear). This is MANDATORY, not optional: the successor slice's carpaccio entry gate BLOCKS until that record exists. Do NOT rely on the `SubagentStop` hook to emit it — the hook fires only on a distinct `G_COMMIT`-phase return, which a folded lean-cycle commit may not produce; it is a backstop, never the sole emitter. Confirm the `SliceCommitVerified` record landed before phase exit (empirical 2026-05-29: a slice committed but left no record, blocking its successor until backfilled).

`E_BATCH_REFACTOR` and the deep review are explicitly NOT part of `/nw-execute` under `atdd_pure` — they belong to `/nw-deliver`'s feature-end cycle. <!-- mode-ref-ok -->

## Recovery Fallback — Subagent Died Before Its Final Mechanical Record

Empirically recurring failure mode (gap-3, cross-instance): a dispatched subagent — the examiner (Vera), the acceptance-designer sealing RED, a reviewer recording an AT-review verdict, an ad-hoc reviewer (e.g. `nw-agent-builder-reviewer`) recording a general review verdict — completes its investigation and DECIDES its verdict, then the process dies exactly before its LAST mechanical step: the `des record-examine-verdict` / `des verify-red-green --record-red` / `des record-at-review-verdict` / `des record-review-verdict` call that persists it. The ledger then lacks the record even though the subagent knew the verdict. This is additive, not a replacement: the subagent still self-records on the happy path — self-recording is tamper-evident (the examiner signs HER OWN verdict, the reviewer signs HER OWN AT-review or general review) and that property is preserved.

Two-part contract:

1. **Dispatch contract (produces recovery data)** — every dispatch whose final step is a `des record-*` / `des verify-red-green --record-red` call MUST instruct the subagent to end its final message with the verdict/seal + observations stated VERBATIM (e.g. `VERDICT: PASS` plus the observation text, or `RED CONFIRMED: <reason>`). Without this line, recovery has nothing to record from.
2. **Orchestrator contract — RECOVER BY DEFAULT, never wait for a relay** (Ale-ratified 2026-07-18). The orchestrator VERIFIES the record actually landed in the relevant ledger (grep `.nwave/telemetry/examine/{feature-id}.jsonl` for `ExamineVerdictRecorded`, the AT-completion ledger for `RedObserved` / `ATReviewVerdict`, or `.nwave/telemetry/review/{feature-id}.jsonl` for `ReviewVerdictRecorded` — the ledger for ad-hoc reviewers that lack a wave-specific recorder, #45). If the record is ABSENT, the orchestrator runs the SAME `des record-*` command the subagent would have run, using the subagent's verbatim verdict line. It never overrides a self-recorded verdict — the ledger is checked first, and a present record ends the matter.

   **The default posture is RECOVERY, not waiting.** The earlier wording said to verify "after the subagent returns or goes idle" — but a subagent that DIED never returns, and "idle" is indistinguishable from "still thinking" until a stale-detector fires. Waiting for a return that will never come is the single largest measured friction multiplier in the loop: ~25-30 minutes of dead wall-clock per `StaleAgentClosed`, recurring, across every instance. So:
   - **Read the TRANSCRIPT, do not wait for the relay.** A dead subagent's final message still exists in its transcript. That is the recovery source. The orchestrator does not need the agent to hand its verdict back — it needs the verdict, and the transcript already holds it.
   - **Check the ledger the moment the agent stops producing** — not after a timeout, not after a stale-detector, not after a reminder. An absent record plus a decided verdict in the transcript is already everything recovery needs.
   - **A missing verdict line in the transcript is itself the finding.** If the subagent died before deciding — nothing to recover — say so and re-dispatch. Never infer a verdict the subagent did not state; a guessed PASS is the exact fabrication these ledgers exist to prevent.

**Per-slice pipelining is mandatory.** At every phase transition, completion,
refusal or emitted artifact, recompute the artifact-level DAG and dispatch every
ownership-safe READY cloud lane until capacity is full. This includes later-slice
charter/DISTILL, independent intra-slice lanes, JIT analysis and review preparation
— not merely “the NEXT slice.” A slice dependency blocks only consumers of its
unstable artifact; it is never a whole-slice barrier. Idle cloud capacity with READY
work is `UNUSED_PARALLELISM` and requires a recorded artifact/file/box reason. The
box-seal lane (carpaccio `entry_gate` → commit-slice) stays strictly serialized:
N cloud lanes, ONE box lane. Load `nw-throughput` for the mandatory scheduling
cycle; canonical DELIVER anchor: `nw-deliver` §Per-slice pipelining.

The long-lived orchestrator always survives to persist a decided verdict — a subagent's death can never silently lose it. This discipline is the canonical locus for the recovery fallback (the per-slice cycle owner); `/nw-deliver` and `/nw-bugfix` point here rather than restating it.

## Syntax

```
/nw-execute @{agent} "{feature-id}" "{slice-id}"
```




## Rigor Profile Integration

Before dispatching the agent, read rigor config from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

- **`agent_model`**: Pass as `model` parameter to Agent tool. If `"inherit"`, omit `model` (inherits from session).
- **`refactor_pass`**: If `false`, omit a separate refactoring dispatch; the fixed delivery floor still requires proportionate cleanup.

## Dispatcher Workflow


1. **Parse Parameters** — Extract agent name, feature ID, and slice ID from invocation. Gate: all three parameters present and non-empty.
2. **Load Rigor Profile** — Read `.nwave/des-config.json` key `rigor` (default: standard if absent). Gate: config loaded or default applied.
3. **Extract Slice Context** — Read the active Feature Delta `[REF] Slice Plan` row, its declared target paths, and its DISTILL-authored ATs. Gate: slice, declared targets, and ATs found.
4. **Invoke Agent** — Call Agent tool with the ATDD-pure template below, applying rigor configuration from step 2. Gate: Agent tool called, not executed inline.

## Agent Invocation

@{agent}

Fill the ATDD-pure template below verbatim. Without DES markers, hooks cannot validate.

### ATDD-Pure DES Dispatch Template

Use this DES template verbatim when `workflow.mode = atdd_pure`. It dispatches ONE carpaccio slice into ONE ATDD-pure phase. Fill `{placeholders}` from the slice plan in `feature-delta.md` — `{feature-id}`, `{slice-NN}` (the bare carpaccio slice id, anchored `slice-\d+` shape), `{phase}` (one of the seven `ATDDPurePhase` members), and `{agent}`. <!-- mode-ref-ok -->


The block between the `ATDD-PURE-DISPATCH-TEMPLATE:BEGIN` / `:END` anchor comments is the copy-fill-verbatim dispatch prompt.

<!-- ATDD-PURE-DISPATCH-TEMPLATE:BEGIN -->
```
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {feature-id} -->
<!-- DES-MODE : atdd_pure --> <!-- mode-ref-ok -->
<!-- DES-PHASE : {phase} -->
<!-- DES-SLICE : {slice-NN} -->
<!-- DES-WAVE: deliver -->

# DES_METADATA
Slice: {slice-NN}
Feature: {feature-id}
Phase: {phase}
Command: /nw-execute — atdd_pure workflow.mode, per-slice lean cycle (ADR-028 D6) <!-- mode-ref-ok -->

# AGENT_IDENTITY
Agent: {agent}

# SKILL_LOADING
Before starting, read your skill files for methodology guidance.
Skills path: ~/.claude/skills/nw-{skill-name}/SKILL.md
Always load at phase entry: nw-tdd-methodology, nw-quality-framework.
In atdd_pure mode also load nw-crafter-discipline-atdd-pure at phase entry. <!-- mode-ref-ok -->
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{slice context from feature-delta.md `[REF] Slice Plan` — slice value statement |
declared target paths | acceptance tests for the slice | the DISTILL-authored ATs.
The Feature Delta Slice Plan declared target paths are this atdd_pure dispatch's
selected mutation authority. This slice's ATs ARE the work unit.}

# DESIGN_CONTEXT
{Summary of architectural decisions relevant to this slice, extracted from
docs/feature/{feature-id}/feature-delta.md DESIGN section. Include component
structure, dependency boundaries, technology choices, design constraints. If
no design artifacts exist, write "No design artifacts available — use project
conventions."}

# ATDD_PURE_PHASES
ATDD-pure per-slice cycle (ADR-027 / ADR-028 D6). The seven canonical phases,
in order: A → B → C → D → (E | reloop A | reroute | exit) → E → F → G.
This dispatch executes the phase named in the DES-PHASE marker.

1. A_GREEN_ATS — crafter. Activate the slice's DISTILL-authored acceptance
   tests and implement the minimum production code that turns them all GREEN.
   Do NOT author new tests. Do NOT add defensive code beyond AT-driven need.
   Gate: all the slice's ATs green; wiring check passes.
2. B_COVERAGE_CLEANUP — same crafter instance. Coverage-driven dead-code
   elimination for the slice. Gate: ≥90% line+branch coverage on new code OR
   justified misses recorded in the commit body.
3. C_REVIEWER_AUDIT — reviewer. 15-item AT-completeness audit.
   Gate: PhaseCReviewerVerdict emitted.
4. D_GAP_ROUTING — orchestrator. Route per ATGapKind.
   Gate: one routing decision recorded.
5. E_BATCH_REFACTOR — separate crafter instance. L1-L6 batch refactor:
   plan in cascade order, apply as one batch, run the suite ONCE at the end.
   Gate: tests stay green post-batch.
6. F_FINAL_REVIEW — reviewer. Code review + refactor green check.
   Gate: PhaseFReviewerVerdict with mandatory verdict_hash.
7. G_COMMIT — crafter. Conventional commit with Slice-Id: + Gate-Scope: +
   Reviewed-by: (verdict_hash) trailers. Gate: G_COMMIT exit gate exit 0.

# QUALITY_GATES
- All the slice's ATs pass before G_COMMIT
- No new tests authored by the crafter (DISTILL owns AT authorship)
- Coverage maintained or improved; dead code eliminated in B_COVERAGE_CLEANUP
- Wiring check: compare production paths in `git diff --name-only` with the
  selected Feature Delta Slice Plan declared target paths; refuse any
  undeclared production path. If the ATs changed RED→GREEN but no declared
  production target appears, refuse Fixture Theater.

# AT_COMPLETION_LEDGER
atdd_pure records phase outcomes to the AT-completion ledger only. The ledger <!-- mode-ref-ok -->
lives at `.nwave/telemetry/atdd-pure/{feature-id}.jsonl`. Each slice records the
at_ids it satisfied and the implementation files those ATs drove.
- The C_REVIEWER_AUDIT / F_FINAL_REVIEW verdicts and the G_COMMIT trailers are
  the records of truth for the slice.
- The DES sequencer appends FeatureEndCheckpoint records to the AT-completion
  ledger at feature-end-cycle boundaries — the crafter does not write these.
- atdd_pure uses the AT-completion ledger; do not create a parallel execution record. <!-- mode-ref-ok -->

# RECORDING_INTEGRITY
Do not fake green. Every AT reaches its assertion and passes for the right
reason. State explicitly whether all the slice's ATs are genuinely green.
- NEVER report a phase outcome you did not actually perform.
- NEVER weaken, skip, or rewrite a DISTILL-authored AT to make it pass — if an
  AT cannot reach GREEN, escalate `AT_INSUFFICIENT_FOR_GREEN` to
  nw-acceptance-designer; do not author or edit a test to compensate.

# BOUNDARY_RULES (slice-scoped)
- Before mutation, select the Feature Delta Slice Plan declared target paths as
  the sole production-path authority. Refuse a production mutation outside it.
- After mutation, compare `git diff --name-only` production paths to that
  selected authority and refuse undeclared paths.
- Stay within the slice's value statement — do NOT implement adjacent slices.
- atdd_pure mode: do not read or create a parallel execution record; the
  slice's ATs are the work unit. <!-- mode-ref-ok -->
- Do NOT author acceptance tests — AT authorship belongs to nw-acceptance-designer.
- Do NOT run E_BATCH_REFACTOR or the deep review here — they belong to
  /nw-deliver's feature-end cycle, not the per-slice /nw-execute cycle.

# TERMINATING_RUN
After any code modification, execute the project-declared focused test command.
Do not invent a language-specific subset; if no command is declared, report the
limitation rather than guessing.
Do NOT run the whole-tree contract suite per slice — it is run once at the
feature-end cycle. The `Gate-Scope:` digest (E2 `--verify-gate-scope`) stays a
whole-tree `--collect-only` digest. Report exact pass/fail counts.

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching the limit, commit current green progress.
If A_GREEN_ATS is complete (all slice ATs pass), MUST commit before returning.
```
<!-- ATDD-PURE-DISPATCH-TEMPLATE:END -->

**Configuration:**
- subagent_type: extracted agent name
- Turn limits are defined in each agent's `maxTurns` frontmatter field (not as a tool parameter)

## Error Handling

1. **Invalid Agent** — Report available agents from the agent registry. Gate: error message returned, no invocation attempted.
3. **Slice Not in Plan** — Report available slice IDs from the feature delta's Slice Plan. Gate: list of valid IDs returned.
4. **Dependency Failure** — Explain which blocking tasks are incomplete. Gate: blocking step IDs named explicitly.

## Resume vs Restart

When subagent times out:

| Observable work state | Action | Rationale |
|-----------------------|--------|-----------|
| Executable AT passes and the change is ready to integrate | Resume | Preserve validated implementation progress. |
| Implementation is partly complete with a clear next change | Resume | Preserve useful context. |
| No validated implementation exists | Restart | Little context is worth replaying. |

Resume costs ~50% more tokens/call due to context replay (measured: 3.7K vs 2.5K tokens/call). For <5 remaining turns, resume is efficient. For 15+ turns, restart is cheaper.

## Examples

```bash
/nw-execute @nw-software-crafter "des-us007-boundary-rules" "slice-02"
/nw-execute @nw-researcher "auth-upgrade" "slice-01"
/nw-execute @nw-software-crafter "des-us007" "slice-03"  # retry after failure
```

## Success Criteria

- [ ] Agent invoked via Agent tool (dispatcher does not execute the work)

## Next Wave

**Handoff To**: /nw-review for post-execution review
