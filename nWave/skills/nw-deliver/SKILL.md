---
name: nw-deliver
description: "Orchestrates the current DELIVER wave end-to-end. Use when all prior waves are complete and the feature is ready for implementation."
user-invocable: true
argument-hint: '[feature-description] - Example: "Implement user authentication with JWT"'
---

> **Code facts** — resolve structural facts about code (who-calls / defs-reads / never-wired / call-graph / atoms-in-file) through the `nw-code-analysis-port` skill: Tsunami-first via the `mcp__tsunami__*` tools, declared fallback (AST, then grep), degrade-LOUD. Never ad-hoc grep for a structural fact.

<!-- gates-ref: deliver -->
<!-- outputs-ref: deliver -->

The DELIVER gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/deliver.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This skill does not re-enumerate the gate stack inline; it POINTS at the registry.

# NW-DELIVER: Complete DELIVER Wave Orchestrator

**Wave**: DELIVER (wave 6 of 6)|**Agent**: Main Instance (orchestrator)|**Command**: `/nw-deliver "{feature-description}"`

## LANGUAGE CONVENTION FRAME (read FIRST — overrides all examples below)

**Code examples in this skill use Python syntax for illustration only.** They are NOT prescriptive about target language. nWave is language-agnostic per the "genericity and agnosticism" mandate (2026-05-24).

**Before crafting**, detect the target project's language from manifest files: `package.json` → TypeScript/JS; `Cargo.toml` → Rust; `go.mod` → Go; `pyproject.toml`/`setup.py`/`Pipfile` → Python; `pom.xml`/`build.gradle` → Java/Kotlin; `*.csproj`/`*.fsproj` → C#/F#; `Gemfile` → Ruby; `Package.swift` → Swift.

**When the target language is NOT Python**: adapt every code example to target conventions (imports, type system, test-framework idioms, file extensions, directory layout). Project conventions ALWAYS WIN over examples below.

**Empirical anchor**: skill examples being Python-only caused LLM to emit Python code in greenfield TS project. Fix per F-SKILL-EXAMPLES-LANGUAGE-LEAK. Connects [[feedback_language_adapter_plugin_architecture_2026_05_24]].

## Overview

Orchestrates complete DELIVER wave: feature description → production-ready code with mandatory quality gates. You (main Claude instance) coordinate by delegating to specialized agents via Task tool. Final wave (DISCOVER > DIVERGE > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER).

Sub-agents cannot use Skill tool or `/nw-*` commands. You MUST:
- Read the relevant command file and embed instructions in the Task prompt
- Remind the crafter to load its skills as needed for the task (skill files are at `~/.claude/skills/nw-{skill-name}/SKILL.md`)

## Composition (load by trigger)

This core holds the mode dispatch, the per-slice spine + feature-end cycle, the dispatch markers + entry gate + per-slice phase table, prior-wave reading, the rigor profile, and the output contract — and COMPOSES the narrow `nw-deliver-*` modules below. Do NOT re-inline a module's content into this core.

| Module | Kind | Trigger — load when... | Covers |
|---|---|---|---|
| `nw-deliver-atdd-pure-slice-gates` | PROCEDURE | a per-slice phase boundary beyond the A_GREEN entry dispatch must be governed (C_REVIEWER_AUDIT verdict routing, D_REFACTOR_COMMIT dispatch, D_REFACTOR_COMMIT commit close) | D_REFACTOR_COMMIT exit gate (E1 + E2), Phase D Routing, Separation Enforcement, Verdict-Hash Trailer, Telemetry per Phase Boundary |

Load path: `~/.claude/skills/nw-{module}/SKILL.md`. Load the module whose trigger matches your current moment; every extracted section lives in exactly one module.

## Output Tiers (per D2)

Provenance: feature `lean-wave-documentation` — D2 (schema-typed sections), D10 (one-line expansion descriptions). Tier-1 [REF] sections (always emitted) + Tier-2 EXPANSION CATALOG items (lazy, on-demand) are the two output bands. Implementation details live in code; the wave-delta sections are pointers + structured summaries. Full contract: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Tier-1 [REF] — always emitted

Under `## Wave: DELIVER / [REF] <Section>` headings:

- Implementation summary — one-paragraph description of what shipped (no design rationale)
- Files modified — categorized list (production, tests, docs) with one-line per file
- Scenarios green count — `<N> of <M>` from the `.feature` file with timestamp
- DoD check — itemized pass/fail against the DISCUSS Definition of Done items
- Demo evidence — captured stdout/exit-code per Elevator Pitch demo command (Phase 3.5 gate)
- Quality gates — per-phase outcomes (refactor, review, integrity, plus mutation ONLY when `rigor.mutation_enabled = true` — deprecated/opt-in-only per FR-1, CLAUDE.md § Mutation Testing Strategy, off by default)
- Pre-requisites — DISTILL scenarios + DESIGN component manifest the implementation depended on

### Tier-2 EXPANSION CATALOG — lazy, on-demand (per D10)

Rendered under `## Wave: DELIVER / [WHY|HOW] <Section>` only when requested via `--expand <id>` (DDD-2), the wave-end menu (`expansion_prompt = "ask"`), `mode = "full"` auto-expansion, or an ad-hoc user request mid-session.

| Expansion ID | Tier label | One-line description |
|---|---|---|
| `refactoring-journal` | [HOW] | L1-L6 refactoring log with rationale per micro-transformation |
| `retrospective-notes` | [WHY] | 5 Whys analysis on issues encountered, lessons learned, what to repeat/avoid |
| `performance-measurements` | [WHY] | Benchmarks, profiling output, latency/memory deltas vs baseline |
| `alternative-implementations-rejected` | [WHY] | Implementation approaches tried and rejected with one-paragraph reason each |
| `mutation-testing-report` | [HOW] | Mutmut/Pitest output: kill rate, surviving mutants, mitigation actions |
| `architecture-decision-deviations` | [WHY] | Where DELIVER deviated from DESIGN and the back-propagation logged in upstream-issues.md |
| `coverage-deltas` | [HOW] | Per-module coverage delta with rationale for any drops |
| `expansion-catalog-rationale` | [WHY] | Why this set of expansions, why these defaults, why D10 enforces one-line descriptions |

## Density resolution (per D12)

Call `resolve_density(global_config)` from `scripts/shared/density_config.py` after reading `~/.nwave/global-config.json` (missing/malformed = empty dict). Returns `mode` (`"lean"` | `"full"`) + `expansion_prompt` (`"ask"` | `"always-skip"` | `"always-expand"` | `"smart"`) per the D12 cascade (resolver-internal, DDD-5 — do NOT replicate locally). Branch on `density.mode` for what to emit; branch on `density.expansion_prompt` at wave end for menu behaviour. Full cascade detail, branch semantics, ad-hoc override workflow: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Telemetry (per D4 + DDD-6)

Every expansion choice emits a `DocumentationDensityEvent` (dataclass at `src/des/domain/telemetry/documentation_density_event.py`) via `event.to_audit_event()` → `JsonlAuditLogWriter().log_event(...)`. Schema fields per D4: `feature_id`, `wave`, `expansion_id`, `choice`, `timestamp`. For this wave the schema declares `"wave": "DELIVER"`. Use helper `scripts/shared/telemetry.py:write_density_event(...)` — do NOT write JSONL directly. **NOT YET WIRED**: `scripts/shared/telemetry.py` does not exist yet and `DocumentationDensityEvent(` has zero constructor call sites in `src/des` — until this lands, skip the emission (the [WHY]/[HOW] section append is unaffected); do not hand-roll a substitute JSONL write.

Wave-specific signal: a DELIVER wave recording `choice = "expand"` for `retrospective-notes` indicates the team needed deeper learning capture; over time the data drives whether retrospective notes should be promoted to Tier-1. Full emission rules: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## CRITICAL BOUNDARY RULES

1. **NEVER implement steps directly.** ALL implementation MUST be delegated to the selected crafter (@nw-software-crafter or @nw-functional-software-crafter per step 1.5) via Task tool with DES markers. You are ORCHESTRATOR — coordinate, not implement.
2. **Use the selected workflow's evidence carrier.** The current spine records the AT-completion ledger and commit trailers; do not create a parallel step log.
3. **Use the feature delta and acceptance tests as the work contract.** Extract each slice from the `[REF] Slice Plan` and its DISTILL-authored ATs.

**DES monitoring is non-negotiable.** Circumventing DES — faking step IDs, omitting markers, or writing log entries manually — is a **violation that invalidates the delivery**. DES detects unmonitored steps and flags them; finalize **blocks** until every flagged step is re-executed through a properly instrumented Task. There is no workaround: unverified steps cannot pass integrity verification, and the delivery cannot be finalized. Without DES monitoring, nWave cannot **verify** TDD phase compliance. For non-deliver tasks (docs, research, one-off edits): `<!-- DES-ENFORCEMENT : exempt -->`.


Before any phase work, read `.nwave/config.yaml` key `workflow.mode`. The DELIVER wave has **two sibling top-level workflows** — not one workflow with an inner swap. `workflow.mode` branches the **entire orchestration flow** at this single dispatch point, so the orchestrator cannot fall through from one spine into the other. <!-- mode-ref-ok -->



<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->


## ATDD-Pure Roadmap-Free Spine (workflow.mode = atdd_pure) <!-- mode-ref-ok -->

Reference: ADR-028 D1/D2/D3/D5 · ADR-027 per-slice DELIVER sequence (carried forward, reduced to the 3 canonical phases) · rollout feature-delta `docs/feature/atdd-pure-roadmap-free-rollout/feature-delta.md`.

This spine is roadmap-free and execution-log-free. It creates **no roadmap.json** and **no execution-log.json**. Decomposition is carried by the feature-delta `## Wave: DISCUSS / [REF] Slice Plan` table; audit is carried by the AT-completion ledger + commit trailers.

**Setup (atdd_pure).** Parse input, derive `feature-id`, then provision the AT-completion ledger directory: <!-- mode-ref-ok -->

```
mkdir -p .nwave/telemetry/atdd-pure/
```

The DES sequencer creates `.nwave/telemetry/atdd-pure/{feature-id}.jsonl` on first append. The per-phase-boundary JSONL record uses `telemetry_schema_version` `1.1.0` (adds `slice_id` + `at_ids` over the retired workflow `1.0.0` record — ADR-028 D5).

**Auto plan-mode at DELIVER-open — derive the delivery plan from the Slice Plan.** Before the first slice dispatch, the orchestrator enters plan mode (native `EnterPlanMode`) and derives a followable delivery plan from the feature-delta's `[REF] Slice Plan` — one plan item per `pending` slice, in Slice-Plan order. The plan is read from the delta (zero drift, never invented); the human approves (or requests a correction) via plan mode's native gate BEFORE delivery; on approval `TaskCreate` projects one todo per slice (its value statement + entry-gate verification + `A_GREEN` dispatch, through `EXAMINE`→`COMMIT`) so the wave is followable. Same shape as DISTILL-open (nw-distill §Auto plan-mode) — proactive-inline, enforcement-cost on the system, no `des plan` CLI.

**Surface the feature-end gate expectations INLINE at DELIVER-open (GDP-2 inline affordance).** The feature-end gates fire at the very end — a defect they catch (a never-executed production file, a build broken on fresh clone, a failing environmental e2e) has by then existed since the first commit. So the DELIVER-open plan does not only enumerate the slices; it also surfaces, up front, the checklist those late gates will apply, so the operator authors WITH them in mind rather than discovering them at the wall:
- **`verify-execution-reach`** — every production file the feature adds/touches must be reached by an executed test/golden run (a file with zero coverage hits fails feature-end). Author each slice so its production code is exercised by its own AT, not left dormant.
- **`verify-fresh-clone`** — the feature's `.nwave/demo-recipe.json` must build + run clean in a fresh export (`git archive HEAD | tar -x` then the recipe). Keep the recipe current as you add build steps; do not leave a build broken-on-fresh-clone.
- **`verify-environmental-e2e`** — the feature's `## Environmental E2E` block must pass after a real build + install (`des verify-environmental-e2e --mode run`). Author the e2e alongside the code, not retrofitted at feature-end.
These are the floor at feature-end; naming them at DELIVER-open is the proactive-inline half — the gate stays as the reactive floor, the affordance moves the knowledge before the effort.

**Per-slice carpaccio loop in place of Phase 1.** There is no whole-feature roadmap-step extraction. In place of Phase 1 roadmap creation, the spine runs the carpaccio entry_gate followed by a **per-slice** DISTILL→DELIVER loop — one A_GREEN→C_REVIEWER_AUDIT→D_REFACTOR_COMMIT pass per slice:

1. Read the next `pending` slice from the feature-delta `[REF] Slice Plan` table; read its `Class` column.
2. **`Class = C`** — run the carpaccio slice gate as the DES `entry_gate` in place of Phase 1 roadmap creation, before the first `A_GREEN` dispatch:
   `des carpaccio-slice-gate --feature-id {feature-id} --entering-slice {slice-NN}`.
   Exit 0 → dispatch the per-slice DELIVER sequence (see §ATDD-Pure DELIVER Sequence). Exit 44/45 → halt with the gate payload.
3. **`Class = P`** — the carpaccio entry_gate is SKIPPED; the spine runs the coherence check for the slice instead (see slice-04 spine routing note at the carpaccio entry_gate), then a single D_REFACTOR_COMMIT commit.
4. At the slice's D_REFACTOR_COMMIT commit, flip the slice plan row `pending → shipped`; advance to the next slice. The feature is complete when every slice row is `shipped`.


### Feature-End Cycle (atdd_pure) — runs ONCE after the last slice <!-- mode-ref-ok -->

Reference: ADR-028 D6 (ratified 2026-05-20).

The per-slice carpaccio loop keeps each slice's cycle lean — a slice ships through `A_GREEN` (AT-greening with coverage cleanup absorbed), a light `C_REVIEWER_AUDIT` slice review, the terminating contract-gate run and the `D_REFACTOR_COMMIT` commit. Whole-feature refactoring and deep adversarial review are deliberately NOT run per slice: refactoring slice-1's code only for slice-2 to add more code is re-work, and a deep review per slice re-reviews code that is still changing. Per the batch-then-verify principle (`feedback_refactor_batch_when_test_suite_slow_2026_05_19`) those passes belong at FEATURE scope.

`/nw-deliver` therefore runs ONE **feature-end cycle** after the last slice's `D_REFACTOR_COMMIT` commit — once the slice-plan loop is exhausted (every `[REF] Slice Plan` row `shipped`) and the coherent feature exists on disk.

**Feature-end preconditions — verify these BEFORE `des feature-end run` (else it refuses reactively):**

- [ ] Every declared Slice-Plan slice is SliceCommitVerified (all slices shipped) — the truncation oracle refuses otherwise.
- [ ] The feature-end EXAMINE has run: for EACH critical charter under `docs/product/expectations/{feature-id}/`, dispatch `@nw-user-examiner` (Vera) at FEATURE scope (hostile re-walk of the finished feature) and record her PASS with `des record-examine-verdict --feature-id {id} --slice feature-end --charter <path> --verdict PASS --observations "..." --examiner nw-user-examiner`. Missing this is the `ExamineVerdictMissing` reactive refusal.
- [ ] `des verify-doc-coherence --repo .` exits 0 (the scoped default now skips forward-looking/example docs; fix any REAL dead-link in a reference/guide/README doc first).
- Then run `des feature-end run --repo . --feature-id {id} --feature-dir docs/feature/{id} --reviewer-agent-id <reviewer> --verdict APPROVED`.

Satisfy each BEFORE the run — each maps to a reactive refusal you avoid by doing it proactively. The four steps below are the how; the checklist above is the proactive pre-flight.

The feature-end cycle has five steps, in order:

1. **`D_REFACTOR_COMMIT` (feature scope)** — L1-L6 refactoring across the WHOLE feature's code, batch-then-verify: all edits batched, ONE test run after the batch. Refactoring the finished, no-longer-changing feature once replaces N per-slice refactor passes.
2. **Feature-end EXAMINE — hostile-probe the critical charters** (evolution-plan P2.2). The per-slice EXAMINE proved each slice's promised outcome in isolation; the feature-end EXAMINE re-walks the CRITICAL charters (the observable-value slices whose failure is a feature-breaker) on the coherent finished feature, with HOSTILE inputs — the failure modes a happy-path walk misses (malformed/adversarial input, cross-slice state interaction, the negative-oracle pushed hard). Dispatch `@nw-user-examiner` ("Vera") on each critical `docs/product/expectations/{feature-id}/*.md` charter against the whole running feature; she records via `des record-examine-verdict` (with a feature-end-scoped slice marker). If she dies before that record lands, apply the recovery fallback in `nw-execute` §Recovery Fallback — recover from her final message's verbatim verdict, never re-guess it. This is execution-observation at feature scope — it is what REPLACES the swarm-review + final-review reviewer-return deadlock class with an observer that runs the thing. **Mechanical enforcement is the P2.2 code-remainder (NOT yet wired): the done-gate must refuse feature-done without a feature-end examine PASS, and the P0 execution gates (fresh-clone / execution-reach / doc-coherence, evolution-plan P0.1/P0.4/P0.5) must fire at step 4 alongside env-e2e. Until that lands, this step is orchestrator-dispatched (advisory), not gate-enforced — catalogued-not-yet-fired, tracked honestly.**
3. **Deep feature-end review** (retained as the code-reading complement to the feature-end EXAMINE — the two are orthogonal: EXAMINE observes execution, the review reads structure): full AT-completeness audit, residuality / RPP stress, cross-slice architecture coherence. Because the code no longer changes, the review sees the whole and a cross-cutting gap can be diagnosed. The verdict carries the same `Reviewed-by:` verdict-hash trailer as a per-slice D_REFACTOR_COMMIT review; the verdict-hash chain terminates here.

   **Haiku panel (throughput).** This step MAY fan out as parallel Haiku reviewers, each on a distinct lens (correctness / AT-density-completeness / security / architecture-coherence), plus an adversarial verify pass (majority-refute kills a contested finding), synthesized by the orchestrator into the single verdict. Wall-clock = the slowest lens (~3-5 min) vs. a serial pass (~10-15 min); cost stays Haiku throughout. Per-slice EXAMINE stays Vera-Haiku unchanged (already v2) — this note is feature-end-scope only. Aligns with the standing rule: never Opus for an audit, reviewers run Haiku.
4. **Final integrity verification** — one final integrity pass. FIRST, the whole-tree full contract run, run once here: `run_contract_gate --repo .` (the full whole-tree run that per-slice `D_REFACTOR_COMMIT` no longer runs); fix any cross-slice or cross-feature regression before the feature is declared done. THEN the integrity pass via `des verify-integrity` (mode-aware, D4): the AT-completion ledger (every `.feature` scenario greened), the slice plan (every row `shipped`), the commit-trailer chain. As part of this step the DES sequencer runs `verify_environmental_e2e --mode run` (the cross-tree environmental-e2e gate floor — `des verify-environmental-e2e` console script, fix-oss-environmental-e2e-gate) and appends its `EnvironmentalE2eGateRan` heartbeat + `EnvironmentalE2eVerified` verdict to the AT-completion ledger; the done-gate blocks declaring the feature done unless both records are present (residuality RM-1 / R10).
5. **Archive + session cleanup (`/nw-finalize`)** — once feature completion evidence is current, `/nw-deliver` composes `/nw-finalize @{reviewer-agent} "{feature-id}"` to create the evolution summary, copy lasting design docs to permanent directories, preserve `docs/feature/{feature-id}/` as living history, and remove only explicitly user-approved session artifacts. Certify (`feature-end`) THEN archive (`finalize`) — the feature is CLOSED, not merely attested. `nw-finalize` owns its completion-evidence check and archive procedure; this step only sequences the call, it does not re-specify it. <!-- mode-ref-ok -->

The carpaccio `entry_gate` and the `D_REFACTOR_COMMIT` `exit_gate` stay strictly per-slice — the feature-end cycle is a final pass *after* the last slice's exit gate; it adds no per-slice gate and removes none.

**Feature-end-cycle resume cue.** A `/nw-deliver` run can be interrupted either *in the slice loop* (some slice rows still `pending` — `/nw-continue` restarts the `/nw-execute` loop at the first un-`shipped` slice) or *inside the multi-step feature-end cycle*, where ALL slice rows are already `shipped` and the Status column gives no signal. For the second case there is NO per-step ledger checkpoint — a step-boundary `FeatureEndCheckpoint` record was named in ADR-028 D6 but never implemented (zero producers in `src/des`; confirmed by `docs/feature/des-next-loop-projection/feature-delta.md`). The real resume cue is coarser: the AT-completion ledger's latest `FeatureEndPending` record (real, durable — written by `des commit-slice` on the last slice) means the cycle has not yet durably concluded. From there, `/nw-continue` re-runs `des feature-end run` (idempotent, safe to repeat) and reads ITS OWN exit code / stdout payload — `FeatureEndCycleComplete` / `FeatureEndCycleRefused` / `FeatureEndCycleIndeterminate` (CLI-stdout only, NOT ledger-durable) — to learn the current outcome. The feature-end branch is "run the command again", never "resume from a mid-cycle step".

## ATDD-Pure DELIVER Sequence — invoked when workflow.mode = atdd_pure <!-- mode-ref-ok -->

Reference: ADR-027 §Decision · plan v3 §4 §7 · domain types `src/des/domain/atdd_pure_phases.py`.

Replace per-step `RED→GREEN→COMMIT` dispatch with this per-slice A_GREEN→C_REVIEWER_AUDIT→D_REFACTOR_COMMIT sequence. One Agent invocation per phase per slice.

**EXAMINE is the v2 semantics of the middle slot** (evolution-plan P2.1/P1.2). `ATDDPurePhase.EXAMINE` is a value alias of `C_REVIEWER_AUDIT` — the SAME phase slot and the SAME `DES-PHASE : C_REVIEWER_AUDIT` marker value; what CHANGES is who runs in it and what evidence clears the slice. The slot is **armed for EXAMINE when a charter exists for the feature** at `docs/product/expectations/{feature-id}/*.md` (authored by the PO in DISCUSS — see nw-discuss §Expectation Charter). **Armed** → the slot is an EXAMINE step: dispatch `@nw-user-examiner` ("Vera") with ONLY the charter; she walks the promised outcome through the REAL surface (as a user for UI/HTTP, as an API consumer for backend-only) and records her verdict with `des record-examine-verdict --repo . --feature-id {id} --slice {slice-NN} --charter {path} --verdict PASS|FAIL|INDETERMINATE --observations "…" --examiner nw-user-examiner`. The commit-slice gate then REFUSES the slice commit unless a PASS verdict exists whose charter-seal matches the current charter bytes (execution-observation replaces the code-reading audit; the dormant-seam / testing-theater class dies at outcome-absence). If Vera dies before self-recording, the orchestrator recovers per `nw-execute` §Recovery Fallback. **Unarmed** (no charter — backward-compat) → the legacy 15-item AT-completeness reviewer audit below is the fallback, unchanged.

### atdd_pure crafter dispatch markers (U0 / ADR-030 D8) <!-- mode-ref-ok -->


```
<!-- DES-MODE : atdd_pure --> <!-- mode-ref-ok -->
<!-- DES-PHASE : A_GREEN -->
<!-- DES-SLICE : slice-01 -->
<!-- DES-WAVE: deliver -->
```

- `DES-PHASE : {phase}` — the current ATDD-pure phase; `{phase}` is one of the canonical `ATDDPurePhase` members (`A_GREEN`, `C_REVIEWER_AUDIT`, `D_REFACTOR_COMMIT`).
- `DES-SLICE : slice-NN` — the carpaccio slice id, anchored `slice-\d+` shape.
- `DES-WAVE: deliver` — the wave declaration. Include it verbatim in every dispatch prompt — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

**Verified-emission assertion (phase-entry diagnostic).** Before dispatching the crafter into any phase, the orchestrator runs the phase-entry diagnostic over the rendered prompt: it parses the prompt via `des.domain.des_marker_parser.DesMarkerParser` and classifies it with `classify_atdd_pure_dispatch`. The dispatch is REFUSED — never sent — if the classification is `defective`, i.e. the rendered prompt is missing or malforms any of the three markers; `atdd_pure_missing_marker` names the offending marker (`des-mode` / `des-phase` / `des-slice`) in the refusal.

**Entry gate (before `A_GREEN`, per slice).** For a `Class = C` slice the orchestrator MUST run the carpaccio slice gate as the DES `entry_gate` before dispatching the crafter into `A_GREEN`:

```
des carpaccio-slice-gate --feature-id {feature-id} --entering-slice {slice-NN}
```

The gate is a pure-function CLI (no filesystem mutation) implementing ADR-028 D2-bis (carpaccio decomposition assertions 1-4: slice size ≤ `.nwave/config.yaml:atdd_pure.carpaccio_slice_max`, incremental total coverage, walking-skeleton-first ordering, value-annotation) + ADR-029 D5 (assertion 5: the AT-review verdict for the entering slice is present, `APPROVED`, content-seal valid, and not stale). Exit `0` → dispatch the crafter into `A_GREEN`; exit `1` (missing slice plan) / `2` (malformed input) / `44` (`CARPACCIO_SLICE_TOO_LARGE`) / `45` (`AT_REVIEW_NOT_APPROVED`) → crafter dispatch REFUSED, halt with the gate's JSON payload. For a `Class = P` slice the carpaccio `entry_gate` is SKIPPED — the coherence check runs instead (see slice-04 spine routing). <!-- mode-ref-ok -->

| Phase | Owner | Action | Gate |
|-------|-------|--------|------|
| A_GREEN | crafter (instance #1) | Make all DISTILL ATs pass with NO defensive code beyond AT-driven need (AT-driven minimalism; the coverage-driven dead-code elimination + ≥90% coverage gate are DEPRECATED per FR-2/FR-3 velocity-v2 — green ATs + EXAMINE are the truth, not a coverage %) | Carpaccio `entry_gate` exit 0 (above); all ATs green |
| C_REVIEWER_AUDIT **(= EXAMINE slot)** | **armed**: `@nw-user-examiner` ("Vera"); **unarmed**: reviewer | **Armed** (charter present): dispatch Vera with ONLY the charter → she walks the promised outcome through the real surface and records the verdict via `des record-examine-verdict`. **Unarmed** (no charter): legacy 15-item AT-completeness audit via `nw-at-completeness-check`; gap routing per `ATGapKind` (see §Phase D Routing in `nw-deliver-atdd-pure-slice-gates`) | **Armed**: a PASS `ExamineVerdict` with a charter-seal matching current bytes — enforced at commit by `des commit-slice` (`ExamineVerdictRefused`/`Missing`/`Stale`/`Indeterminate`). **Unarmed**: `ReviewVerdictRecorded` recorded via `des record-review-verdict`; one Routing decision recorded |
| D_REFACTOR_COMMIT | **crafter (same instance as A_GREEN)** | **Commit-only, unconditional** — no refactor sub-dispatch, no per-slice review; `des commit-slice` seals the slice with `Step-Id:`/`Slice-Id:` + `Gate-Scope:` trailers. WHY: a91bf4f6b (2026-07-04) restored `D_REFACTOR_COMMIT` as the per-slice COMMIT step after a prior total drop left slices uncommitted — but the per-slice L1-L6 refactor it also restored is now SUPERSEDED, not re-dropped: the mandatory per-feature Prefactoring Assessment (upstream, DESIGN wave, behaviour-preserving, green-to-green) moves that refactor EARLIER instead of skipping it. a91bf4f6b answered a total drop with no substitute; here the substitute exists, so the regression does not recur. Whole-feature L1-L6 batch refactor still runs once at feature-end (the feature-end `D_REFACTOR_COMMIT` (feature scope) step, out of scope here — see §Feature-end cycle) | `D_REFACTOR_COMMIT` `exit_gate` exit 0 (see `nw-deliver-atdd-pure-slice-gates`) |

### EXAMINE failure routing — ownership firewall (inline)

An EXAMINE/reviewer verdict is a **routing event**, never permission for the
orchestrator to edit tests or production. `RELOOP_A` means re-enter the spine
through the owning agent:

| Finding | Required owner | Required route |
|---|---|---|
| Missing or weak acceptance oracle (`AT_GAP_IN_DELIVERY_SCOPE`) | `@nw-acceptance-designer` | re-enter DISTILL through a DES-generated dispatch; test files only |
| Existing AT/charter is sufficient, implementation is wrong | selected crafter | re-dispatch `A_GREEN` through DES; production files only |
| Specification or architecture ambiguity | DISCUSS / DESIGN / DEVOPS owner selected by Phase D | reroute upstream; no delivery edit |
| Blocker or exhausted cycle | human escalation | halt; no automatic edit |
| No gaps | same crafter | proceed to commit-only `D_REFACTOR_COMMIT` |

**The main orchestrator MUST NOT become the acceptance designer or crafter.**
It may classify findings, generate dispatches, coordinate dependencies and
serialize the box; it MUST NOT author ATs, paired tests or production code. If
orchestrator-authored WIP already exists, treat it as an unattested proposal:
the owning agent may replace it, and it is not RED/GREEN evidence.

The exact commands, sentinels and routing precedence live in
`nw-deliver-atdd-pure-slice-gates` §Phase D Routing. Load that module before
acting on any non-PASS EXAMINE/reviewer verdict.

**Per-slice pipelining (throughput) is mandatory.** While the crafter greens
slice N (`A_GREEN`), recompute the artifact-level DAG and dispatch every
ownership-safe READY cloud lane: `@nw-acceptance-designer` for AT(N+1), a fresh
`@nw-product-owner` for an observable slice's charter(N+1), plus independent
JIT-analysis or intra-slice lanes. Continue until cloud capacity is full or no
READY lane remains. Do not treat a slice boundary or `depends-on slice-N` as a
whole-slice barrier: only the downstream work that consumes N's unstable
artifact waits. An idle cloud slot while READY work exists is
`UNUSED_PARALLELISM` and MUST carry a recorded artifact/file/box reason.

The box-seal lane (carpaccio `entry_gate` → `D_REFACTOR_COMMIT` `exit_gate` →
commit) stays strictly serialized, one slice at a time. Empirical: this hid
~4-5 min/slice (2026-07-10). Constraint: N LLM lanes may run concurrently; only
ONE box lane runs at a time — never two heavy box gates (seals) concurrently.
Load `nw-throughput` and apply its mandatory scheduling cycle at every phase
transition, completion, refusal or new artifact.

**Git safety when Vera's real-surface recipe needs a throwaway git repo**: she builds and touches it with `git -C <tmp>` explicit-target invocations only — never a bare `git config`/`--global`, never a git WRITE against the real project repo (see nw-user-examiner.md's Critical Rules; incident 2026-07-09 contaminated the real repo's committer identity via a bare `git config`).

### Per-slice phase-boundary contracts (module)

The remaining per-slice contracts — the `D_REFACTOR_COMMIT` exit gate (E1 slice-commit completeness + E2 contract-gate scope), §Phase D Routing, §Separation Enforcement, §Verdict-Hash Trailer, and §Telemetry per Phase Boundary — live in `nw-deliver-atdd-pure-slice-gates`. Load `~/.claude/skills/nw-deliver-atdd-pure-slice-gates/SKILL.md` when a slice crosses any phase boundary beyond the A_GREEN entry dispatch.

## Skill Loading (ATDD-pure additions)

When `workflow.mode = atdd_pure`, orchestrator MUST embed skill-load directives in every dispatch prompt. <!-- mode-ref-ok -->
The mode-conditional skill set per agent is declared by the mode registry `skill_load_set` (projected into each agent spec's GENERATED skill-load region — the registry, never this guide, is the author): embed a directive to load every skill the registry declares for the dispatched agent at its phase entry. Phase-specific additions that are not mode-conditional:

`D_REFACTOR_COMMIT` carries no phase-specific skill addition beyond the mode-registry set: it is commit-only (see the `D_REFACTOR_COMMIT` table row above) — no refactor or review dispatch happens per slice, so `nw-refactor`/`nw-review` are not loaded here. They remain loaded at the feature-end cycle's `D_REFACTOR_COMMIT` (feature scope) and Deep feature-end review steps (out of scope for this table; see a91bf4f6b + the Prefactoring Assessment supersession noted above).


## Rigor Profile Integration

Before dispatching any agent, read the rigor profile from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

**How rigor affects deliver phases:**

| Setting | Effect |
|---------|--------|
| `agent_model` | Pass as `model` parameter to all Task tool invocations for crafter agents. If `"inherit"`, omit `model` parameter (Task tool inherits from session). |
| `reviewer_model` | Pass as `model` parameter to reviewer Task invocations. If `"skip"`, skip Phase 4 entirely. |
| `review_enabled` | If `false`, skip Phase 4 (Adversarial Review). |
| `double_review` | If `true`, run Phase 4 twice with separate review scopes. |
| `refactor_pass` | If `false`, skip Phase 3 (Complete Refactoring). |
| `mutation_enabled` | Deprecated (FR-1, CLAUDE.md § Mutation Testing Strategy): the config default is `false` and Phase 5 is SKIPPED unless this is explicitly set `true` for an opt-in run — the inverse of "runs unless disabled". |

**Task invocation with rigor model:**
```python
Task(
    subagent_type="{agent}",
    model=rigor_agent_model,  # omit this line entirely if "inherit"
    max_turns=45,
    prompt=...,
)
```

## Prior Wave Consultation

Before beginning DELIVER work, read prior wave content. With lean v3.14, all wave decisions live in a single `feature-delta.md` (sections tagged `## Wave: <NAME> / [REF|WHY|HOW] <Section>`); legacy multi-file directories are no longer produced.

1. **DISCOVER** (skip): Synthesized into DISCUSS sections of `feature-delta.md`.
2. **DISCUSS** (read on demand): in `docs/feature/{feature-id}/feature-delta.md` under `## Wave: DISCUSS / [REF] ...` sections. Already encoded as acceptance scenarios — read for elevator pitch extraction (Phase 3.5) and clarification only.
3. **DESIGN** (structural context, read-if-present; degrade loud if absent): Read `docs/product/architecture/brief.md` (cross-feature SSOT — component boundaries, driving ports, C4 diagrams) when present; DESIGN is optional, so a DESIGN-skipped feature has no brief.md — proceed without it (degrade loud, never hard-fail). PLUS read `docs/feature/{feature-id}/feature-delta.md` filtered to `## Wave: DESIGN / [REF] ...` sections — DDD list, component decomposition, driving/driven ports, technology choices, decisions table, reuse analysis.
4. **DEVOPS** (read on demand): in `feature-delta.md` under `## Wave: DEVOPS / [REF] ...` sections. Read only if test environment issues arise.
5. **DISTILL** (primary input, MANDATORY): TWO sources:
   - `feature-delta.md` `## Wave: DISTILL / [REF] ...` sections — scenario list with tags, walking skeleton strategy, adapter coverage, scaffold inventory, test placement, driving adapter coverage, pre-requisites
   - Executable `.feature` files at the test placement path declared in DISTILL (e.g. `tests/{feature-id-or-bounded-context}/acceptance/*.feature`) — these are the authoritative specification

**READING ENFORCEMENT**: You MUST read `feature-delta.md` (full file) AND every `.feature` file referenced in the DISTILL Test Placement section before proceeding. Additionally, read `docs/product/architecture/brief.md` if present — DESIGN is optional, so when it is absent emit `⊘ brief.md (not found) — proceeding without architecture context` and continue (never hard-fail on the missing DESIGN artifact). After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes implementation disconnected from architecture and acceptance tests.

**Migration fallback for legacy features**: If `docs/feature/{feature-id}/feature-delta.md` does NOT exist BUT legacy multi-file directories (`discuss/`, `design/`, `devops/`, `distill/`) DO exist, treat the legacy layout as authoritative for THIS feature only. Read all files in those directories. Future waves should consolidate to `feature-delta.md` per lean v3.14.

**Upstream issues check**: look for `## Wave: <NAME> / [WHY] Upstream Issues` sections in `feature-delta.md` (or legacy `upstream-changes.md` / `upstream-issues.md` files in legacy multi-file features). If unresolved issues exist, flag them to the user before starting implementation.

**On-demand escalation**: If during implementation a crafter encounters ambiguity not resolved by DISTILL tests or DESIGN architecture, the orchestrator re-reads specific sections of `feature-delta.md` — never re-reads the full file unnecessarily.

## Document Update (Back-Propagation)

When DELIVER implementation reveals gaps or contradictions in prior waves:
1. Document findings as a `## Wave: DELIVER / [WHY] Upstream Issues` section appended to `docs/feature/{feature-id}/feature-delta.md` (lean v3.14 — Tier-2 expansion) OR `docs/feature/{feature-id}/deliver/upstream-issues.md` (legacy multi-file)
2. Reference the original prior-wave document and describe the issue
3. If implementation requires deviating from architecture or requirements, document the deviation and rationale
4. Resolve with user before continuing past the affected step
