## nWave (beta) — How to Work in This Project

nWave is a spine-driven delivery framework. Wave commands (`/nw-*`) carry the
gates; skills carry on-demand knowledge; agents execute. This section is an
INDEX — it tells you which to reach for, not how each one works internally.

**Before any tool call (including read-only discovery), establish and state the route:** load `nw-mode-select` for posture (`direct`/`human`/`auto`), size (S/M/L), and one observable reason. Explicit mode still gets sized S/M/L; generic autonomy is `auto`.

{{DELIVERY_ROUTE_FRAGMENT}}

For Auto M/L, load `nw-auto` directly — never `/nw-deliver` first and never in parallel with it. Human authority decides only genuine scope or trade-offs.

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

**Mandatory floor**: M/L `DISTILL → DELIVER` (acceptance-test TDD). Never hand-roll delivery work: `nw-acceptance-designer`, crafter, independent examiner if `examine=true`; never substitute.

{{TOOL_BATCHING_FRAGMENT}}

{{QUESTION_FORMAT_FRAGMENT}}

### Communication

<!-- GENERATED:communication-rules START — source of truth: des.adapters.driven.config.des_config.DESConfig.effective_config() (ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json); do not hand-edit (docgen renders this region) -->
- Communication verbosity: **standard**
<!-- GENERATED:communication-rules END -->

### Privacy — Non-Negotiable

nWave runs entirely local: no telemetry ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.
