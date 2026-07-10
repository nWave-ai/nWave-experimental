---
name: nw-buddy-wave-knowledge
description: Wave methodology knowledge for the buddy agent — what each wave does, its inputs and outputs, and how to route questions.
---

# Wave Methodology Knowledge

The nWave methodology organizes work into a canonical sequence of **waves**. Each wave has a purpose, a primary agent, inputs from earlier waves, and outputs consumed by later waves. The buddy agent uses this map to answer "where am I in the process" and "what should I do next" questions without stepping into execution territory.

## The canonical wave sequence

```
DISCOVER -> DIVERGE(opt) -> DISCUSS -> DESIGN -> DEVOPS -> DISTILL -> DELIVER
```

Each wave has a slash command (`/nw-<wave>`) and a primary agent. Waves run top-to-bottom. Skipping waves is a smell; going back to revise an earlier wave is normal and expected. DIVERGE is optional — run it when a validated problem has several plausible solution approaches and the team hasn't converged yet. (SPIKE was a canonical phase before v3.16.0 and is now deprecated — pre-design spike/analysis is embedded in DESIGN. See the deprecated note below.)

## Wave-by-wave reference

### 1. DISCOVER

- **Purpose**: validate that an opportunity exists and is worth pursuing.
- **Primary agent**: product-discoverer.
- **Inputs**: a rough idea, a user complaint, a market signal, or a strategic prompt.
- **Outputs**: an evidence brief — problem statement, target users, pains, existing solutions, strength of signal, go/no-go recommendation.
- **Typical artifacts**: `docs/discover/<opportunity>-brief.md`, user interview notes, competitive scans.
- **Common questions**: "is this worth doing?", "who has this problem?", "what's the evidence?"

### 2. DIVERGE (optional)

- **Purpose**: generate 3–5 divergent solution directions before converging on one — via JTBD analysis, competitive research, structured brainstorming, and taste-filtered evaluation.
- **Primary agent**: diverger (Flux).
- **Inputs**: DISCOVER output — a validated problem and target users, but no chosen approach yet.
- **Outputs**: a ranked set of design directions with a branch-point recommendation.
- **Typical artifacts**: `docs/feature/<id>/diverge/recommendation.md`.
- **Common questions**: "which approach should we take?", "what are the options?"
- **When to run**: run DIVERGE when the problem is validated but the solution shape is genuinely open. Skip when the approach is obvious or already decided.

### 3. DISCUSS

- **Purpose**: turn a validated opportunity into user stories with acceptance criteria.
- **Primary agent**: product-owner.
- **Inputs**: DISCOVER output — validated problem and target users; DIVERGE recommendation (if run) — the chosen solution direction handed off from Flux.
- **Outputs**: a set of user stories, each with a goal, acceptance criteria in Given-When-Then form, and a rough priority.
- **Typical artifacts**: `docs/discuss/<feature>-stories.md`, a backlog update.
- **Common questions**: "what does 'done' look like for this feature?", "what are the user stories?"

> **SPIKE (deprecated).** SPIKE was a canonical wave phase before v3.16.0. It is now deprecated — pre-design spike/analysis work is embedded in the DESIGN wave. The `/nw-spike` command remains for backward compatibility, but the buddy must NOT present SPIKE as a step in the canonical sequence. Route spike-type questions ("will this mechanism work?", "can we hit the performance budget?") to DESIGN. See the `spike` entry's `deprecation_note` in `framework-catalog.yaml`.

### 4. DESIGN

- **Purpose**: propose the solution architecture — component boundaries, key abstractions, major trade-offs.
- **Primary agent**: solution-architect.
- **Inputs**: DISCUSS output — stories and acceptance criteria (carrying through the DIVERGE recommendation, if one was made). Any pre-design spike/analysis is embedded in this wave.
- **Outputs**: an architecture proposal, usually updating the SSOT architecture doc, plus ADRs for significant decisions.
- **Typical artifacts**: `docs/architecture/architecture-design.md` updates, `docs/adrs/ADR-NNN-<title>.md`, diagrams.
- **Common questions**: "how will this be built?", "what are the components?", "what are the boundaries?"

### 5. DEVOPS

- **Purpose**: plan the infrastructure, CI/CD, and deployment needed to run what DESIGN proposed.
- **Primary agent**: platform-architect.
- **Inputs**: DESIGN output.
- **Outputs**: infrastructure plan, CI/CD changes, deployment checklist, rollback plan.
- **Typical artifacts**: updated CI workflow files, IaC changes, runbooks.
- **Common questions**: "how do we ship this?", "what does CI need?", "what's the rollback plan?"

### 6. DISTILL

- **Purpose**: translate stories and acceptance criteria into executable BDD test scenarios — the specification the crafter will implement against.
- **Primary agent**: acceptance-designer.
- **Inputs**: DISCUSS stories and DESIGN architecture.
- **Outputs**: `tests/acceptance/` files with Given-When-Then scenarios as active-RED scaffolds (run + raise AssertionError — no @skip, per ADR-GV-001 D6; atdd_pure: current slice only, future slices absent from disk), plus a delivery slice plan. <!-- mode-ref-ok -->
- **Typical artifacts**: feature files or test classes with BDD scenarios, a delivery roadmap in `docs/feature/<name>/roadmap.md`.
- **Common questions**: "what are the test scenarios?", "what's the delivery plan?"

### 7. DELIVER

- **Purpose**: implement the feature using Outside-In TDD, step by step, until all DISTILL scenarios pass.
- **Primary agent**: software-crafter.
- **Inputs**: DISTILL output — scenarios and roadmap.
- **Outputs**: working, tested, committed code.
- **Typical artifacts**: commits following the TDD 3-phase canon (RED -> GREEN -> COMMIT, ADR-025 2026-05-07; legacy 5-phase PREPARE -> RED_ACCEPTANCE -> RED_UNIT -> GREEN -> COMMIT preserved for pre-2026-05-07 audit-log replay), updated tests, updated source files.
- **Common questions**: "is this feature done?", "what step are we on?", "is the test suite green?"

## Carpaccio slice-size ceiling and the `@coupled` escape

Under `workflow.mode == atdd_pure`, DISTILL/DELIVER slices are constrained by a <!-- mode-ref-ok -->
carpaccio slice-size ceiling (ratified 7 ATs per slice, ADR-028 D2-bis) enforced
by the carpaccio entry gate. A slice's AT count may exceed the ceiling and still
clear the gate when it is genuinely cohesive: annotate the Slice Plan row
`@coupled` (Annotation column) with a recorded coupling justification
(Justification column) — the DESIGNED escape path (`CoupledSliceAccepted`, ADR-028
D2), not a hack or a violation. It exists because some AT groups cannot be
decomposed further without breaking the single end-to-end vertical they prove
(e.g. an adapter's full error-taxonomy coverage matrix).

Prefer splitting into thinner slices first when a natural seam exists (e.g. by
property, by error class). Reach for `@coupled` only when the AT group is truly
inseparable. A slice that is over-ceiling and not cleanly re-sliceable warrants a
deep-review + refactor conversation at FEATURE scope, not a per-slice patch.

**Where the escape is READ for a pytest-regression feature (no `.feature` scenario
tags)**: the `@coupled` escape lives ONLY in the Annotation column of that slice's
`[REF] Slice Plan` row, plus a non-empty Justification cell on the same row —
never in the test file. A marker/decorator on the pytest file itself is not read
by the gate. `@walking_skeleton`/`@infrastructure` govern ordering and slice
composition, not size — only `@coupled`+justification on the Slice Plan row
lifts the ceiling (currently 7 ATs).

## Gate expectations + the producing tool for each (ask before you hit the wall)

Every gate fires the earliest it can, but the point is to satisfy it BEFORE it fires — so
when someone asks "what does gate X expect / how do I author for it / what tool produces the
artifact", answer with the expectation AND the producing tool (the gate's rejection routes there
too — you never hand-assemble the checked artifact):

| Gate (when it fires) | What it expects | Producing tool (the how) |
|---|---|---|
| readiness-pre-dispatch (before crafter dispatch) | the feature-delta carries the required sections (Reuse Analysis, Test Reuse & Consolidation, Slice Plan) with canonical headings/tokens | `des feature-delta-doctor` lists every gap in one pass; author the section from the schema |
| dispatch guard (at crafter dispatch) | the 12-section atdd_pure dispatch, marker-triple, correct lane | `des dispatch --mode atdd_pure --project-id … --slice … --phase … [--lane …] --intent …` GENERATES a valid dispatch by construction — never hand-assemble it | <!-- mode-ref-ok -->
| carpaccio slice gate (before A_GREEN) | slice ≤ ceiling (or `@coupled`+justification), an APPROVED AT-review or a mechanical-seal pair | re-slice, or `des verify-red-green --record-red` + `des verify-negative-at` for the seal |
| slice commit (at commit) | E1 completeness + E2 contract + E3 examine; the record is written by `des commit-slice` itself | `des commit-slice` stamps the Gate-Scope trailer AND folds in the verify-then-record (writes SliceCommitVerified) — no hook to miss |
| DISTILL gate-out (spec-coverage, gate-G, at DISTILL return) | every requirement row covered by a marked AT; every contract obligation has exactly one inducing AT tracing to a contract row | tag each AT `@covers Rn`; induce from the 3-source map (see DISTILL); do not over-author |
| mode-registry-completeness (pre-commit) | every flavor declares the full field set, exactly one `default: true` | `des flavor-scaffold --flavor-id <id>` PRODUCES a structurally-complete flavor skeleton — fill the placeholders, never hand-assemble the field set |
| feature-end (execution-reach, fresh-clone, env-e2e, at feature-end) | every prod file executed; the demo-recipe builds clean on a fresh clone; the env-e2e passes after real build+install | author each so its code is exercised by its own AT; keep `.nwave/demo-recipe.json` current; write the e2e alongside the code (surfaced inline at DELIVER-open) |

The rule the buddy repeats: **a gate names its producing tool in the rejection; run that tool, don't
hand-repair.** If a gate blocks and you're unsure why, run the gate directly and read its
`how`/`recovery_suggestions` field — every gate self-explains what/why/how.

## Cross-wave agents

Some agents operate across waves:

- **researcher** — gathers evidence for any wave that needs it.
- **troubleshooter** — diagnoses problems in existing code or processes.
- **documentarist** — produces user-facing documentation, typically after DELIVER.
- **data-engineer** — advises on data architecture, schema, and storage for any wave that needs it.

Diagrams are produced via the `/nw-diagram` command (owned by the solution-architect), not a separate agent.

Peer reviewers exist for each specialist (one per wave) and enforce quality gates.

## Routing questions to the right wave

When a user asks something, the buddy identifies which wave owns the question and answers from that wave's artifacts. Examples:

| Question | Wave | Where to read |
|---|---|---|
| "Is this idea any good?" | DISCOVER | discover briefs |
| "Which approach should we take?" | DIVERGE | `diverge/recommendation.md` |
| "What are the user stories?" | DISCUSS | story docs / backlog |
| "How will the module be shaped?" | DESIGN | architecture doc, ADRs |
| "What's the CI plan?" | DEVOPS | CI workflows, runbooks |
| "What are the test scenarios?" | DISTILL | feature files, roadmap |
| "What step are we on?" | DELIVER | commits, test suite, roadmap |

If the user's question spans multiple waves (e.g., "what's this feature and how does it work?"), answer with contributions from each relevant wave, in order.

## Recognizing which wave the user is in

Signals:

- **DISCOVER**: user is asking about opportunity, not code. Words like "should we", "is there demand".
- **DIVERGE**: user is weighing several solution approaches and hasn't committed. Words like "which approach", "what are the options", "this way or that way".
- **DISCUSS**: user is talking about stories, acceptance criteria, user needs.
- **DESIGN**: user is asking about components, layers, boundaries, trade-offs.
- **DEVOPS**: user is talking about deployment, CI, environments, secrets, rollout.
- **DISTILL**: user is asking about test scenarios, Given-When-Then, the roadmap.
- **DELIVER**: user is asking about implementation status, failing tests, next step, commits.

If unsure, ask.

## What the buddy does NOT do

- **Does not run the crafter.** The buddy is read-only guidance. If the user wants code written, they should invoke `/nw-deliver` or the crafter agent directly.
- **Does not skip waves.** If a user asks to "just implement this" and DISTILL hasn't been run, the buddy points out the gap and suggests running DISTILL first.
- **Does not invent artifacts.** If a DESIGN doc doesn't exist, the buddy says so — it doesn't make one up.
- **Does not write acceptance tests on the fly.** That's DISTILL's job.
- **Does not change the wave order.** The sequence exists because each wave depends on the previous.

## Rule of thumb

The buddy's mental model is always: *"What wave is this question in, which files hold the answer, and what are the gaps?"* Answer from those files, cite them, and flag gaps as findings.
