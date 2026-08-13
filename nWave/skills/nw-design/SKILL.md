---
name: nw-design
description: "Designs system architecture with C4 diagrams and technology selection (recomposing core). DESIGN identity + density-aware output contract + gate-parsed Reuse Analysis contract + interactive decision points + architect routing/dispatch. Lean core that COMPOSES the narrow nw-design-* modules; the prior-wave-reading and discovery-flow procedures live in those modules, not re-inlined here. Routes to the right architect based on design scope (system, domain, application, or full stack). Two interaction modes: guide (collaborative Q&A) or propose (architect presents options with trade-offs)."
user-invocable: true
argument-hint: '[component-name] - Optional: --residuality --paradigm=[auto|oop|fp]'
---

> **Code facts** — resolve structural facts about code through `des code-fact` CLI (vendor-neutral, bundled adapters: AST then TextSearch). Degrade LOUD. Never ad-hoc grep. Example: `des code-fact query.callers-of SYMBOL --root ROOT`.

# NW-DESIGN: Architecture Design (recomposing core)

**Wave**: DESIGN (wave 3 of 6) | **Agents**: Morgan (nw-solution-architect), nw-system-designer, nw-ddd-architect | **Command**: `*design-architecture`

## Overview

Execute DESIGN wave through discovery-driven architecture design. The command starts with two interactive decisions:

1. **Design Scope** — routes to the right architect: system-level (@nw-system-designer), domain-level (@nw-ddd-architect), application-level (@nw-solution-architect), or full stack (all three in sequence).
2. **Interaction Mode** — guide (architect asks questions, you decide together) or propose (architect reads requirements, presents 2-3 options with trade-offs).

All architects write to `docs/product/architecture/brief.md` (SSOT), each in its own section. Analyzes existing codebase, evaluates open-source alternatives, produces C4 diagrams (Mermaid) as mandatory output.

This core holds the cross-cutting DESIGN concerns — identity, the density-aware output contract, telemetry, the gate-parsed Reuse Analysis contract (AT-pinned), the interactive decision points, rigor integration, and the architect routing/dispatch block — and COMPOSES the narrow `nw-design-*` modules. The phase procedures live in those modules, not re-inlined here.

## Composition (load by trigger)

| Module | Kind | Trigger — load when... | Covers |
|---|---|---|---|
| `nw-design-prior-wave-reading` | PROCEDURE | BEFORE beginning DESIGN work — consuming SSOT + prior-wave artifacts | Prior Wave Consultation reading order + confirmation checklist, contradiction check, migration gate, Document Update (back-propagation + upstream-changes.md) |
| `nw-design-discovery-flow` | PROCEDURE | architecture work begins — wave-entry Decisions 0-1 resolved | Discovery Flow steps 1-8 (problem, constraints, Conway, paradigm selection, Reuse Analysis pointer, recommendation, stress analysis, deliverables) + Outcome Collision Check |

Load path: `~/.claude/skills/nw-{module}/SKILL.md`. Load the module whose trigger matches your current moment; the triggers partition the DESIGN phase-space — every section lives in exactly one module. Do NOT re-inline a module's content into this core. The Reuse Analysis step-5 contract, the Reuse-first DESIGN exit gate, and the Wave Decisions Summary template stay in this core (below) — they are AT-pinned to this file.

## Workflow (phase order)

At the start of execution, create these tasks using TaskCreate and follow them in order, loading each phase's module at that phase: prior-wave reading → Decision 0 (design scope) + Decision 1 (interaction mode, below) → architect dispatch (below) → discovery flow with the Reuse Analysis contract (below) and the Outcome Collision Check → Wave Decisions Summary + Outputs (below).

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Output Tiers (per D2)

Provenance: feature `lean-wave-documentation` — D2 (schema-typed sections), D10 (one-line expansion descriptions). Tier-1 [REF] sections (always emitted) + Tier-2 EXPANSION CATALOG items (lazy, on-demand) are the two output bands. Full contract: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Tier-1 [REF] — always emitted

Under `## Wave: DESIGN / [REF] <Section>` headings, **except for the two
gate-consumed canonical sections whose bare headings are literal protocol
tokens**:

- `## Reuse Analysis`
- `## Prefactoring Assessment`

Never render either exception as `## Wave: DESIGN / [REF] ...`; the readiness
parsers correctly classify that shape as missing.

- DDD list — D-numbered design decisions with verdicts and one-line rationale
- Component decomposition — table of components with paths and change types
- Driving ports — inbound surfaces (CLI, skill, HTTP) named per the C4 contract
- Driven ports + adapters — outbound side-effects with adapter mapping **and a Runtime Contract Matrix**: declared argument/receipt/authority type → exact invoked method → concrete runtime argument/receipt → boundary AT
- Technology choices — pinned languages/frameworks/runtime versions
- Decisions table — DD-N row per locked decision (no rationale prose)
- ADR Refs — `## Wave: DESIGN / [REF] ADR Refs`, a RefList of `ADR-<PREFIX>-<NNN>` ids for every decision promoted to a standalone ADR (see Decision-once below); `des feature-delta-doctor` dereferences each id against the 4 declared ADR roots and names any that is dangling or could-not-verify — never silently accepted
- Reuse Analysis table — every overlapping component classified EXTEND or CREATE_NEW
- Prefactoring Assessment — a `@prefactoring` slice, or an explicit justified NONE (never silently absent)
- Open questions — items deliberately deferred to DISTILL/DELIVER

### Decision-once — point, don't copy

A decision lives in exactly ONE place; every other place that needs it points, it does not
re-narrate. This is not a style preference — duplicated rationale is what turns a one-line
review correction into an N-file edit (one edit per copy) and is the recurring source of
DESIGN sections silently drifting apart from each other inside the same delta.

- **Within this delta**: give the decision a `DD-N` row in the Decisions table (Decision +
  one-line Rationale, no prose duplication). Every other section that touches the same
  decision — Reuse Analysis rows, Contract/Architecture Tests, Application Architecture prose
  — cites it (`per DD-N`) instead of restating the rationale.
- **Across artifacts**: when a decision is durable or spans features (the kind that would earn
  its own ADR), write it ONCE as `docs/product/architecture/ADR-*.md` (or the feature-local
  `docs/feature/{id}/design/adrs/` for a feature-scoped one), list its id under ADR Refs above,
  and cite the id at every point elsewhere the decision is relevant — do not paste the ADR's
  rationale into feature-delta.md prose a second time.
- **A pointer must resolve, or say so LOUD** (GDP-6): an id cited nowhere else is a broken
  reference, not a saved edit. `des feature-delta-doctor` reports every `adr-refs` id as
  PRESENT, dangling, or could-not-verify — run it before handoff; a dangling id is a defect in
  the delta, not something DISTILL should discover downstream.
- This is forward-only: it governs how a NEW feature-delta is authored. It does not require
  retrofitting decisions already duplicated in already-delivered features.

### Tier-2 EXPANSION CATALOG — lazy, on-demand (per D10)

Rendered under `## Wave: DESIGN / [WHY|HOW] <Section>` only when requested via `--expand <id>` (DDD-2), the wave-end menu (`expansion_prompt = "ask"`), `mode = "full"` auto-expansion, or an ad-hoc user request mid-session.

| Expansion ID | Tier label | One-line description |
|---|---|---|
| `trade-off-analysis` | [WHY] | Quality-attribute trade-off matrix with prioritization rationale |
| `rejected-alternatives` | [WHY] | Architectures weighed and rejected with one-paragraph reason per option |
| `c4-narrative` | [HOW] | Long-form C4 walkthrough: System Context → Container → Component prose |
| `evolution-scenarios` | [WHY] | Hypothetical future stress vectors and how the design absorbs them |
| `paradigm-rationale` | [WHY] | Why FP/OOP was selected; comparison vs the alternative for this domain |
| `reuse-analysis-deep-dive` | [WHY] | Per-row justification for every EXTEND vs CREATE_NEW decision in the Reuse table |
| `c4-component-diagrams` | [HOW] | Component-level C4 diagrams for complex subsystems (Mermaid) |
| `expansion-catalog-rationale` | [WHY] | Why this set of expansions, why these defaults, why D10 enforces one-line descriptions |

## Density resolution (per D12)

Call `resolve_density(global_config)` from `scripts/shared/density_config.py` after reading `~/.nwave/global-config.json` (missing/malformed = empty dict). Returns `mode` (`"lean"` | `"full"`) + `expansion_prompt` (`"ask"` | `"always-skip"` | `"always-expand"` | `"smart"`) per the D12 cascade (resolver-internal, DDD-5 — do NOT replicate locally). Branch on `density.mode` for what to emit; branch on `density.expansion_prompt` at wave end for menu behaviour. Full cascade detail, branch semantics, ad-hoc override workflow: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Telemetry (per D4 + DDD-6)

Every expansion choice emits a `DocumentationDensityEvent` (dataclass at `src/des/domain/telemetry/documentation_density_event.py`) via `event.to_audit_event()` → `JsonlAuditLogWriter().log_event(...)`. Schema fields per D4: `feature_id`, `wave`, `expansion_id`, `choice`, `timestamp`. For this wave the schema declares `"wave": "DESIGN"`. Use helper `scripts/shared/telemetry.py:write_density_event(...)` — do NOT write JSONL directly. **NOT YET WIRED**: `scripts/shared/telemetry.py` does not exist yet and `DocumentationDensityEvent(` has zero constructor call sites in `src/des` — until this lands, skip the emission (the [WHY]/[HOW] section append is unaffected); do not hand-roll a substitute JSONL write.

Wave-specific signal: DEVOPS/DISTILL consuming a lean DESIGN feature-delta — downstream `--expand` requests for trade-off or evolution scenarios indicate the `[REF]` baseline was insufficient. Full emission rules: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Reuse Analysis

Discovery Flow step 5 — the gate-parsed contract.

Referenced as step 5 of the Discovery Flow (`nw-design-discovery-flow`); the contract stays in this core because it is AT-pinned to this file. Before designing ANY new component, search the existing codebase for components with overlapping responsibilities. For each overlap, decide "extend existing" or "justify new". Output a table:

### Mandatory feature-delta ownership

Every DESIGN architect dispatch MUST grant the architect write ownership of the
DESIGN sections in `docs/feature/{feature-id}/feature-delta.md`. A detailed
architecture document may supplement that file; it never replaces the
gate-consumed `## Reuse Analysis` and `## Prefactoring Assessment` sections.

A dispatch that requests DESIGN while limiting the architect to a separate
design document or withholding those feature-delta sections is DEFECTIVE. The
architect MUST refuse it before authoring and request a regenerated ownership
envelope. The orchestrator MUST NOT repair the missing sections after handoff.

```
| Existing Component | File | Overlap | Decision | Justification |
|-------------------|------|---------|----------|---------------|
| PreToolUseService | src/des/application/pre_tool_use_service.py | Agent-invocation gate evaluation | EXTEND | Add a narrowly-scoped policy branch only when the driving-port contract requires it |
```

Rules:
- If the design creates a new class that does something an existing class already does (iterate phases, evaluate gates, dispatch agents, handle retry), the default is EXTEND, not CREATE_NEW.
- CREATE_NEW requires evidence that extending is impossible or creates unacceptable coupling (not just "it's complex").
- "The existing class has too many dependencies" is NOT a valid justification — simplify the existing class instead (see F-4: strategy pattern extraction).
- The reviewer MUST verify this table exists and challenge every "CREATE_NEW" decision.
- Gate: Reuse Analysis table present with zero unjustified CREATE_NEW decisions.
- **Closure seed**: an `EXTEND` row that names a field, a count, a partition, or an
  absence/silence SEEDS a closure obligation the DISTILL AT must discharge — name the
  population behind a count, assert conservation across a partition, name the discriminator that
  tells looked-and-absent from never-looked. Write the implied population/law/discriminator into
  the row's Justification so the ATD inherits it (SSOT: Closure obligations, `nw-test-design-mandates`).
- **Blast radius includes `tests/` as a FIRST-CLASS surface** (2026-07-28, two independent lanes
  converged on this gap in one night). When a decision NARROWS or CHANGES an existing semantics,
  the caller search MUST cover `tests/`, not only production callers. A test that pins the OLD
  behaviour is not collateral — it is part of the change, and updating it is intrinsic to the fix.
  Grep the touched symbols across `tests/` and name every test that will flip verdict, in the
  row's Justification.
  **Then carry that list into the Slice Plan's `Owns`.** `Owns` naming only production files makes
  the slice's own ownership declaration FALSE BY CONSTRUCTION whenever behaviour changes: the plan
  says "disjoint — parallel-safe" while the slice genuinely cannot reach green inside those files.
  Measured cost of omitting this: two lanes blocked mid-GREEN in one night, each needing an
  out-of-band ownership extension before it could close.
- **The third surface: ORDER OF REFUSALS.** Searching `tests/` for what ASSERTS the changed
  semantics is still not enough. A change that moves, widens, or un-gates a guard reorders the
  diagnostics of UNRELATED axes: a test that used to reach the check it was written for now
  meets the relocated guard first, and fails having received the wrong refusal. Such a test
  names none of the touched symbols — it passes THROUGH the point where the order changed, so
  no grep finds it. When a decision changes WHICH refusal fires FIRST (not only what the code
  computes), the blast radius must ask "what else flows through this decision point?", and the
  honest answer usually costs a run, not a search.
  Corollary worth stating because it saves the argument later: a guard that MASKS another
  axis's diagnostic is wrong on its own merits, independent of the feature that exposed it —
  fix the order, do not paper over the symptom in the tests that noticed.
  Measured 2026-07-28: a lane's PRESUMED impact list was 2 files, the MEASURED one was 5, and
  a third of the reds belonged to this surface — invisible to both other surfaces.
- **Name WHO updates them, not only WHICH.** Listing the tests a behaviour change invalidates is
  half the job; the plan must also route them. The crafter CANNOT do it — rewriting what a test
  asserts is test authorship, the exclusive territory of `nw-acceptance-designer`, and a crafter
  asked to do it will correctly refuse mid-slice. Nor can a peer grant that scope: an
  authorization relayed sideways is not an authorization. So a behaviour-changing slice needs a
  DISTILL dispatch for its stale tests, planned from the start — not discovered at GREEN.
  Measured 2026-07-28: routing that work to the crafter cost four round-trips on a slice whose
  production code had been ready for an hour.

## Prefactoring Assessment (mandatory DESIGN output — the sibling of Reuse Analysis)

Reuse Analysis asks *which* existing component to extend. Prefactoring asks the question that comes
immediately after, and that a design bolting a feature onto misshapen code never asks:

> **"Make the change easy, then make the easy change."** Is the component we chose to EXTEND in the
> right SHAPE to receive this feature — or does landing the feature on its current shape force a
> compromise (a flag, a second code path, a god-method, a special case) that the code will carry forever?

If the shape is wrong, the fix is NOT to absorb the ugliness into the feature slices. It is a
**`@prefactoring` slice**, delivered FIRST: a behaviour-preserving reshape of the EXISTING code, tests
green at every step, adding zero new behaviour — so the feature that follows lands as an *easy change*.

**Every DESIGN wave MUST emit a `## Prefactoring Assessment` section. It is never silently absent.**
Exactly one of two outcomes:

1. **A `@prefactoring` slice** — declared in the Slice Plan (Class P), ordered BEFORE the feature slices,
   naming: the component reshaped, the compromise it removes, and the invariant "no behaviour change,
   suite green throughout". Its value statement is the *shape*, not a user outcome — so it carries NO
   expectation charter (the charter lives at the OBSERVABLE slice; an `@prefactoring` slice has no user
   surface to examine, and pretending otherwise manufactures a fake oracle).
2. **An explicit, justified NONE** — one or two sentences naming what you LOOKED AT and why the current
   shape already receives the feature cleanly. "Not applicable" / "no need" / silence are REFUSED: an
   unexamined NONE is indistinguishable from a NONE that was never considered — the same absence-vs-
   incapacity confusion the certification gates exist to kill.

**Anti-patterns the assessment must refuse:**
- *Prefactoring smuggled into a feature slice* — a slice that both reshapes AND adds behaviour cannot be
  reverted, cannot be reviewed for either job, and hides a behaviour change inside a "refactor" diff.
- *Prefactoring proposed as a rewrite* — the slice is behaviour-PRESERVING and small; a rewrite is a
  different (and much more expensive) decision, and belongs in an ADR, not smuggled in as prep.
- *Speculative reshaping* — prefactoring earns its slice only when a CONCRETE compromise in THIS feature
  is what it removes. Naming that compromise is the justification; without it, it is speculative
  generality and must be refused.

### Reuse-first DESIGN exit gate

Every DESIGN wave that introduces ≥1 NEW component MUST author a
`## Reuse Analysis` section in the feature-delta. The section is a GFM table with columns:
| Existing Component | File | Overlap | Decision | Justification |

> **Gate contract (the readiness gate REJECTS any other form).** Source of truth:
> `src/des/cli/validate_feature_delta.py` — `REUSE_ANALYSIS_HEADING`,
> `REUSE_ANALYSIS_COLUMNS`, `_REUSE_DECISION_TOKENS`. Consumed by
> `des verify-readiness-pre-dispatch` (invariant 6) and `des validate-feature-delta
> --require-reuse-analysis`. Emit EXACTLY:
> - **Heading**: `## Reuse Analysis` — the bare canonical heading. NOT
>   `## Wave: DESIGN / [REF] Reuse Analysis` (the gate greps `^## Reuse Analysis$`;
>   the Wave-form heading is parsed as MISSING and DELIVER is refused).
> - **Columns**: exactly these 5, in this order — `Existing Component | File |
>   Overlap | Decision | Justification`. A 4-column table or a re-order is
>   `malformed-reuse-analysis`.
> - **Decision cell**: the substantive token, `EXTEND` or `CREATE_NEW`. PREFER a
>   bare token and put qualifiers in the Overlap/Justification cell. A trailing
>   parenthetical qualifier is TOLERATED (DDD-7 leniency, 2026-07-05):
>   `CREATE_NEW (companion)` normalises to `CREATE_NEW`. A cell that does not
>   reduce to a canonical token (e.g. `MAYBE_REWRITE`) is still
>   `malformed-reuse-analysis`.
> - **Justification**: non-empty on every `CREATE_NEW` row (empty → `unjustified-create-new`).
> - **Read-only consumed dependency**: a Protocol/interface the code merely calls, or a property it cross-checks, is NOT a Reuse-Analysis row — describe it in prose beneath the table instead. Any Decision cell besides `EXTEND`/`CREATE_NEW` (e.g. `REUSE`, `READ-ONLY`) is `malformed-reuse-analysis`.

For each NEW class declared under the feature's scoped-path
(default `src/`), the table MUST contain ≥1 row where:
- `Existing Component` column names a candidate class evaluated for extension
- `Justification` column is non-empty (concrete reason the extension was rejected
  in favour of a NEW component)

**Methodology components are also declared (DDD-12)**: the architect declares
reuse not only for NEW `src/` classes but also for NEW *methodology components*
the feature adds — a new data SSOT under `nWave/data` (e.g. a
`dor-items.yaml` data file there), a new skill under `nWave/skills` (e.g. a new
`SKILL.md`), or a new gate under `scripts/cli` (e.g. a new check script). Each
such methodology file is a file-component: it requires its own Reuse Analysis
row exactly as a `src/` class does, naming the candidate it was evaluated
against and a non-empty `Justification`. The gate detects added files under
these three methodology-path kinds — `nWave/data`, `nWave/skills`,
`scripts/cli` — and FAILs the DESIGN when an added methodology file has no
matching row, so the guidance and the enforcement cover the same component set.

**Lenient match (slice-01 baseline)**: the NEW class name appearing
anywhere in any Reuse Analysis section row cell is sufficient.
Column-precise match is slice-02 territory.

**Lenient match for a methodology file-component (DDD-10/DDD-12)**: a NEW
methodology file-component is justified when EITHER form appears in an Existing
Component cell — the **path** form (the file's repo-relative path under one of
the methodology-path kinds) OR the **stem** form (the file's stem, e.g.
`dor-items` for a `dor-items.yaml` data file). Naming the file-component by
either its repo-relative path or its stem satisfies the gate.

**Enforcement**: the SF-side / cross-tree CLI
`scripts/cli/check_reuse_first_design.py` (DEV-owned, shipped by
`fix-design-reuse-first-gate-cli`) inspects the feature-delta + `git diff
master...HEAD --name-status` and emits:
- stdout token: `reuse_first feature=<id> new_components=<n> justified=<m> verdict=<PASS|FAIL>`
- exit code: `0` PASS (every NEW component justified) / `1` FAIL (≥1 unjustified) / `2` MALFORMED

The CLI wires into nw-design SKILL.md as the post-DESIGN-wave gate (analog of
the env-e2e Gate A post-DELIVER feature-end gate).

**When the architect agent dispatches**: if any NEW component is missing
its Reuse Analysis row, the agent MUST refuse to declare DESIGN complete and
emit a structured refusal naming the missing component(s).

**Rejection rationale templates** (non-exhaustive examples, architect agents
SHOULD select one OR author a feature-specific rationale):
- "existing component <X> is in a different bounded context and extending
  it would violate hexagonal boundary"
- "existing component <X> implements a closed protocol; the NEW component's
  responsibility extends the protocol surface"
- "existing component <X> is in a frozen exemption set (see <link>);
  extension forbidden"
- "existing component <X> would require a depth-N refactor incompatible
  with the slice's carpaccio scope"

**Anti-pattern to refuse**: empty `Justification` cell OR a hand-wave
("not applicable", "different use case", "TBD") — these MUST be expanded into
a concrete rejection rationale before DESIGN exits.

**Cross-reference**: DEV CLI commit `04e07c08a` (slice-01 walking-skeleton) ships
the enforcement binary; surface contract anchored at
`docs/feature/fix-design-reuse-first-gate-cli/feature-delta.md` (DDD-4 stdout
token, DDD-5 exit codes 0/1/2, DDD-6 lenient match, DDD-7 NEW component
detection scoped to `src/`).

## Rigor Profile Integration

Before dispatching the architect agent, read rigor config from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

- **`agent_model`**: Pass as `model` parameter to Task tool. If `"inherit"`, omit `model` (inherits from session).
- **`reviewer_model`**: If design review is performed, use this model for the reviewer agent. If `"skip"`, skip design review.
- **`review_enabled`**: If `false`, skip post-design review step.

**Structural-correctness reviewer never skips**: `rigor.reviewer_model: "skip"` applies to scale-sensitive cost-driven reviewers (Eclipse / Architect / Forge here, plus their per-wave equivalents). The structural-correctness reviewer at the end of DISTILL (Sentinel / `@nw-acceptance-designer-reviewer`) ALWAYS dispatches — silent skip masks Gherkin antipatterns / boundary violations / contract drift, which is the bug class issue #52 fixed.

## Interactive Decision Points

### Decision 0: Design Scope (MANDATORY — do NOT skip)

**Question**: What are you designing?

You MUST ask this question before invoking any architect. Do NOT default to application scope. The answer determines WHICH agent to invoke.

**Options**:
1. **System / infrastructure** → invokes @nw-system-designer
2. **Domain / bounded contexts** → invokes @nw-ddd-architect
3. **Application / components** → invokes @nw-solution-architect
4. **Full stack** → invokes all three agents sequentially

### Decision 1: Interaction Mode

**Question**: How do you want to work?

**Options**:
1. **Guide me** — the architect asks questions, you make decisions together
2. **Propose** — the architect reads your requirements and proposes 2-3 options with trade-offs

## Agent Invocation

### Architect Routing (based on Decision 0)

| Decision 0 | Agent | Focus |
|-------------|-------|-------|
| System / infrastructure | @nw-system-designer | Distributed architecture, scalability, caching, load balancing, message queues |
| Domain / bounded contexts | @nw-ddd-architect | DDD, aggregates, Event Modeling, event sourcing, context mapping |
| Application / components | @nw-solution-architect | Component boundaries, hexagonal architecture, tech stack, ADRs |
| Full stack | @nw-system-designer then @nw-ddd-architect then @nw-solution-architect | All three in sequence |

Pass Decision 1 (guide/propose) to the invoked agent as the interaction mode.

All agents write to `docs/product/architecture/` (SSOT). Each architect owns its section:
- @nw-system-designer writes `## System Architecture` in `brief.md`
- @nw-ddd-architect writes `## Domain Model` in `brief.md`
- @nw-solution-architect writes `## Application Architecture` in `brief.md`

For **Full stack** mode, each agent reads the prior architect's output before starting its own work.

### Agent Dispatch (after Decision 0 — no default)

<!-- DES-WAVE: design -->
<!-- gates-ref: design -->
<!-- outputs-ref: design -->

The DESIGN gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/design.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This skill narrates DESIGN intent (discovery-driven architecture whose feature-delta
the acceptance-designer consumes) but does NOT enumerate the registry gate stack
inline; consult the registry for the authoritative gate stack + output contract.

Include the `<!-- DES-WAVE: design -->` marker line above verbatim in EVERY architect Agent dispatch prompt — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

Based on Decision 0 answer, invoke the corresponding agent. Do NOT default to application scope without asking.

**System scope** → @nw-system-designer
**Domain scope** → @nw-ddd-architect
**Application scope** → @nw-solution-architect
**Full stack** → @nw-system-designer then @nw-ddd-architect then @nw-solution-architect

Execute \*design-architecture for {feature-id}.

Context files: see `nw-design-prior-wave-reading` (Prior Wave Consultation) + project context files.

**Configuration:**
- model: rigor.agent_model (omit if "inherit")
- interaction_mode: {Decision 1: "guide" or "propose"}
- interactive: moderate
- output_format: markdown
- diagram_format: mermaid (C4)
- stress_analysis: {true if --residuality flag (force-on) or `nw-stress-analysis`'s own semantic trigger fires per the role registry, false otherwise}

**SKILL_LOADING**: Read your skill files at `~/.claude/skills/nw-{skill-name}/SKILL.md`. At Phase 4, always load: `nw-architecture-patterns`, `nw-architectural-styles-tradeoffs`. Then follow your Skill Loading Strategy table for phase-specific skills.

## Success Criteria

- [ ] Business drivers and constraints gathered before architecture selection
- [ ] Existing system analyzed before design (codebase search performed)
- [ ] Integration points with existing components documented
- [ ] **Reuse Analysis table present** with every overlapping component listed (HARD GATE — reviewer blocks without this)
- [ ] Architecture supports all business requirements
- [ ] Technology stack selected with clear rationale
- [ ] Development paradigm selected and (optionally) written to project CLAUDE.md
- [ ] Component boundaries defined with dependency-inversion compliance
- [ ] C4 System Context + Container diagrams produced (Mermaid)
- [ ] ADRs written with alternatives considered
- [ ] Per-wave peer review (OPTIONAL — invoke `/nw-review nw-solution-architect-reviewer` only on trigger: contested ADR, novel pattern, performance-budget unverified by spike, security boundary change. Default: skip. Mandatory consolidated review fires at end of DISTILL covering all 4 waves in parallel.)
- [ ] Handoff accepted by nw-platform-architect (DEVOPS wave)

## Next Wave

**Handoff To**: nw-platform-architect (DEVOPS wave)
**Deliverables**: See Morgan's handoff package specification in agent file

## Wave Decisions Summary

There is no separate `design/wave-decisions.md` file (that shape is a legacy multi-file
output — `scripts/validation/validate_feature_layout.py` flags any loose markdown under
`design/` as an offender, canonical alternative "merge into feature-delta.md"). The Decisions
table + ADR Refs already emitted under Tier-1 above (per Decision-once) ARE the summary DEVOPS
and DISTILL read — a second file would be exactly the duplication that section forbids.

## Outputs

**Single narrative file**: `docs/feature/{feature-id}/feature-delta.md` — DDD list, component decomposition, driving/driven ports, technology choices, decisions table, reuse analysis, open questions use the density contract. The gate-consumed `## Reuse Analysis` and `## Prefactoring Assessment` headings remain bare; every other DESIGN section uses `## Wave: DESIGN / [REF|WHY|HOW] <Section>`.

**Machine artifacts**: none unique to feature dir (the `feature-delta.md` IS the artifact; SSOT writes carry the architectural payload).

**SSOT updates** (per Recommendation 3 / back-propagation contract — DESIGN is the primary SSOT integrator):
- `docs/product/architecture/brief.md` — created or updated. Each architect owns its section: `## System Architecture` (nw-system-designer), `## Domain Model` (nw-ddd-architect), `## Application Architecture` (nw-solution-architect)
- `docs/product/architecture/adr-*.md` — one ADR per significant architectural decision
- `docs/product/architecture/c4-diagrams.md` — current component topology if separate from brief

**Optional** (project-root, not feature-dir): `CLAUDE.md` `## Development Paradigm` section.

Legacy multi-file outputs (per-wave `wave-decisions.md`, `architecture-design.md`, etc. inside `docs/feature/{id}/design/`) are NOT produced — that content lives in `feature-delta.md` plus the SSOT integration above. Validator: `scripts/validation/validate_feature_layout.py`.
