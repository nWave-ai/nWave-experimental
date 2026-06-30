## nWave (beta) — How to Work in This Project

### Drive Work Through the Spine — Use the `/nw-*` Commands

Epic and feature work in this project flows through nWave's wave-based methodology. Use the `/nw-*` slash commands to guide work end-to-end.

The seven waves are:
- `/nw-discover` — explore the market and problem space
- `/nw-diverge` — compare design directions and approaches
- `/nw-discuss` — gather requirements and user stories
- `/nw-design` — architecture and domain modeling
- `/nw-devops` — infrastructure and deployment
- `/nw-distill` — write acceptance tests (Given-When-Then scenarios)
- `/nw-deliver` — TDD implementation (red → green → refactor)

**Mandatory floor**: DISTILL → DELIVER. Every feature must include acceptance tests and test-driven code. The five upstream waves are optional; start where your knowledge is incomplete.

**Never hand-roll feature work** bypassing the spine. Use `/nw-deliver` in full, including its feature-end cycle. This ensures your work goes through the quality gates, TDD discipline, and peer review that define nWave.

If you need to continue work from a previous session or pick up where another developer left off, use `/nw-continue` to see the current state and next steps.

### Help Us Improve nWave — Local Feedback Log

nWave is in **active development**. Your experience shapes the official release.

After each wave, log your observations in `.nwave/beta-feedback.md` (this file is local to your project and git-ignorable). Capture:

- **Methodology friction**: Did the wave feel unclear? Did a command reject something without explaining why? Did the output mislead you? (Describe the tool's behavior, not your specific project.)
- **Time spent per wave**: How long did DISCUSS, DESIGN, DISTILL, DELIVER take? Realistic timelines help us tune defaults.
- **Token and cost consumption**: Approximate tokens and cost per wave. We're optimizing for efficiency.

Format is free-form — describe what happened and what confused you in plain language.

**Share feedback manually** via GitHub Issues on the experimental repo (use the `feedback` or `beta` label) or email. Nothing is auto-transmitted.

### Privacy — Non-Negotiable

Your feedback log must contain **ZERO project content, code, secrets, user details, or identifying information**. Document how nWave behaved ("the DESIGN gate took 47 minutes on a 600-line microservice module"), never what you built ("OAuth2 flow for the medical patient portal").

Before sharing the log, review it and remove any accidental project detail. The goal is to describe the *tool's behavior* so we can improve it for everyone — no project context needs to leave your machine.

See [PRIVACY.md](../../PRIVACY.md) for nWave's complete privacy policy. The same guarantees apply to this beta: local-only storage, no telemetry, no automatic transmission of any kind.
