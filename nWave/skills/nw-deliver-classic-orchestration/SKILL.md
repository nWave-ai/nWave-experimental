---
name: nw-deliver-classic-orchestration
description: "DELIVER classic roadmap-driven spine (deprecated fallback, ADR-028 D6) — the §Orchestration Flow phase list (setup, paradigm/mutation/deliverable-type detection, roadmap creation + review, execute-all-steps, post-merge integration + Elevator Pitch demo gate, refactoring, adversarial review, mutation, integrity, finalize, retrospective, report), orchestrator responsibilities, the Task invocation pattern (DES template), the roadmap quality gate, skip/resume, and the per-step design compliance check. Load when the mode dispatch routes to the classic spine, or when the per-slice spine re-enters the shared refactor/review/mutation/integrity/finalize phases as written."
user-invocable: false
disable-model-invocation: true
---

# DELIVER Classic Roadmap-Driven Orchestration (PROCEDURE)

**Kind**: PROCEDURE | **One job**: run the roadmap-driven DELIVER orchestration phase flow | **One trigger**: the `nw-deliver` mode dispatch routes to the classic spine (deprecated fallback under explicit per-instance authorization, ADR-028 D6), or the per-slice spine re-enters this flow's shared refactor/review/mutation/integrity/finalize phases "as written".

Composed by `nw-deliver`. The mode dispatch, the per-slice spine, prior-wave reading, rigor profile, and the output contract live in the `nw-deliver` core — this module is the classic §Orchestration Flow preserved as written.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Orchestration Flow

At the start of execution, create these tasks using TaskCreate and follow them in order:

0. **Read Rigor Profile** — Read `.nwave/des-config.json` key `rigor`. Store: `agent_model`, `reviewer_model`, `tdd_phases`, `review_enabled`, `double_review`, `mutation_enabled`, `refactor_pass`. Use standard defaults if absent. Gate: rigor profile loaded or defaults set.

0.5. **Prior Wave Consultation** — Read `docs/feature/{feature-id}/feature-delta.md` (lean v3.14: full file with DISCUSS/DESIGN/DEVOPS/DISTILL sections) + `docs/product/architecture/brief.md` + every `.feature` file declared in the DISTILL Test Placement section. Legacy fallback: if `feature-delta.md` is missing but multi-file dirs exist, read those instead. Flag contradictions, resolve before proceeding. Summarize key design decisions into a reusable DESIGN_CONTEXT block for crafter dispatch (component structure, boundaries, tech choices, data models). Gate: all required files read, confirmation checklist output, no unresolved contradictions.

1. **Setup** — Parse input, derive `feature-id` (kebab-case), create `docs/feature/{feature-id}/deliver/`.
   - a. Create `execution-log.json` via CLI: `des init-log --project-dir docs/feature/{feature-id}/deliver --feature-id {feature-id}`. Do NOT use Write tool directly.
   - b. Create deliver session marker: `.nwave/des/deliver-session.json`.
   - Gate: directory exists, `execution-log.json` created via CLI, session marker written.

1.5. **Detect Development Paradigm** — Read project `CLAUDE.md` (project root, NOT `~/.claude/CLAUDE.md`). Search "## Development Paradigm".
   - Found → extract paradigm: `"functional"` → `@nw-functional-software-crafter` or `"object-oriented"` → `@nw-software-crafter` (default).
   - Not found → ask user "OOP or Functional?", offer to write to `CLAUDE.md`.
   - Store selected crafter for all Phase 2 dispatches.
   - Functional → property-based testing default; `@property` tags signal PBT; example-based = fallback.
   - Gate: crafter selected and stored.

1.6. **Detect Mutation Testing Strategy** — Read same `CLAUDE.md`, search "## Mutation Testing Strategy".
   - Found → extract: `per-feature` | `nightly-delta` | `pre-release` | `disabled`.
   - Not found → default `nightly-delta` (recommended mode — CI runs mutmut nightly on changed modules; keeps per-feature gates fast).
   - Log strategy for traceability. Note: strategy locks at deliver start; `CLAUDE.md` edits during delivery take effect next run.
   - Gate: strategy recorded.

1.7. **Detect Deliverable Type** (ADR-PST-003 / DDD-6) — Read `deliverable_type` from the SAME `.nwave/des-config.json` the runtime gate uses — this is the single source of truth (`DESConfig.deliverable_type` precedence, ADR-PST-002): (1) declared project `.nwave/des-config.json` key `deliverable_type` if in the known set `{application, plugin, skill}`; (2) else global `~/.nwave/global-config.json` `defaults.deliverable_type`; (3) else root-only FS detection; (4) a present-but-typo'd value resolves to the safe default (treated as `application`). Do NOT re-detect independently — read what the gate reads so the verification plan and the enforcement gate never diverge.
   - `application` (or unresolved) → store `application`. Verification plan UNCHANGED (pytest / Hypothesis routing, `@nw-software-crafter-reviewer`).
   - `plugin` → store `plugin`. The Phase 4 verification plan branches (see Phase 4).
   - `skill` → store `skill`. The Phase 4 verification plan branches (see Phase 4).
   - Gate: deliverable type read from `.nwave/des-config.json` and stored for Phase 4 routing.

2. **Phase 1 — Roadmap Creation + Review** — Gate: roadmap created, integrity verified, reviewer approved.
   - a. Skip if `docs/feature/{feature-id}/deliver/roadmap.json` exists with `validation.status == "approved"`. If found in `design/` instead, move to `deliver/` and log warning.
   - b. Dispatch `@nw-solution-architect` to create `roadmap.json` (load `~/.claude/skills/nw-roadmap/SKILL.md`). Step IDs MUST match `NN-NN` format (01-01, 01-02). If `distill/` exists, architect MUST populate `test_file` and `scenario_name` per step.
   - c. Run automated quality gate (see Roadmap Quality Gate section below).
   - c2. Run roadmap integrity verification (HARD GATE): `des verify-integrity docs/feature/{feature-id}/deliver/ --roadmap-only` — validates `roadmap.json` against the schema only; execution-log cross-reference is skipped (no log entries exist yet pre-crafter). Exit 0 = roadmap OK; exit 1 = schema errors printed; exit 2 = file missing or usage error. BLOCK on any non-zero exit; fix before dispatching any crafter.
   - d. Dispatch `@nw-acceptance-designer-reviewer` to review roadmap (load `~/.claude/skills/nw-review/SKILL.md`): verify every DISTILL scenario has a step, flag orphan scenarios as BLOCKER; flag steps covering 8+ scenarios as `@sizing-review-needed`; verify walking skeleton scenarios map to Phase 1 steps.
   - e. Retry once on rejection → stop for manual intervention.

3. **Phase 2 — Execute All Steps** — Gate: all steps reach COMMIT/PASS in `execution-log.json`.
   - a. Extract steps from `roadmap.json` in dependency order.
   - b. Check `execution-log.json` for prior completion (resume mode).
   - c. Dispatch selected crafter (from step 1.5) with full DES Prompt Template from `execute.md` (load `~/.claude/skills/nw-execute/SKILL.md`). Include DES markers (`DES-VALIDATION`, `DES-PROJECT-ID`, `DES-STEP-ID`) + all mandatory sections. Functional crafter → PBT default; `@property` tags signal PBT.
   - d. Verify COMMIT/PASS in `execution-log.json` per step.
   - e. Missing phase → RE-DISPATCH agent. NEVER write entries directly.
   - f. Stop on first failure.
   - g. Timeout recovery: GREEN completed → resume (~5 turns); GREEN partial → resume; otherwise → restart with higher `max_turns`.
   - h. Wiring smoke check: verify every new function defined in production files has at least one call site in production code (not just tests). Flag "function X defined but only called from tests" → re-dispatch crafter.
   - i. Acceptance test gate: after each step's COMMIT/PASS, run `tests/acceptance/{feature-id}/`. Fix failures before proceeding to next step. No deferral.

3.5. **Post-Merge Integration Gate (Hard Gate)** — AFTER all steps reach COMMIT/PASS, BEFORE Phase 3. Gate: full acceptance suite passes in all environments AND every story's Elevator Pitch demo command produces non-empty output.
   - a. Run `uv run pytest tests/acceptance/{feature-id}/ -v --tb=short`.
   - b. Run acceptance tests against EVERY environment listed in the `## Wave: DEVOPS / [REF] Environment Matrix` section of `feature-delta.md` (lean v3.14) OR `docs/feature/{feature-id}/devops/environments.yaml` (legacy multi-file). If neither, use defaults: `clean`, `with-pre-commit`, `with-stale-config`.
   - c. BLOCK if ANY test fails in ANY environment.
   - d. **Elevator Pitch demo execution (HARD GATE)** — For every user story in the `## Wave: DISCUSS / [REF] User Stories with Elevator Pitches` section of `feature-delta.md` (lean v3.14) OR `docs/feature/{feature-id}/discuss/user-stories.md` (legacy) that is NOT tagged `@infrastructure`:
      - Extract the `After: run ... → sees ...` line
      - Execute the exact command (subprocess, not function call)
      - Capture stdout + exit code
      - Verify: exit code is 0, stdout is non-empty, stdout contains the substring described by the "sees" clause
      - On any failure: BLOCK with message "Story {N}: demo command {cmd} did not produce visible output — either the CLI is broken or the story Elevator Pitch is fictional. Fix one or the other."
      - Append demo output to `docs/feature/{feature-id}/feature-delta.md` as `## Wave: DELIVER / [REF] Demo Evidence` (lean v3.14 — single narrative file) OR `docs/feature/{feature-id}/deliver/wave-decisions.md` under a `## Demo Evidence — {date}` section (legacy multi-file). Do NOT create a separate demo-output file.
   - e. On failure at step a/b: identify failing environment + test, re-dispatch crafter for new TDD cycle, re-run full gate after fix. If same test fails in 2+ environments after one fix attempt, STOP and report to user.
   - f. On success: record gate passage in `execution-log.json`: `{"gate": "post-merge-integration", "status": "PASS", "environments_tested": [...], "stories_demoed": [...], "timestamp": "ISO-8601"}`.

4. **Phase 3 — Complete Refactoring (L1-L6)** — [SKIP if `rigor.refactor_pass = false`]. Gate: all tests green after each module refactored.
   - a. Collect modified files: `git diff --name-only {base-commit}..HEAD -- '*.py' | sort -u`. Split into PRODUCTION_FILES (`src/`) and TEST_FILES (`tests/`).
   - b. Run `/nw-refactor {files} --levels L1-L6` via selected crafter with DES orchestrator markers: `<!-- DES-VALIDATION : required -->`, `<!-- DES-PROJECT-ID : {feature-id} -->`, `<!-- DES-MODE : orchestrator -->`, `<!-- DES-WAVE: deliver -->`.

5. **Phase 4 — Adversarial Review** — [SKIP if `rigor.review_enabled = false` or `rigor.reviewer_model = "skip"`]. Gate: review passed or one revision complete. **Reviewer routing branches on the deliverable type stored in step 1.7** (ADR-PST-003 / DDD-6):
   **`application` (or unresolved)** — UNCHANGED:
   - a. Dispatch `/nw-review @nw-software-crafter-reviewer implementation "{execution-log-path}"` with `model=rigor.reviewer_model` and DES orchestrator markers.
   - b. If `rigor.double_review = true` → run review a second time with different scope focus.
   - c. Scope: ALL files modified during feature; includes Testing Theater 7-pattern detection.
   - d. One revision pass on rejection → proceed.

   **`plugin`** — dispatch `@nw-plugin-validator` (Claude Code plugin structure/schema) AND `@nw-skill-reviewer` (SKILL.md quality), both on Haiku, plus `@nw-software-crafter-reviewer` for any application-layer code in the same feature. Verification evidence is behavioral Gherkin + example-interaction evidence (the plugin demonstrated through its real invocation path), with optional `bats`/`shellcheck` for any shell. NOT pytest/Hypothesis-centric. One revision pass on rejection → proceed.

   **`skill`** — dispatch `@nw-skill-reviewer` (SKILL.md quality, Haiku). Do NOT dispatch `@nw-plugin-validator` (no plugin structure to validate). Verification evidence is behavioral Gherkin. One revision pass on rejection → proceed.

   **Authoring stays with `@nw-agent-builder`**: when a plugin/skill review finds content to author or rewrite, route the fix to `@nw-agent-builder` — the validators/reviewers are read-only. The four `*-development` specialist agents remain DEFERRED.

6. **Phase 5 — Mutation Testing** — [SKIP if `rigor.mutation_enabled = false`]. Gate: ≥80% kill rate or strategy skip logged.
   - `per-feature` → gate ≥80% kill rate (load `~/.claude/skills/nw-mutation-test/SKILL.md`).
   - `nightly-delta` → SKIP; log "handled by CI nightly pipeline".
   - `pre-release` → SKIP; log "handled at release boundary".
   - `disabled` → SKIP; log "disabled per project configuration".

7. **Phase 6 — Deliver Integrity Verification** — Gate: `verify_deliver_integrity` exits 0.
   - a. Run: `des verify-integrity docs/feature/{feature-id}/deliver/`.
   - b. Exit 0 → proceed. Exit 1 → STOP, read output. Exit 2 → rigor misconfiguration (see e).
   - c. No entries = not executed through DES. Partial = incomplete TDD.
   - d. Violations → re-execute via Task with DES markers. Proceed only after pass.
   - e. **Rigor-aware integrity** (F-3, ADR-025): the verifier tracks the rigor-profile phase set declared in `.nwave/des-config.json` (`rigor.tdd_phases`), intersected with the canonical TDDSchema. 3-phase ADR-025 projects (`[RED, GREEN, COMMIT]`) verify cleanly. Legacy 5-phase projects continue to verify unchanged. Empty intersection → exit 2 with diagnostic naming the offending rigor phases (fix `.nwave/des-config.json` and rerun).

8. **Phase 7 — Finalize** — Gate: evolution archived, session markers removed, commit pushed, hook offer made (if applicable).
   - a. Dispatch `@nw-platform-architect` to archive to `docs/evolution/` (load `~/.claude/skills/nw-finalize/SKILL.md`).
   - b. Commit + push. Run: `rm -f .nwave/des/deliver-session.json .nwave/des/des-task-active`.
   - c. **One-time test-hook offer** — Check whether the project's pre-commit/pre-push test hooks are installed (absence of the pre-commit framework marker in `.git/hooks/pre-push`). If NOT installed AND not previously declined (no `.nwave/hook-offer-declined` marker): offer the user ONCE — suggest running `pre-commit install --hook-type pre-commit --hook-type pre-push` so tests also run automatically on commit/push. This is an OFFER, not enforcement; it does NOT replace the crafter's own mandatory terminating test run (the suite always runs at the end of every code modification regardless of hooks — `feedback_target_machine_independence_2026_05_15`). If the user declines, write `.nwave/hook-offer-declined` and do not re-offer.

9. **Phase 8 — Retrospective (conditional)** — Skip if clean execution. Gate: 5 Whys documented or clean-run noted.
   - On issues found → dispatch `@nw-troubleshooter` for 5 Whys analysis.

10. **Phase 9 — Report Completion** — Display summary: phases, steps, reviews, artifacts. Gate: report output, return to DISCOVER for next iteration.

## Orchestrator Responsibilities

Follow this flow directly. Do not delegate orchestration.

Per phase:
1. **Read command file** — Read the relevant command file (paths listed in each phase above).
2. **Embed instructions** — Extract instructions and embed them in the Task prompt.
3. **Add task boundary** — Include task boundary instructions to prevent workflow continuation.
4. **Verify artifacts** — Verify output artifacts exist after each Task completes.
5. **Update progress** — Update `.develop-progress.json` for resume capability.

## Task Invocation Pattern

DES markers required for step execution. Without markers → unmonitored. Full DES Prompt Template in `~/.claude/skills/nw-execute/SKILL.md`.

When dispatching steps via Agent tool, use the COMPLETE DES template from execute.md verbatim. Fill all `{placeholders}` from roadmap step context. The DES hook validates the prompt BEFORE the sub-agent starts — abbreviated prompts that delegate template reading to the sub-agent will be BLOCKED.

Copy the template from the code block in `~/.claude/skills/nw-execute/SKILL.md` (between ``` markers), fill placeholders, and pass as the Agent prompt. The template sections are defined in execute.md — do not hardcode the list here.

```python
Task(
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
Skills path: ~/.claude/skills/nw-{skill-name}/SKILL.md
Always load at PREPARE: tdd-methodology.md, quality-framework.md
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{step context extracted from roadmap - name|criteria|test_file|scenario_name|implementation_notes|deps|files_to_modify (per nWave/templates/roadmap-schema.json)}

# DESIGN_CONTEXT
{Summarize key architectural decisions from design wave artifacts read at step 0.5.
Include: component structure, dependency-inversion boundaries, technology choices,
data models, and any design constraints relevant to this step.
Source files: docs/product/architecture/brief.md, wave-decisions.md.
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

After roadmap creation, before reviewer, run these checks:

1. **AC coupling** — Flag AC referencing private methods (`_method()`). HIGH → return to architect.
2. **Decomposition ratio** — Flag steps/files > 2.5. HIGH → return to architect.
3. **Identical patterns** — Flag 3+ steps with same AC structure (batch them). HIGH → return to architect.
4. **Validation-only** — Flag steps with no `files_to_modify`. HIGH → return to architect.
5. **Step ID format** — Flag non-matching `^\d{2}-\d{2}$`. HIGH → return to architect.
6. **DISTILL linkage** — If `feature-delta.md` contains `## Wave: DISTILL / [REF] ...` sections OR `docs/feature/{feature-id}/distill/` exists (legacy), flag steps missing `test_file`/`scenario_name`. HIGH → return to architect.

## Skip and Resume

1. **Check progress** — Read `.develop-progress.json` on start for resume state.
2. **Skip approved roadmap** — Skip Phase 1 if `roadmap.json` exists with `validation.status == "approved"`.
3. **Skip completed steps** — Skip steps already showing COMMIT/PASS in `execution-log.json`.
4. **Cap retries** — Max 2 retries per review rejection → stop for manual intervention.

## Design Compliance Check (MANDATORY — RCA F-2 fix)

After each crafter step's COMMIT, verify the files modified match the DESIGN specification:

1. Read the `## Wave: DESIGN / [REF] Component Decomposition` table in `feature-delta.md` (lean v3.14) OR `docs/feature/{feature-id}/design/architecture-design.md` "Changes Per File" table (legacy multi-file)
2. Compare against `git diff --name-only` for the crafter's commit
3. If the crafter created a NEW file not listed in the design table: **STOP and flag**
   - A new file means a new component — this may be duplication of an existing component
   - Check the DESIGN's Reuse Analysis table (F-1) — if the new file's class overlaps an existing component, the crafter must extend the existing component instead
   - Do NOT proceed to the next step until resolved
4. If the crafter modified files not in the design table: acceptable (tests, config) but flag for review

This gate prevents the pattern where crafters create parallel implementations instead of extending existing components (see RCA `docs/analysis/rca-systematic-duplication-despite-design.md`).
