# Wave Directory Structure

How nWave organizes artifacts across the six-wave pipeline.

## The Rule

Every wave writes its output under a single, predictable path:

```
docs/feature/{feature-id}/{wave}/
```

Where `{feature-id}` is a kebab-case identifier derived from the feature description (see [Feature ID Derivation](#feature-id-derivation) below).

## Directory Layout

```
docs/feature/{feature-id}/
├── discover/                 # DISCOVER wave — evidence & validation
│   ├── problem-validation.md
│   ├── opportunity-tree.md
│   ├── solution-testing.md
│   ├── lean-canvas.md
│   └── interview-log.md
│
├── discuss/                  # DISCUSS wave — JTBD, journeys, requirements
│   ├── jtbd-job-stories.md
│   ├── jtbd-four-forces.md
│   ├── jtbd-opportunity-scores.md
│   ├── journey-{name}-visual.md
│   ├── journey-{name}.yaml
│   ├── journey-{name}.feature
│   ├── shared-artifacts-registry.md
│   ├── requirements.md
│   ├── user-stories.md
│   ├── acceptance-criteria.md
│   └── dor-checklist.md
│
├── design/                   # DESIGN wave — architecture & ADRs
│   ├── architecture-design.md
│   ├── technology-stack.md
│   ├── component-boundaries.md
│   └── data-models.md
│
├── devops/                   # DEVOPS wave — infrastructure & CI/CD
│   ├── platform-architecture.md
│   ├── ci-cd-pipeline.md
│   ├── observability-design.md
│   ├── monitoring-alerting.md
│   ├── branching-strategy.md
│   └── continuous-learning.md
│
├── distill/                  # DISTILL wave — acceptance tests
│   ├── test-scenarios.md
│   ├── walking-skeleton.md
│   └── acceptance-review.md
│
└── deliver/                  # DELIVER wave — TDD execution
    ├── roadmap.json
    ├── execution-log.json
    ├── .develop-progress.json
    └── mutation/
        └── mutation-report.md
```

## Cross-Feature Directories

Two artifact types live outside the per-feature tree:

| Directory | Content | Why |
|-----------|---------|-----|
| `docs/adrs/` | Architecture Decision Records | Cross-feature — one ADR can affect multiple features |
| `docs/evolution/` | Post-completion archives | Centralized history — created by `/nw:finalize` after DELIVER completes |

## Feature ID Derivation

When you run `/nw:new`, `/nw:deliver`, or any wave command, nWave derives a feature ID from your description:

1. Strip common prefixes: "implement", "add", "create", "build"
2. Remove English stop words: "a", "the", "to", "for", "with", "and", "in", "on", "of"
3. Convert to kebab-case (lowercase, hyphens)
4. Limit to 5 segments maximum

**Examples:**
- "Add rate limiting to the API gateway" → `rate-limiting-api-gateway`
- "OAuth2 upgrade" → `oauth2-upgrade`
- "Implement real-time notifications with WebSocket" → `real-time-notifications-websocket`

## Wave Detection

`/nw:continue` uses these rules to detect progress:

| Wave | Complete When |
|------|--------------|
| DISCOVER | `discover/problem-validation.md` AND `discover/lean-canvas.md` exist |
| DISCUSS | `discuss/requirements.md` AND `discuss/user-stories.md` exist |
| DESIGN | `design/architecture-design.md` exists |
| DEVOPS | `devops/platform-architecture.md` exists |
| DISTILL | `distill/test-scenarios.md` exists |
| DELIVER | `deliver/execution-log.json` with all steps at COMMIT/PASS |

## Handoff Chain

Each wave reads from the previous wave's directory:

```
DISCOVER → DISCUSS reads discover/
DISCUSS  → DESIGN reads discuss/
DESIGN   → DEVOPS reads design/
DEVOPS   → DISTILL reads devops/ + design/
DISTILL  → DELIVER reads distill/ + design/
DELIVER  → reads deliver/ (roadmap + execution log)
```

After DELIVER completes, `/nw:finalize` archives a summary to `docs/evolution/`.
