---
name: nw-distill
description: "Acceptance test creation methodology for the DISTILL wave (recomposing core). DISTILL identity + induction map + gate-G design↔AT coherence rubric + the mandatory final wave review gate. Lean core that COMPOSES the narrow nw-distill-* modules and the nw-test-design-mandates-* family; deep domain knowledge lives in those modules, not re-inlined here."
user-invocable: true
argument-hint: '[story-id] - Optional: --test-framework=[cucumber|specflow|pytest-bdd] --integration=[real-services|mocks]'
---

> **Code facts** — resolve structural facts about code (who-calls / defs-reads / never-wired / call-graph / atoms-in-file) through the `nw-code-analysis-port` skill: Tsunami-first via the `mcp__tsunami__*` tools, declared fallback (AST, then grep), degrade-LOUD. Never ad-hoc grep for a structural fact.

<!-- gates-ref: distill -->
<!-- outputs-ref: distill -->

The DISTILL gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/distill.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This skill does not re-enumerate the gate stack inline; it POINTS at the registry.

# DISTILL Methodology: Acceptance Test Creation (recomposing core)

Acceptance-designer methodology. Orchestrator owns flow (agent dispatch, review gate, handoff); this skill owns the DISTILL-specific orchestration knowledge and ROUTES the deep domain knowledge to narrow modules.

This core holds the cross-cutting DISTILL concerns — identity (ADR-025 authorship, language frame), the density-aware output contract, the 3-source induction map, the gate-G coherence rubric, and the mandatory final wave review gate — and COMPOSES the narrow `nw-distill-*` modules plus the `nw-test-design-mandates-*` family. The canonical definitions of test mechanics (Mandates 8-15, PBT/Universe, two-tier, polyglot, DSL, dormant-seam) live in the mandate family — this core does not re-inline them.

## Composition (load by trigger)

| Module | Kind | Trigger — load when... | Covers |
|---|---|---|---|
| `nw-distill-prior-wave-reading` | PROCEDURE | BEFORE writing any scenario — reconciling prior-wave SSOT + feature-delta | Prior Wave Reading, Wave-Decision Reconciliation HARD GATE, Graceful Degradation, Advisory-Skip-Gate Pattern + DESIGN-absent/Total-AT advisories, back-propagation |
| `nw-distill-feature-delta-schema` | KNOWLEDGE | authoring or validating a `feature-delta.md` section's TABLE FORMAT / scaffold | Feature-Delta Schema (US-01/02), canonical 4-column commitments table, E1+E2 validator rules, incremental authoring |
| `nw-distill-port-treatment-policy` | KNOWLEDGE | classifying a port → test treatment + concrete mechanism for THIS codebase | Port-to-Port AC, Architecture of Reference, Project Infrastructure Policy, Walking Skeleton Strategy + canonical WS definition |
| `nw-distill-red-scaffolding` | PROCEDURE | making ATs RED-ready + classifying RED-vs-BROKEN before DELIVER | Mandate-7 RED-Ready Scaffolding, per-language scaffold recipes, Pre-DELIVER fail-for-right-reason gate, lazy expansion templates |
| `nw-distill-coverage-obligations` | PROCEDURE | verifying adapter / driving-port / dormant-seam / outcome coverage at gate-OUT | Driving Adapter Verification, Adapter Scenario Coverage, Adapter Integration Slice, Register Outcomes, Self-Review Checklist, scenario-writing guidelines |
| `nw-test-design-mandates` (+ `-scenario-design` / `-layered-mechanics` / `-composition-contract`) | KNOWLEDGE | choosing scenario SHAPE, test MECHANICS, or the AT's driving-surface CONTRACT | Mandates 1-15, 3 Pillars, Universe/PBT mode, two-tier, polyglot matrix, SSOT-via-types DSL, dormant-seam — the canonical SSOT for all test-design mandates |

Load path: `~/.claude/skills/nw-{module}/SKILL.md`. Load the module whose trigger matches your current moment; the triggers partition the DISTILL knowledge-space — every section lives in exactly one module. Do NOT re-inline a module's content into this core.

## LANGUAGE CONVENTION FRAME (read FIRST — overrides all examples in the modules)

**Code examples in nw-distill modules: target-language-illustration ONLY.** NOT prescriptive about target language. nWave is language-agnostic per the "genericity and agnosticism" mandate (2026-05-24).

**Before authoring ATs**, detect target project language from these manifest files (in order):
- `package.json` → TypeScript / JavaScript (jest, vitest, cucumber-js, playwright)
- `Cargo.toml` → Rust (cargo test, proptest, cucumber-rust)
- `go.mod` → Go (testing, ginkgo, godog)
- `pyproject.toml` / `setup.py` / `Pipfile` → Python (pytest, pytest-bdd, hypothesis)
- `pom.xml` / `build.gradle` → Java / Kotlin (JUnit5, Cucumber-JVM, jqwik)
- `*.csproj` / `*.fsproj` → C# / F# (xUnit, SpecFlow, FsCheck)
- `Gemfile` → Ruby (RSpec, Cucumber-Ruby)
- `Package.swift` → Swift (XCTest, swift-testing)

**Target language NOT Python** — adapt EVERY code example to target-language conventions (naming, imports, type system, test-framework idioms, file extensions, directory conventions). **Project conventions ALWAYS WIN** over module examples: a repo with 50 TS files and zero Python files → ATs MUST be TypeScript, never Python pytest-bdd, however authoritative a module example looks.

**Empirical anchor**: Python-only examples once caused the LLM to infer Python conventions universal, emitting Python code in a greenfield TS project. Connects [[feedback_language_adapter_plugin_architecture_2026_05_24]] (genericity mandate) + F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE epic.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

Acceptance-designer working prose + reports = caveman: verdict-first, tables, zero narrative. Depth modulated by `rigor` profile, never by padding (D-caveman, Ale 2026-06-10).

## ADR-025 (2026-05-07) — DISTILL is canonical AT author

DISTILL produces ALL ATs as **active-RED scaffolds** — RUN + raise `AssertionError` (impl missing), NOT `@skip`/`@pending` (per ADR-GV-001 D6). DELIVER 3-phase cycle (RED / GREEN / COMMIT, ADR-025) does NOT re-author ATs in RED — makes active-RED scaffolds GREEN via production code. Wave separation: DISTILL = "what should the system do" (ATs) · DELIVER = "how" (PBT unit + impl).

**atdd_pure (the path)**: per-slice JIT — current slice scenarios active-RED (run + raise `AssertionError`); future-slice scenarios ABSENT from disk. No `@skip` ever: absent (future slice) or active-RED (current slice). <!-- mode-ref-ok -->

Pre-DELIVER fail-for-right-reason gate (`nw-distill-red-scaffolding`) = DELIVER RED-phase entry/exit gate per ADR-025 D2.

## Output Tiers (per D2)

Provenance: feature `lean-wave-documentation` — D2 (schema-typed sections), D10 (one-line expansion descriptions). Two output bands: Tier-1 [REF] sections (always emitted) + Tier-2 EXPANSION CATALOG items (lazy, on-demand). `.feature` file = scenario SSOT; wave-delta sections = pointers + structured summaries. Full contract: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Tier-1 [REF] — always emitted

Under `## Wave: DISTILL / [REF] <Section>` headings:

| Section | Content |
|---|---|
| Scenario list | titles + tags (`@walking_skeleton`, `@US-N`, `@real-io`, `@in-memory`, `@error`, `@property`) + **Real-Surface Binding** column (NEW features): each scenario names the shipped artifact / real entry point it touches — repo file path (`nWave/...`), subprocess (`des <subcommand>`), or production composition root. Declarative now, AST-detector-verifiable later; ties the assertion to a shipped artifact / observed effect per the Driving-Port-Only mandate (SSOT: `nw-test-design-mandates-composition-contract`). Schema: `schemas/feature-delta-tier1-sections.yaml` (rule R4, provisional). |
| WS strategy | port-class treatment per `nw-distill-port-treatment-policy`, one-line justification |
| Adapter coverage table | every driven adapter → ≥1 `@real-io` scenario (`nw-distill-coverage-obligations`) |
| Scaffolds | RED-ready files (`nw-distill-red-scaffolding`) with `__SCAFFOLD__` markers |
| Test placement | `tests/{path}/` choice, one-line precedent justification |
| Driving Adapter coverage | every CLI/endpoint/hook in DESIGN → ≥1 subprocess/HTTP/hook scenario |
| Pre-requisites | DESIGN driving ports + DEVOPS environment matrix dependencies |

### Tier-2 EXPANSION CATALOG — lazy, on-demand (per D10)

Rendered under `## Wave: DISTILL / [WHY|HOW] <Section>` only when requested via `--expand <id>` (DDD-2), wave-end menu (`expansion_prompt = "ask"`), `mode = "full"` auto-expansion, or ad-hoc user request mid-session.

| Expansion ID | Tier label | One-line description |
|---|---|---|
| `scenario-alternatives-considered` | [WHY] | Alternative scenario phrasings weighed and rejected (Gherkin variants, tag schemes) |
| `fixture-design-discussion` | [WHY] | Why these tmp_path/conftest fixtures, why these scopes, what they cannot model |
| `edge-case-enumeration` | [WHY] | Full edge-case taxonomy: empty/null/boundary/concurrency/timeout/permission |
| `error-path-rationale` | [WHY] | Why each `@error` scenario was chosen and what failure mode it surfaces |
| `tagging-cookbook` | [HOW] | Cookbook for tag application: `@property`, `@requires_external`, `@walking_skeleton` |
| `scaffold-authoring-recipes` | [HOW] | Per-language scaffold recipes — defined in `nw-distill-red-scaffolding` |
| `pbt-strategy-notes` | [WHY] | Property-based testing strategies for invariants surfaced by the feature |
| `expansion-catalog-rationale` | [WHY] | Why this set of expansions, why these defaults, why D10 enforces one-line descriptions |
| `domain-language-fact-to-step-table` | [HOW] | Soft gate: agent proposes fact→step-name pairs for user review before committing step-method names to code (`nw-distill-red-scaffolding`) |
| `policy-bootstrap-template` | [HOW] | `docs/architecture/atdd-infrastructure-policy.md` bootstrap snippet — defined in `nw-distill-port-treatment-policy` |
| `tier-b-state-machine-template` | [HOW] | State-machine PBT skeleton for Tier B in-memory journey testing (Mandate 10, `nw-test-design-mandates-layered-mechanics`) |

## Density resolution (per D12)

Call `resolve_density(global_config)` from `scripts/shared/density_config.py` after reading `~/.nwave/global-config.json` (missing/malformed = empty dict). Returns `mode` (`"lean"` | `"full"`) + `expansion_prompt` (`"ask"` | `"always-skip"` | `"always-expand"` | `"smart"`) per D12 cascade (resolver-internal, DDD-5 — do NOT replicate locally). Branch on `density.mode` for emission; on `density.expansion_prompt` at wave end for menu. Full cascade, branch semantics, ad-hoc override: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Telemetry (per D4 + DDD-6)

Every expansion choice → `DocumentationDensityEvent` (dataclass `src/des/domain/telemetry/documentation_density_event.py`) via `event.to_audit_event()` → `JsonlAuditLogWriter().log_event(...)`. D4 schema fields: `feature_id`, `wave`, `expansion_id`, `choice`, `timestamp`. This wave: `"wave": "DISTILL"`. Use helper `scripts/shared/telemetry.py:write_density_event(...)` — do NOT write JSONL directly.

Wave-specific signal: DELIVER consuming a lean DISTILL feature-delta — downstream `--expand` for fixture-design or edge-case enumeration = `[REF]` baseline + `.feature` file insufficient for the crafter. Full emission rules: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Induce, do not reinvent — the 3-source induction map (JOB-025)

Once `nw-distill-prior-wave-reading` has consumed the design's code-design contract (the
code-design section read during prior-wave reading), the acceptance tests are not authored from
intuition — **the acceptance-designer induces the acceptance tests from the design
contract**. The AT structure is a function of the contract, derived through a
fixed 3-source induction map rather than reinvented per feature. Each source row
of the contract induces a specific AT obligation:

| Contract source | Induces | Correspondence |
|---|---|---|
| **Slice Plan** (`[REF] Slice Plan` rows) | the AT scaffold per slice | ATs are scaffolded per-slice per the Slice Plan enumeration, active-RED never skipped |
| **Example tables** (the scenario examples carried in the contract) | the Given-When-Then scenarios | every example-table row maps to exactly one Given-When-Then scenario |
| **Contract shape** (declared laws + error-encodings on each component) | the property tests + sad-path scenarios | a declared law induces at least one property test; a declared error-encoding induces a sad-path scenario |

Reading the map:

- **Slice Plan → AT scaffold.** The contract's Slice Plan enumeration is the
  authority for which scenarios exist on disk in the current slice. ATs are
  scaffolded per-slice per the Slice Plan enumeration, active-RED never skipped —
  the current slice's scenarios run and fail for the right reason; future-slice
  scenarios are absent, never `@skip`'d into dormancy.
- **Example table → scenario (1:1).** every example-table row maps to exactly one
  Given-When-Then scenario. The bijection forbids both dropping a row (silent
  coverage loss) and fabricating a scenario the contract never authored.
- **Contract shape → treatment.** The design's code-design contract declares each
  component's contract shape (pure-function, bounded-change,
  unbounded-preservation) with its laws and error-encodings. a declared law
  induces at least one property test; a declared error-encoding induces a sad-path
  scenario. The treatment is induced, not guessed: a law without a property test,
  or an error-encoding without a sad path, is an induction gap.

This is the gate-IN consume discipline: the design contract is the input, the AT
set is the induced output, and the correspondence above is the witness that no AT
was reinvented and no contract obligation was dropped.

## The gate-G review-rubric — design↔AT coherence at DISTILL gate-OUT (JOB-025)

Gate-IN induces the AT set from the contract; gate-OUT proves the induced set is
coherent with it. The rubric named here is the witness: the gate-G review-rubric
witnesses the design to AT coherence at DISTILL gate-OUT. It is the
reviewer-facing checklist (Sentinel runs it on the
DISTILL output before the DELIVER handoff) that walks the induction map backwards:
for every obligation the design's code-design contract declared, the rubric asks
"is there exactly one corresponding AT, and does that AT trace to a real contract
row?". The rubric witnesses coherence; it never re-authors the AT set and it never
emits an authorizing YES — a clean run is "no incoherence found", and the human GO
is still required.

The gate-G rubric is a SKILL-normative checklist, not a second AST parser. The
mechanical fact-queries it leans on (which contract rows exist, which scenarios
exist, which property declarations carry a verdict) are delegated to the shared
code-fact provider rather than re-implemented here — the rubric describes WHAT
coherence means; the provider answers the factual sub-questions. The rubric's job
is the judgement: matching obligations to ATs and emitting one of the verdicts
below.

### DEVOPS-induced scenarios are first-class

The induction map's three sources (Slice Plan, Example tables, Contract shape) are
not the only legitimate origin for a scenario. **DEVOPS-induced scenarios are
first-class and trace to the DEVOPS status, not to a missing design row** — a
scenario that exists because the DEVOPS wave declared an infrastructure constraint
is fully coherent even though no `[REF]`-prefixed design row induced it. The gate-G
rubric therefore tests provenance, not bare presence: an AT with no inducing design
row is NOT automatically an over-author finding — first check whether it traces to
the DEVOPS status. Only a scenario that traces to neither a design obligation nor
the DEVOPS status is a fabrication.

### No-coupling — an ambiguous port-shaped coupling is UNVERIFIED, never a silent pass

Coherence is symmetric: as the rubric forbids dropping a contract obligation, it
also forbids an AT reaching past the contract. The rule is that an AT coupling to a
port-shaped surface not yet on the contract is UNVERIFIED, never a silent pass —
when a
scenario drives or asserts against a port the design contract has not yet declared,
the rubric cannot confirm the coupling is intended, so it must surface UNVERIFIED
and route the ambiguity back into the wave for resolution (extend the contract, or
retarget the AT). The forbidden outcome is treating an un-contracted coupling as
incidentally fine and letting it pass green; suspected-incompleteness of the
contract is the same class — UNVERIFIED, not pass.

### §17 — the gate-G verdict mapping (five verdicts, never a sixth)

The gate-G rubric encodes each coherence outcome to exactly one of five verdicts.
This closed set is the §17 error-encoding mapping the design contract declares for
this gate:

| Verdict | When the rubric emits it | Routing |
|---|---|---|
| **PASS** | every contract obligation has its one inducing AT, every AT traces to a contract row or the DEVOPS status | no objection — proceed to the human GO |
| **FAIL** | an un-covered contract row (a declared obligation with no inducing AT) | redo-in-wave: author the missing AT, re-run the rubric |
| **UNVERIFIED** | an AT coupling to a port-shaped surface not yet on the contract, OR suspected-incompleteness of the contract | route the ambiguity back into the wave; never a silent pass |
| **INDETERMINATE** | the coherence mechanism cannot run (asset unreadable, fact provider unavailable) | degrade-LOUD; never a false green |
| **N/A** | the gate does not apply to this feature (e.g. no design contract was authored — the gate-IN advisory already fired) | recorded explicitly, never inferred as PASS |

A FAIL on an un-covered row means **redo-in-wave**: the missing AT is authored and
the rubric re-run, the deficiency is fixed inside DISTILL rather than deferred to
DELIVER. The N/A branch is first-class and recorded honestly — the absence of a
design contract is N/A, not PASS, so a feature that skipped DESIGN never earns a
coherence green it did not pass.

### Degrade-LOUD — INDETERMINATE when the mechanism cannot run

The rubric is a mechanical witness, so it can itself fail to execute: the cited
asset may be absent or undecodable, or the code-fact provider may be unavailable on
the target machine. The discipline is that when the coherence mechanism cannot run
the verdict is INDETERMINATE, degrade-LOUD, never a false green. The rubric must
announce the
non-execution explicitly (which asset, why it could not be read) and emit
INDETERMINATE — it must never silently assume PASS, and it must never silently
assume FAIL. This is the gate-out twin of the gate-IN degrade-loud discipline (the
`⊘` notice): an absent witness is a loud INDETERMINATE, not an inferred outcome.

## Prior-Wave Reading + Advisories (pinned cross-cutting summary — procedure in `nw-distill-prior-wave-reading`)

Before writing any scenario, `nw-distill-prior-wave-reading` reads all prior-wave SSOT + feature-delta, runs the Wave-Decision Reconciliation HARD GATE, and fires two Tier-A advisories. The full procedure + tables live in that module; the pinned advisory + degradation contract is summarized here.

### Row 7b — DESIGN-absent advisory (gate-IN soft-gate)

After the brief.md read and before Wave-Decision Reconciliation, inspect the active `docs/feature/{feature-id}/feature-delta.md` for the literal heading `## Wave: DESIGN / [REF] Code-Design`. This row keys a Tier-A advisory off that section's presence — it NEVER blocks: on ANY answer the flow continues to DISTILL.

| Step | Action |
|---|---|
| **Observe** | Read the feature-delta. Test for the `[REF] Code-Design` section the DESIGN wave authors. |
| **Branch** | DESIGN-artifact **present** → **silent** (no advisory; the feature ran DESIGN). DESIGN-artifact **absent** → emit the advisory: NAME the evidence ("no `[REF] Code-Design` section in feature-delta"), state the RISK ("duplication + incoherent architecture"), PROPOSE `/nw-design`, ASK the closed option set {run `/nw-design` · proceed without it}. |
| **Proceed** | On ANY answer, **continue to DISTILL** — the advisory has no veto power. The DESIGN-present branch is silent; the DESIGN-absent branch advises then proceeds. Either way the flow continues to DISTILL; row 7b never blocks. |

Degrade-loud: if the feature-delta is unreadable, emit `⊘ feature-delta unreadable — cannot evaluate DESIGN-absent advisory; proceeding` and continue (never block, never assume present). Row 7b is an instantiation of the Advisory-Skip-Gate Pattern (Tier-A) — full pattern + slot binding in `nw-distill-prior-wave-reading`.

### Row 7c — Total-AT advisory (gate-IN soft-gate)

After row 7b and before Wave-Decision Reconciliation, key a second Tier-A advisory off the feature's **total** acceptance-test volume. Like row 7b it NEVER blocks. NAME the evidence ("total AT {N} > threshold {M}"), state the RISK ("too big for one iteration"), PROPOSE `/nw-discuss`, ASK {run `/nw-discuss` · proceed without it}; on ANY answer continue to DISTILL. Branch: total AT **over** the threshold → fire the advisory (propose `/nw-discuss`); at-or-under → stay **silent** (no false advisory on a right-sized feature). Threshold key `feature_total_at_advisory_threshold` (rigor cascade) — distinct from the per-slice `carpaccio_slice_max` ceiling. Full table in `nw-distill-prior-wave-reading`.

### Graceful Degradation Matrix (warn vs block)

Missing artifacts → warnings, not failures; DESIGN-absence is surfaced via the advisory soft-gate, never a block.

| Missing artifact | Action | Reason |
|---|---|---|
| `docs/feature/{id}/devops/` directory | **WARN**, use project default infra | tests can proceed without env spec |
| `docs/feature/{id}/discuss/` directory | **WARN**, derive ACs from DESIGN, skip story-to-scenario traceability | story traceability lost, scenarios still coherent |
| `docs/feature/{id}/design/` directory | **WARN** — proceed (advisory): emit the DESIGN-absent soft-gate, derive driving ports from DISCUSS/feature-delta if present | DESIGN is optional; absence is surfaced advisorily, never blocks |

### Graceful Degradation for Missing Upstream Artifacts

| Missing | Action | Block? |
|---|---|---|
| `docs/feature/{feature-id}/devops/` | apply default environment matrix: clean, with-pre-commit, with-stale-config | NO — proceed |
| `docs/feature/{feature-id}/discuss/` | derive acceptance criteria from DESIGN architecture documents; skip story-to-scenario traceability | NO — proceed |
| `docs/feature/{feature-id}/design/` | derive driving ports from DISCUSS/feature-delta if present; emit the DESIGN-absent advisory and continue | NO — proceed (advisory) |

Missing artifacts → warnings, not failures; DESIGN-absence is surfaced via the advisory soft-gate, never a block.

## Final Wave Review Gate (Mandatory — covers DISCUSS+DESIGN+DEVOPS+DISTILL)

AFTER all DISTILL Tier-1 [REF] sections are appended to `feature-delta.md` and acceptance scenarios + scaffolds written: dispatch FOUR reviewers in parallel against the full `feature-delta.md`. Consolidated mandatory review — replaces per-wave reviews (per-wave now opt-in only — see DISCUSS/DESIGN/DEVOPS skills). All four see the entire 4-wave chain in one file → cross-wave consistency checks per-wave review misses.

1. **Dispatch four reviewers in parallel** (single message, multiple Agent tool uses, all Haiku for cost):
   - `@nw-product-owner-reviewer` (Eclipse) — DISCUSS sections (lines 1 to first `## Wave: DESIGN` heading)
   - `@nw-solution-architect-reviewer` (Architect) — DESIGN sections (between `## Wave: DESIGN` and `## Wave: DEVOPS`)
   - `@nw-platform-architect-reviewer` (Forge) — DEVOPS sections (between `## Wave: DEVOPS` and `## Wave: DISTILL`)
   - `@nw-acceptance-designer-reviewer` (Sentinel) — DISTILL sections + executable `.feature` files + scaffolds
   Gate: all four dispatched concurrently.

   <!-- DES-WAVE: distill -->

   Include the `<!-- DES-WAVE: distill -->` marker line above verbatim in EACH of the four reviewer Agent dispatch prompts — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

| Step | Rule | Gate |
|---|---|---|
| 2 | Each reviewer outputs YAML verdict: `approval_status` ∈ {approved, conditionally_approved, needs_revision, rejected} + `blocker_count`, `high_count`, `low_count`, `findings_list` | structured verdict received from each |
| 3 | Cross-wave consistency: Eclipse APPROVES DISCUSS but Architect's findings reveal DISCUSS contradictions (e.g. story claims X, ADR assumes Y) → surface as cross-wave blocker | contradictions flagged |
| 4 | Per NEEDS_REVISION verdict: dispatch fix to the wave's primary agent (Luna DISCUSS · Morgan DESIGN · platform-architect DEVOPS · acceptance-designer DISTILL); re-run only the affected reviewer after fix | 2 revision cycles max per wave; escalate to user if unresolved |
| 5 | Block DELIVER handoff until all four verdicts APPROVED or CONDITIONALLY_APPROVED with documented action items in DELIVER scope | zero blockers, zero high (or accepted-with-conditions) |

**Cost**: 4 Haiku reviewers in parallel ≈ $0.05-0.20 per feature. Small cost vs late-feedback-blast-radius reduction (full chain visible).

**Structural-correctness reviewer never skips**: `rigor.reviewer_model: "skip"` applies ONLY to the three scale-sensitive cost-driven reviewers (Eclipse / Architect / Forge). Sentinel (`@nw-acceptance-designer-reviewer`) ALWAYS dispatches regardless of rigor cascade or scenario count fast-path — structural-correctness reviewer (Gherkin antipatterns, hexagonal boundary, scaffold integrity); silent skip masks the bug class issue #52 fixed.

**Per-wave review trigger override**: a wave-skill may still trigger its own per-wave review (DoR ambiguity, contested ADR, novel deployment target, etc.). Per-wave reviewer outputs = PR-ephemeral, not committed; they inform the wave's primary agent in real time, never substitute this final gate.

## Deliverable-Type Verification Routing (ADR-PST-003 / DDD-6)

The verification plan branches on the `deliverable_type` resolved in Prior Wave Reading step 1b (`nw-distill-prior-wave-reading`) — read from the SAME `.nwave/des-config.json` the DES runtime gate uses (single source of truth, `DESConfig.deliverable_type` precedence). The four-reviewer Final Wave Review Gate above ALWAYS runs; this section declares the ADDITIONAL, type-specific verification.

| Deliverable type | Verification plan |
|---|---|
| **`application`** (or unresolved) | UNCHANGED — pytest / Hypothesis routing. No plugin or skill reviewer. The four-reviewer gate (Sentinel reviews the scenarios/scaffolds) is the verification. |
| **`plugin`** | `@nw-plugin-validator` (Claude Code plugin structure/schema) + `@nw-skill-reviewer` (SKILL.md quality) + **behavioral Gherkin** scenarios + **example-interaction evidence** (the plugin demonstrated through its real invocation path) + optional `bats`/`shellcheck` for any shell. NOT pytest/Hypothesis-centric. |
| **`skill`** | `@nw-skill-reviewer` (SKILL.md quality) + **behavioral Gherkin** scenarios. Do NOT dispatch `@nw-plugin-validator` (no plugin structure to validate). |

**Mixed plugin/skill features** (a plugin that also bundles application-layer code) get `@nw-software-crafter-reviewer` on that code at **DELIVER Phase 4**, not here — DISTILL has no execution log to review, so the crafter-reviewer is intentionally absent from this DISTILL table (see `nw-deliver` Phase 4 for the symmetric DELIVER routing).

**Authoring routing**: plugin/skill AUTHORING (writing the plugin manifest, hooks, commands, agents, or SKILL.md content) routes to `@nw-agent-builder`. `@nw-plugin-validator` and `@nw-skill-reviewer` are read-only verification agents — they review, they do not author. The four `*-development` specialist agents remain DEFERRED (not created).

**Single-source-of-truth invariant**: the routing here and the DES enforcement gate both read `deliverable_type` from `.nwave/des-config.json` via `DESConfig.deliverable_type`. Never re-detect the type independently — divergence between the verification plan and the enforcement gate is the failure this routing prevents.

## Outputs

**Single narrative file**: `docs/feature/{feature-id}/feature-delta.md` — scenario list with tags, WS strategy, adapter coverage table, scaffolds list, test placement, driving adapter coverage, pre-requisites all become `## Wave: DISTILL / [REF|WHY|HOW] <Section>` headings. `.feature` file (below) = SSOT for executable scenarios; wave-delta sections = pointers + structured summaries. Table format: `nw-distill-feature-delta-schema`.

**Machine artifacts** (declared, parseable by downstream — `.feature` files ARE the scenario SSOT, executable by pytest-bdd):
- `tests/{test-type-path}/{feature-id}/acceptance/walking-skeleton.feature`
- `tests/{test-type-path}/{feature-id}/acceptance/milestone-{N}-{description}.feature`
- `tests/{test-type-path}/{feature-id}/acceptance/integration-checkpoints.feature`
- `tests/{test-type-path}/{feature-id}/acceptance/steps/conftest.py` + `{domain}_steps.py`
- `src/{production-path}/{module}.py` — RED scaffold stubs (`nw-distill-red-scaffolding`)

> **`.feature` tag contract (the carpaccio gate finds files + scenarios by tag).** Source of truth:
> `src/des/application/feature_at_files.py` (`wanted = f"@feature-{feature_id}"`) +
> `src/des/cli/carpaccio_format.py` (`_SLICE_TAG_RE = @(slice-\d+)`, `_parse_scenarios_in_text`).
> Consumed by `des carpaccio-slice-gate`. Two MANDATORY tags, or the gate reports
> `no-scenarios-for-slice`:
> - **File-level `@feature-{feature-id}`** — placed at the top of every slice `.feature` file,
>   on the line(s) preceding the `Feature:` header. This is how the gate DISCOVERS the file
>   (`feature_tag_files` rglobs `tests/**/*.feature` and keeps only files self-identifying with
>   this tag). Omit it → the gate finds ZERO files → `no-scenarios-for-slice`.
> - **Per-scenario `@slice-NN`** — placed on EACH scenario. Feature-level tags do NOT inherit:
>   `_parse_scenarios_in_text` clears pending tags at the `Feature:` line, so a `@slice-NN`
>   sitting only above `Feature:` binds to ZERO scenarios → `no-scenarios-for-slice`. Tag every
>   scenario the slice owns individually.
> - **Hermetic subprocess driving port** — ATs drive the in-tree DES runtime via
>   `python -m des.cli.<gate>` (Layer 3 subprocess). NO `expanduser("~/.claude")` / no personal-hook
>   paths in step composition — the `tests/meta/test_acceptance_hermeticity.py` guard rejects
>   `Path.home() / ".claude"` and `expanduser("~/.claude")` at collection.

For bug fix regression tests: `tests/regression/{component-or-module}/bug-{ticket-or-description}.feature` + matching `tests/unit/{component-or-module}/test_{module}_bug_{ticket-or-description}.py`.

**SSOT updates** (per Recommendation 3 / back-propagation contract):
- `docs/product/kpi-contracts.yaml` — refine acceptance metrics: per-KPI scenario tag (`@kpi`) link, expected measurement window, soft-vs-hard gate classification. DISTILL inherits the contract from DEVOPS, tightens it as scenarios are written.

Legacy multi-file outputs (`walking-skeleton.md`, `wave-decisions.md`, `test-scenarios.md`, `acceptance-review.md` as separate files in `docs/feature/{id}/distill/`) NOT produced — content lives in `feature-delta.md`; executable `.feature` files = scenario SSOT. Reviewer output ephemeral (PR comments / retrospective, not committed). Validator: `scripts/validation/validate_feature_layout.py`.
