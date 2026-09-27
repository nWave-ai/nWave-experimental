## nWave (beta) — How to Work in This Project

At session start, read `~/.claude/skills/nw-typesafe-system-one/SKILL.md`
alongside these instructions. Loading alone is not use: every supported semantic question MUST use Jev when
authorized and available, with valid same-owner reuse and explicit capability
limits as defined by the skill. Confidence and predicted savings are not exemptions.
Skip this load for source-blind EXAMINE until isolated access is verified.

{{DELIVERY_ROUTE_FRAGMENT}}

nWave is a spine-driven delivery framework. Wave commands (`/nw-*`) carry the
gates; skills carry on-demand knowledge; agents execute. This section is an
INDEX — it tells you which to reach for, not how each one works internally.

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
| Resume after an interruption | `des state --repo-root "$(pwd -P)"` from the repository root (where the Request stands; `NEXT` is advisory) |
| Decide how big a Request is, and when to ask the human | skill `nw-auto` |
| Anything else — methodology, routing, "what do I do" | skill `nw-buddy` |

{{TOOL_BATCHING_FRAGMENT}}

{{QUESTION_FORMAT_FRAGMENT}}

### Communication

<!-- GENERATED:communication-rules START — source of truth: des.adapters.driven.config.des_config.DESConfig.effective_config() (ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json); do not hand-edit (docgen renders this region) -->
- Communication verbosity: **standard**
<!-- GENERATED:communication-rules END -->

### Privacy — Non-Negotiable

nWave stores workflow data locally and collects no telemetry. Explicitly authorized Jev questions use a remote service; credential presence alone is not authorization ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.
