---
description: "Designs CI/CD pipelines, infrastructure, observability, and deployment strategy. Use when preparing platform readiness for a feature."
argument-hint: "[deployment-target] - Optional: --environment=[staging|production] --validation=[full|smoke]"
---

# NW-DEVOPS: Platform Readiness and Infrastructure Design

**Wave**: DEVOPS (wave 4 of 6) | **Agent**: Apex (nw-platform-architect) | **Command**: `/nw-devops`

## Overview

Execute DEVOPS wave: platform readiness|CI/CD pipeline setup|observability design|infrastructure preparation. Positioned between DESIGN and DISTILL (DISCOVER > DIVERGE > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER), ensures infrastructure is ready before acceptance tests and code.

Apex translates DESIGN architecture decisions into operational infrastructure: CI/CD pipelines|logging|monitoring|alerting|observability.

## Platform Decisions (flow-v2: KPI-driven, applicability-first)

The pre-flow-v2 free-form decision-question block (deployment-target / container-orchestration / CI-platform / observability-stack / deployment-strategy / continuous-learning / branching asked by open judgement) is removed. Under flow-v2 these are NOT free-form questions: Apex (nw-platform-architect) derives them from the prior-wave SSOT and the DISCUSS outcome KPIs rather than asking them blind. See `@nw-platform-architect` for the normative model:

- **Applicability-first**: the DEVOPS gate-IN consumes the DESIGN-OUT pass and the DISCUSS outcome KPIs and runs the applicability check first. A feature with no infra, deploy, or observability delta records an explicit N/A DEVOPS skip (Tier-B advisory notifies without blocking).
- **KPI → telemetry**: the platform-architect maps every outcome KPI to a concrete telemetry signal — a log event, a metric, a trace span, or a golden-signal threshold — and designs second-way observability around the outcome-KPI signals, not generic dashboards untraced to a KPI. An un-instrumentable KPI fails the gate at gate-OUT and is routed to redo in-wave.
- **Infrastructure / deployment / branching / security**: derived from the SSOT architecture (deployment topology, scaling needs, risk profile) and the team-capability evidence the architect gathers — not from a blind menu. Deployment-strategy selection carries evidence-based justification referencing SLOs|risk|team capability, with a tested rollback procedure.

Decision 9 (Mutation Testing Strategy) below remains an explicit flow-v2 decision because it persists to project CLAUDE.md.

### Decision 9: Mutation Testing Strategy
**Question**: When should mutation testing run?
**Options**:
1. **per-feature** (default) -- Runs after each feature delivery (refactoring + review), scoped to modified files. Best for small/medium projects where per-feature overhead is acceptable. Fastest feedback loop but adds ~5-15 min per delivery.
2. **nightly-delta** -- Runs in CI nightly on files modified that day. Best for large projects where per-feature mutation testing is too slow. Delays feedback but keeps delivery fast.
3. **pre-release** -- Runs before each release on the entire solution. Best for projects with long release cycles where comprehensive mutation coverage matters most at release boundaries. Slowest feedback but most thorough.
4. **disabled** -- No mutation testing. Only appropriate for prototypes, spikes, or projects where test quality is validated through other means.

After selection, Apex asks permission to write to project CLAUDE.md under `## Mutation Testing Strategy`:

**per-feature**: `This project uses **per-feature** mutation testing. Runs after refactoring during each delivery, scoped to modified files. Kill rate gate: >= 80%.`

**nightly-delta**: `This project uses **nightly-delta** mutation testing. CI runs on files modified each day. NOT run during feature delivery.`

**pre-release**: `This project uses **pre-release** mutation testing. Runs on entire solution before each release. Delivery not blocked.`

**disabled**: `Mutation testing is **disabled**. Test quality validated through code review and CI coverage.`

Default if not chosen: **per-feature**.

## Prior Wave Consultation

Before beginning DEVOPS work, read SSOT and prior wave artifacts:

1. **SSOT** (if `docs/product/` exists):
   - `docs/product/architecture/brief.md` and `docs/product/architecture/adr-*.md` — current architecture (driving ports, component topology) and durable design decisions; this is the primary input for infrastructure decisions
   - `docs/product/kpi-contracts.yaml` — existing KPI contracts (if any — extend, don't duplicate)
2. **DISCUSS** (KPIs only, ephemeral workspace while the delivery is open): read the current `outcome-kpis.md` under the feature's DISCUSS output — drives observability and instrumentation design for this specific feature

There is no separate DESIGN decision-summary ledger to read: `docs/product/architecture/brief.md`/ADRs already carry every durable DESIGN decision DEVOPS needs.

**READING ENFORCEMENT**: You MUST read every file listed in Prior Wave Consultation above using the Read tool before proceeding. After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes infrastructure decisions disconnected from architecture.

After reading, check whether any DEVOPS decisions would contradict DESIGN architecture. Flag contradictions and resolve with user before proceeding. Example: DESIGN specifies "single-region deployment" but DEVOPS discovers latency requirements from outcome-kpis.md that demand multi-region — this must be resolved.

## Downstream Correction (No Delta Artifact)

When a DEVOPS decision contradicts an earlier-wave fact, name the conflicting
canonical owner and correct it there directly — never in a side file. An
infrastructure constraint that requires an architecture change is returned to
`docs/product/architecture/brief.md` or the relevant ADR, stated inline with
the original assumption, the new one and the rationale (ADR Section 7). There
is no `upstream-changes.md` ledger.

## Agent Invocation

@nw-platform-architect

<!-- DES-WAVE: devops -->

**Wave-entry dispatch marker contract.** Include the `<!-- DES-WAVE: devops -->` marker line above verbatim in the Agent dispatch prompt. For a wave-ENTERING dispatch this single marker is the COMPLETE and SUFFICIENT contract — it both declares the wave (so the PreToolUse hook arms enforcement via the INFERRED fallback even on runtimes whose prompt-submission anchor never fired) and is recognized by the spine as a legitimate entry that is EXEMPT from the WAVE_MARKER_BYPASS veto. Do not add `DES-VALIDATION`/`DES-PROJECT-ID`/`DES-STEP-ID` to the entry dispatch; the DES-WAVE marker can only ADD gating, never remove it.

**In-wave child dispatch (non-entering).** If you dispatch a FURTHER sub-agent while the wave is already active (not the entry dispatch), that child is NOT exempt. A child carrying no DES markers is DENIED loud as a wave bypass. Such a child MUST carry the wave's DES marker set — copy `<!-- DES-WAVE: devops -->` plus the wave's `DES-*` markers from the parent dispatch onto the child prompt.

Execute platform readiness and infrastructure design for {feature-id}.

Context files: see Prior Wave Consultation above.

**Configuration:**
- Platform decisions (deployment target, container orchestration, CI/CD platform, existing infrastructure, observability/logging, deployment strategy, continuous learning, git branching) are DERIVED by Apex from the SSOT architecture + DISCUSS outcome KPIs per the flow-v2 KPI-driven, applicability-first model above — not supplied as free-form answers.
- mutation_testing_strategy: {Decision 9}

**KPI-Driven Observability:**
If `outcome-kpis.md` exists in the feature's discuss directory, Apex MUST read it and design instrumentation to collect the defined KPIs. Each KPI's "Measured By" and "Measurement Plan" sections drive:
- Data collection infrastructure (events, logs, analytics)
- Dashboard design (which metrics to visualize)
- Alerting rules (guardrail metric thresholds)

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] CI/CD pipeline design finalized and documented
- [ ] Logging infrastructure design complete (structured logging|aggregation)
- [ ] Monitoring and alerting design complete (metrics|dashboards|SLOs/SLIs)
- [ ] Observability design complete (distributed tracing|health checks)
- [ ] Infrastructure integration assessed (if existing infra)
- [ ] Continuous learning capabilities designed (if applicable)
- [ ] Git branching strategy selected and CI/CD triggers aligned
- [ ] Mutation testing strategy selected and persisted to project CLAUDE.md
- [ ] Outcome KPIs instrumentation designed (if outcome-kpis.md exists)
- [ ] Data collection pipeline documented for each KPI
- [ ] Dashboard mockup or spec includes all outcome KPIs
- [ ] Handoff accepted by nw-acceptance-designer (DISTILL wave)

## Next Wave

**Handoff To**: nw-acceptance-designer (DISTILL wave)
**Deliverables**: Infrastructure design documents informing test environment setup

## Examples

### Example 1: Cloud-native greenfield
```
/nw-devops payment-gateway
```
User selects: cloud-native, Kubernetes, GitHub Actions, no existing infra, OpenTelemetry, blue-green, trunk-based development. Apex designs full infrastructure from scratch with robust CI gates on every commit to main.

### Example 2: Brownfield with existing CI/CD
```
/nw-devops auth-upgrade
```
User selects: hybrid, Docker Compose, GitLab CI (existing), existing CI/CD only, Datadog, rolling, GitFlow. Apex extends existing pipelines with branch-specific stages for develop, release, and hotfix branches.

## SSOT Update

The durable product-level SSOT is the only normative handoff DISTILL reads —
not a per-wave decision file. Update it directly:

1. **KPI contracts**: Translate `outcome-kpis.md` (from DISCUSS) into machine-readable contracts in `docs/product/kpi-contracts.yaml`. Each contract needs: `id`, `feature`, `job`, `metric`, `baseline`, `target`, `threshold_alert`, `measurement_method`, `status`. Add changelog entry. If `kpi-contracts.yaml` does not exist, create it with `schema_version: 1`.

If `docs/product/` does not exist, create it. This is SSOT bootstrap for KPI contracts.

## Expected Outputs

### SSOT updates (in `docs/product/`)
```
  kpi-contracts.yaml               (created or updated + changelog entry)
```
