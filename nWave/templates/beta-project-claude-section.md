## nWave (beta) — How to Work in This Project

nWave is a spine-driven delivery framework. Wave commands (`/nw-*`) carry the
gates; skills carry on-demand knowledge; agents execute. This section is an
INDEX — it tells you which to reach for, not how each one works internally.

{{DELIVERY_ROUTE_FRAGMENT}}

Human authority decides only genuine scope or trade-offs.

| User wants... | Load / run |
|---|---|
| Validate a problem is real | `/nw-discover` |
| Compare solution directions | `/nw-diverge` |
| Clarify jobs, journeys, outcomes | `/nw-discuss` |
| Architecture, reuse, boundaries | `/nw-design` |
| Deployment / operational constraints | `/nw-devops` |
| Executable public oracle | `/nw-distill` |
| Dispatch one Request | `/nw-deliver` |
| Fix one observed defect | `/nw-bugfix` |
| Review an artifact or diff | `/nw-review` |
| Reduce a noisy test suite | `/nw-optimize-tests` |
| Explicit mutation probe | `/nw-mutation-test` |
| Resume after an interruption | `/nw-new` (reads durable authorities, routes to the earliest missing owner) |
| Decide how big a Request is, and when to ask the human | skill `nw-auto` |
| Anything else — methodology, routing, "what do I do" | skill `nw-buddy` |

**Mandatory floor**: every Request goes to the runner. The Product Owner decomposes it into ordered values, the runner prepares and crafts the values that consume identical design facts as one group against one shared executable oracle, and one independent reviewer reads the whole candidate diff. Never hand-roll that work, and never substitute a role.

{{TOOL_BATCHING_FRAGMENT}}

{{QUESTION_FORMAT_FRAGMENT}}

### Communication

<!-- GENERATED:communication-rules START — source of truth: des.adapters.driven.config.des_config.DESConfig.effective_config() (ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json); do not hand-edit (docgen renders this region) -->
- Communication verbosity: **standard**
<!-- GENERATED:communication-rules END -->

### Privacy — Non-Negotiable

nWave runs entirely local: no telemetry ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.
