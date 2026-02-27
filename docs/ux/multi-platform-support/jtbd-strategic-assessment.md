# Strategic Assessment: Is Multi-Platform nWave Worth the Investment?

**Date**: 2026-02-27 (updated 2026-02-27 — added Plugin Marketplace as Phase 0.5)
**Decision**: Should nWave invest in multi-platform support beyond Claude Code?
**Recommendation**: **Yes, but phased and selective** — plugin marketplace first, then cross-platform, not all features at once.

---

## The Core Question

Is the development and maintenance cost of multi-platform nWave justified by the value it delivers?

**Short answer**: The Claude Code plugin marketplace is the highest-ROI investment — it maps 1:1 to nWave's component model and dramatically reduces adoption friction. Cross-platform skills and agents justify moderate additional investment. Full DES portability does not justify investment today but the architecture should be prepared for it.

---

## Cost Analysis

### Development Cost Estimate

| Component | Effort | Complexity | Platforms |
|-----------|--------|------------|-----------|
| **Claude Code Plugin packaging** | 2-3 weeks | Low-Medium | Claude Code (official marketplace) |
| **Cross-platform skill installer** | 1-2 weeks | Low | All 4 (SKILL.md standard) |
| **Agent format adapters** | 2-3 weeks | Medium | OpenCode + Copilot CLI (not Codex) |
| **AGENTS.md / instruction file adapters** | 1 week | Low | All 4 (file renaming + path management) |
| **Platform-specific installer plugins** | 2-3 weeks | Medium | 3 new plugins (opencode, copilot, codex) |
| **DES as MCP server** | 6-10 weeks | High | Universal (MCP supported by all 4) |
| **Platform-specific DES hook adapters** | 3-5 weeks per platform | High | OpenCode (TypeScript), Copilot (JSON hooks), Codex (blocked) |
| **Cross-platform integration testing** | 3-4 weeks | High | All supported platforms |
| **Documentation and migration guides** | 1-2 weeks | Low | Per platform |

**Total estimated effort**:
- **Phase 0.5 (Plugin Marketplace)**: 2-3 weeks
- **Phase 1 (Skills + Agents + Instructions)**: 6-9 weeks
- **Phase 2 (DES MCP Server)**: 6-10 weeks
- **Phase 3 (Platform-specific DES adapters)**: 6-10 weeks per platform
- **Full implementation**: 20-32 weeks (5-8 months for one developer)

### Maintenance Cost (Ongoing)

| Concern | Risk Level | Mitigation |
|---------|------------|------------|
| Platform API changes | High — all 3 new platforms are rapidly evolving (OpenCode, Copilot CLI GA Feb 2026, Codex active dev) | Pin to stable APIs only; avoid experimental features |
| Hook system bugs | High — OpenCode Issue #5894 (subagent bypass), Copilot cwd-scoped hooks, Codex no hooks | Platform abstraction layer isolates breakage |
| Format drift | Low — SKILL.md is an open standard; agent formats are converging | Test matrix per release |
| Installer complexity | Medium — 4 platform plugins vs 1 today | Shared base class, platform-specific overrides |

**Estimated ongoing maintenance**: 15-20% of one developer's time (~1 day/week) to keep 3 additional platforms working. This is not negligible.

---

## Value Analysis

### Market Expansion

| Dimension | Current (custom installer) | With Plugin Marketplace | With Multi-Platform |
|-----------|---------------------------|------------------------|---------------------|
| Addressable users | Claude Code users who find GitHub repo | **All Claude Code `/plugin` browsers** | All AI coding agent users (~5-10M) |
| Discovery channel | GitHub → docs → install | **Browse `/plugin` → 1 click** | Per-platform installer |
| Enterprise evaluability | Blocked by vendor lock-in concern | **Unblocked for Claude Code orgs** | Fully unblocked — multi-vendor |
| Installation friction | CLI tool, manual config (~30 min) | **Single command (~1 min)** | Per-platform adapter install |
| Auto-updates | Manual reinstall | **Automatic via plugin system** | Per-platform update mechanism |
| Team distribution | Individual install per developer | **`extraKnownMarketplaces` + managed scope** | Per-platform + managed plugins |
| Pricing sensitivity | Only Claude Pro/API users | Only Claude Pro/API users | Includes free/local model users |
| OSS community | Excluded (proprietary dependency) | Excluded | Included (OpenCode pathway) |

**TAM expansion estimate**: Plugin marketplace alone addresses the existing Claude Code user base (~500K-1M) with dramatically improved conversion. Multi-platform adds ~5-10x on top. However, addressable does not mean convertible — nWave's adoption depends on users wanting structured methodology.

**Key insight**: The plugin marketplace and multi-platform support address *different conversion bottlenecks*. The plugin reduces installation friction (top-of-funnel). Multi-platform expands the addressable market (TAM). Both are needed, but the plugin ROI is immediate.

### Competitive Positioning

| Without Multi-Platform | With Multi-Platform |
|------------------------|---------------------|
| "nWave is a Claude Code workflow" | "nWave is a development methodology that runs anywhere" |
| Competes with Claude Code-specific tools | Competes as a methodology framework (unique positioning) |
| Vulnerable to Claude Code changes | Resilient — value is in methodology, not platform |
| Cannot be recommended by platform-agnostic voices | Can be recommended by anyone |

The positioning shift from "Claude Code plugin" to "methodology framework" is strategically significant. It changes the competitive landscape and makes nWave defensible against platform-level competition.

### Revenue / Adoption Impact

| Scenario | Likelihood | Impact |
|----------|------------|--------|
| Enterprise adoption unlocked | Medium (needs demo-quality port) | High (enterprise = revenue, credibility) |
| OSS community adoption | Medium-High (OpenCode is growing fast) | Medium (community = contributors, visibility) |
| Cost-conscious user segment | High (zero-cost model support) | Low-Medium (these users are least likely to pay) |
| Existing user retention | Low impact (current users are satisfied) | Medium (reduces churn risk from platform switching) |

---

## Risk Analysis

### Risk 1: Spreading Too Thin

**Probability**: High
**Impact**: High — degraded quality across all platforms including Claude Code

Each new platform adds testing surface, edge cases, and maintenance. With a small team, supporting 4 platforms risks the "master of none" outcome.

**Mitigation**: Support Claude Code (full) + ONE additional platform (near-full) + skills-only for the rest. Do not attempt 4-platform DES parity.

### Risk 2: Platform Evolution Breaks Compatibility

**Probability**: High — all 3 target platforms shipped major changes in the last 3 months
**Impact**: Medium — requires reactive maintenance

OpenCode, Copilot CLI, and Codex are all in rapid evolution. Features we depend on today may change or break tomorrow.

**Mitigation**: Depend only on stable/GA features. Avoid experimental APIs (OpenCode's ACP, Codex's multi-agent). Pin to specific hook protocol versions.

### Risk 3: DES MCP Server Is Weaker Than Native Hooks

**Probability**: High
**Impact**: Medium — enforcement model changes from "system intercepts all" to "agent must cooperate"

A DES MCP server exposes enforcement as tools the agent calls (e.g., `des_validate_phase`, `des_start_step`). This is cooperative, not coercive. A misconfigured or poorly prompted agent could skip the DES tools entirely. Native hooks (Claude Code's PreToolUse) are coercive — the agent cannot bypass them.

**Mitigation**: Accept the enforcement trade-off. MCP-based DES provides "guardrails" (soft enforcement) vs "gates" (hard enforcement). For most users, guardrails are sufficient. Reserve hard enforcement for Claude Code only.

### Risk 4: Maintenance Cost Exceeds Value

**Probability**: Medium
**Impact**: High — ongoing drag on development velocity

If multi-platform adoption is low, the maintenance cost (15-20% developer time) becomes pure overhead.

**Mitigation**: Phase 1 (skills + agents) has near-zero ongoing maintenance (static files). Only invest in Phase 2/3 (DES) if Phase 1 adoption signals justify it. Set a clear adoption threshold: proceed with Phase 2 only if 50+ active users on non-Claude platforms within 6 months of Phase 1.

---

## Platform Selection: Which One First?

Based on research compatibility scores, opportunity analysis, and plugin marketplace discovery:

| Platform | Agents | Skills | Commands | Hooks/DES | Instructions | MCP | Auto-Update | Enterprise Dist. | Overall Score | Recommendation |
|----------|--------|--------|----------|-----------|--------------|-----|-------------|-------------------|---------------|----------------|
| **Plugin Marketplace** | Full | Full | Full | Full | Full | Full | **Native** | **Native** | **1.0+** | **Immediate priority** |
| **Claude Code** (custom) | Full | Full | Full | Full | Full | Full | Manual | Manual | 1.0 | Baseline (superseded by plugin) |
| **OpenCode** | Partial | Full | Partial | Partial (bug) | Full | Full | None | None | 0.65 | Primary cross-platform target |
| **Copilot CLI** | Compatible | Full | None | Partial (cwd) | Unreliable | Full | None | None | 0.56 | Secondary target |
| **Codex CLI** | None | Full | None | None | Partial | Full | None | None | 0.35 | Skills-only |

**Recommendation: Plugin Marketplace first, OpenCode second.**

Plugin Marketplace rationale:
1. **Perfect compatibility** — nWave's component model (agents, skills, commands, hooks, MCP) maps 1:1 to plugin spec
2. **Native auto-updates** — new agents, skills, and DES improvements delivered automatically
3. **Enterprise distribution built-in** — `extraKnownMarketplaces` + `enabledPlugins` in managed settings
4. **Official marketplace legitimacy** — submission via claude.ai/settings/plugins/submit or platform.claude.com/plugins/submit
5. **Zero installation friction** — `/plugin install nwave@claude-plugins-official` replaces 30-minute manual setup
6. **Project-scoped installs** — team consistency via `.claude/settings.json` without individual setup
7. **Version pinning** — `ref` + `sha` fields enable release channels (stable/latest)

OpenCode rationale (unchanged):
1. Highest cross-platform compatibility score (0.65)
2. Open-source — aligns with community adoption strategy
3. CLAUDE.md fallback support means existing instruction files work as-is
4. TypeScript plugin system is architecturally superior to shell hooks (once subagent bug is fixed)
5. 75+ model providers — addresses cost-optimization personas (F1, F2)
6. Growing community (SST ecosystem, active development)

---

## Recommended Strategy

### Phase 0: Architecture Preparation (2 weeks)

**Do now, regardless of multi-platform decision:**
- Abstract nWave's installer to support pluggable platform targets
- Document the platform-neutral "nWave Core" (skills, agents, methodology) vs "nWave DES" (enforcement)
- Create a platform compatibility matrix as a living document

**Cost**: Low. **Risk**: None. **Benefit**: Makes any future platform work cheaper.

### Phase 0.5: Claude Code Plugin Marketplace (2-3 weeks) — NEW

**The highest-ROI investment. Do immediately after Phase 0.**

Package nWave as a Claude Code plugin for the official Anthropic marketplace:

**Plugin structure**:
```
nwave-plugin/
├── .claude-plugin/
│   └── plugin.json          # name, version, description, keywords
├── agents/                  # 23 agent .md files (YAML frontmatter)
├── skills/                  # 98+ skill directories with SKILL.md
├── commands/                # 21 slash command .md files
├── hooks/
│   └── hooks.json           # DES PreToolUse/PostToolUse/SubagentStop hooks
├── .mcp.json                # DES MCP tools (future Phase 2)
└── settings.json            # Default agent settings
```

**Deliverables**:
1. Plugin package with all nWave components (agents, skills, commands, hooks)
2. Submission to official Anthropic marketplace (claude.ai/settings/plugins/submit)
3. Own marketplace on GitHub (nwave-ai/nwave-plugin) for version control and release channels
4. Enterprise configuration example (`extraKnownMarketplaces` + `enabledPlugins`)
5. Migration guide from custom installer to plugin

**Technical considerations**:
- DES hooks: The plugin `hooks/hooks.json` can define PreToolUse, PostToolUse, SubagentStop hooks — identical to current DES hook adapter. The hook commands use `${CLAUDE_PLUGIN_ROOT}` instead of `$HOME/.claude/`.
- MCP servers: Plugin `.mcp.json` can bundle DES MCP server (future Phase 2).
- Skills reference files: Plugin skills can include supporting files alongside SKILL.md (scripts, reference docs).
- Auto-updates: Version bumps in plugin.json trigger automatic updates for users with auto-update enabled.
- Scoped installs: Users choose user/project/local scope. Project scope = team standardization.

**Value delivered**: Jobs G1 (one-click install), G2 (auto-updates), G3 (enterprise distribution), plus dramatically improved conversion for ALL existing jobs by reducing adoption friction.
**Cost**: Low. **Risk**: Low. **DES**: Included (hooks work natively in plugins).

**Why this changes everything**: The plugin marketplace doesn't just add a distribution channel — it eliminates the biggest adoption bottleneck. Every job scored in this analysis assumed the user has already installed nWave. The plugin marketplace increases the number of users who reach that point by 5-10x.

### Phase 1: Cross-Platform Skills and Agents (6-8 weeks)

**The "wedge" — prove multi-platform value with minimal risk:**
- Ship cross-platform skill installer (all 4 platforms)
- Ship agent format adapters for OpenCode and Copilot CLI
- Ship AGENTS.md generators for Codex CLI
- Ship instruction file adapters (CLAUDE.md to AGENTS.md bridge)

**Value delivered**: Jobs C2 (skill sharing), D2 (incremental rollout), E1 (OSS access), F1 (zero-cost methodology guidance)
**Cost**: Moderate. **Risk**: Low. **DES**: Not included.

### Phase 2: DES MCP Server (8-10 weeks, conditional)

**Only proceed if Phase 1 achieves 50+ active non-Claude-Code users within 6 months.**
- Build DES as an MCP server (platform-neutral enforcement)
- MCP is supported by ALL 4 target platforms
- Soft enforcement model (cooperative, not coercive)
- Test on OpenCode first (primary non-Claude target)

**Value delivered**: Jobs A1 (platform resilience), B1 (TDD discipline), C1 (team consistency)
**Cost**: High. **Risk**: Medium (enforcement model is weaker than native hooks).

### Phase 3: Native DES Adapters (conditional, per-platform)

**Only proceed if DES MCP server adoption is strong AND platform hook bugs are resolved:**
- OpenCode: TypeScript DES plugin (requires Issue #5894 fix)
- Copilot CLI: Hook adapter (requires cwd hook loading workaround)
- Codex CLI: Blocked indefinitely (no hook system exists)

**Value delivered**: Job #8 (DES parity — identical enforcement)
**Cost**: Very high (6-10 weeks per platform). **Risk**: High (platform dependency).

### Do Not Do

- Do not attempt 4-platform DES parity in 2026
- Do not port Codex CLI agents (TOML format is too different, multi-agent is experimental)
- Do not depend on experimental features (OpenCode ACP, Codex multi-agent, Copilot coding agent)
- Do not sacrifice Claude Code quality for multi-platform breadth

---

## Decision Framework

| Question | Answer | Evidence |
|----------|--------|----------|
| Is there user demand? | Yes, moderate-to-high | Enterprise vendor-lock-in concerns, OSS community interest, cost-optimization need, plugin marketplace browsing behavior |
| Is the market expanding? | Yes, significantly | AI coding agents grew from 2 to 5+ major platforms in 12 months; plugin marketplace is a new native discovery channel |
| Is the technical feasibility proven? | **Plugin: yes.** Cross-platform: partially | Plugin spec matches nWave's component model 1:1. Skills: proven. Agents: proven for 3/4 platforms. DES: unproven. |
| Is the maintenance cost manageable? | **Plugin: near-zero** (version bump). Phase 1: yes. Phase 2+: conditional | Plugin auto-updates handle distribution; skills are static files; DES adapters need active maintenance |
| Does it strengthen competitive position? | Yes, significantly | Plugin = "official Anthropic ecosystem tool." Multi-platform = "methodology framework." |
| Is the opportunity cost acceptable? | **Plugin: trivially yes** (2-3 weeks). Phase 1: yes. Full: debatable | Plugin ROI is immediate; 4.5-7 months for full implementation is significant |
| Does a native distribution channel exist? | **Yes — Claude Code plugin marketplace** | Official marketplace with 8.5K stars, submission forms at claude.ai and platform.claude.com. Supports agents, skills, commands, hooks, MCP servers — exactly nWave's components. |

---

## Final Recommendation

**Invest in Phase 0 + Phase 0.5 (Plugin) immediately. Then Phase 1. Gate Phase 2 on adoption metrics. Defer Phase 3 indefinitely.**

The plugin marketplace discovery changes the priority order. The highest-ROI action is packaging nWave as a Claude Code plugin — it addresses 3 Extremely Underserved outcomes at one-third the cost of Phase 1.

The phased approach delivers:

1. **Phase 0.5 (Plugin)**: Maximize adoption within the existing Claude Code user base. One-click install, auto-updates, enterprise distribution. **2-3 weeks, immediate value.**
2. **Phase 1 (Cross-platform)**: Expand TAM to non-Claude-Code users. Skills + agents on OpenCode, Copilot CLI, Codex. **6-8 weeks, medium-term value.**
3. **Phase 2 (DES MCP)**: Gated on adoption signals. Only if 50+ active non-Claude-Code users within 6 months.
4. **Positioning upgrade**: Even Phase 0.5 alone positions nWave as an "official" methodology framework in the Anthropic ecosystem.

The worst outcome is investing 7 months in full DES portability across 4 platforms and discovering that only 20 people use nWave outside Claude Code. The phased approach avoids this by validating demand before committing resources. The plugin marketplace provides the fastest feedback loop — install counts are visible immediately.

**Expected ROI timeline**:
- Phase 0: 2 weeks investment, immediate architectural benefit
- Phase 0.5: 2-3 weeks investment, **immediate adoption signal** (plugin install counts visible from day 1)
- Phase 1: 6-8 weeks investment, 3-6 months to measure cross-platform adoption
- Phase 2: Gate decision at month 6 based on adoption data
- Break-even: If Phase 0.5 drives 500+ plugin installs within 3 months, the investment is justified by adoption velocity alone. If Phase 1 drives 100+ non-Claude-Code users within 12 months, the TAM expansion justifies the additional investment.

**Arguments against** (steel-manned for completeness):
- **"Do nothing"**: nWave on Claude Code is already sufficient. The custom installer works. Plugin packaging is polish, not product. Counter: installation friction is the #1 reason users bounce — reducing it from 30 minutes to 1 command is a product change, not polish.
- **"Go all-in now"**: First-mover advantage in methodology frameworks is enormous. Waiting 6 months to validate demand means someone else fills the gap. Counter: no competing methodology framework exists today. The market risk is low. The execution risk of spreading thin is high.
- **"Plugin cannibalizes the custom installer"**: The `nwave-ai` CLI on PyPI becomes redundant if the plugin works. Counter: yes, and that's good. One distribution channel is simpler to maintain than two. Keep the CLI for non-Claude-Code platforms only.
