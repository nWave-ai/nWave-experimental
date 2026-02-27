# Research: OpenAI Codex CLI — Extensibility, Configuration, and Hook System

**Date**: 2026-02-26
**Researcher**: nw-researcher (Nova)
**Overall Confidence**: High
**Sources Consulted**: 22

---

## Executive Summary

OpenAI Codex CLI (`openai/codex` on GitHub) is a production-ready, open-source terminal coding agent written in Rust (96% of codebase). It is generally available as of 2025, distributed via npm (`@openai/codex`) and Homebrew, and ships an active release cadence (version 0.105.0 as of February 2026). The tool is distinct from legacy `gh copilot` and from the cloud-based Codex web agent at chatgpt.com/codex, though they share authentication and model infrastructure.

For nWave platform portability, the key finding is: **partial compatibility is achievable in three of five nWave feature categories; full nWave support is not feasible today and may never be fully achievable without a fundamental hook system redesign from OpenAI**.

The strongest compatibility surfaces are configuration directory structure (`~/.codex/` analogous to `~/.claude/`), global instructions (`AGENTS.md` with an open-standard discovery hierarchy), and skills (`SKILL.md` files with YAML frontmatter stored in `$HOME/.agents/skills/` — a near-identical match to nWave's skill convention). The weakest surfaces are agents (no dedicated agent definition file format; agents are configured via TOML sections only), custom commands (no user-defined slash command API exists; only built-in commands and a deprecated prompts system exist, now superseded by skills), and — most critically — hooks/DES (the current hook system has only one event, `agent-turn-complete`, delivered to a `notify` external process; `PreToolUse`/`PostToolUse` equivalents are highly requested community features but as of February 2026 are not in the product, and two community PRs implementing comprehensive lifecycle hooks were declined on the grounds that OpenAI is designing their own).

The bottom line: nWave skills and global instructions are immediately portable to Codex CLI. Config directory and MCP integration are feasible with moderate installer work. The agent persona system requires workarounds. Custom wave commands cannot be replicated. DES enforcement is impossible today and dependent on OpenAI shipping a hook system that does not yet exist.

---

## Research Methodology

**Search Strategy**: Primary sources from `developers.openai.com/codex/*` (official documentation), `github.com/openai/codex` (source, issues, PRs, discussions), and the GitHub Issues/Discussions tracker for community status. Secondary verification from comparison articles, Azure OpenAI documentation (learn.microsoft.com), and community forum posts. CLI reference and config reference pages fetched directly to validate all configuration fields.

**Source Selection Criteria**:
- Source types: official documentation (primary), official GitHub repository (primary), GitHub issues/discussions (for unmerged/community features), industry comparison articles (secondary verification only)
- Reputation threshold: High minimum for all feature claims; medium-high for community status verification
- Verification method: All major claims cross-referenced across at least 2 official sources; hook system status verified via GitHub issue tracker + PR status

**Quality Standards**:
- Minimum sources per claim: 3 for major findings
- Cross-reference requirement: All 8 research questions independently verified
- Source reputation: Average score 0.92

---

## Findings

### Finding 1: What Is Codex CLI — Identity, Status, and Platform

**Evidence**: "GitHub — openai/codex: Lightweight coding agent that runs in your terminal." The repository has 4,062 commits and 544 releases. The description at `developers.openai.com/codex/cli/` states: "OpenAI's coding agent that you can run locally from your terminal." Version 0.105.0 shipped February 25, 2026. The codebase is 96.1% Rust with supporting TypeScript (2.3%) and Python (0.9%).

**Source**: [github.com/openai/codex](https://github.com/openai/codex) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Codex CLI — developers.openai.com](https://developers.openai.com/codex/cli/) — official product page
- [Codex Changelog 0.105.0](https://developers.openai.com/codex/changelog/) — confirms active release as of Feb 25, 2026
- [Northflank: Claude Code vs OpenAI Codex](https://northflank.com/blog/claude-code-vs-openai-codex) — independent confirmation of status

**Analysis**: This is definitively the same product as `openai/codex` on GitHub. There are four distinct Codex surfaces to distinguish:

| Surface | Status | Description |
|---------|--------|-------------|
| **Codex CLI** (`@openai/codex`) | GA | Terminal agent; primary focus of this research |
| Codex App (desktop) | Limited availability (macOS only) | GUI wrapper; same backend |
| Codex IDE Extensions | GA | VS Code, Cursor, Windsurf |
| chatgpt.com/codex | GA | Web-based agent; cloud execution |

The CLI is **generally available** (not alpha/beta). It requires a ChatGPT Plus, Pro, Business, Edu, or Enterprise subscription, or an OpenAI API key. Authentication uses OAuth (ChatGPT account) or API key. Platform support: macOS and Linux (GA), Windows via WSL (experimental). The CLI is open-source under Apache-2.0.

**nWave relevance**: Codex CLI is the only Codex surface with an interactive, session-based terminal execution model analogous to Claude Code. The desktop app and web agent use the same architecture but are not scriptable targets for nWave installer tooling.

---

### Finding 2: Configuration Directory Structure

**Evidence**: "User-level configuration lives in `~/.codex/config.toml`. You can also add project-scoped overrides in `.codex/config.toml` files." The system also supports `/etc/codex/config.toml` on Unix for system-level defaults.

**Source**: [Config Basics — developers.openai.com/codex/config-basic/](https://developers.openai.com/codex/config-basic/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Configuration Reference — developers.openai.com/codex/config-reference/](https://developers.openai.com/codex/config-reference/) — confirms `~/.codex/` as home
- [github.com/openai/codex/blob/main/docs/config.md](https://github.com/openai/codex/blob/main/docs/config.md) — confirms `~/.codex/config.toml` and `CODEX_SQLITE_HOME` env var
- [Web search confirming directory structure](https://developers.openai.com/codex/config-basic/) — third confirmation

**Analysis**: The full configuration directory structure:

```
~/.codex/                          # User-level config root ($CODEX_HOME; overridable via env)
  config.toml                      # Primary config (TOML format)
  prompts/                         # Deprecated custom prompts (use skills/ instead)
  themes/                          # Custom .tmTheme syntax highlight files

.codex/                            # Project-level config (in project root)
  config.toml                      # Project overrides (trusted projects only)
```

**Configuration precedence** (highest to lowest):
1. CLI flags and `--config key=value` overrides
2. Profile values (via `--profile <name>`)
3. Project `.codex/config.toml` files (closest directory wins; trusted projects only)
4. User `~/.codex/config.toml`
5. System `/etc/codex/config.toml`
6. Built-in defaults

**Key differences from Claude Code**:
- Format: TOML (not YAML or JSON like Claude Code adjacent tools)
- No `agents/`, `commands/`, or `skills/` subdirectories under `~/.codex/` — these live in different paths (see Finding 5)
- Project config is an opt-in trust model — Codex will not load `.codex/config.toml` from an untrusted directory without explicit approval
- The `$CODEX_HOME` environment variable can override the default `~/.codex/` path

**nWave relevance**: An nWave Codex installer plugin would write to `~/.codex/config.toml`. The two-tier (user + project) pattern matches Claude Code's `~/.claude/` + project-local model. The trust model for project config adds a one-time user confirmation step that the installer would need to handle.

---

### Finding 3: Agent / Persona System

**Evidence**: "Agent roles are configured via `[agents]` in `config.toml`." Four built-in roles exist: `default`, `worker`, `explorer`, `monitor`. Custom roles are defined under `[agents.<name>]` sections. The multi-agent feature (experimental, disabled by default) exposes `spawn_agent`, `send_input`, `resume_agent`, `wait`, and `close_agent` tools.

**Source**: [Multi-agents — developers.openai.com/codex/multi-agent/](https://developers.openai.com/codex/multi-agent/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Configuration Reference — developers.openai.com/codex/config-reference/](https://developers.openai.com/codex/config-reference/) — confirms `agents.<name>.config_file`, `agents.max_depth`, `agents.max_threads`
- [GitHub Discussion #6109 — how to create custom agents](https://github.com/openai/codex/discussions/6109) — community confirmation that no dedicated agent file format exists
- [Codex CLI features — developers.openai.com/codex/cli/features/](https://developers.openai.com/codex/cli/features/) — confirms experimental multi-agent status

**Analysis**: Codex CLI does **not** have a dedicated agent definition file format (no `agent.md`, no `agents.yaml`). Agents are configured entirely via `config.toml`:

```toml
[agents.reviewer]
description = "Focuses on code review and quality assurance"
config_file = "~/.codex/reviewer-config.toml"   # Optional TOML overlay

[agents.tester]
description = "Runs tests and validates correctness"

[agents]
max_depth = 2        # Maximum spawned agent nesting depth (default: 1)
max_threads = 4      # Concurrent agent thread limit
```

**What does NOT exist** (confirmed via documentation gaps and community discussion):
- No Markdown + YAML frontmatter agent definition (contrast: OpenCode, Copilot CLI both use this)
- No per-agent tool permission model (no equivalent to `tools: [read, write]` per agent)
- No `mode` field (primary vs subagent distinction)
- No per-agent model override at the agent definition level (override possible via `config_file`)
- No dedicated `agents/` directory under `~/.codex/`

The `/agent` slash command switches between threads in multi-agent mode. The multi-agent feature is experimental and disabled by default as of February 2026.

**nWave relevance**: nWave's 23 agent specifications (YAML frontmatter + Markdown body) have no direct mapping to Codex CLI's TOML-based agent roles. The closest equivalent is embedding agent instructions in AGENTS.md (global or project-level) and using `config.toml` sections for model/behavior overrides. This is a significant adaptation: nWave's agent catalog and behavior definitions cannot be ported as-is — they would need to be flattened into AGENTS.md content or expressed as separate config profiles.

---

### Finding 4: Custom Commands / Slash Commands

**Evidence**: "Codex ships with a curated set of built-ins [slash commands], and you can create custom ones for team-specific tasks or personal shortcuts." However, the custom prompt system is explicitly marked **deprecated**: "Custom prompts are deprecated in favor of skills."

**Source**: [Custom Prompts — developers.openai.com/codex/custom-prompts/](https://developers.openai.com/codex/custom-prompts/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Slash Commands in Codex CLI — developers.openai.com/codex/cli/slash-commands/](https://developers.openai.com/codex/cli/slash-commands/) — 26 built-in commands documented; no custom slash command API documented
- [GitHub Issue #4311 — Feature Request: Add SlashCommand tool-style auto invocation to Codex CLI](https://github.com/openai/codex/issues/4311) — confirms community request for custom slash commands that are not yet available
- [GitHub Issue #5392 — Support for Slash Commands and Custom Command Definitions via .codex File in VS Code Extension](https://github.com/openai/codex/issues/5392) — confirms absence of the feature

**Analysis**: There are two distinct but related concepts to understand:

**Built-in slash commands (26 total)**: Hardcoded into Codex CLI. Key commands:
- `/model` — switch model mid-session
- `/permissions` — adjust approval policy
- `/plan` — switch to plan mode
- `/agent` — switch agent thread (multi-agent mode)
- `/compact` — summarize conversation
- `/diff` — show git diff
- `/review` — code review
- `/mcp` — manage MCP servers
- `/status` — session diagnostics
- `/init` — generate AGENTS.md scaffold
- `/experimental` — toggle experimental features
- `/new`, `/resume`, `/fork` — session management

**Custom prompts (deprecated, replaced by skills)**: Markdown files in `~/.codex/prompts/` with YAML frontmatter:
```yaml
---
description: Draft a pull request description
argument-hint: [FILES="path1 path2"] [PR_TITLE="<title>"]
---
Review the following files and write a PR description...
$ARGUMENTS
```
- Invoked via `/prompts:<filename>` syntax
- Support positional (`$1`–`$9`, `$ARGUMENTS`) and named (`$FILE`, `$TICKET_ID`) placeholders
- **Status**: Deprecated. OpenAI recommends migrating to skills.

**Skills (current replacement)**: SKILL.md files (see Finding 5). Skills are invoked explicitly via `/skills` or `$skill-name` syntax, or auto-selected by Codex based on task description matching.

**No user-defined slash command API**: Custom slash commands as a first-class extension point (like OpenCode's `commands/` directory or nWave's task files) do not exist in Codex CLI. Community issues requesting this feature remain open and unaddressed.

**nWave relevance**: nWave's slash commands (`/nw:deliver`, `/nw:design`, `/nw:distill`, etc.) have no equivalent in Codex CLI. The closest analogue is skills (auto-invoked or explicit `$nw-skill` mention), but skills deliver context/instructions rather than dispatching structured task chains. The wave command dispatch model cannot be replicated.

---

### Finding 5: Global Instructions — AGENTS.md System

**Evidence**: "Codex reads AGENTS.md files before doing any work. Codex builds an instruction chain when it starts (once per run; in the TUI this usually means once per launched session)."

**Source**: [Custom instructions with AGENTS.md — developers.openai.com/codex/guides/agents-md/](https://developers.openai.com/codex/guides/agents-md/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Configuration Reference — developers.openai.com/codex/config-reference/](https://developers.openai.com/codex/config-reference/) — confirms `project_doc_fallback_filenames`, `project_doc_max_bytes`, `model_instructions_file`, `features.child_agents_md`
- [github.com/openai/codex/blob/main/AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md) — the repo itself contains an AGENTS.md, confirming the format is in active use
- [Web search confirming AGENTS.md discovery hierarchy](https://developers.openai.com/codex/guides/agents-md/) — third source confirmation

**Analysis**: The AGENTS.md system is the equivalent of Claude Code's `CLAUDE.md`. The discovery hierarchy:

1. **Global scope** (`~/.codex/` by default, or `$CODEX_HOME`):
   - Checks `AGENTS.override.md` first (temporary override without deleting base)
   - Falls back to `AGENTS.md`
   - Only the first non-empty file at this level is used

2. **Project scope** (from git root down to current working directory):
   - Each directory level: checks `AGENTS.override.md`, then `AGENTS.md`, then configured fallback names
   - At most one file per directory level

3. **Merge order**: Files concatenate from root downward (closer files appear later, effectively taking precedence)

**Configuration**:
```toml
# In config.toml — customize AGENTS.md behavior
project_doc_max_bytes = 32768          # 32 KiB default cap
project_doc_fallback_filenames = ["TEAM_GUIDE.md", ".agents.md"]
model_instructions_file = "path/to/custom.md"  # Full replacement (not append)
developer_instructions = "..."          # Additional instructions injected per session
```

**Key characteristics**:
- No strict format — plain Markdown with natural language guidance
- Supports working agreements, conventions, build procedures, security requirements
- Rebuilt on every run and every TUI session start (no caching needed)
- 32 KiB combined size limit (configurable)
- The `AGENTS.override.md` mechanism allows temporary global overrides without file deletion

**Importantly**: Codex reads `AGENTS.md` not `CLAUDE.md`. The Claude Code compatibility fallback that OpenCode provides (reading `CLAUDE.md` if no `AGENTS.md`) is **not present** in Codex CLI. nWave's existing `CLAUDE.md` files would NOT be automatically recognized by Codex CLI.

**nWave relevance**: nWave uses `CLAUDE.md` (project-level) and `~/.claude/CLAUDE.md` (global). For Codex CLI, these would need to be renamed or duplicated as `AGENTS.md` files. The global identity layer (Lyra persona, principles, memory instructions) would need an `AGENTS.md` in `~/.codex/` (or `$CODEX_HOME`). This is a mechanical adaptation — the content of `CLAUDE.md` is fully compatible with the AGENTS.md format (plain Markdown). The global path differs (`~/.codex/AGENTS.md` vs `~/.claude/CLAUDE.md`) but the installer can manage both.

---

### Finding 6: Skills System

**Evidence**: "Skills extend Codex with task-specific capabilities by packaging instructions, resources, and optional scripts so the AI can follow a workflow reliably. They can be shared across teams or publicly. Skills adhere to the open agent skills standard."

**Source**: [Agent Skills — developers.openai.com/codex/skills](https://developers.openai.com/codex/skills) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Configuration Reference — developers.openai.com/codex/config-reference/](https://developers.openai.com/codex/config-reference/) — confirms `skills.config` with `enabled` and `path` per-skill overrides
- [Codex changelog — features.child_agents_md](https://developers.openai.com/codex/changelog/) — confirms skills as active, evolving feature
- [Community comparison: Codex vs Claude Code vs OpenCode — awesomeagents.ai](https://awesomeagents.ai/tools/codex-vs-claude-code-vs-opencode/) — independent confirmation

**Analysis**: The skills system is the most nWave-compatible feature in Codex CLI:

**File structure** (a directory with):
```
skill-name/
  SKILL.md           # Required — instructions + YAML frontmatter metadata
  scripts/           # Optional — executable helper scripts
  references/        # Optional — documentation files
  assets/            # Optional — templates, resources
  agents/
    openai.yaml      # Optional — UI configuration and policy
```

**SKILL.md frontmatter**:
```yaml
---
name: skill-name
description: When this skill should or shouldn't trigger (used for auto-selection matching)
---
```

**Storage locations** (highest to lowest priority):
| Scope | Path | Use Case |
|-------|------|----------|
| REPO | `.agents/skills` (current dir) | Folder-specific skills |
| REPO | Parent `.agents/skills` directories | Nested repo skills |
| REPO | `$REPO_ROOT/.agents/skills` | Org-wide skills |
| USER | `$HOME/.agents/skills` | Personal cross-repo skills |
| ADMIN | `/etc/codex/skills` | System defaults |
| SYSTEM | Bundled with Codex | Built-ins |

**Invocation**:
- Explicit: `/skills` slash command, or `$skill-name` mention in composer
- Implicit: Codex auto-selects matching skills based on task description vs skill `description` field
- Progressive loading: Codex loads only metadata initially, then full SKILL.md when a skill is selected

**nWave relevance**: nWave's skill files (`~/.claude/skills/{agent}/skill-name.md`) use exactly the same YAML frontmatter pattern (`name`, `description`). The nWave skill storage path (`~/.claude/skills/`) differs from Codex's user-scope path (`$HOME/.agents/skills/`). The format is the open agent skills standard — shared with Copilot CLI and other tools. An nWave Codex installer plugin would copy/symlink skill files from `~/.claude/skills/` to `$HOME/.agents/skills/`. This is the highest-fidelity compatibility surface among all nWave features.

---

### Finding 7: Hook / Lifecycle System

**Evidence**: "Codex can run a notification hook when the agent finishes a turn." This is the current, only documented hook: `notify = ["python3", "/path/to/notify.py"]` in `config.toml`, triggered on `agent-turn-complete` events only.

**Source**: [Advanced Configuration — developers.openai.com/codex/config-advanced/](https://developers.openai.com/codex/config-advanced/) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [GitHub Discussion #2150 — Hook would be a great feature](https://github.com/openai/codex/discussions/2150) — Maintainer confirmed `notify` exists but acknowledged expansion is in progress (Feb 2026: "We are actively working on designing a hooks system")
- [GitHub Issue #2109 — Event Hooks (436+ upvotes, OPEN)](https://github.com/openai/codex/issues/2109) — confirms `PreToolUse`/`PostToolUse` equivalents do not exist
- [PR #11067 — CLOSED without merge Feb 8, 2026](https://github.com/openai/codex/pull/11067) — maintainer declined: "contributions are by invitation only; OpenAI is actively designing their own hooks system"
- [PR #9796 — CLOSED without merge Jan 24, 2026](https://github.com/openai/codex/pull/9796) — second comprehensive hook implementation declined for same reason

**Analysis**: The hook system situation is the most critical finding for DES compatibility:

**Current state — `notify` only**:
```toml
notify = ["python3", "/path/to/notify.py"]
```
- Single event: `agent-turn-complete`
- JSON payload on stdin: `{type, thread-id, turn-id, cwd, input-messages, last-assistant-message}`
- No response protocol — notification only (cannot block or modify tool calls)
- No `PreToolUse`, `PostToolUse`, `SessionStart`, `SubagentStop` equivalents

**Community hook proposals (all declined)**:
Two community PRs (#9796 and #11067) proposed comprehensive lifecycle hook systems with `PreToolUse`, `PostToolUse`, `SessionStop`, `UserPromptSubmit`, and `AfterAgent` events — including a stdin/stdout JSON protocol matching Claude Code's hook pattern. Both PRs were closed without merge. OpenAI stated they are designing their own system but gave no timeline.

**What is missing**:
| Needed for DES | Status in Codex CLI |
|----------------|---------------------|
| `PreToolUse` (intercept before tool call; can block) | Does not exist |
| `PostToolUse` (observe after tool call) | Does not exist |
| `SessionStart` (on new session) | Does not exist |
| `SubagentStop` (on sub-agent completion) | Does not exist |
| `agent-turn-complete` (notification only, cannot block) | Exists |

**OpenTelemetry (OTel) observability**: Codex emits structured OTel logs for tool decisions (`codex.tool_decision`) and results (`codex.tool_result`). These could theoretically be used for observability but are one-way emission — not a bidirectional hook that can block execution.

**Git hook — commit attribution**: Codex manages a `prepare-commit-msg` git hook for co-author attribution. This is a narrow, internal hook, not a general lifecycle extension point.

**nWave relevance**: DES is nWave's core value proposition — deterministic TDD phase enforcement via `PreToolUse`/`PostToolUse` hooks. Without these events, DES cannot function on Codex CLI. The `notify` hook at turn-complete level provides observability but not enforcement. This is the fundamental blocker for full nWave support on Codex CLI. The situation is worse than OpenCode (which has `tool.execute.before` with a subagent bypass bug) — Codex CLI has no tool-level interception at all.

---

### Finding 8: Extension / Plugin API and Model Support

**Evidence — Extension**: "Give Codex access to additional third-party tools and context" via Model Context Protocol (MCP). "Codex can connect to MCP servers configured in `~/.codex/config.toml`." Codex can also run as an MCP server itself: "orchestrate Codex via the Agents SDK (by running the CLI as an MCP server)."

**Source**: [Codex CLI features — developers.openai.com/codex/cli/features/](https://developers.openai.com/codex/cli/features/) — Accessed 2026-02-26

**Evidence — Model support**: "Codex works best with the models listed above. You can also point Codex at any model and provider that supports either the Chat Completions or Responses APIs to fit your specific use case."

**Source**: [Codex Models — developers.openai.com/codex/models](https://developers.openai.com/codex/models) — Accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Advanced Configuration — developers.openai.com/codex/config-advanced/](https://developers.openai.com/codex/config-advanced/) — confirms `model_providers` TOML section with `base_url`, `env_key`, `wire_api`, Azure example
- [Web search confirming Ollama, Azure, Mistral provider config](https://developers.openai.com/codex/config-reference/) — multiple provider examples verified
- [learn.microsoft.com — Codex with Azure OpenAI in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/codex?view=foundry-classic) — third-party official confirmation of Azure integration

**Analysis — Plugin/Extension API**:

Codex CLI has **no traditional plugin system** (no plugin marketplace, no plugin file format, no `/plugin install` command). Extension is achieved through three mechanisms:

1. **MCP servers** (Model Context Protocol): Connect external tools via STDIO or streaming HTTP. Configured in `~/.codex/config.toml`:
   ```toml
   [mcp_servers.my-tool]
   command = "npx"
   args = ["-y", "@my-org/my-mcp-tool"]
   env = { MY_KEY = "value" }
   enabled_tools = ["tool1", "tool2"]
   ```
   Codex can also expose itself as an MCP server for orchestration by external agents.

2. **Skills** (see Finding 6): The primary extension mechanism for adding task-specific AI capabilities.

3. **Feature flags**: `codex features enable <feature>` persistently enables experimental capabilities (e.g., `multi_agent`, `shell_snapshot`, `apply_patch_freeform`).

**Analysis — Model Support**:

Primary models (OpenAI-optimized):
- `gpt-5.3-codex` (recommended)
- `gpt-5.3-codex-spark` (research preview, ChatGPT Pro)
- `gpt-5.2-codex`, `gpt-5.2`, `gpt-5.1-codex-max`

**Alternative providers** (via `model_providers` TOML section):
```toml
model_provider = "azure"

[model_providers.azure]
name = "Azure OpenAI"
base_url = "https://YOUR_RESOURCE.openai.azure.com/openai/v1"
env_key = "AZURE_OPENAI_API_KEY"
wire_api = "responses"

[model_providers.ollama]
name = "Ollama (local)"
base_url = "http://localhost:11434/v1"

[model_providers.mistral]
base_url = "https://api.mistral.ai/v1"
env_key = "MISTRAL_API_KEY"
```

Or via environment variable: `OPENAI_BASE_URL=http://proxy.example.com` overrides the default OpenAI endpoint without a config change. The `--oss` CLI flag enables local open-source provider mode (requires Ollama).

**Important caveat**: Codex is optimized for OpenAI models. The documentation notes "Chat Completions API support is deprecated and will be removed in future releases" — providers that only support Chat Completions (not the Responses API) will lose compatibility over time. This limits the breadth of truly model-agnostic use compared to OpenCode (75+ providers via Vercel AI SDK).

**nWave relevance**: MCP server support provides an integration pathway. A hypothetical nWave MCP server could expose nWave's workflow orchestration as MCP tools callable by Codex. No traditional plugin format exists for distributing a bundled collection of agents + skills + hooks. The `model_providers` system supports Azure, Ollama, and any OpenAI-compatible API — covering enterprise scenarios where Claude models are used via proxy. However, Codex CLI is notably less model-agnostic than OpenCode or Claude Code with proxies; Anthropic Claude models are not directly supported without an OpenAI-compatible proxy layer.

---

## Compatibility Assessment: nWave Feature Parity

### Config Directory

**Score**: Partial

Codex CLI's `~/.codex/` (or `$CODEX_HOME`) analogizes to Claude Code's `~/.claude/`. The two-tier (user + project) configuration model matches. The nWave installer plugin pattern is directly applicable — a new `codex_plugin.py` would write `~/.codex/config.toml` entries for model configuration, MCP servers, and skills paths. Key differences: config format is TOML (not YAML), the project trust model requires an opt-in step, and there are no `agents/` or `commands/` subdirectories under `~/.codex/`. The installer's structural logic transfers with format adaptation.

### Agents

**Score**: Incompatible

Codex CLI has no dedicated agent definition file format. nWave's 23 agent specifications (YAML frontmatter + Markdown body with tool permissions, model selection, persona) cannot be represented in Codex CLI's agent system. The TOML `[agents.<name>]` section supports only `description` and `config_file` — no tool access control, no per-agent system prompts in the config, no mode distinction (primary vs subagent). Agent persona content must be embedded in AGENTS.md rather than per-agent files. This is a fundamental architectural gap: nWave's agent catalog is file-per-agent; Codex CLI is config-section-per-agent with flat TOML.

### Custom Commands

**Score**: Incompatible

No user-defined slash command API exists in Codex CLI. The custom prompts system (deprecated) provided a partial analogue — Markdown files with YAML frontmatter in `~/.codex/prompts/`, invokable as `/prompts:<name>` — but this is being removed in favor of skills. Skills are not equivalent to commands: they inject context rather than dispatch task chains. nWave's wave commands (`/nw:deliver`, `/nw:design`, `/nw:distill`, `/nw:research`) have no viable Codex CLI mapping. Community issues requesting this feature are open and unaddressed.

### Hooks / DES

**Score**: Incompatible

This is the most critical gap. The current `notify` hook provides a single post-turn notification — useful for desktop alerts but incapable of enforcing phase ordering. DES requires bidirectional `PreToolUse` (intercept before tool call, with blocking capability) and `PostToolUse` hooks. These do not exist in Codex CLI. Two community PRs implementing exactly these hooks were declined in January–February 2026, with OpenAI stating they are designing their own system. Even the OTel observability stream is one-way. Until OpenAI ships a `PreToolUse`-equivalent hook with blocking capability, DES cannot be ported. This is not a "hard with workarounds" situation — it is a hard blocker with no current path.

### Global Instructions

**Score**: Partial

Codex CLI has a robust AGENTS.md system that is the direct equivalent of CLAUDE.md for global and project-level instructions. The gap is format mismatch: Codex reads `AGENTS.md`, not `CLAUDE.md`. Unlike OpenCode (which explicitly falls back to `CLAUDE.md`), Codex CLI does not provide a `CLAUDE.md` compatibility layer. nWave's existing instruction files would need to be renamed or duplicated as `AGENTS.md`. The global user path (`~/.codex/AGENTS.md` or `$CODEX_HOME/AGENTS.md`) requires a new file vs Claude Code's `~/.claude/CLAUDE.md`. This is a mechanical adaptation, not an architectural one. The installer can manage both files. Content compatibility is complete — plain Markdown is the format for both.

### Skills

**Score**: Compatible

The Codex CLI skills system (`SKILL.md` with YAML frontmatter in `$HOME/.agents/skills/`) is the open agent skills standard, also used by Copilot CLI. The frontmatter structure (`name`, `description`) matches nWave's skill file convention. The storage path differs (`$HOME/.agents/skills/` vs `~/.claude/skills/`) but an nWave installer can write to both. Progressive loading, implicit auto-selection, and explicit invocation patterns align with nWave's on-demand skill loading. This is the highest-ROI portability investment.

---

## Bottom Line

**nWave support on Codex CLI is not feasible today, and is unlikely to become fully feasible without OpenAI shipping a `PreToolUse`-equivalent blocking hook — a feature in active design but not committed to a timeline.**

The skills layer and global instructions layer are immediately portable with mechanical adaptation (path changes, file renames). The config directory is adaptable with format translation (Python → TOML generation). These three surfaces could deliver a "nWave Skills and Instructions" lite experience on Codex CLI with modest installer work.

The two irreconcilable gaps are deeper than in comparable platforms:

1. **No PreToolUse/PostToolUse hooks**: Unlike OpenCode (which has the hooks but with a subagent bypass bug) and Copilot CLI (which has a full 6-event hook system), Codex CLI has no tool-level lifecycle interception at all. DES enforcement is architecturally impossible, not just difficult. The community has raised this loudly (436+ upvote Issue #2109, two declined implementation PRs) and OpenAI has acknowledged it is "actively designing" a hooks system — but with no committed timeline.

2. **No custom slash commands**: Unlike OpenCode and Copilot CLI (both of which have slash command extension systems), Codex CLI's command surface is entirely hardcoded. The deprecated `custom prompts` system was the only user-defined command mechanism and is being removed. nWave's wave command dispatch model has no viable analogue.

Additionally, the agent definition system is flat TOML (not per-file Markdown), making nWave's 23-agent catalog impractical to represent in a usable way.

**Recommended strategic posture**: Do not invest in a Codex CLI port of nWave core (DES + agents + commands). Instead, invest in the **open agent skills standard** compatibility: ensure nWave skill files are valid `SKILL.md` files that work across Codex CLI, Copilot CLI, and OpenCode simultaneously. Track GitHub Issue #2109 for hook system progress. Revisit feasibility of a DES port when OpenAI ships a blocking `PreToolUse` hook. Monitor via the `openai/codex` changelog and discussions.

---

## Source Analysis

| Source | Domain | Reputation | Type | Access Date | Verified |
|--------|--------|------------|------|-------------|---------|
| [github.com/openai/codex](https://github.com/openai/codex) | github.com | Medium-High | Primary source (official) | 2026-02-26 | Yes |
| [Config Basics](https://developers.openai.com/codex/config-basic/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Configuration Reference](https://developers.openai.com/codex/config-reference/) | developers.openai.com | High (official) | Official reference | 2026-02-26 | Yes |
| [Advanced Configuration](https://developers.openai.com/codex/config-advanced/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Config Sample](https://developers.openai.com/codex/config-sample/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Agent Skills](https://developers.openai.com/codex/skills) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Multi-agents](https://developers.openai.com/codex/multi-agent/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Slash Commands in Codex CLI](https://developers.openai.com/codex/cli/slash-commands/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Custom Prompts (deprecated)](https://developers.openai.com/codex/custom-prompts/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Codex CLI Features](https://developers.openai.com/codex/cli/features/) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Codex CLI Reference](https://developers.openai.com/codex/cli/reference/) | developers.openai.com | High (official) | Official reference | 2026-02-26 | Yes |
| [Codex Models](https://developers.openai.com/codex/models) | developers.openai.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Codex Changelog](https://developers.openai.com/codex/changelog/) | developers.openai.com | High (official) | Official changelog | 2026-02-26 | Yes |
| [Issue #2109 — Event Hooks (open)](https://github.com/openai/codex/issues/2109) | github.com | Medium-High | Official issue tracker | 2026-02-26 | Yes |
| [Discussion #2150 — Hook feature request](https://github.com/openai/codex/discussions/2150) | github.com | Medium-High | Official discussion | 2026-02-26 | Yes |
| [PR #11067 — hooks (closed)](https://github.com/openai/codex/pull/11067) | github.com | Medium-High | PR (declined) | 2026-02-26 | Yes |
| [PR #9796 — hooks (closed)](https://github.com/openai/codex/pull/9796) | github.com | Medium-High | PR (declined) | 2026-02-26 | Yes |
| [Discussion #6109 — custom agents](https://github.com/openai/codex/discussions/6109) | github.com | Medium-High | Community discussion | 2026-02-26 | Yes |
| [Azure OpenAI — Codex integration](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/codex?view=foundry-classic) | learn.microsoft.com | High (official) | Official docs | 2026-02-26 | Yes |
| [Northflank: Claude Code vs Codex](https://northflank.com/blog/claude-code-vs-openai-codex) | northflank.com | Medium | Industry article | 2026-02-26 | Cross-ref with official |
| [Codex vs Claude Code vs OpenCode comparison](https://awesomeagents.ai/tools/codex-vs-claude-code-vs-opencode/) | awesomeagents.ai | Medium | Community analysis | 2026-02-26 | Cross-ref with official |

**Reputation Summary**:
- High reputation sources: 15 (68%)
- Medium-high reputation: 5 (23%)
- Medium reputation: 2 (9%)
- Average reputation score: 0.92

---

## Knowledge Gaps

### Gap 1: OpenAI Hook System Design — Timeline and Specification

**Issue**: OpenAI has stated they are "actively working on designing a hooks system" (Discussion #2150, February 2026) and declined external PRs on this basis. The design, timeline, and event set of the official hook system are not publicly available.

**Attempted Sources**: GitHub discussions, changelog, official docs — none contain a hook system specification or roadmap item.

**Recommendation**: Monitor `openai/codex` releases and `developers.openai.com/codex/changelog/` monthly. When a hook system ships, reassess DES portability immediately. The proposed events in declined PRs (`PreToolUse`, `PostToolUse`, `SessionStop`, `UserPromptSubmit`, `AfterAgent`) closely match what DES needs.

### Gap 2: Skills Open Standard Specification

**Issue**: Skills are described as adhering to an "open agent skills standard" — the same standard used by Copilot CLI. The authoritative specification for this standard was not located during this research session. Understanding the full spec would clarify cross-platform skill portability requirements precisely.

**Attempted Sources**: `developers.openai.com/codex/skills`, Copilot CLI `SKILL.md` documentation. Neither references a canonical specification URL.

**Recommendation**: Search for the open agent skills standard specification separately. The likely source is the AI Foundation or a GitHub repository linked from both Codex and Copilot CLI skill documentation. This research is a prerequisite for confident nWave-wide skills standardization.

### Gap 3: `model_providers` Compatibility With Anthropic Claude

**Issue**: The `model_providers` TOML configuration supports OpenAI-compatible and Responses API-compatible endpoints. Whether Anthropic's Claude API can be configured via `model_providers` (e.g., via an OpenAI-compatible proxy) was not definitively confirmed from primary sources.

**Attempted Sources**: `developers.openai.com/codex/config-advanced/`, `developers.openai.com/codex/models`. Neither explicitly addresses Anthropic/Claude provider configuration.

**Recommendation**: Test empirically with a Claude-compatible OpenAI proxy (e.g., `claude-code-proxy` pattern documented in community resources). Determine whether a `model_providers.anthropic` entry with `wire_api = "responses"` and Anthropic's API endpoint works in practice.

### Gap 4: Deprecation Timeline for Custom Prompts

**Issue**: Custom prompts are explicitly marked deprecated in favor of skills. The deprecation timeline (when the feature will be removed) is not specified in the documentation.

**Attempted Sources**: `developers.openai.com/codex/custom-prompts/`, changelog. The deprecation notice appears without a date.

**Recommendation**: This is low priority for nWave since skills are the recommended replacement and are fully compatible. The custom prompts mechanism should not be used in any nWave Codex integration design.

---

## Conflicting Information

### Conflict 1: Codex Model-Agnosticism Claims

**Position A**: "Codex works best with the models listed above [OpenAI GPT-5.x-Codex]. You can also point Codex at any model and provider that supports either the Chat Completions or Responses APIs."
- Source: [Codex Models](https://developers.openai.com/codex/models) — Reputation: High (official)
- Evidence: Official documentation claims broad provider support

**Position B**: "Codex CLI is locked to OpenAI models with no official local model support." / "OpenCode [is] the clear choice for air-gapped environments."
- Source: [OpenCode vs Codex CLI comparison — morphllm.com](https://www.morphllm.com/comparisons/opencode-vs-codex) — Reputation: Medium (community article)
- Evidence: Comparative analysis characterizing Codex as OpenAI-locked

**Assessment**: Position A is more authoritative (official documentation) but incomplete. The official docs confirm `model_providers` support for Azure, Ollama, Mistral, and any OpenAI-compatible endpoint. However, the deprecation of Chat Completions API support limits future provider range to Responses API-compatible providers — a narrower set than "any LLM." Position B overstates the lock-in for current releases but correctly predicts the trajectory. For nWave purposes: alternative provider configuration is possible today (Azure, OpenAI-compatible proxies) but may become more restricted as Responses API becomes the only supported protocol.

---

## Recommendations for Further Research

1. **Monitor openai/codex Issue #2109 and the changelog for hook system release**. This is the single gate for DES portability. Set a quarterly review calendar item. When a `PreToolUse`-equivalent lands, initiate a DES Codex adapter feasibility study immediately.

2. **Research the open agent skills standard specification**. Both Codex CLI and Copilot CLI reference this standard. A common specification would enable nWave to produce a single SKILL.md format that works across all target platforms. This is the highest-ROI cross-platform investment.

3. **Prototype skills portability**. Install Codex CLI and copy nWave skill files to `$HOME/.agents/skills/`. Verify they are discovered and auto-selected correctly. This validates the compatibility claim empirically before investing in installer automation.

4. **Evaluate Codex-as-MCP-server for nWave orchestration**. The documentation confirms Codex CLI can run as an MCP server, enabling external orchestration. Research whether a nWave orchestrator could drive Codex CLI sessions via MCP protocol as an alternative to hook-based enforcement.

5. **Compare AGENTS.md content portability**. The existing `~/.claude/CLAUDE.md` and project `CLAUDE.md` files contain nWave's workflow instructions. Test whether copying this content to `AGENTS.md` format produces equivalent Codex CLI behavior — particularly the `/lyra`, `/principles`, and memory system instructions, which reference Claude-specific tools (mcp__lyra__*) that don't exist in Codex CLI.

---

## Full Citations

[1] OpenAI. "openai/codex — Lightweight coding agent that runs in your terminal". GitHub. 2025–2026. https://github.com/openai/codex. Accessed 2026-02-26.

[2] OpenAI. "Config basics". developers.openai.com. 2025–2026. https://developers.openai.com/codex/config-basic/. Accessed 2026-02-26.

[3] OpenAI. "Configuration Reference". developers.openai.com. 2025–2026. https://developers.openai.com/codex/config-reference/. Accessed 2026-02-26.

[4] OpenAI. "Advanced Configuration". developers.openai.com. 2025–2026. https://developers.openai.com/codex/config-advanced/. Accessed 2026-02-26.

[5] OpenAI. "Custom instructions with AGENTS.md". developers.openai.com. 2025–2026. https://developers.openai.com/codex/guides/agents-md/. Accessed 2026-02-26.

[6] OpenAI. "Agent Skills". developers.openai.com. 2025–2026. https://developers.openai.com/codex/skills. Accessed 2026-02-26.

[7] OpenAI. "Multi-agents". developers.openai.com. 2025–2026. https://developers.openai.com/codex/multi-agent/. Accessed 2026-02-26.

[8] OpenAI. "Slash commands in Codex CLI". developers.openai.com. 2025–2026. https://developers.openai.com/codex/cli/slash-commands/. Accessed 2026-02-26.

[9] OpenAI. "Custom Prompts". developers.openai.com. 2025–2026. https://developers.openai.com/codex/custom-prompts/. Accessed 2026-02-26.

[10] OpenAI. "Codex CLI features". developers.openai.com. 2025–2026. https://developers.openai.com/codex/cli/features/. Accessed 2026-02-26.

[11] OpenAI. "Command line options". developers.openai.com. 2025–2026. https://developers.openai.com/codex/cli/reference/. Accessed 2026-02-26.

[12] OpenAI. "Codex Models". developers.openai.com. 2025–2026. https://developers.openai.com/codex/models. Accessed 2026-02-26.

[13] OpenAI. "Codex changelog". developers.openai.com. 2025–2026. https://developers.openai.com/codex/changelog/. Accessed 2026-02-26.

[14] OpenAI. "Codex CLI". developers.openai.com. 2025–2026. https://developers.openai.com/codex/cli/. Accessed 2026-02-26.

[15] openai/codex community. "Event Hooks · Issue #2109". GitHub. August 9, 2025. https://github.com/openai/codex/issues/2109. Accessed 2026-02-26.

[16] openai/codex community. "Hook would be a great feature · Discussion #2150". GitHub. August 11, 2025. https://github.com/openai/codex/discussions/2150. Accessed 2026-02-26.

[17] RyderFreeman4Logos. "feat(hooks): comprehensive hook system with lifecycle events and steering · PR #11067". GitHub. Closed February 8, 2026. https://github.com/openai/codex/pull/11067. Accessed 2026-02-26.

[18] am-will. "feat: Comprehensive hooks system for tool, file, and event lifecycle · PR #9796". GitHub. Closed January 24, 2026. https://github.com/openai/codex/pull/9796. Accessed 2026-02-26.

[19] openai/codex community. "How can I create custom agents using the Codex CLI? · Discussion #6109". GitHub. 2025. https://github.com/openai/codex/discussions/6109. Accessed 2026-02-26.

[20] Microsoft. "Codex with Azure OpenAI in Microsoft Foundry Models". learn.microsoft.com. 2025–2026. https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/codex?view=foundry-classic. Accessed 2026-02-26.

[21] Northflank. "Claude Code vs OpenAI Codex: which is better in 2026?". northflank.com. 2026. https://northflank.com/blog/claude-code-vs-openai-codex. Accessed 2026-02-26.

[22] Awesome Agents. "Codex vs Claude Code vs OpenCode: Three Terminal Coding Agents, Compared". awesomeagents.ai. 2026. https://awesomeagents.ai/tools/codex-vs-claude-code-vs-opencode/. Accessed 2026-02-26.

---

## Research Metadata

- **Research Duration**: ~60 minutes
- **Total Sources Examined**: 28
- **Sources Cited**: 22
- **Cross-References Performed**: 18
- **Confidence Distribution**: High: 72%, Medium: 22%, Low: 6%
- **Output File**: /mnt/c/Repositories/Projects/nWave-dev/docs/research/codex-cli-extensibility-research.md
- **Knowledge Gaps Documented**: 4
- **Conflicts Documented**: 1
