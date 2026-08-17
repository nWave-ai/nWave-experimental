## nWave (beta) — How to Work in This Project

### Drive Work Through the Spine — Use the `/nw-*` Commands

Epic and feature work flows through nWave's `/nw-*` wave-based slash commands.

**Before any tool call — including read-only discovery, not just your first mutating call (Write/Edit/Agent) — establish and state your route: posture (`human` / `auto` / `direct`), size (S/M/L) with one observable reason for that size, and the path you are taking.** A self-contained S still invokes `nw-mode-select` once, is classified S, then exits direct — no wave, no re-ask, no `nw-auto`. Everything else — M, L, or undetermined size — invokes `nw-mode-select` first; an explicit mode (a generic autonomy grant counts as `auto`) still gets sized S/M/L. Undetermined shape invokes `nw-new` first, not `/nw-deliver`.

Waves, in order: `/nw-discover` `/nw-diverge` `/nw-discuss` `/nw-design` `/nw-devops` `/nw-distill` `/nw-deliver`.

**Mandatory floor**: DISTILL → DELIVER — acceptance tests, test-driven code; upstream waves optional.

**Never hand-roll delivery work** bypassing the spine. For Auto mode on M/L work, load the `nw-auto` skill directly — never `/nw-deliver` first, never in parallel with it; `nw-auto` owns the floor: `nw-acceptance-designer` compiles the immutable DeliveryContract into acceptance tests, one crafter implements, and one independent examiner verifies the real surface — the root must never substitute any of these roles itself. Human mode adds staged review to the same floor. Both routes join evidence and finalize the whole delivery exactly once; neither runs a per-slice closure cycle.

After an interruption, re-enter through `/nw-new` — it reads durable product/design authorities and routes to the earliest missing owner; it does not infer progress from a feature directory.

{{TOOL_BATCHING_FRAGMENT}}

### Privacy — Non-Negotiable

nWave runs entirely local: no telemetry ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.
