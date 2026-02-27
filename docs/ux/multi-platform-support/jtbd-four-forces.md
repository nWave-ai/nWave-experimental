# Four Forces Analysis: Multi-Platform nWave Support

**Date**: 2026-02-27 (updated 2026-02-27 — added Job G1: Plugin Marketplace)
**Feature**: Extending nWave beyond Claude Code to OpenCode, Codex CLI, GitHub Copilot CLI, and the Anthropic Plugin Marketplace

---

## Forces Model

For switching to happen: **Push + Pull > Anxiety + Habit**

---

## Force Analysis by Primary Job

### Job A1: Continue TDD on Alternative Platform (Marco — Current User)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Claude Code API outages disrupt sprints. Token limits hit during peak work. Anthropic pricing increases feel uncontrollable. Single-vendor dependency is career risk ("what if they sunset Claude Code?") |
| **Pull** | Generating | Work continues regardless of any vendor. OpenCode offers 75+ providers. Codex works with local models. True resilience — not dependent on one company's uptime. |
| **Anxiety** | Reducing | Will DES enforcement be as reliable on other platforms? Will agents behave differently on non-Claude models? Will I lose subtle features I depend on (custom identity, hook-based workflows)? Will my workflow regress while adapting? |
| **Habit** | Reducing | Claude Code "just works" for nWave today. All my muscle memory is Claude Code-specific. My CLAUDE.md, settings, and hooks are dialed in. Switching cost is high — I know every quirk. |

**Assessment**:
- Switch likelihood: **Low-Medium** (Marco switches only under pain — outage or price shock)
- Key blocker: Anxiety about DES enforcement quality on other platforms
- Key enabler: A real API outage during a critical sprint
- Design implication: Must offer near-parity DES enforcement or Marco will not switch. "Skills-only" is insufficient for this persona.

---

### Job B1: Enforce TDD Phases on OpenCode (Aisha — New Platform User)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Ships features without tests. Gets burned by regressions. Code reviews always flag "add tests." Knows she should do TDD but cannot maintain discipline under pressure. |
| **Pull** | Generating | A system that enforces test-first. Cannot skip RED phase. Specialized agents for unfamiliar tasks. Professional methodology without years of practice. |
| **Anxiety** | Reducing | Learning curve for nWave methodology itself. Will it work with her Ollama/local models? Will it slow her down initially? What if enforcement is annoying rather than helpful? |
| **Habit** | Reducing | Currently codes first, tests maybe. "It works on my machine" is the current standard. Free-form coding feels productive even when it produces bugs later. |

**Assessment**:
- Switch likelihood: **Medium** (Aisha wants discipline but fears friction)
- Key blocker: Habit of code-first workflow — enforcement must feel like guardrails, not handcuffs
- Key enabler: A painful production bug that tests would have caught
- Design implication: DES enforcement is the core value for this persona. Without it, nWave on OpenCode is just "more agents" — not compelling enough to change behavior.

---

### Job C1: Consistent Methodology Across Team (Tomoko — Team Lead)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | PR quality varies wildly by developer and tool. No shared methodology — every developer has their own AI workflow. Code review is the only quality gate, and it is reactive. |
| **Pull** | Generating | Every PR follows the same TDD phases regardless of tool. Shared skill library amplifies team knowledge. New hires onboard to one methodology, not N tool-specific workflows. |
| **Anxiety** | Reducing | Will the methodology be consistent enough across platforms to actually standardize? Maintenance burden of 4 platform adapters. What if one platform falls behind? Who owns cross-platform compatibility? |
| **Habit** | Reducing | Current approach: hire good people, trust them. Mandating a methodology feels micromanagey. Each developer's "personal setup" is their identity. |

**Assessment**:
- Switch likelihood: **Medium-High** (Tomoko has organizational authority and motivation)
- Key blocker: Anxiety about maintenance burden and platform parity
- Key enabler: Skills-only portability (immediate value, low risk) builds trust toward full adoption
- Design implication: Skills and agents are sufficient for Phase 1 adoption. DES consistency across platforms is Phase 2. Incremental value delivery is critical.

---

### Job C2: Share Skills Across Platforms (Tomoko — Team Lead)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Good practices discovered by one developer stay locked in their tool. Repeated work across team members. No knowledge compounding. |
| **Pull** | Generating | Write a skill once, every team member gets it regardless of tool. Domain-specific patterns (e.g., "how we test our payment module") become institutional knowledge. |
| **Anxiety** | Reducing | Will skill format differences across platforms cause subtle behavior changes? Who maintains cross-platform skill compatibility? |
| **Habit** | Reducing | Currently share knowledge via docs and Slack — informal, lossy, not embedded in workflow. |

**Assessment**:
- Switch likelihood: **High** (lowest friction, highest immediate value)
- Key blocker: Minor — skill format differences are mechanical
- Key enabler: Open agent skills standard (SKILL.md) works on 4/4 platforms today
- Design implication: This is the "wedge" feature. Ship cross-platform skill portability first.

---

### Job D1: Prove Multi-Vendor Support (Henrik — Enterprise Architect)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Architecture review boards reject single-vendor tools. Procurement requires vendor diversity strategy. Anthropic is a startup — "what if they go under?" is a real board question. |
| **Pull** | Generating | "nWave runs on Claude Code AND Copilot CLI" instantly addresses vendor risk. Enterprise Copilot license already paid for. Phased migration path is procurement-friendly. |
| **Anxiety** | Reducing | Is multi-platform support production-ready or a checkbox feature? Will enforcement be equivalent? Will Anthropic support this or fight it? Enterprise support SLA questions. |
| **Habit** | Reducing | Enterprise inertia — evaluating new developer tools takes 6-12 months. Current tools (GitHub Copilot without nWave) are "good enough." Switching cost for 200 developers is enormous. |

**Assessment**:
- Switch likelihood: **Low** (enterprise evaluation cycles are long)
- Key blocker: Habit — enterprise inertia and evaluation timelines
- Key enabler: A credible "works on Copilot CLI" demo unlocks the evaluation. Does not need full parity — needs to prove the architecture supports it.
- Design implication: Even a partial port (skills + agents on Copilot) could unlock enterprise pipeline. The architecture must be demonstrably multi-platform even if full enforcement is Claude Code only.

---

### Job E1: Run nWave on Open-Source Tools (Ravi — OSS Advocate)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Philosophically opposed to proprietary developer tooling dependency. Claude Code is closed-source. Anthropic controls pricing, features, and access. |
| **Pull** | Generating | nWave methodology on OpenCode — open-source agent, open models, no vendor lock. Can inspect, modify, and contribute. Values-aligned tooling. |
| **Anxiety** | Reducing | Will open-source implementation be second-class? Will nWave prioritize Claude Code and treat OpenCode as afterthought? Community contribution model unclear. |
| **Habit** | Reducing | Currently uses unstructured AI coding on OpenCode. Works fine for personal projects. The "it works for me" comfort zone. |

**Assessment**:
- Switch likelihood: **Medium** (values-driven adoption is strong but requires confidence in first-class support)
- Key blocker: Anxiety about being a second-class platform
- Key enabler: Open-source DES MCP server that works identically across platforms
- Design implication: Platform abstraction must be genuinely equal, not "Claude Code first, others adapted." The MCP server approach (proposed in research) addresses this because MCP is platform-neutral.

---

### Job F1: TDD Enforcement at Zero Cost (Sofia — Cost-Conscious)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Cannot afford Claude Pro + API costs. Sees quality gap between her code and funded teams. Clients notice bugs that tests would catch. |
| **Pull** | Generating | Professional TDD methodology running on free local models. Same quality discipline as well-funded teams. Competitive advantage despite budget constraints. |
| **Anxiety** | Reducing | Will local models (Llama, DeepSeek) follow nWave agent instructions reliably? Will DES enforcement work with models that are less capable at following complex system prompts? |
| **Habit** | Reducing | Current workflow: code fast, ship fast, fix bugs later. Budget pressure reinforces speed over quality. |

**Assessment**:
- Switch likelihood: **Medium-High** (strong economic incentive, low switching cost)
- Key blocker: Anxiety about local model capability with structured methodology
- Key enabler: Proof that nWave skills + agents work acceptably on mid-tier models
- Design implication: Skills and agents (no DES) may deliver sufficient value for this persona. The methodology guidance alone, even without enforcement, improves outcomes.

---

### Job G1: Frictionless Plugin Install (Kenji — Claude Code Power User)

| Force | Direction | Description |
|-------|-----------|-------------|
| **Push** | Generating | Current nWave install requires CLI tool, manual configuration, reading docs. Compared to `/plugin install github@my-tools` for other tools, feels like 2020-era setup. Colleagues won't bother with a multi-step install. |
| **Pull** | Generating | One command: `/plugin install nwave@claude-plugins-official`. Auto-updates when nWave releases new agents. Enterprise teams deploy via `extraKnownMarketplaces` in managed settings. Project-scoped install means team consistency without individual setup. |
| **Anxiety** | Reducing | Will the plugin version be as complete as the custom installer? Will DES hooks work through the plugin system? Will auto-updates break my workflow? |
| **Habit** | Reducing | Almost none — Kenji already uses `/plugin` for other tools. The plugin UX is his natural discovery channel. The habit actually *helps* here. |

**Assessment**:
- Switch likelihood: **Very High** (near-zero friction, familiar UX pattern)
- Key blocker: Only whether the plugin delivers full nWave feature parity (DES hooks, MCP servers, agents, skills, commands)
- Key enabler: Presence in the official Anthropic marketplace (legitimacy signal)
- Design implication: This is the **lowest-cost, highest-conversion** distribution channel. nWave's component model (agents + skills + commands + hooks + MCP) maps 1:1 to the plugin spec. Packaging is primarily a structural task, not a feature-development task.

---

## Forces Summary Matrix

| Job | Push Strength | Pull Strength | Anxiety | Habit | Net | Switch Likelihood |
|-----|---------------|---------------|---------|-------|-----|-------------------|
| A1 (platform resilience) | Medium | High | High | High | Low | Low-Medium |
| B1 (TDD discipline) | High | High | Medium | High | Medium | Medium |
| C1 (team consistency) | High | High | Medium | Medium | High | Medium-High |
| C2 (skill sharing) | Medium | High | Low | Low | Very High | **High** |
| D1 (vendor risk) | High | Medium | High | Very High | Low | Low |
| E1 (OSS values) | High | High | Medium | Medium | High | Medium |
| F1 (zero cost TDD) | High | High | Medium | Medium | High | Medium-High |
| G1 (plugin install) | Medium | Very High | Low | None (helps) | **Very High** | **Very High** |

---

## Key Insight: Three Tiers of Value

The forces analysis reveals a natural segmentation:

**Tier 0 — Plugin Marketplace (Claude Code native)**: Job G1 has the highest net forces score of any job. Habit is *zero* (users already use `/plugin`), anxiety is low, and Pull is very high. This is the lowest-cost, highest-ROI investment because nWave's component model maps 1:1 to the plugin spec. **Ship this first.**

**Tier 1 — Skills + Agents on Other Platforms (no DES)**: Jobs C2, D2, E1, F1, F2 can be substantially served by cross-platform skill portability and agent catalog availability. These require NO DES porting. Push + Pull already exceeds Anxiety + Habit for these jobs.

**Tier 2 — Full DES Enforcement**: Jobs A1, B1, C1 specifically require deterministic phase enforcement. These are higher-value but require the hardest technical work (MCP server DES, platform-specific hook adapters). The anxiety force is strongest here because users want enforcement guarantees.

**The strategic play**: Ship Tier 0 (plugin) to maximize adoption on Claude Code's existing user base, then Tier 1 (cross-platform skills/agents) to expand TAM, then Tier 2 (DES) based on adoption signals. Tier 0 may deliver more adoption than Tier 1 at a fraction of the cost.
