# JTBD Job Stories: Multi-Platform nWave Support

**Date**: 2026-02-27 (updated 2026-02-27 — added Persona G: Plugin Marketplace)
**Feature**: Extending nWave beyond Claude Code to support OpenCode, Codex CLI, GitHub Copilot CLI, and the Anthropic Plugin Marketplace
**Analysis basis**: Research reports for OpenCode, Codex CLI, and Copilot CLI (2026-02-26); Claude Code Plugin System documentation (2026-02-27)

---

## Personas and Their Jobs

### Persona A: Marco Bianchi — Current nWave User Wanting Platform Freedom

**Profile**: Senior developer, 3 years using Claude Code + nWave. Has internalized the TDD wave methodology. Pays for Claude Pro subscription. Frustrated by Anthropic API outages and pricing changes. Curious about OpenCode's model flexibility but unwilling to lose DES enforcement.

#### Job Story A1 — Platform Optionality (Functional)

> **When** Claude Code has an API outage or I hit my daily token limit during a critical sprint,
> **I want to** continue my TDD workflow on an alternative coding agent without losing phase enforcement,
> **so I can** maintain delivery velocity regardless of any single vendor's availability.

- **Functional**: Continue structured TDD work on a different platform
- **Emotional**: Feel safe knowing my methodology works everywhere — not trapped
- **Social**: Be seen as someone who delivers regardless of tooling disruptions

#### Job Story A2 — Model Cost Optimization (Functional)

> **When** I am doing routine test-writing or refactoring tasks that do not require frontier model quality,
> **I want to** use a cheaper or local model through OpenCode while keeping the same nWave workflow,
> **so I can** reduce my monthly AI costs without sacrificing methodology discipline.

- **Functional**: Run nWave on cheaper models for routine tasks
- **Emotional**: Feel smart about resource allocation, not wasteful
- **Social**: Justify AI spending to management with cost-optimized model selection

---

### Persona B: Aisha Okonkwo — Developer on Another Platform Wanting Structured TDD

**Profile**: Mid-level developer using OpenCode with Ollama (local models) at a startup. Self-taught, strong on shipping but weak on test discipline. Has seen nWave demos and wants the methodology but will not switch to Claude Code due to cost and philosophical preference for open tools.

#### Job Story B1 — Adopt TDD Discipline (Functional)

> **When** I start a new feature and know I should write tests first but always skip them under delivery pressure,
> **I want to** have a system that enforces TDD phases so I cannot skip the RED step,
> **so I can** build reliable test coverage habits without relying on my willpower alone.

- **Functional**: Enforce TDD phase ordering during development
- **Emotional**: Feel relieved that the system catches my bad habits before they cause bugs
- **Social**: Produce code that passes team code reviews without "add tests" comments

#### Job Story B2 — Access Specialized Agents (Functional)

> **When** I need to design an architecture or write acceptance tests but I am not an expert in those areas,
> **I want to** invoke specialized agents (solution-architect, acceptance-designer) from my preferred tool,
> **so I can** get expert-level guidance without switching platforms or learning a new tool.

- **Functional**: Use nWave's agent catalog from OpenCode/Copilot
- **Emotional**: Feel empowered — like having senior colleagues available on demand
- **Social**: Deliver architecture-quality work that earns trust from leads

---

### Persona C: Tomoko Hayashi — Team Lead Wanting Consistent Methodology

**Profile**: Engineering manager at a 40-person company. Half the team uses Claude Code, a quarter uses Copilot CLI (enterprise license), the rest use OpenCode or Codex. Wants consistent code quality standards across the team regardless of individual tool choice.

#### Job Story C1 — Team Methodology Consistency (Functional)

> **When** I review PRs from different team members using different coding agents,
> **I want to** see the same TDD discipline, commit conventions, and acceptance criteria regardless of which tool they used,
> **so I can** enforce consistent quality standards without mandating a single tool.

- **Functional**: Ensure uniform methodology across heterogeneous tooling
- **Emotional**: Feel confident that quality is embedded in process, not dependent on individual discipline
- **Social**: Be recognized as a lead who achieves consistency without being authoritarian about tool choices

#### Job Story C2 — Skill Knowledge Sharing (Functional)

> **When** one team member creates a valuable skill file (e.g., domain-specific testing patterns),
> **I want to** share that skill across all team members regardless of their coding agent,
> **so I can** amplify team knowledge without maintaining separate skill libraries per platform.

- **Functional**: Distribute skill files across Claude Code, OpenCode, Copilot CLI, and Codex
- **Emotional**: Feel efficient — write once, use everywhere
- **Social**: Build a team knowledge base that compounds over time

---

### Persona D: Henrik Lindgren — Enterprise Architect Evaluating nWave

**Profile**: Principal architect at a Fortune 500 financial services company. Evaluating AI-assisted development tools for a 200-developer organization. Interested in nWave's structured approach but cannot propose a tool that locks the company into a single vendor (Claude/Anthropic). Procurement requires multi-vendor strategy.

#### Job Story D1 — Vendor Lock-in Avoidance (Functional)

> **When** I present a tool recommendation to the architecture review board,
> **I want to** demonstrate that nWave works across at least two major AI platforms,
> **so I can** get approval without the board flagging single-vendor dependency risk.

- **Functional**: Prove multi-platform support exists before procurement
- **Emotional**: Feel confident defending the recommendation against "what if Anthropic pivots?" questions
- **Social**: Be seen as a careful architect who anticipates vendor risk — not a fan of one tool

#### Job Story D2 — Phased Enterprise Rollout (Functional)

> **When** rolling out nWave to 200 developers who already use a mix of Copilot (enterprise license) and internal tools,
> **I want to** start with skills and agents on existing platforms before requiring a platform switch,
> **so I can** demonstrate value incrementally without a disruptive all-at-once migration.

- **Functional**: Deploy nWave capabilities incrementally on platforms teams already use
- **Emotional**: Feel in control of the rollout — manageable risk, measurable progress
- **Social**: Show leadership that adoption is growing organically, not forced

---

### Persona E: Ravi Sharma — Open-Source Advocate

**Profile**: Staff engineer at an infrastructure company. Philosophically committed to open-source tooling. Uses OpenCode daily. Sees nWave's value but will not adopt a tool that requires proprietary Claude Code. Contributes to OSS projects and evangelizes open standards.

#### Job Story E1 — Use nWave Without Proprietary Dependencies (Functional)

> **When** I find a development methodology that improves my code quality significantly,
> **I want to** adopt it on an open-source platform without any proprietary tool dependency,
> **so I can** maintain my principles and recommend it to the OSS community without compromise.

- **Functional**: Run nWave methodology on open-source tooling (OpenCode)
- **Emotional**: Feel aligned — my tools match my values
- **Social**: Recommend nWave to OSS community without "but you need Claude Code" asterisk

#### Job Story E2 — Contribute Platform Adapters (Functional)

> **When** nWave has a platform abstraction layer that I can extend,
> **I want to** contribute adapters for platforms I care about,
> **so I can** help nWave grow while ensuring my preferred platform stays first-class.

- **Functional**: Contribute to nWave's multi-platform support
- **Emotional**: Feel ownership and investment in the tool I use daily
- **Social**: Be known as a contributor to a respected development methodology framework

---

### Persona F: Sofia Petrova — Cost-Conscious Independent Developer

**Profile**: Freelance developer building MVPs for startups. Cannot afford Claude Pro ($20/month) plus Anthropic API costs for heavy coding sessions. Runs Ollama locally with DeepSeek or Llama models via OpenCode. Wants structured methodology but at zero marginal cost.

#### Job Story F1 — Zero-Cost TDD Enforcement (Functional)

> **When** I am building an MVP on a tight budget and every dollar of API cost matters,
> **I want to** run nWave's TDD enforcement against local models via OpenCode or Codex with --oss,
> **so I can** maintain code quality discipline without any per-token charges.

- **Functional**: Run nWave with local/free models
- **Emotional**: Feel resourceful — getting premium methodology at zero marginal cost
- **Social**: Ship quality code that does not reveal budget constraints to clients

#### Job Story F2 — Selective Model Escalation (Functional)

> **When** a complex architecture decision requires frontier model quality but routine coding does not,
> **I want to** use nWave on a cheap model for daily work and escalate to Claude/GPT only for design waves,
> **so I can** optimize my AI spending by matching model cost to task complexity.

- **Functional**: Mix models across wave phases based on complexity
- **Emotional**: Feel strategically smart about AI spend
- **Social**: Compete with well-funded teams despite budget asymmetry

---

## Job Summary Table

| # | Persona | Job Story | Dimension | Core Need |
|---|---------|-----------|-----------|-----------|
| A1 | Marco (current user) | Continue TDD on alt platform during outage | Functional + Emotional | Platform resilience |
| A2 | Marco (current user) | Use cheaper models for routine tasks | Functional | Cost optimization |
| B1 | Aisha (new platform user) | Enforce TDD phases on OpenCode | Functional + Emotional | Discipline enforcement |
| B2 | Aisha (new platform user) | Access specialized agents from preferred tool | Functional + Social | Expert guidance |
| C1 | Tomoko (team lead) | Consistent methodology across tools | Functional + Social | Team consistency |
| C2 | Tomoko (team lead) | Share skills across platforms | Functional | Knowledge portability |
| D1 | Henrik (enterprise) | Prove multi-vendor support | Functional + Social | Vendor risk mitigation |
| D2 | Henrik (enterprise) | Incremental rollout on existing platforms | Functional + Emotional | Controlled adoption |
| E1 | Ravi (OSS advocate) | Run nWave on open-source tools | Functional + Emotional | Values alignment |
| E2 | Ravi (OSS advocate) | Contribute platform adapters | Functional + Social | Community ownership |
| F1 | Sofia (cost-conscious) | TDD enforcement at zero cost | Functional + Emotional | Budget discipline |
| F2 | Sofia (cost-conscious) | Mix models by task complexity | Functional | Cost/quality optimization |
| G1 | Kenji (plugin user) | One-click install via marketplace | Functional + Emotional | Frictionless adoption |
| G2 | Kenji (plugin user) | Automatic updates via plugin system | Functional | Version management |
| G3 | Kenji (plugin user) | Enterprise distribution via managed plugins | Functional + Social | Org-wide deployment |

---

### Persona G: Kenji Takahashi — Claude Code Power User Wanting One-Click Install

**Profile**: Full-stack developer, daily Claude Code user. Discovers tools through the `/plugin` marketplace. Currently hand-curates CLAUDE.md instructions, agents, and MCP servers. Would adopt a structured methodology but won't spend 30 minutes configuring files manually. Expects plugin-quality installation UX.

#### Job Story G1 — Frictionless Methodology Adoption (Functional)

> **When** I discover nWave in the Claude Code plugin marketplace and want to try structured TDD,
> **I want to** install it with a single `/plugin install nwave` command,
> **so I can** start using the methodology immediately without manual file setup, PATH configuration, or reading installation docs.

- **Functional**: Install nWave as a Claude Code plugin with zero manual configuration
- **Emotional**: Feel that nWave is "official" and production-ready — not a hacky side project
- **Social**: Recommend it to colleagues with "just install the plugin" — no asterisks

#### Job Story G2 — Automatic Updates and Version Management (Functional)

> **When** nWave releases new agents, skills, or DES improvements,
> **I want to** receive automatic updates through the plugin system,
> **so I can** always have the latest methodology without manual reinstallation.

- **Functional**: Plugin auto-update delivers new agents, skills, and commands seamlessly
- **Emotional**: Feel confident I'm on the latest version without checking manually
- **Social**: Team can standardize on a plugin version via project-scoped settings

#### Job Story G3 — Enterprise Distribution via Managed Plugin (Functional)

> **When** my organization adopts nWave for 50+ developers,
> **I want to** distribute it as a managed plugin through `extraKnownMarketplaces` in enterprise settings,
> **so I can** ensure all developers use the same methodology version without individual installation steps.

- **Functional**: Org-wide deployment through Claude Code's managed plugin system
- **Emotional**: Feel in control of methodology rollout — no "works on my machine" variance
- **Social**: Present to leadership as enterprise-grade tooling with proper distribution

---

## Cross-Cutting Observations

1. **The plugin marketplace is the highest-ROI channel**: Persona G reveals that nWave's current custom installer (`nwave-ai` CLI) creates unnecessary friction. The Claude Code plugin system natively supports agents, skills, commands, hooks, and MCP servers — exactly nWave's component model. Packaging nWave as a plugin eliminates the installation barrier AND provides auto-updates, version management, and enterprise distribution for free.

2. **Skills are the universal bridge**: Every persona benefits from cross-platform skill portability. Skills are the ONE nWave feature that is immediately compatible across all 4+ platforms with minimal adaptation (path changes only).

3. **DES is the value differentiator but the hardest to port**: Personas B1, C1, and D1 specifically want enforcement (not just guidance). Without DES, multi-platform nWave delivers "agent catalog + skills" but not the deterministic methodology that distinguishes nWave from ad-hoc AI coding.

4. **Enterprise personas (D, G3) converge on managed plugins**: Henrik needs multi-vendor proof, Kenji needs managed distribution. The Claude Code plugin system's `extraKnownMarketplaces` + `enabledPlugins` in `.claude/settings.json` addresses both — enterprise teams get org-wide nWave deployment with version pinning.

5. **The "habit of present" is different per persona**: Marco must give up Claude Code reliability; Aisha must adopt discipline she currently lacks; Tomoko must accept imperfect consistency; Henrik must accept phased rollout; Ravi must accept that full DES may require proprietary hooks; Kenji has nearly zero habit barrier — just clicks install.

6. **Plugin marketplace changes the adoption funnel**: Today's funnel: hear about nWave → find GitHub repo → read docs → run installer → configure. Plugin funnel: browse `/plugin` → read description → click install. This collapses 5 steps into 2 and dramatically increases the top-of-funnel conversion.
