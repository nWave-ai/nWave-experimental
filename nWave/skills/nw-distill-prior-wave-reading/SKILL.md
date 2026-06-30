---
name: nw-distill-prior-wave-reading
description: "DISTILL prior-wave reading + reconciliation procedure — read all prior-wave SSOT + feature-delta, run the Wave-Decision Reconciliation HARD GATE, fire the DESIGN-absent + Total-AT Tier-A advisories, and back-propagate gaps. Run BEFORE writing any scenario."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Prior-Wave Reading + Reconciliation (PROCEDURE)

**Kind**: PROCEDURE | **One job**: consume prior-wave knowledge + reconcile contradictions before scenario writing | **One trigger**: a DISTILL session is about to author scenarios and has not yet read the prior-wave SSOT + feature-delta.

Composed by `nw-distill`. The pinned advisory + degradation summary lives in the `nw-distill` core (`## Prior-Wave Reading + Advisories`); this module is the full deterministic procedure.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **READ PRIOR WAVES** — read SSOT + feature-delta artifacts. **READING ENFORCEMENT**: use the Read tool on every file in the table; after reading output a confirmation checklist (`+ {file}` read, `- {file} (not found)` missing). Do NOT skip files that exist. Gate: every listed file read or marked missing.
1b. **READ DELIVERABLE TYPE** (ADR-PST-003 / DDD-6) — Read `deliverable_type` from the SAME `.nwave/des-config.json` the DES runtime gate uses — this is the single source of truth (`DESConfig.deliverable_type` precedence, ADR-PST-002): (1) declared project `.nwave/des-config.json` key `deliverable_type` if in `{application, plugin, skill}`; (2) else global `~/.nwave/global-config.json` `defaults.deliverable_type`; (3) else root-only FS detection; (4) a present-but-typo'd value resolves to the safe default (`application`). Do NOT re-detect independently — read what the gate reads so the Final Wave Review Gate routing and the enforcement gate never diverge. Store the resolved type to route the Final Wave Review Gate (see `nw-distill` core, §Deliverable-Type Verification Routing). Gate: deliverable type read from `.nwave/des-config.json` and stored.
2. **MIGRATION / GREENFIELD GATE** — `docs/product/` absent + `docs/feature/` has features → STOP, guide to `docs/guides/migrating-to-ssot-model/README.md`; greenfield bootstrapped `docs/product/`. Gate: migration or greenfield confirmed.
3. **ROW 7b — DESIGN-absent advisory** — inspect feature-delta for `## Wave: DESIGN / [REF] Code-Design`; present → silent; absent → emit advisory (NAME / RISK `/nw-design` / ASK / PROCEED). Never blocks. Gate: advisory emitted or silent; flow continues to DISTILL.
4. **ROW 7c — Total-AT advisory** — sum the `[REF] Slice Plan` per-slice AT counts → `N`; compare `DESConfig().rigor_feature_total_at_advisory_threshold` → `M`; `N>M` → emit advisory (PROPOSE `/nw-discuss`); else silent. Never blocks. Gate: advisory emitted or silent.
5. **WAVE-DECISION RECONCILIATION HARD GATE** — the ONLY hard gate before scenario writing. Per DISCUSS decision check DESIGN/DEVOPS contradiction; ANY contradiction → return `{CLARIFICATION_NEEDED: true, questions: [{file, contradicting-decisions, ask-which-stands}]}` + BLOCK; zero → log "Reconciliation passed — 0 contradictions". Gate: zero contradictions or `CLARIFICATION_NEEDED` returned.
6. **GRACEFUL DEGRADATION** — missing upstream artifact → WARN + proceed per the degradation matrices; DESIGN-absence is surfaced via the advisory soft-gate, never a block. Gate: every missing artifact logged + degraded, never blocked.
7. **BACK-PROPAGATION** — when DISTILL reveals gaps/contradictions in prior waves, write findings to `docs/feature/{feature-id}/distill/upstream-issues.md`; flag untestable DISCUSS criteria; resolve contradictions with the user before testing ambiguous requirements. Gate: gaps written or none found.

## Prior Wave Reading table

| # | Read | Extract / check | Gate |
|---|---|---|---|
| 1 | `docs/product/journeys/{name}.yaml` | embedded Gherkin as starting scenarios; integration checkpoints + `failure_modes` per step | read or marked missing |
| 2 | `docs/product/architecture/brief.md` | driving ports (`## For Acceptance Designer` section) for `@driving_port` scenarios + the code-design contract (the induction-map input — `nw-distill`) | read or marked missing |
| 3 | `docs/product/kpi-contracts.yaml` | behaviors needing `@kpi` scenarios (soft gate — warn if missing, proceed) | read or marked missing |
| 4 | `docs/feature/{feature-id}/discuss/user-stories.md` + `story-map.md` + `wave-decisions.md` | scope boundary + embedded ACs · walking-skeleton priority + release slicing · upstream-change check | files read or marked missing |
| 5 | (if spike ran) `docs/feature/{feature-id}/spike/findings.md` + `spike/wave-decisions.md` | validated/failed assumptions, performance, **promotion decision** (PROMOTE / DISCARD / PIVOT); update ACs if findings contradict DISCUSS | read if present, marked not found if absent |
| 5b | (only if SPIKE promoted) `tests/{test-type-path}/{feature-id}/acceptance/walking-skeleton.feature` + the `src/` modules it exercises | skeleton **already committed and green** — build **additional** scenarios on top, never rewrite; identify driving adapter, e2e path, uncovered scenarios | read + `@walking_skeleton` scenario confirmed green, or marked not found |
| 6 | `docs/feature/{feature-id}/devops/wave-decisions.md` | infrastructure constraints affecting tests | read or marked missing |

DISTILL = conjunction point — reads all three SSOT dimensions + feature delta to translate prior-wave knowledge into executable acceptance tests.

## Wave-Decision Reconciliation HARD GATE detail

| Step | Action |
|---|---|
| 1 | Read all prior-wave `wave-decisions.md`: `docs/feature/{feature-id}/{discuss,design,devops}/wave-decisions.md` |
| 2 | Per DISCUSS decision, check DESIGN/DEVOPS contradiction. Examples — all = CONTRADICTION: DISCUSS "email notifications" vs DESIGN "in-app only" · DISCUSS "REST API" vs DESIGN "gRPC" · DISCUSS "single-tenant" vs DEVOPS "multi-tenant" |
| 3 | ANY contradiction → return `{CLARIFICATION_NEEDED: true, questions: [{file, contradicting-decisions, ask-which-stands}]}` + BLOCK |
| 4 | Zero contradictions → log "Reconciliation passed — 0 contradictions", proceed |

Do NOT silently pick one side. Do NOT write scenarios against ambiguous specifications. Blocking costs minutes; wrong behavior costs hours.

## Advisory-Skip-Gate Pattern (Tier-A) — the reusable shape

The reusable Tier-A advisory-skip-gate shape — authored ONCE here as the SSOT anchor. Rows 7b/7c (and the five sibling wave-migrations) EXTEND this pattern by referencing this anchor and binding its five slots to their own trigger; the shape is never re-inlined per trigger. A Tier-A advisory names evidence, states a consequence, proposes a remedy wave, asks a closed option set, and proceeds on any answer (it never blocks). The five slots a sibling binds per wave:

- **NAME** — the evidence that keys the advisory (which artifact or count was observed in the feature-delta).
- **RISK** — the consequence of skipping the proposed wave.
- **PROPOSE** — the remedy wave the advisory suggests the operator run.
- **ASK** — the closed option set offered to the operator ({run the remedy wave · proceed without it}).
- **PROCEED** — on any answer the flow continues forward; the advisory has no veto power (soft gate, never blocks).

Degrade-loud: when the keying evidence is unreadable, emit a `⊘` notice and proceed (never block, never assume the firing branch).

## Document Update (Back-Propagation)

| Step | Action | Gate |
|---|---|---|
| 1 | Write findings to `docs/feature/{feature-id}/distill/upstream-issues.md`, referencing the original prior-wave document + the gap | file written |
| 2 | DISCUSS criteria untestable as written → note the specific criteria + why | all untestable criteria flagged |
| 3 | Resolve contradictions with user before testing ambiguous/contradictory requirements | user resolution received |

## Success Criteria

- [ ] Every prior-wave file read or marked missing (reading-enforcement checklist emitted)
- [ ] Wave-Decision Reconciliation HARD GATE run — zero contradictions or `CLARIFICATION_NEEDED` returned
- [ ] Rows 7b + 7c advisories fired or correctly silent; neither blocked
- [ ] Missing artifacts degraded with WARN, never blocked
- [ ] Back-propagation findings written or none found
