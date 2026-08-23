## nWave (beta) — How to Work in This Project

nWave is a spine-driven delivery framework. Wave commands (`/nw-*`) carry the
gates; skills carry on-demand knowledge; agents execute. This section is an
INDEX — it tells you which to reach for, not how each one works internally.

**Before any tool call — including read-only discovery — state your route.**
Load skill `nw-mode-select` to pick posture (`direct` / `human` / `auto`) and
size (`S` / `M` / `L`) with one observable reason, then follow it. A generic
autonomy grant ("use your judgment") counts as `auto`.

| User wants... | Load / run |
|---|---|
| Validate a problem is real | `/nw-discover` |
| Compare solution directions | `/nw-diverge` |
| Clarify jobs, journeys, outcomes | `/nw-discuss` |
| Architecture, reuse, boundaries | `/nw-design` |
| Deployment / operational constraints | `/nw-devops` |
| Executable oracle + DeliveryContract | `/nw-distill` |
| Ship one validated contract | `/nw-deliver` |
| Fix one observed defect | `/nw-bugfix` |
| Review an artifact or diff | `/nw-review` |
| Reduce a noisy test suite | `/nw-optimize-tests` |
| Explicit mutation probe | `/nw-mutation-test` |
| Resume after an interruption | `/nw-new` (reads durable authorities, routes to the earliest missing owner) |
| Autonomous M/L delivery, no staged review | skill `nw-auto`, after `nw-mode-select` picks `auto` |
| Anything else — methodology, routing, "what do I do" | skill `nw-buddy` |

**Mandatory floor**: DISTILL → DELIVER (acceptance tests, TDD-first). Upstream
waves are human-skippable only, never self-skipped. Never hand-roll delivery
work bypassing the spine.

{{TOOL_BATCHING_FRAGMENT}}

{{QUESTION_FORMAT_FRAGMENT}}

### Communication

<!-- GENERATED:communication-rules START — source of truth: des.adapters.driven.config.des_config.DESConfig.effective_config() (ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json); do not hand-edit (docgen renders this region) -->
- Communication verbosity: **standard**
<!-- GENERATED:communication-rules END -->

### Privacy — Non-Negotiable

nWave runs entirely local: no telemetry ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.
