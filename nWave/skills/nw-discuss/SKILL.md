---
name: nw-discuss
description: "Conducts Jobs-to-be-Done analysis, UX journey design, and requirements gathering through interactive discovery (recomposing core). DISCUSS identity + output-tier contract + scope escalation/Epic Mode + agent dispatch. Lean core that COMPOSES the narrow nw-discuss-* modules; phase procedures live in those modules, not re-inlined here. Use when starting feature analysis, defining user stories, or creating acceptance criteria."
user-invocable: true
argument-hint: '[feature-name] - Optional: --epic=[epic-id] --phase=[jtbd|journey|requirements] --interactive=[high|moderate] --output-format=[md|yaml]'
---

# NW-DISCUSS: Jobs-to-be-Done Analysis, UX Journey Design, and Requirements Gathering (recomposing core)

**Wave**: DISCUSS (wave 2 of 6) | **Agent**: Luna (nw-product-owner) | **Command**: `/nw-discuss`

## Overview

Execute DISCUSS wave through Luna's integrated workflow: JTBD analysis|UX journey discovery|emotional arc design|shared artifact tracking|requirements gathering|user story creation|acceptance criteria definition. Luna uncovers jobs users accomplish, maps to journeys and requirements, handles complete lifecycle from user motivations through DoR-validated stories ready for DESIGN. Establishes ATDD foundation.

For greenfield projects (no src/ code, no docs/feature/ history), Luna proposes Walking Skeleton as Feature 0.

This core holds the cross-cutting DISCUSS concerns — identity, the density-aware output contract, telemetry, the Phase 1.5 scope escalation + Epic Mode contract, and the agent dispatch block — and COMPOSES the narrow `nw-discuss-*` modules. The phase procedures and the decision catalog live in those modules, not re-inlined here.

## Composition (load by trigger)

| Module | Kind | Trigger — load when... | Covers |
|---|---|---|---|
| `nw-discuss-prior-wave-reading` | PROCEDURE | BEFORE beginning DISCUSS work — consuming SSOT + prior-wave artifacts | Prior Wave Consultation reading order, READING ENFORCEMENT checklist, migration gate, DISCOVER-contradiction check, Document Update (back-propagation) |
| `nw-discuss-decision-points` | KNOWLEDGE | presenting or resolving the wave-entry Decisions 1-4 | Decision catalog: feature type, walking skeleton, UX research depth, JTBD inclusion (+ default and rationale) |
| `nw-discuss-jtbd-analysis` | PROCEDURE | Phase 1 — Decision 4 = Yes and JTBD analysis is about to run | Job discovery, job dimensions, four forces, opportunity scoring, JTBD-to-story bridge + artifact paths |
| `nw-discuss-journey-design` | PROCEDURE | Phase 2 — designing the UX journey informed by JTBD | Mental model discovery, happy path, emotional arc, shared artifact tracking, error paths, Gherkin generation + artifact paths |
| `nw-discuss-story-mapping` | PROCEDURE | Phase 2.5 — decomposing into story map + elephant-carpaccio slices | Backbone, walking-skeleton slice, carpaccio slicing + taste tests, slice briefs, prioritization + artifact paths |
| `nw-discuss-requirements-stories` | PROCEDURE | Phase 3 — crafting stories/ACs/DoR and closing the wave | LeanUX stories + job traceability, Elevator Pitch gate, slice-composition hard gate, ACs, KPIs, DoR, optional peer review, handoff, Wave Decisions Summary |

Load path: `~/.claude/skills/nw-{module}/SKILL.md`. Load the module whose trigger matches your current moment; the triggers partition the DISCUSS phase-space — every section lives in exactly one module. Do NOT re-inline a module's content into this core. Phase 1.5 (Scope Assessment) and Epic Mode stay in this core (below) — they are AT-pinned to this file.

## Workflow (phase order)

At the start of execution, create these tasks using TaskCreate and follow them in order, loading each phase's module at that phase: prior-wave reading → wave-entry decisions → Phase 1 (JTBD analysis) → Phase 1.5 (Scope Assessment, below) → Phase 2 (Journey Design) → Phase 2.5 (User Story Mapping) → Phase 3 (Requirements and User Stories).

## Migration gate (SSOT + greenfield bootstrap)

If `docs/product/` does not exist but `docs/feature/` has existing features, STOP. The project has old-model features that should be migrated to SSOT before new waves run. Guide the user to `docs/guides/migrating-to-ssot-model/README.md` and complete the migration first. If `docs/product/` does not exist and no old features exist (greenfield), DIVERGE owns the greenfield bootstrap — in the canonical DISCOVER → DIVERGE → DISCUSS order, DIVERGE initializes `docs/product/` (via `jobs.yaml`) before DISCUSS runs. DISCUSS does not bootstrap it; the gate-IN MIGRATION_UNMET signal is advisory (soft-gate), so DISCUSS proceeds and updates the SSOT it finds.

## Reasoning mandate (D-caveman, Ale 2026-06-10)

Discuss-wave working prose + reports = caveman: verdict-first, tables over prose, zero narrative. Depth modulated by `rigor` profile, never by padding.

## Output Tiers (per D2)

Provenance: feature `lean-wave-documentation` — D2 (schema-typed sections), D10 (one-line expansion descriptions), DDD-7 (DISCUSS pilot wave), D6 (install-time pedagogical prompt). Tier-1 [REF] sections (always emitted) + Tier-2 EXPANSION CATALOG items (lazy, on-demand) are the two output bands. Full contract: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Tier-1 [REF] — always emitted

Under `## Wave: DISCUSS / [REF] <Section>` headings:

- Persona ID — one-line user identifier mapped to the journey
- JTBD one-liner — single-sentence Job-to-be-Done statement
- Locked decisions — D-numbered design decisions with verdicts
- User stories with elevator pitches — every story has Before/After/Decision-enabled triplet
- Slice Plan — `## Wave: DISCUSS / [REF] Slice Plan`, a five-column fixed-order carpaccio table (Slice, Value statement, Status, Annotation, Justification). Emitted when `workflow.mode == atdd_pure` (ADR-028 D2 / ADR-029 D3); the PO authors it in place of UAT-scenario user stories, and it replaces the user-story + AC sections as the decomposition + value SSOT. Structurally checked by the feature-delta validator (gate-id in `nWave/gates/_catalog.yaml`) with `--require-slice-plan` (verdict `accepted`). <!-- mode-ref-ok -->
- Expectation Charters — one per slice that promises observable value (evolution-plan P2.0/P2.1). The PO derives each charter from that slice's Value statement and writes it to `docs/product/expectations/{feature-id}/{intent-name}.md` using `nWave/templates/expectation-charter.md`. See §Expectation Charter below. Authoring the charter is what ARMS the DELIVER EXAMINE step + the commit-slice examine-verdict gate for that feature (no charter → the gate is unarmed and DELIVER falls back to the legacy reviewer audit). <!-- mode-ref-ok -->
- Acceptance criteria (ACs) — testable, embedded per story (classic mode; under `atdd_pure` the per-slice `.feature` ATs are the AC SSOT, authored downstream in DISTILL) <!-- mode-ref-ok -->
- Definition of Done (DoD) — 9-item checklist
- Out-of-scope — explicit non-goals
- WS strategy — A/B/C/D per Mandate 5
- Pre-requisites — dependencies on prior waves or features
- Epic-mode — when the request is bigger than one feature, `/nw-discuss --epic <id>` authors an epic-delta (epic-JTBD + Feature Plan) instead of a feature-delta; see §Epic Mode below. Discoverable here as a Tier-1 capability and surfaced by the Phase 1.5 escalation (slice-04).

### Tier-2 EXPANSION CATALOG — lazy, on-demand (per D10)

Rendered under `## Wave: DISCUSS / [WHY|HOW] <Section>` only when requested via `--expand <id>` (DDD-2), the wave-end menu (`expansion_prompt = "ask"` or `"ask-intelligent"`), `mode = "full"` auto-expansion, or an ad-hoc user request mid-session.

| Expansion ID | Tier label | One-line description |
|---|---|---|
| `jtbd-narrative` | [WHY] | Full JTBD analysis: job dimensions (functional/emotional/social), four forces, opportunity scores |
| `persona-narrative` | [WHY] | Extended persona: goals, frustrations, mental model, vocabulary glossary |
| `alternatives-considered` | [WHY] | Decision rationale: alternatives weighed and rejected per locked decision |
| `migration-playbook` | [HOW] | Step-by-step migration guide for users on a prior version |
| `journey-deep-dive` | [HOW] | Full UX journey: emotional arc, shared artifacts registry, error-path map |
| `gherkin-scenarios` | [HOW] | Generated Gherkin scenarios covering happy path and key error paths |
| `reviewer-findings-trace` | [WHY] | R1-R10 reviewer findings chain with verdicts and how each landed in D1-D10 |
| `expansion-catalog-rationale` | [WHY] | Why this set of expansions, why these defaults, why D10 enforces one-line descriptions |

## Density resolution (per D12)

Call `resolve_density(global_config)` from `scripts/shared/density_config.py` after reading `~/.nwave/global-config.json` (missing/malformed = empty dict). Returns `mode` (`"lean"` | `"full"`) + `expansion_prompt` (`"ask"` | `"ask-intelligent"` | `"always-skip"` | `"always-expand"` | `"smart"`) per the D12 cascade (resolver-internal, DDD-5 — do NOT replicate locally). DISCUSS hard default is `lean`+`ask-intelligent` per Decision 4 (2026-04-28). Branch on `density.mode` (lean = Tier-1 only; full = Tier-1 + all Tier-2) and at wave end on `density.expansion_prompt`. Full cascade detail, branch semantics, ad-hoc override workflow: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Trigger detection (`ask-intelligent` mode, per Decision 4)

DISCUSS-specific extension on top of the shared contract. When `expansion_prompt = "ask-intelligent"`, evaluate ALL triggers below against the wave artifacts produced so far. Each trigger that fires contributes its suggested expansion to a scoped menu. If NO trigger fires, emit no menu — strict lean output.

| Trigger | Detection criterion | Suggested expansion |
|---------|--------------------|--------------------|
| AC ambiguity | ≥2 user stories share an AC where reasonable readers could disagree on the outcome | `gherkin-scenarios` |
| Cross-context complexity | Feature touches ≥3 bounded contexts (per DDD glossary) OR ≥3 distinct technologies | `alternatives-considered` |
| Multi-stakeholder need | ≥3 distinct personas referenced across the user stories | `persona-narrative` |
| Compliance / regulatory | ACs reference regulatory terms (GDPR, HIPAA, SOX, audit, retention, encryption, PII, data residency) | `migration-playbook` (data migration) OR `journey-deep-dive` (user-facing) |
| WS strategy = D | Walking Skeleton strategy is "Configurable" (env-switching) | `alternatives-considered` |

Menu when 1+ trigger fires: `Suggested expansions for this feature (triggered by: {trigger names}): - {id}: {description} ... Apply? [Y/n/all/none/custom]`. Do NOT show the generic 8-item Tier-2 catalog in `ask-intelligent` mode — only triggered items. Ad-hoc override path ("expand <X>") still works for any catalog item. Telemetry: one event per scoped-menu choice; when NO trigger fires, one `choice = "skip"` event with `expansion_id = "*"` records the silent-lean opportunity.

## Telemetry (per D4 + DDD-6)

Every expansion choice emits a `DocumentationDensityEvent` (dataclass at `src/des/domain/telemetry/documentation_density_event.py`) via `event.to_audit_event()` → `JsonlAuditLogWriter().log_event(...)`. Schema fields per D4: `feature_id`, `wave`, `expansion_id`, `choice`, `timestamp`. For this wave the schema declares `"wave": "DISCUSS"`. Use helper `scripts/shared/telemetry.py:write_density_event(...)` — do NOT write JSONL directly.

Wave-specific signal: feeds DDD-7 pilot success metric (4) — "downstream agent regression — DESIGN consumes lean DISCUSS feature-delta.md and produces no `--expand` invocation". `ask-intelligent` emission rules: one expand event per scoped-menu acceptance; one skip event for no-trigger silent-lean; one skip event for triggers fired but user declined. Full emission rules + per-mode patterns: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Expectation Charter (atdd_pure — arms the DELIVER EXAMINE step) <!-- mode-ref-ok -->

Provenance: evolution-plan P2.0/P2.1 (evidence-by-execution). For each Slice Plan row that promises **observable value**, the PO authors ONE expectation charter — the human-intent, re-examinable product document the User-Examiner ("Vera") walks in DELIVER.

- **Path**: `docs/product/expectations/{feature-id}/{intent-name}.md`. `{intent-name}` is kebab-case and NAMES THE INTENT from the user's side (e.g. `a-visitor-confirms-a-seat-and-finds-it-in-their-bookings`), never the implementation.
- **Template**: `nWave/templates/expectation-charter.md`. Fill: Intent (derived from the slice Value statement), Preconditions/start-recipe (how to launch + which surfaces), Charter (what to explore), **Expected observations (the oracle) — INCLUDING at least one negative observation** (the system must NOT claim success while the outcome is absent), and an append-only Session log.
- **Charter, not click-script**: describe the outcome to observe, not a keystroke sequence — independence must survive re-execution (the same charter, re-run by a different examiner or a swarm, must produce comparable logs; divergence = signal).
- **Two independent derivations**: the acceptance-designer (DISTILL) derives the ATs and the examiner derives its walk from the SAME value statement, INDEPENDENTLY — the crafter never authors either. The charter is the examiner's half.
- **Arming contract**: writing at least one charter under `docs/product/expectations/{feature-id}/` ARMS the DELIVER EXAMINE step and the commit-slice examine-verdict gate for that feature. A slice that promises observable value but ships no charter leaves the gate unarmed — flag it (the observable-value slice was meant to be examined).
- For a backend-only slice the charter's surface is the API (the examiner acts as an API consumer); for an infra/observability outcome the charter names a concrete observable surface (see evolution-plan P2.3 — open design).

## Agent Invocation

@nw-product-owner

<!-- DES-WAVE: discuss -->
<!-- gates-ref: discuss -->
<!-- outputs-ref: discuss -->

The DISCUSS gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/discuss.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This skill narrates DISCUSS intent (it produces a slice plan the architect consumes)
but does NOT enumerate gate-ids or the [REF]-section list inline; consult the registry
for the authoritative gate stack + output contract.

Include the `<!-- DES-WAVE: discuss -->` marker line above verbatim in the Agent dispatch prompt — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

IF Decision 4 = Yes (default): Execute *jtbd-analysis for {feature-id}, then *journey informed by JTBD artifacts, then *story-map, then *gather-requirements with outcome KPIs. Every user story must include a `job_id` field traceable to `docs/product/jobs.yaml`. **THEN, before closing the wave, author the Expectation Charters — this is a REQUIRED step, not an optional deliverable (§Expectation Charter): for EACH Slice Plan row that promises observable value, WRITE `docs/product/expectations/{feature-id}/{intent-name}.md` from `nWave/templates/expectation-charter.md`, deriving the Intent from that row's Value statement, with ≥1 NEGATIVE observation in the oracle. Writing the charters is what ARMS the DELIVER EXAMINE gate; skipping this step ships the feature un-examinable. Emit the list of charter paths written in the wave summary.**
IF Decision 4 = No (infrastructure-only escape valve): Execute *journey for {feature-id}, then *story-map, then *gather-requirements with outcome KPIs. Every story must use `job_id: infrastructure-only` AND include an `infrastructure_rationale` field. Reviewer rejects this branch for any user-facing feature.

Context files: see `nw-discuss-prior-wave-reading` (Prior Wave Consultation) + project context files.

**Configuration:**
- format: visual | yaml | gherkin | all (default: all)
- research_depth: {Decision 3} | interactive: high | output_format: markdown
- elicitation_depth: comprehensive | feature_type: {Decision 1}
- walking_skeleton: {Decision 2}
- output_directory: docs/feature/{feature-id}/discuss/

## Phase 1.5: Scope Assessment (Elephant Carpaccio early gate)

**Per Decision 3 (2026-04-28)**: scope assessment runs BEFORE journey visualization investment to detect oversized features early and save rework. The agent (`nw-product-owner`) runs this as workflow Phase 2 (between Discovery and Journey Visualization).

Oversized signals (closed list — ESC-1, NO new heuristics): >10 user stories · >3 bounded contexts or modules · walking skeleton requires >5 integration points · estimated effort >2 weeks · multiple independent user outcomes that could ship separately.

**Escalation contract (ESC-1..ESC-6)** — when 2+ signals fire, the request is bigger than one feature. The detection ESCALATES to epic-mode:

- **Explain** (ESC-2): NAME each fired signal with its observed evidence — never a generic "this looks big".
- **Propose** (ESC-3): propose epic-mode and NAME the literal `--epic` flag (discoverability floor — the user discovers the capability at the moment of need).
- **Ask** (ESC-4): ASK confirmation with closed options (switch to epic-mode / continue feature-level). NEVER auto-switch — the tool proposes, the human decides (§22.0-coherent).
- **Decline** (ESC-5): the user declines → standard feature-level DISCUSS continues, zero epic artifacts.
- **Right-sized** (ESC-6): fewer than 2 signals fire → zero escalation, zero new prompts. Note `## Scope Assessment: PASS` in `wave-decisions.md`.

On confirmation the run switches to epic-mode (§Epic Mode below). Deeper Elephant Carpaccio slicing of a right-sized feature happens later in Phase 2.5 (User Story Mapping). Gate: scope assessed; right-sized (zero prompts) OR escalation raised (named signals + `--epic` proposal + confirmation ask) and the user's decision honored.

## Epic Mode (`--epic`)

The hierarchy is epic → feature → slice. `feature → slice` has full discipline (Slice Plan, carpaccio taste tests, cohesion-MECC). `epic → feature` is epic-mode: same DISCUSS wave, one level up. Invoked when a request spans multiple independently-shippable features.

### Invocation

- Explicit: `/nw-discuss --epic <epic-id>` (`<epic-id>` kebab-case).
- Escalated: Phase 1.5 oversized-detection proposes `--epic` and asks confirmation (slice-04 ESC contract). The tool proposes, the human decides — never auto-switches.

Epic-mode runs under the SAME DISCUSS gates as feature-level (wave-active anchor · gate-IN/OUT · PO-review veto) — UNCHANGED. The only difference is the artifact and its decomposition granularity.

### What it produces (fractal JIT)

Epic-mode produces ONLY the plan — `docs/epic/{id}/epic-delta.md`. It does NOT create any `docs/feature/{id}/` workspace, feature-delta, or downstream artifact. Each feature's full DISCUSS runs just-in-time when that feature is picked up (its row flips `pending` → `in-flight` and gains its `docs/feature/{id}/` link at that moment). Generating N feature-deltas upfront is a fractal-JIT violation by definition.

### Epic-delta contract (EDC — what the `--epic` procedure authors)

| # | Contract |
|---|----------|
| EDC-1 | Path `docs/epic/{epic-id}/epic-delta.md`, kebab-case id |
| EDC-2 | Title line `# Epic Delta: {epic-id}` |
| EDC-3 | Epic-JTBD section under `## Wave: DISCUSS / [REF] Epic Job & Intent` (When-I-want-so-that + persona) |
| EDC-4 | Feature Plan under the EXACT heading `## Wave: DISCUSS / [REF] Feature Plan`, five fixed columns `Feature \| Value statement \| Status \| Annotation \| Justification` (the Slice Plan grammar reused at feature granularity) |
| EDC-5 | Keystone = exactly ONE row annotated `@walking-skeleton` (Slice Plan annotation token reused — no new token) |
| EDC-6 | Dependency order = ROW ORDER, backward-only (row K depends only on rows < K); optional explicit `depends-on {feature-id}` in Annotation for a non-adjacent dependency, referencing an earlier row only |
| EDC-7 | Status tokens = closed set `pending \| in-flight \| shipped`; authored rows start `pending` |
| EDC-8 | Gate-OUT: the run ends with the feature-delta validator (gate-id in `nWave/gates/_catalog.yaml`) run `--require-feature-plan --format=json` over `docs/epic/{id}/epic-delta.md`, verdict `accepted` (slice-01 keystone validator) |
| EDC-9 | JIT: the run produces ONLY `epic-delta.md` — zero `docs/feature/{id}/` workspaces |

### Feature right-sizing (D-granularity)

A feature is right-sized when it is independently shippable + walking-skeleton-able + single JTBD outcome + ≈≤2 weeks. Carpaccio taste tests scale up to feature granularity:

- Keystone-abstraction-first: the `@walking-skeleton` feature ships the thinnest end-to-end vertical every later feature hangs on.
- Merge-if-identical-except-scale: two Feature Plan rows that differ only by scale → merge into one (name the merge in that row's Justification).
- A Feature Plan whose every row is `@infrastructure` carries no user value → `rejected-infra-only` (cohesion-MECC, slice-03). Mechanically non-representable.

### Gate-OUT (the mechanical exit)

The authored epic-delta MUST clear the slice-01 keystone validator before handoff:
run the feature-delta validator (gate-id in `nWave/gates/_catalog.yaml`) with
`--require-feature-plan --format=json` over `docs/epic/{id}/epic-delta.md`.

Exit 0 ⇔ verdict `accepted`. Closed verdict set: `accepted · malformed-wave-heading · missing-feature-plan · malformed-feature-plan · rejected-infra-only`. A non-`accepted` verdict blocks the epic-mode run — fix the Feature Plan and re-validate.

### Epic-delta maintenance (LSC — keeping the plan live)

The epic-delta is a LIVE tracker, not a write-once artifact. As features are picked up and finalized, the maintainer edits the Feature Plan rows in place so the plan always shows current progress — the next pickup is decided from the plan, not from memory.

- **Pick-up** (LSC-1) — when a feature's own DISCUSS starts, its row is ONE atomic edit: flip `pending` → `in-flight` AND change the Feature cell to a `docs/feature/{id}/` link. The link and the flip land together — never one without the other.
- **Finalize** (LSC-2) — at feature completion, flip the row `in-flight` → `shipped`.
- **Forward-only** (LSC-5) — status moves `pending` → `in-flight` → `shipped`, monotone. Never flip a row backward (`shipped` → `in-flight`, `in-flight` → `pending`) or skip ahead.
- **Closed token set** (LSC-6) — the only legal Status tokens are `pending | in-flight | shipped` (EDC-7). The maintenance procedure REJECTS any other token (e.g. `done`, `wip`, `blocked`) — the keystone validator does NOT validate Status cells (DC-1), so the procedure owns this rejection. A garbage token is a maintenance error to fix, not a state to record.
- **Fractal JIT on pick-up** (LSC-3) — ONLY the picked-up feature gets a `docs/feature/{id}/` workspace. A row still `pending` has NO workspace. Creating workspaces for not-yet-picked-up features is a fractal-JIT violation (it re-introduces the upfront-N-feature-deltas anti-pattern epic-mode exists to prevent).
- **Citation** (LSC-4) — the picked-up feature's own artifacts cite the epic BY NAME, and the backlog entry cites the epic by name (one home for the feature list — the epic-delta — never duplicated lists elsewhere).

A flip edits only the Status cell (and, on pick-up, the Feature cell link), so the document's structure is untouched and it still clears the slice-01 keystone gate (`accepted`) after every flip. Re-validate (Gate-OUT) after maintenance edits to confirm structural validity held.

## Gotchas (dogfood-surfaced, 2026-07-03)

Hard-won lessons from running DISCUSS on real features (two independent dogfoods: Python/infra + TS/product, which converged on the SAME form-defects — a strong signal they are real).

- **Infrastructure / internal features strain the user-journey machinery — do NOT fabricate a journey.** DISCUSS Phases 1-2 (JTBD, mental model, emotional arc, journey visualization) and Phase 4 (story-map backbone) are built around a human moving through screens. For an infra/tooling feature (`job_id: infrastructure-only` + Decision-3 = Lightweight) whose "outcome" is a CLI exit code / a gate firing, those phases are DEGENERATE: there is no screen, no emotional arc, one activity. The right move is NOT to fabricate a feeling or silently no-op four mandated phases — it is to go lean: the Slice Plan + Expectation Charters carry the real content; express the "emotion" as an Outcome KPI (maintainer trust that a caught defect class stays caught), and waive the journey/story-map artifacts explicitly (atdd_pure already waives user-stories — the same logic extends to journey/story-map for infra). Do not let the story-map "backbone present" or emotional-arc gates push you into ceremony a 1-2 day wiring task does not warrant. <!-- mode-ref-ok -->
- **Over-instruction is a confound — do NOT compensate for a weak native trigger with an emphatic prompt.** When dispatching the PO, if you find yourself adding "treat this as first-class, not optional" beyond what the skill natively says, that is the tell that the skill under-specifies — report it as a friction, do not paper over it. (Empirical: the charter-authoring step needed to be made a native REQUIRED dispatch step precisely because a documented [REF] deliverable alone did not trigger it.)
- **The Expectation Charter format is medium-agnostic** — it holds up on a CLI/gate outcome (start recipe = `des <cmd>`, oracle = exit code + JSON event + absence-of-ledger-record), not just a browser UI. Don't assume the seat-booking UI example is the only shape.

## Success Criteria

1. - [ ] JTBD analysis complete: all jobs in job story format (mandatory unless infrastructure-only escape valve)
2. - [ ] Job dimensions identified: functional|emotional|social per job
3. - [ ] Four Forces mapped per job (push|pull|anxiety|habit)
4. - [ ] Opportunity scores produced (when multiple jobs)
5. - [ ] UX journey map with emotional arcs and shared artifacts
6. - [ ] Every journey maps to at least one job
7. - [ ] Discovery complete: user mental model understood, no vague steps
8. - [ ] Happy path defined: all steps start-to-goal with expected outputs
9. - [ ] Emotional arc coherent: confidence builds progressively
10. - [ ] Shared artifacts tracked: every ${variable} has single documented source
11. - [ ] Story map created with backbone, walking skeleton, and **elephant carpaccio slices** (≤1 day each, each with a named learning hypothesis, each with its own slice brief at `docs/feature/{id}/slices/slice-NN-*.md`, all carpaccio taste tests passed)
12. - [ ] Outcome KPIs defined with measurable targets
13. - [ ] Prioritization suggestions based on outcome impact
14. - [ ] Requirements completeness score > 0.95
15. - [ ] Every user story traces to at least one job story (or `job_id: infrastructure-only` with rationale)
16. - [ ] All acceptance criteria testable
17. - [ ] DoR passed: all 9 items validated with evidence
18. - [ ] Per-wave peer review (OPTIONAL — invoked only on trigger; mandatory consolidated review fires at end of DISTILL)
19. - [ ] Handoff accepted by nw-solution-architect (DESIGN wave)

## Next Wave

**Handoff To**: nw-solution-architect (DESIGN wave) + nw-platform-architect (DEVOPS wave, KPIs only)
**Deliverables**: User stories + story map + outcome KPIs + SSOT journey/jobs updates | JTBD artifacts (when selected)

DISCUSS hands off to BOTH DESIGN (full artifacts) and DEVOPS (outcome-kpis.md only). DEVOPS and DESIGN can proceed in parallel — DESIGN receives the complete artifact set while DEVOPS receives only the KPI file to drive observability and instrumentation design.

## Outputs

**Single narrative file**: `docs/feature/{feature-id}/feature-delta.md` — all DISCUSS findings (Tier-1 [REF] sections + any rendered Tier-2 expansions) live here. User stories with embedded AC, story map, DoR validation, outcome KPIs, wave-decisions all become `## Wave: DISCUSS / [REF|WHY|HOW] <Section>` headings.

**Machine artifacts** (declared, parseable by downstream waves):
- `docs/feature/{feature-id}/slices/slice-NN-*.md` — slice briefs (one per elephant-carpaccio slice; consumed by DELIVER for roadmap-step decomposition)

**SSOT updates** (per Recommendation 3 / back-propagation contract):
- `docs/product/jobs.yaml` — add validated job stories (functional/emotional/social dimensions, four forces, opportunity score)
- `docs/product/journeys/{name}.yaml` — create or extend journey schema (refines DISCOVER seed)
- `docs/product/personas/{name}.yaml` — create or extend persona profile

Legacy multi-file outputs (`user-stories.md`, `story-map.md`, `dor-validation.md`, `outcome-kpis.md`, `wave-decisions.md`, `journey-{name}-visual.md` as separate files) are NOT produced — that content lives in `feature-delta.md`. Validator: `scripts/validation/validate_feature_layout.py`.

## Examples

### Example 1: User-facing feature with comprehensive UX research
```
/nw-discuss first-time-setup
```
Orchestrator asks Decision 1-3. User selects "User-facing", "No skeleton", "Comprehensive". Luna starts with JTBD analysis: discovers jobs like "When I first open the app, I want to feel productive immediately, so I can justify the purchase." Maps four forces for each job. Scores opportunities. Then runs journey discovery informed by JTBD, produces visual journey + YAML + Gherkin. Finally crafts stories where each traces to a job, validates DoR, and prepares handoff.

### Example 2: JTBD-only invocation
```
/nw-discuss --phase=jtbd onboarding-flow
```
Runs only Luna's JTBD analysis phase (job discovery + dimensions + four forces + opportunity scoring). Produces JTBD artifacts without proceeding to journey design or requirements. Useful for early discovery when you need to understand user motivations before committing to UX design.

### Example 3: Journey-only invocation
```
/nw-discuss --phase=journey release-nwave
```
Runs only Luna's journey design phases (discovery + visualization + coherence validation). Produces journey artifacts without proceeding to requirements crafting. Useful when JTBD is already done and journey design needs standalone iteration.

### Example 4: Requirements-only invocation
```
/nw-discuss --phase=requirements new-plugin-system
```
Runs only Luna's requirements phases (gathering + crafting + DoR validation). Assumes JTBD and journey artifacts already exist or are not needed (e.g., backend feature).
