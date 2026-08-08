## nWave (beta) — How to Work in This Project

### Drive Work Through the Spine — Use the `/nw-*` Commands

Epic and feature work in this project flows through nWave's wave-based methodology. Use the `/nw-*` slash commands to guide work end-to-end.

**Before any tool call — including read-only discovery, not just your first mutating call (Write/Edit/Agent) — establish and state your route: posture (`human` / `auto` / `direct`), size (S/M/L), one observable reason for that size, and the path you are taking.** Route first, then explore: once the route is stated, use bounded, read-only discovery to fill gaps in your own understanding. An unambiguous, self-contained S may state `direct + S + reason` and proceed straight to the fix, without invoking `nw-mode-select` or a wave. Everything else — M, L, or undetermined size — invokes the `nw-mode-select` skill (Skill tool) first, unless the route is already explicit in this conversation (a generic autonomous-execution authorization counts as explicit `auto`; do not ask again) — an explicit mode still gets sized S/M/L, it only skips the re-ask. For undetermined-shape new work with no prior wave artifacts, invoke `nw-new` first: it recommends the correct starting wave instead of guessing directly at `/nw-deliver`.

The seven waves are:
- `/nw-discover` — explore the market and problem space
- `/nw-diverge` — compare design directions and approaches
- `/nw-discuss` — gather requirements and user stories
- `/nw-design` — architecture and domain modeling
- `/nw-devops` — infrastructure and deployment
- `/nw-distill` — write acceptance tests (Given-When-Then scenarios)
- `/nw-deliver` — TDD implementation (red → green → refactor)

**Mandatory floor**: DISTILL → DELIVER. Every feature must include acceptance tests and test-driven code. The five upstream waves are optional; start where your knowledge is incomplete.

**Never hand-roll feature work** bypassing the spine — not even under a tight budget. For Auto mode on M/L work, load the `nw-auto` skill directly — never `/nw-deliver` first, and never in parallel with it; `nw-auto` owns the fixed floor end-to-end — `nw-acceptance-designer` authors the thin contract and acceptance tests, one paradigm-appropriate crafter implements, one independent examiner verifies — cheaper than hand-implementing and self-checking the same work, not "the full pipeline." You orchestrate this handoff; you never substitute for any of the three roles by authoring the contract, the acceptance tests, or the examiner's verdict yourself. A tight budget shrinks context and documentation; it never skips these roles. For Human mode, `/nw-deliver` carries this same floor plus staged review; its feature-end cycle runs once per feature (not once per slice, and not a second multi-agent round) to re-verify the whole tree — see `/nw-deliver` for the mechanics. Auto mode has no separate feature-end cycle: `nw-auto`'s own examiner verdict is the re-verification.

If you need to continue work from a previous session or pick up where another developer left off, use `/nw-continue` to see the current state and next steps.

### Privacy — Non-Negotiable

nWave is in **active development** and runs entirely local: no telemetry, no automatic transmission of any kind. See [PRIVACY.md](../../PRIVACY.md) for the complete policy. Feedback on nWave itself is welcome via GitHub Issues on the experimental repo, at your discretion — never a required step of doing the work.
