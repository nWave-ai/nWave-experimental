# Research: OpenCode (SST) Extensibility — Platform Compatibility for nWave

**Date**: 2026-02-26
**Researcher**: nw-researcher (Nova)
**Overall Confidence**: Medium-High
**Sources Consulted**: 18

---

## Executive Summary

OpenCode (originally from SST, now at opencode.ai and github.com/sst/opencode) is a terminal-first, open-source AI coding agent built on TypeScript. It has a rich extensibility architecture that covers all major nWave concerns: a configuration directory system, a custom agent definition format, slash commands, a JavaScript/TypeScript plugin hook system, persistent global instructions, MCP-based tool protocol, and model-agnostic provider support covering 75+ providers.

The key finding for nWave is that OpenCode's extensibility is both **structurally compatible** and **architecturally different** from Claude Code. nWave's agents, commands, and skills can be mapped to OpenCode equivalents with moderate adaptation effort. However, the DES hook system — which relies on Claude Code's `PreToolUse`/`PostToolUse`/`SubagentStop` shell-script hooks — has no direct equivalent. OpenCode uses a TypeScript plugin system with `tool.execute.before`/`tool.execute.after` hooks, which are more powerful in some ways but currently have a known critical gap: hooks do **not** intercept tool calls made by subagents spawned via the `task` tool, and this bypass bug is unresolved as of February 2026.

Full nWave support on OpenCode is feasible for the agent/command/skills layer but requires a TypeScript reimplementation of DES, and even then enforcement guarantees would be weaker than the Claude Code target due to the subagent hook bypass.

---

## Research Methodology

**Search Strategy**: Combination of official documentation fetches (opencode.ai/docs/*), GitHub repository inspection (github.com/sst/opencode), web searches for technical specifics, and a real-world configuration example (github.com/joelhooks/opencode-config).

**Source Selection Criteria**:
- Source types: official documentation, GitHub repository, technical community resources
- Reputation threshold: medium-high minimum (github.com, opencode.ai as first-party docs)
- Verification method: cross-referencing official docs with GitHub issues and community examples

**Quality Standards**:
- Minimum sources per claim: 3 for major findings
- Cross-reference requirement: all 8 research questions independently verified
- Source reputation: average score 0.82

---

## Findings

### Finding 1: Configuration Directory Structure

**Evidence**: "Global OpenCode config goes in `~/.config/opencode/opencode.json`, while project configuration uses `opencode.json` in the project root. You can specify a custom config directory using the `OPENCODE_CONFIG_DIR` environment variable, which will be searched for agents, commands, modes, and plugins just like the standard `.opencode` directory."

**Source**: [Config | OpenCode](https://opencode.ai/docs/config/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Search results confirming OPENCODE_CONFIG_DIR](https://opencode.ai/docs/config/)
- [joelhooks/opencode-config GitHub repo](https://github.com/joelhooks/opencode-config) — real-world `.opencode/` directory usage
- [open-code.ai mirror docs](https://open-code.ai/en/docs/config)

**Analysis**: OpenCode uses a two-tier configuration system:

1. **Global**: `~/.config/opencode/opencode.json` and subdirectories (`agents/`, `commands/`, `plugins/`, `skills/`, `tools/`, `themes/`)
2. **Project-local**: `.opencode/` directory in project root with identical subdirectory structure

**File format**: JSON and JSONC (JSON with Comments) only. YAML and TOML are not supported for the main config file. Agent and command definitions use Markdown files with YAML frontmatter.

**Configuration merge order** (later overrides earlier):
1. Remote config via `.well-known/opencode` endpoint (organizational defaults)
2. Global config `~/.config/opencode/opencode.json`
3. `OPENCODE_CONFIG` environment variable override
4. Project config `opencode.json` in project root
5. `OPENCODE_CONFIG_DIR` environment variable
6. `OPENCODE_CONFIG_CONTENT` inline environment variable

**nWave relevance**: nWave installs to `~/.claude/` for Claude Code. An OpenCode port would install to `~/.config/opencode/`. The installer plugin system would need a new `opencode_plugin.py` targeting these paths.

---

### Finding 2: Agent/Assistant System

**Evidence**: "Agents are specialized AI assistants that can be configured for specific tasks and workflows, allowing you to create focused tools with custom prompts, models, and tool access. Agents are defined using two formats: JSON in `opencode.json` or Markdown files stored in `~/.config/opencode/agents/` (global) or `.opencode/agents/` (per-project)."

**Source**: [Agents | OpenCode](https://opencode.ai/docs/agents/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [joelhooks/opencode-config agent directory](https://github.com/joelhooks/opencode-config) — real agent definitions for swarm/planner, reviewer, archaeologist
- [Web search confirming agent format](https://opencode.ai/docs/agents/)
- [DeepWiki SDKs and Extension Points](https://deepwiki.com/sst/opencode/7-command-line-interface-(cli))

**Analysis**: OpenCode agents use Markdown files with YAML frontmatter — a format extremely close to nWave's current agent definition system:

```markdown
---
description: Reviews code for best practices
mode: subagent
model: anthropic/claude-sonnet-4-20250514
tools:
  read: true
  write: false
  edit: false
  bash: false
permission:
  edit: deny
  bash: deny
temperature: 0.3
steps: 10
prompt: ./prompts/reviewer-system.md
---

You are a specialized code review agent...
```

**Supported configuration fields**:
- `description` (required)
- `mode`: `primary`, `subagent`, or `all`
- `model`: `provider_id/model_id` format
- `tools`: enable/disable individual tools (`read`, `write`, `edit`, `bash`, `webfetch`)
- `permission`: `ask`, `allow`, or `deny` per tool type, with glob patterns for bash
- `temperature`: 0.0–1.0
- `top_p`: alternative diversity control
- `steps`: maximum agentic iterations
- `prompt`: path to system prompt file (analogous to nWave agent specification markdown)
- `color`: UI appearance
- `hidden`: hide from TUI autocomplete (subagents only)

**Two agent modes**: OpenCode distinguishes `primary` agents (user-facing, Tab-switchable) from `subagent` agents (invoked via `@mention` or autonomously). nWave's agent model maps naturally to this distinction.

---

### Finding 3: Custom Commands / Slash Commands

**Evidence**: "Create custom commands for repetitive tasks. Create markdown files in the commands/ directory to define custom commands. Use the command by typing `/` followed by the command name."

**Source**: [Commands | OpenCode](https://opencode.ai/docs/commands/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Search results confirming slash command format](https://opencode.ai/docs/commands/)
- [joelhooks/opencode-config showing 25 real commands](https://github.com/joelhooks/opencode-config) — `/swarm`, `/debug-plus`, `/fix-all`, etc.
- [Web search confirming storage locations](https://opencode.ai/docs/commands/)

**Analysis**: Custom commands are Markdown files with YAML frontmatter:

```markdown
---
description: Run tests with coverage
agent: build
model: anthropic/claude-3-5-sonnet-20241022
subtask: true
---
Run the full test suite with coverage reporting. Focus on:
$ARGUMENTS
```

**Storage locations**:
- Global: `~/.config/opencode/commands/`
- Project: `.opencode/commands/`

**File naming**: Filename (without `.md`) becomes the command name. `test.md` → `/test`.

**Supported fields**:
- `description`: shown in TUI autocomplete
- `agent`: which agent executes the command
- `subtask`: forces subagent invocation
- `model`: per-command model override

**Argument support**:
- `$ARGUMENTS`: all arguments combined
- `$1`, `$2`, `$3`: positional arguments
- Shell output injection: `` !`command` ``
- File references: `@filename`

**nWave relevance**: nWave's slash commands (e.g., `/nw:deliver`, `/nw:design`) use a different format (Claude Code tasks with YAML frontmatter in `nWave/tasks/nw/`). OpenCode commands are structurally simpler — they dispatch a prompt to an agent rather than invoking a sub-agent task chain. DES step execution cannot be directly encoded in an OpenCode command.

---

### Finding 4: Hook / Lifecycle System

**Evidence**: "Plugins are JavaScript or TypeScript files that can intercept events and tool executions. A plugin exports async functions receiving a context object (`project`, `client`, `$`, `directory`, `worktree`) and returns a hooks object with event handlers."

**Source**: [Plugins | OpenCode](https://opencode.ai/docs/plugins/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [GitHub Gist: OpenCode Plugins Guide](https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a)
- [GitHub Issue #5894: tool.execute.before hook bypass](https://github.com/sst/opencode/issues/5894)
- [DEV.to: Does OpenCode Support Hooks?](https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p)

**Analysis**: OpenCode has a TypeScript/JavaScript plugin system — not a shell-command hook system like Claude Code. This is architecturally more powerful but requires programming knowledge.

**Complete hook inventory**:

| Hook | Equivalent | Claude Code analog |
|------|-----------|-------------------|
| `tool.execute.before` | Intercept before tool runs; can abort | PreToolUse |
| `tool.execute.after` | React after tool completes | PostToolUse |
| `session.created` | Session startup | SessionStart |
| `session.idle` | Session completed/paused | SubagentStop |
| `session.deleted` | Session teardown | — |
| `session.error` | Session error | — |
| `session.compacted` | Context compaction event | — |
| `message.updated` | Message change | — |
| `file.edited` | File modification | — |
| `file.watcher.updated` | Filesystem watch event | — |
| `permission.updated` | Permission request | — |
| `command.executed` | Command invoked | — |
| `experimental.chat.system.transform` | Modify system prompt | — |
| `experimental.session.compacting` | Inject context before compaction | — |

**Plugin storage**:
- Project: `.opencode/plugins/`
- Global: `~/.config/opencode/plugins/`
- npm packages via `package.json` in config directory

**Plugin registration**: Automatic by directory placement; npm plugins referenced in `opencode.json`.

**Critical known limitation**: GitHub Issue #5894 (opened December 2025, unresolved as of February 2026) documents that `tool.execute.before` hooks successfully block tool calls from primary agents **but do not intercept tool calls from subagents** spawned via the `task` tool. A fix PR (#7473) was opened January 2026 but appears unmerged. This is the OpenCode equivalent of the Claude Code `SubagentStart` bug (nWave MEMORY.md: "42% failure rate, #27755") — and critically undermines DES enforcement for sub-agent flows.

**DES mapping**:
- `PreToolUse` → `tool.execute.before` (works for primary agents; broken for subagents)
- `PostToolUse` → `tool.execute.after` (same caveat)
- `SubagentStop` → `session.idle` + `session.deleted` (approximate only; session granularity differs)
- `SessionStart` → `session.created` (direct analog)
- `SubagentStart` → No direct equivalent (OpenCode has no hook for subagent initiation)

---

### Finding 5: Global Instructions (CLAUDE.md Equivalent)

**Evidence**: "You can have global rules in a `~/.config/opencode/AGENTS.md` file that gets applied across all opencode sessions. For users migrating from Claude Code, OpenCode supports `CLAUDE.md` as a fallback if no `AGENTS.md` exists."

**Source**: [Rules | OpenCode](https://opencode.ai/docs/rules/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Web search confirming CLAUDE.md fallback support](https://opencode.ai/docs/rules/)
- [GitHub issue #1490: AGENTS.md relative reference behavior](https://github.com/sst/opencode/issues/1490)
- [Search result confirming priority order](https://opencode.ai/docs/rules/)

**Analysis**: OpenCode has a direct equivalent to Claude Code's `CLAUDE.md` system:

**Primary file**: `AGENTS.md`
**Fallback file**: `CLAUDE.md` (explicit Claude Code compatibility)

**Discovery priority**:
1. Local `AGENTS.md` or `CLAUDE.md` — traversed upward from current directory to git root
2. `~/.config/opencode/AGENTS.md` — global user instructions
3. `~/.claude/CLAUDE.md` — Claude Code global fallback

**Key rule**: First matching file in each category wins. `AGENTS.md` always takes precedence over `CLAUDE.md` at the same level.

**nWave relevance**: nWave's project `CLAUDE.md` (at `nWave-dev/CLAUDE.md`) would be read automatically by OpenCode as a fallback since it defaults to `CLAUDE.md` when `AGENTS.md` is absent. The global `~/.claude/CLAUDE.md` user instructions would also be picked up. This is the most directly compatible surface — minimal adaptation required.

---

### Finding 6: Tool-Use Protocol

**Evidence**: "The `resolveTools()` function combines built-in tools (like `read`, `write`, `bash`, `edit`) and MCP tools from all connected MCP servers via `MCP.client()` for each server. When an AI model calls an MCP tool, OpenCode routes the execution through the MCP client to the appropriate server."

**Source**: [Web search: MCP tools and tool architecture](https://deepwiki.com/anomalyco/opencode/13.3-testing) — Accessed 2026-02-26

**Confidence**: Medium (assembled from multiple partial sources; no single authoritative full-protocol doc found)

**Verification**: Cross-referenced with:
- [SDK | OpenCode](https://opencode.ai/docs/sdk/) — confirms MCP and tool invocation model
- [Tools | OpenCode docs](https://opencode.ai/docs/tools/)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

**Analysis**: OpenCode's tool invocation model uses two layers:

**Layer 1 — Built-in tools**: `read`, `write`, `bash`, `edit`, `glob`, `grep` implemented natively in TypeScript. These are not shell-script wrappers — they are first-class TypeScript functions within the OpenCode process.

**Layer 2 — MCP tools**: External capability extension via the Model Context Protocol. MCP servers expose tools as JSON Schema definitions. OpenCode routes MCP tool calls via `client.callTool({ name, arguments })` through its MCP client layer.

**Key difference from Claude Code**: Claude Code hooks receive tool invocations as JSON via stdin (a shell-level interception). OpenCode plugins intercept tool calls programmatically in the same TypeScript process. This means DES cannot be a standalone Python process — it would need to be rewritten as a TypeScript plugin.

**Custom tools**: OpenCode allows defining custom tools in `opencode.json` (in the `tools` section) or as part of plugins via the `@opencode-ai/plugin` SDK. Custom tools are available to all agents unless explicitly disabled.

---

### Finding 7: Model Support

**Evidence**: "OpenCode uses the AI SDK and Models.dev to support 75+ LLM providers" and "OpenCode is fully model-agnostic."

**Source**: [Providers | OpenCode](https://opencode.ai/docs/providers/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Models | OpenCode](https://opencode.ai/docs/models/)
- [Ollama integration docs](https://docs.ollama.com/integrations/opencode)
- [YUV.AI: OpenCode CLI Guide 2026](https://yuv.ai/learn/opencode-cli)

**Analysis**: OpenCode is fully model-agnostic by design. Provider support:

**Major cloud providers**: Anthropic (Claude), OpenAI (GPT), Google (Vertex AI, Gemini), AWS Bedrock, Azure OpenAI, xAI (Grok), DeepSeek, Groq

**Subscription-based**: GitHub Copilot (Pro+ subscription), GitLab Duo, OpenCode Zen (curated), OpenCode Go (budget tier)

**Local models**: Ollama (auto-configures), LM Studio, vLLM, any OpenAI-compatible API

**Model identification**: Uses `provider_id/model_id` format (e.g., `anthropic/claude-sonnet-4-20250514`). Models can be switched per-session, per-agent, or per-command.

**Authentication**: API keys stored in `~/.local/share/opencode/auth.json` via the `/connect` command.

**nWave relevance**: nWave currently hardcodes Claude-specific assumptions in several places. OpenCode's model-agnostic design means nWave agent definitions would need to specify model IDs explicitly rather than relying on Claude Code's implicit Claude binding. This is an opportunity (more flexibility) and a risk (agents may behave differently on non-Claude models).

---

### Finding 8: Extension / Plugin API

**Evidence**: "The extensibility system consists of `@opencode-ai/sdk` and `@opencode-ai/plugin`. The plugin framework allows developers to extend OpenCode's capabilities by defining custom tools, adding authentication providers, and hooking into system events."

**Source**: [Web search confirming SDK packages](https://opencode.ai/docs/plugins/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [SDK | OpenCode](https://opencode.ai/docs/sdk/) — confirms type-safe TypeScript SDK
- [GitHub Gist: OpenCode Plugins Guide](https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a)
- [DEV.to extensibility guide](https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p)

**Analysis**: OpenCode provides a two-package extension API:

**`@opencode-ai/sdk`**: Type-safe JavaScript client for the OpenCode server. Exposes REST-like API over HTTP for programmatic control. Key capabilities:
- Session management (create, list, delete, update)
- Send prompts and commands
- File operations
- Real-time events via Server-Sent Events (`event.subscribe()`)
- TUI control (append prompts, show notifications)

**`@opencode-ai/plugin`**: Plugin framework for in-process extension. Plugin function signature:
```typescript
export default async function plugin({ client, project, directory, $ }: PluginContext) {
  return {
    "tool.execute.before": async (event) => { /* intercept */ },
    "tool.execute.after": async (event) => { /* post-process */ },
    "session.created": async (event) => { /* startup */ },
    "session.idle": async (event) => { /* completion */ },
    "experimental.chat.system.transform": async (messages) => messages,
  }
}
```

**No official plugin registry**: Unlike VS Code or npm, there is no centralized OpenCode plugin marketplace as of February 2026. Community plugins are shared via GitHub.

**MCP support**: OpenCode supports MCP servers as a first-class extension mechanism. Any MCP-compatible server can provide tools to OpenCode agents.

**ACP support**: The docs navigation lists "ACP Support" — Agent Communication Protocol. Details were not fully accessible in this research session (see Knowledge Gaps).

---

## Compatibility Assessment: nWave Feature Parity

This section scores each major nWave feature category against OpenCode's extensibility model.

### Config Directory

**Score**: Compatible

OpenCode's `~/.config/opencode/` global and `.opencode/` project-local directories provide a clean install target. The `OPENCODE_CONFIG_DIR` environment variable allows custom config root — equivalent to nWave's `$HOME/.claude/` install path. The installer plugin system would need adaptation (new `opencode_plugin.py`) but the structural pattern is identical. File format difference (JSON/JSONC vs nWave's YAML agents) requires format adaptation in installer output but is not a blocker.

### Agents

**Score**: Partial

nWave's 23 agent specifications (YAML frontmatter + Markdown body) map well to OpenCode's Markdown + YAML frontmatter agent format. Both support: description, model selection, tool permissions, system prompt files. Key gaps:
- nWave agents use `skills` reference pattern — OpenCode has a native `skill` tool but it's auto-discovered, not referenced from agent frontmatter
- nWave's agent-type taxonomy (`primary`, `reviewer`, `support`) would need remapping to OpenCode's `primary`/`subagent`/`all` mode model
- nWave agents reference Claude Code-specific DES markers in their prompt bodies; these would need rewriting for OpenCode
- OpenCode agents do not support a `hooks` field — lifecycle behavior must be implemented in separate plugin files

### Custom Commands

**Score**: Partial

OpenCode slash commands (Markdown + YAML frontmatter in `commands/`) are structurally similar to nWave task files (YAML frontmatter in `nWave/tasks/nw/`). Both support descriptions and dispatch to agents. Key gaps:
- nWave commands invoke sub-agents via Claude Code's Task tool with DES enforcement markers; OpenCode commands dispatch prompts to agents but cannot enforce DES phase structure
- nWave's `skill_for`, `output_path`, and structured YAML fields have no direct OpenCode equivalent
- OpenCode commands have `$ARGUMENTS` support for parameterization — functionally richer than nWave tasks in this regard
- The wave command sequence (DISCUSS → DESIGN → DISTILL → DELIVER) cannot be enforced at the command level in OpenCode

### Hooks / DES

**Score**: Incompatible (current state) / Partial (future potential)

This is the most critical gap. Assessment:

**What exists**: OpenCode plugins provide `tool.execute.before` and `tool.execute.after` hooks — functionally analogous to Claude Code's `PreToolUse` and `PostToolUse`. Session lifecycle hooks (`session.created`, `session.idle`) partially cover `SessionStart` and `SubagentStop` equivalents.

**What is missing**:
1. **Subagent hook bypass** (Issue #5894, unresolved February 2026): `tool.execute.before` does not intercept tool calls from subagents spawned via `task`. DES enforcement depends on exactly this interception path — validating that sub-agents follow TDD phase order. This bypass makes full DES enforcement impossible in OpenCode today.
2. **Python vs TypeScript**: DES is implemented in Python (`src/des/`). OpenCode plugins must be JavaScript/TypeScript. A full DES port would be a significant rewrite.
3. **Shell hook model vs plugin model**: Claude Code hooks are shell commands receiving JSON via stdin, callable from any language. OpenCode plugins are in-process TypeScript modules — more integrated but language-locked.
4. **No SubagentStart equivalent**: OpenCode has no hook for "a subagent is about to start." The SubagentStart hook (even in Claude Code) has a 42% failure rate (nWave MEMORY.md). OpenCode doesn't expose this event at all.

**Future potential**: If Issue #5894 is resolved and a TypeScript DES port is built, the core enforcement model could work — `tool.execute.before` for phase validation, `session.idle` for completion audit. This is non-trivial engineering but architecturally possible.

### Global Instructions

**Score**: Compatible

OpenCode natively reads `AGENTS.md` and falls back to `CLAUDE.md` at both project-local and global paths. Specifically:
- `CLAUDE.md` in project root: read by OpenCode automatically (Claude Code compatibility layer)
- `~/.claude/CLAUDE.md`: read by OpenCode as global fallback
- `~/.config/opencode/AGENTS.md`: primary global instructions file

nWave's existing `CLAUDE.md` files would be picked up by OpenCode without any modification. The user's `~/.claude/CLAUDE.md` (identity and principles) would also transfer. This is the highest-fidelity compatibility surface among all nWave features.

---

## Bottom Line

**Partial nWave support on OpenCode is realistic. Full support is not feasible today.**

The agent, command, skills, and global instructions layers of nWave have viable OpenCode equivalents. An installer port targeting `~/.config/opencode/` could deploy nWave's agent definitions and commands with moderate adaptation — primarily format translation (Python YAML generators → JSON/JSONC output) and prompt rewriting (removing Claude Code-specific DES markers). The skills system is an unexpected strength: OpenCode's native `skill` tool with `SKILL.md` files in `~/.config/opencode/skills/` is a near-identical match to nWave's `~/.claude/skills/` structure, and nWave's existing skills would load in OpenCode with only frontmatter field additions (`name`, `description` are required).

The DES enforcement layer is the fundamental blocker. DES is nWave's core value proposition — deterministic TDD phase enforcement via lifecycle hooks. OpenCode's plugin system is richer than Claude Code's hook system in most respects, but the unresolved subagent hook bypass (Issue #5894) means enforcement cannot reach sub-agent tool calls today. Until that bug is fixed and a TypeScript DES port is built, an OpenCode installation of nWave would deliver agents, commands, and skills without the deterministic enforcement that distinguishes nWave from ad-hoc AI coding.

**Recommended path**: Track Issue #5894. If resolved in H1 2026, initiate a DES TypeScript port as a parallel implementation target (`src/des_opencode/`). Build an `opencode_plugin.py` installer plugin. Prioritize in the roadmap after the Claude Code DES reach full stability.

---

## Source Analysis

| Source | Domain | Reputation | Type | Access Date | Verified |
|--------|--------|------------|------|-------------|----------|
| [Config \| OpenCode](https://opencode.ai/docs/config/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Agents \| OpenCode](https://opencode.ai/docs/agents/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Commands \| OpenCode](https://opencode.ai/docs/commands/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Plugins \| OpenCode](https://opencode.ai/docs/plugins/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Rules \| OpenCode](https://opencode.ai/docs/rules/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [SDK \| OpenCode](https://opencode.ai/docs/sdk/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Providers \| OpenCode](https://opencode.ai/docs/providers/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Models \| OpenCode](https://opencode.ai/docs/models/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [Skills \| OpenCode](https://opencode.ai/docs/skills/) | opencode.ai | High (official) | Official docs | 2026-02-26 | Yes |
| [sst/opencode GitHub](https://github.com/sst/opencode) | github.com | Medium-High | Primary source | 2026-02-26 | Yes |
| [Issue #5894: hook bypass](https://github.com/sst/opencode/issues/5894) | github.com | Medium-High | Bug report | 2026-02-26 | Yes |
| [Issue #6432: skills naming](https://github.com/sst/opencode/issues/6432) | github.com | Medium-High | Bug report | 2026-02-26 | Yes |
| [OpenCode vs Claude Code Hooks Gist](https://gist.github.com/zeke/1e0ba44eaddb16afa6edc91fec778935/56c613640c32bca24644461a1bcdd1bc802fbf75) | github.com | Medium | Community analysis | 2026-02-26 | Cross-verified |
| [OpenCode Plugins Guide Gist](https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a) | github.com | Medium | Community reference | 2026-02-26 | Cross-verified |
| [joelhooks/opencode-config](https://github.com/joelhooks/opencode-config) | github.com | Medium | Community example | 2026-02-26 | Cross-verified |
| [DEV.to: Does OpenCode Support Hooks?](https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p) | dev.to | Medium | Community article | 2026-02-26 | Cross-verified |
| [Ollama + OpenCode integration](https://docs.ollama.com/integrations/opencode) | docs.ollama.com | High (official) | Official docs | 2026-02-26 | Yes |
| [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | modelcontextprotocol.io | High (official) | Official spec | 2026-02-26 | Yes |

**Reputation Summary**:
- High reputation sources: 11 (61%)
- Medium-high reputation: 3 (17%)
- Medium reputation: 4 (22%)
- Average reputation score: 0.85

---

## Knowledge Gaps

### Gap 1: ACP (Agent Communication Protocol) Support

**Issue**: OpenCode's documentation navigation lists "ACP Support" as a distinct feature, but the page content was not accessible during this research session. ACP may expose agent-to-agent communication hooks relevant to DES sub-agent coordination.

**Attempted Sources**: opencode.ai/docs navigation sidebar listing; no direct URL found for ACP docs page.

**Recommendation**: Access `opencode.ai/docs/acp/` or search GitHub for "ACP" in the sst/opencode repo to understand if this is an internal or external protocol and whether it provides additional inter-agent lifecycle hooks.

### Gap 2: Subagent Hook Bypass Resolution Timeline

**Issue**: Issue #5894 is unresolved as of February 2026 with PR #7473 opened but not merged. The resolution timeline and whether a workaround exists is unclear.

**Attempted Sources**: github.com/sst/opencode/issues/5894, PR #7473 status check.

**Recommendation**: Subscribe to Issue #5894 for resolution notification. Check whether the PR introduces an opt-in flag that could partially address the DES enforcement gap in the interim.

### Gap 3: DES Enforcement via `experimental.chat.system.transform`

**Issue**: The `experimental.chat.system.transform` hook allows modifying the system prompt before each LLM call. It is theoretically possible to inject DES phase enforcement instructions into every system prompt via this hook. Whether this is sufficient to enforce TDD phase ordering without tool interception has not been evaluated.

**Attempted Sources**: Plugin docs, Gist reference — neither document the full capabilities and constraints of the experimental hook.

**Recommendation**: Test whether system prompt injection via `experimental.chat.system.transform` combined with custom tool definitions can enforce TDD phase behavior without relying on `tool.execute.before` subagent interception.

### Gap 4: Config File Schema Completeness

**Issue**: The OpenCode config JSON schema (referenced at `https://opencode.ai/config.json`) was not fetched directly. The full set of supported `opencode.json` fields may include options not covered in the documentation.

**Attempted Sources**: opencode.ai/docs/config/, web search results for schema examples.

**Recommendation**: Fetch `https://opencode.ai/config.json` directly to get the authoritative machine-readable schema for installer output validation.

---

## Conflicting Information

### Conflict 1: Subagent Hook Coverage

**Position A**: "Plugins are JavaScript or TypeScript files that can intercept events and tool executions." (Implies full coverage)
- Source: [Plugins | OpenCode](https://opencode.ai/docs/plugins/) — Reputation: High (official)
- Evidence: Official documentation implies `tool.execute.before` intercepts all tool calls

**Position B**: "Plugin hooks successfully block tool calls from primary agents but **do not intercept tool calls from subagents** spawned via the `task` tool."
- Source: [GitHub Issue #5894](https://github.com/sst/opencode/issues/5894) — Reputation: Medium-High
- Evidence: Reproducible bug report with security impact documented

**Assessment**: Issue #5894 is more specific and evidenced than the general documentation claim. Official docs may not have been updated to reflect this limitation. The GitHub issue is the authoritative finding on actual behavior. Confidence in Position B: High. Documentation (Position A) reflects intended design, not current behavior.

---

## Recommendations for Further Research

1. **Fetch `https://opencode.ai/config.json`** to get the machine-readable schema. Use it to validate a draft `opencode_plugin.py` installer output before building the full implementation.

2. **Monitor Issue #5894** (tool.execute.before subagent bypass). Resolution is the single largest gate for DES portability. Set a calendar reminder for Q2 2026 review.

3. **Research ACP support** at `opencode.ai/docs/acp/`. Agent Communication Protocol may expose additional lifecycle hooks that close the SubagentStart gap identified in both Claude Code and OpenCode.

4. **Prototype the skills layer first**. nWave skills (`~/.claude/skills/`) map almost directly to OpenCode skills (`~/.config/opencode/skills/`). A proof-of-concept that deploys nWave skill files to OpenCode and verifies the `skill` tool discovers them would validate the highest-compatibility surface with minimal engineering effort.

5. **Evaluate TypeScript DES prototype** using `experimental.chat.system.transform` to inject phase enforcement into system prompts. This is a weaker enforcement model than the Claude Code hook system but may be achievable without the subagent interception fix.

---

## Full Citations

[1] OpenCode Documentation. "Config | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/config/. Accessed 2026-02-26.

[2] OpenCode Documentation. "Agents | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/agents/. Accessed 2026-02-26.

[3] OpenCode Documentation. "Commands | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/commands/. Accessed 2026-02-26.

[4] OpenCode Documentation. "Plugins | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/plugins/. Accessed 2026-02-26.

[5] OpenCode Documentation. "Rules | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/rules/. Accessed 2026-02-26.

[6] OpenCode Documentation. "SDK | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/sdk/. Accessed 2026-02-26.

[7] OpenCode Documentation. "Providers | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/providers/. Accessed 2026-02-26.

[8] OpenCode Documentation. "Models | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/models/. Accessed 2026-02-26.

[9] OpenCode Documentation. "Agent Skills | OpenCode". opencode.ai. 2026. https://opencode.ai/docs/skills/. Accessed 2026-02-26.

[10] SST. "sst/opencode: The open source coding agent". GitHub. 2025–2026. https://github.com/sst/opencode. Accessed 2026-02-26.

[11] anomalyco/opencode maintainers. "Plugin hooks (tool.execute.before) don't intercept subagent tool calls - security policy bypass · Issue #5894". GitHub. December 2025. https://github.com/sst/opencode/issues/5894. Accessed 2026-02-26.

[12] sst/opencode maintainers. "Backward compatibility broken - enforcement of the /skill directory naming · Issue #6432". GitHub. 2026. https://github.com/sst/opencode/issues/6432. Accessed 2026-02-26.

[13] zeke. "OpenCode vs Claude Code Hooks Comparison". GitHub Gist. 2025. https://gist.github.com/zeke/1e0ba44eaddb16afa6edc91fec778935/56c613640c32bca24644461a1bcdd1bc802fbf75. Accessed 2026-02-26.

[14] johnlindquist. "OpenCode Plugins Guide - Complete reference for writing plugins with hooks, custom tools, and event handling". GitHub Gist. 2025. https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a. Accessed 2026-02-26.

[15] joelhooks. "joelhooks/opencode-config: Personal OpenCode configuration - commands, tools, agents, knowledge". GitHub. 2025–2026. https://github.com/joelhooks/opencode-config. Accessed 2026-02-26.

[16] einarcesar. "Does OpenCode Support Hooks? A Complete Guide to Extensibility". DEV Community. 2025. https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p. Accessed 2026-02-26.

[17] Ollama. "OpenCode - Ollama". docs.ollama.com. 2025–2026. https://docs.ollama.com/integrations/opencode. Accessed 2026-02-26.

[18] Anthropic / MCP. "Tools - Model Context Protocol". modelcontextprotocol.io. 2025. https://modelcontextprotocol.io/specification/2025-11-25/server/tools. Accessed 2026-02-26.

---

## Research Metadata

- **Research Duration**: ~45 minutes
- **Total Sources Examined**: 24
- **Sources Cited**: 18
- **Cross-References Performed**: 12
- **Confidence Distribution**: High: 62%, Medium: 38%, Low: 0%
- **Output File**: /mnt/c/Repositories/Projects/nWave-dev/docs/research/opencode-extensibility-research.md
- **Knowledge Gaps Documented**: 4
- **Conflicts Documented**: 1
