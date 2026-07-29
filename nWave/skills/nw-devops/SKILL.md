---
name: nw-devops
description: "Designs CI/CD pipelines, infrastructure, observability, and deployment strategy (recomposing core). DEVOPS identity + density-aware output contract + agent dispatch + peer-review gate + output/handoff contract. Lean core that COMPOSES the narrow nw-devops-* modules; the prior-wave-reading, decision-point, and environment-inventory procedures live in those modules, not re-inlined here. Use when preparing platform readiness for a feature."
user-invocable: true
argument-hint: '[deployment-target] - Optional: --environment=[staging|production] --validation=[full|smoke]'
---

# NW-DEVOPS: Platform Readiness and Infrastructure Design (recomposing core)

**Wave**: DEVOPS (wave 4 of 6) | **Agent**: Apex (nw-platform-architect) | **Command**: `/nw-devops`

## Overview

Execute DEVOPS wave: platform readiness|CI/CD pipeline setup|observability design|infrastructure preparation. Positioned between DESIGN and DISTILL (DISCOVER > DIVERGE > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER), ensures infrastructure is ready before acceptance tests and code.

Apex translates DESIGN architecture decisions into operational infrastructure: CI/CD pipelines|logging|monitoring|alerting|observability.

This core holds the cross-cutting DEVOPS concerns — identity, the density-aware output contract, telemetry, the agent dispatch block, the peer-review gate, success criteria, and the output/handoff contract — and COMPOSES the narrow `nw-devops-*` modules. The phase procedures live in those modules, not re-inlined here.

## Composition (load by trigger)

| Module | Kind | Trigger — load when... | Covers |
|---|---|---|---|
| `nw-devops-prior-wave-reading` | PROCEDURE | BEFORE beginning DEVOPS work — consuming prior-wave artifacts | Prior Wave Consultation reading order (DISCUSS KPIs + DESIGN artifacts) + confirmation checklist, contradiction check, Document Update (back-propagation + upstream-changes.md) |
| `nw-devops-decision-points` | KNOWLEDGE | presenting or resolving the wave-entry Decisions 1-9 | Deployment target, container orchestration, CI/CD platform, existing infrastructure, observability and logging, deployment strategy, continuous learning, Git branching strategy, mutation testing strategy (incl. CLAUDE.md persistence wording) |
| `nw-devops-environment-inventory` | PROCEDURE | BEFORE completing the DEVOPS wave — the environment inventory is not yet produced | environments.yaml structure + population steps + DISTILL Mandate-4 consumption contract |

Load path: `~/.claude/skills/nw-{module}/SKILL.md`. Load the module whose trigger matches your current moment; the triggers partition the DEVOPS phase-space — every section lives in exactly one module. Do NOT re-inline a module's content into this core.

## Workflow (phase order)

At the start of execution, create these tasks using TaskCreate and follow them in order, loading each phase's module at that phase: prior-wave reading → Decisions 1-9 (decision-points module) → agent dispatch (below) → environment inventory (module) → peer-review gate + Wave Decisions Summary + Outputs (below).

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Output Tiers (per D2)

Provenance: feature `lean-wave-documentation` — D2 (schema-typed sections), D10 (one-line expansion descriptions). Tier-1 [REF] sections (always emitted) + Tier-2 EXPANSION CATALOG items (lazy, on-demand) are the two output bands. Full contract: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

### Tier-1 [REF] — always emitted

Under `## Wave: DEVOPS / [REF] <Section>` headings:

- Environment matrix — table of target environments with platform + preconditions
- CI/CD pipeline outline — stage list with trigger rules per branch
- Monitoring contracts — KPI-to-instrument mapping (one row per outcome KPI)
- Deployment strategy — chosen strategy + rollback contract (one paragraph)
- Mutation testing strategy — selected mode (per-feature/nightly-delta/pre-release/disabled)
- Observability stack — chosen tools per signal class (logs/metrics/traces)
- Branching strategy — selected model + CI trigger alignment
- Coexistence matrix — tools that must continue to work alongside deployment
- Pre-requisites — DESIGN constraints the platform must satisfy

### Tier-2 EXPANSION CATALOG — lazy, on-demand (per D10)

Rendered under `## Wave: DEVOPS / [WHY|HOW] <Section>` only when requested via `--expand <id>` (DDD-2), the wave-end menu (`expansion_prompt = "ask"`), `mode = "full"` auto-expansion, or an ad-hoc user request mid-session.

| Expansion ID | Tier label | One-line description |
|---|---|---|
| `infra-cost-analysis` | [WHY] | Per-environment monthly cost estimate with vendor pricing assumptions |
| `alternative-deploy-targets` | [WHY] | Cloud/on-prem/hybrid options weighed and rejected with one-paragraph reason |
| `observability-deep-dive` | [HOW] | Detailed metric/log/trace schemas, alert thresholds, dashboard layouts |
| `runbook-drafts` | [HOW] | Incident response runbooks for the top failure modes |
| `kpi-instrumentation-recipes` | [HOW] | Per-KPI data collection recipe (event names, log fields, metric labels) |
| `ci-pipeline-yaml` | [HOW] | Full CI/CD pipeline YAML with comments per stage |
| `disaster-recovery-plan` | [HOW] | Backup, restore, and DR procedures with RPO/RTO targets |
| `expansion-catalog-rationale` | [WHY] | Why this set of expansions, why these defaults, why D10 enforces one-line descriptions |

## Density resolution (per D12)

Call `resolve_density(global_config)` from `scripts/shared/density_config.py` after reading `~/.nwave/global-config.json` (missing/malformed = empty dict). Returns `mode` (`"lean"` | `"full"`) + `expansion_prompt` (`"ask"` | `"always-skip"` | `"always-expand"` | `"smart"`) per the D12 cascade (resolver-internal, DDD-5 — do NOT replicate locally). Branch on `density.mode` for what to emit; branch on `density.expansion_prompt` at wave end for menu behaviour. Full cascade detail, branch semantics, ad-hoc override workflow: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Telemetry (per D4 + DDD-6)

Every expansion choice emits a `DocumentationDensityEvent` (dataclass at `src/des/domain/telemetry/documentation_density_event.py`) via `event.to_audit_event()` → `JsonlAuditLogWriter().log_event(...)`. Schema fields per D4: `feature_id`, `wave`, `expansion_id`, `choice`, `timestamp`. For this wave the schema declares `"wave": "DEVOPS"`. Use helper `scripts/shared/telemetry.py:write_density_event(...)` — do NOT write JSONL directly. **NOT YET WIRED**: `scripts/shared/telemetry.py` does not exist yet and `DocumentationDensityEvent(` has zero constructor call sites in `src/des` — until this lands, skip the emission (the [WHY]/[HOW] section append is unaffected); do not hand-roll a substitute JSONL write.

Wave-specific signal: DISTILL consuming a lean DEVOPS environment matrix — downstream `--expand` requests for runbook drafts or alternative deploy targets indicate the `[REF]` baseline was insufficient. Full emission rules: `nWave/skills/nw-density-resolution-contract/SKILL.md`.

## Agent Invocation

<!-- DES-WAVE: devops -->
<!-- gates-ref: devops -->
<!-- outputs-ref: devops -->

The DEVOPS gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/devops.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
The registry's gate-out runs the DEVOPS review-verdict veto (a DEVOPS return is
mechanically gated by an artefact-current platform-architect-reviewer verdict) and
its output contract lists the nine mandatory `[REF]` sections plus the
feature-delta file. This skill narrates DEVOPS intent (platform readiness whose
environment inventory DISTILL consumes) but does NOT enumerate the registry gate
stack inline; consult the registry for the authoritative gate stack + output
contract.

Include the `<!-- DES-WAVE: devops -->` marker line above verbatim in the Agent dispatch prompt — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

1. **Dispatch** — Invoke `@nw-platform-architect` with the feature-id and configuration below. Gate: agent accepts invocation.
2. **Provide context** — Pass all prior wave consultation files (see `nw-devops-prior-wave-reading`). Gate: context files attached.
3. **Pass configuration** — Include all Decision 1-9 selections (resolved via `nw-devops-decision-points`) in the invocation:
   - deployment_target: {Decision 1} | container_orchestration: {Decision 2}
   - cicd_platform: {Decision 3} | existing_infrastructure: {Decision 4}
   - observability_and_logging: {Decision 5} | deployment_strategy: {Decision 6}
   - continuous_learning: {Decision 7} | git_branching_strategy: {Decision 8}
   - mutation_testing_strategy: {Decision 9}
4. **KPI-driven observability** — If `outcome-kpis.md` exists in the feature's discuss directory, Apex MUST read it and design instrumentation to collect the defined KPIs. Each KPI's "Measured By" and "Measurement Plan" sections drive: data collection infrastructure (events, logs, analytics), dashboard design (which metrics to visualize), alerting rules (guardrail metric thresholds). Gate: all KPIs have corresponding instrumentation design.

## Peer Review Gate (OPTIONAL — per-wave; mandatory at end of DISTILL)

Per-wave Forge review is opt-in. Default: skip and proceed to DISTILL. The mandatory consolidated review covering DISCUSS+DESIGN+DEVOPS+DISTILL fires at end of DISTILL where Eclipse + Architect + Forge + Sentinel run in parallel against the full `feature-delta.md` (all 4 waves visible — catches cross-wave inconsistencies that per-wave review misses).

**Structural-correctness reviewer never skips**: `rigor.reviewer_model: "skip"` applies to scale-sensitive cost-driven reviewers (Eclipse / Architect / Forge) only; the structural-correctness reviewer at the end of DISTILL (Sentinel / `@nw-acceptance-designer-reviewer`) ALWAYS dispatches — silent skip masks the bug class issue #52 fixed.

Invoke per-wave Forge review explicitly via `/nw-review nw-platform-architect-reviewer` only if:
- Novel deployment target not in prior coexistence matrix
- New CI/CD framework introduced (e.g., switching from GitHub Actions to GitLab)
- Observability stack rewrite (not extension)
- Security posture change (new secrets management, new RBAC layer)
- Maintainer explicitly flags uncertainty

When triggered, the reviewer covers: CI/CD pipeline correctness and completeness, environment inventory coverage, observability design alignment with outcome KPIs, infrastructure security and deployment strategy soundness. On REJECTION: revise artifacts per findings and re-submit (max 2 revision cycles before escalation). Gate: optional unless triggered.

## Success Criteria

- [ ] Environment inventory produced (`environments.yaml` with target environments and coexistence matrix)
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
- [ ] Per-wave peer review (OPTIONAL — invoked only on trigger; mandatory consolidated review fires at end of DISTILL)
- [ ] Handoff accepted by nw-acceptance-designer (DISTILL wave)

## Next Wave

**Handoff To**: nw-acceptance-designer (DISTILL wave)
**Deliverables**: Infrastructure design documents + `environments.yaml` (mandatory for DISTILL Mandate 4)

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

## Wave Decisions Summary

Before completing DEVOPS, produce `docs/feature/{feature-id}/devops/wave-decisions.md`:

```markdown
# DEVOPS Decisions — {feature-id}

## Key Decisions
- [D1] {decision}: {rationale} (see: {source-file})

## Infrastructure Summary
- Deployment: {target + strategy}
- CI/CD: {platform + branching strategy}
- Observability: {stack}
- Mutation testing: {strategy}

## Constraints Established
- {infrastructure constraint}

## Upstream Changes
- {any DESIGN assumptions changed, with rationale}
```

## Outputs

**Single narrative file**: `docs/feature/{feature-id}/feature-delta.md` — environment matrix, CI/CD outline, monitoring contracts, deployment strategy, mutation strategy, observability stack, branching strategy, coexistence matrix all become `## Wave: DEVOPS / [REF|WHY|HOW] <Section>` headings.

**Machine artifacts** (declared, parseable by downstream):
- `docs/feature/{feature-id}/devops/environments.yaml` — target environments + coexistence matrix + platform coverage + deployment assumptions. DISTILL parses this to parametrize acceptance scenarios over environments (Mandate 4 / Environmental Realism).

**SSOT updates** (per Recommendation 3 / back-propagation contract):
- `docs/product/kpi-contracts.yaml` — instrumentation deltas: per-KPI data collection (event names, log fields, metric labels), dashboard mapping, alerting thresholds. Created if absent; extended otherwise.
- `docs/product/architecture/brief.md` — append/update deployment topology subsection if the chosen platform changes the system-context diagram (e.g. new managed services, new region).

Legacy multi-file outputs (`platform-architecture.md`, `ci-cd-pipeline.md`, `observability-design.md`, `monitoring-alerting.md`, `infrastructure-integration.md`, `branching-strategy.md`, `continuous-learning.md`, `kpi-instrumentation.md`, `wave-decisions.md` as separate files) are NOT produced — that content lives in `feature-delta.md`. Only `environments.yaml` survives as a separate machine artifact because it has a parseable downstream consumer. Validator: `scripts/validation/validate_feature_layout.py`.
