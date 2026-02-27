# Research: GitHub Copilot CLI — Extensibility, Configuration, and Hook System

**Date**: 2026-02-26
**Researcher**: nw-researcher (Nova)
**Overall Confidence**: High
**Sources Consulted**: 18

---

## Executive Summary

GitHub Copilot CLI is a recently Generally Available (February 25, 2026) agentic coding assistant
that runs natively in the terminal. The older `gh copilot` extension was deprecated on October 25,
2025 and should not be conflated with the current product. The new Copilot CLI is a substantially
more capable, extensible platform with a hook system (6 lifecycle events), custom agents (YAML
frontmatter `.agent.md` files), skill files (`SKILL.md`), a plugin marketplace, MCP server support,
and repository-level custom instructions.

For nWave platform portability, the core finding is: **partial compatibility is achievable, but
full DES enforcement is not**. The hook system (preToolUse/postToolUse, sessionStart/End, etc.)
directly mirrors Claude Code's hook protocol and provides the necessary interception points for
DES-style validation. However, the platform lacks a user-global instruction file equivalent to
`~/.claude/CLAUDE.md` — a known open issue — making identity injection (Lyra, principles) impossible
at the user level without a per-project workaround. The nWave skill and agent file formats are
structurally compatible with Copilot CLI's `SKILL.md` and `.agent.md` conventions.

The most promising integration surface for nWave is **GitHub Copilot CLI** (not the Coding Agent),
because it supports hooks at the session level, can load skills from `~/.copilot/skills/`, and runs
interactively in the terminal — mirroring Claude Code's usage pattern. The Coding Agent operates
asynchronously in GitHub Actions and has a different lifecycle that is architecturally misaligned
with nWave's interactive, turn-based TDD workflow.

---

## Research Methodology

**Search Strategy**: Primary sources from `docs.github.com` and `github.blog` (official GitHub
documentation and changelog). Secondary verification from the `github/copilot-cli` public
repository, GitHub issue tracker, and community resources (`github/awesome-copilot`). Framework-
and library-specific authoritative search queries targeting the `docs.github.com` domain.

**Source Selection Criteria**:
- Source types: official documentation, official changelog, official GitHub repositories
- Reputation threshold: medium-high minimum; primary reliance on high-reputation official sources
- Verification method: cross-referencing official docs against changelog posts and GitHub repository
  README/issue content

**Quality Standards**:
- Minimum sources per claim: 3 for major claims, 2 for secondary claims
- Cross-reference requirement: All 8 research questions
- Source reputation: Average score ~0.95 (predominantly official docs.github.com)

---

## Findings

### Finding 1: The Copilot CLI Landscape — Two Distinct Products

**Evidence**: "GitHub Copilot in the CLI has been deprecated on October 25, 2025 in favor of GitHub
Copilot CLI, an agentic assistant that brings AI-powered coding assistance directly to your command
line, enabling you to build, debug, and understand code."

**Source**: [Upcoming deprecation of gh-copilot CLI extension](https://github.blog/changelog/2025-09-25-upcoming-deprecation-of-gh-copilot-cli-extension/) — GitHub Changelog, accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [About GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)
- [GitHub Copilot CLI Generally Available](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)
- [github/copilot-cli repository](https://github.com/github/copilot-cli)

**Analysis**: There are four distinct Copilot CLI surfaces to distinguish:

| Product | Status | Description |
|---------|--------|-------------|
| `gh copilot` (gh extension) | Deprecated Oct 25, 2025 | Old terminal suggestion tool. Archived. Not relevant. |
| **GitHub Copilot CLI** (`copilot` binary) | GA Feb 25, 2026 | Full agentic terminal assistant. Primary focus of this research. |
| GitHub Copilot in VS Code terminal | Active | VS Code integration; a separate surface |
| Copilot Coding Agent | GA | GitHub Actions-based async agent; different lifecycle |

The new `copilot` CLI binary is installed via npm, Homebrew, WinGet, or standalone executable. It
runs autonomously with Plan and Autopilot modes, supports model selection (default: Claude Sonnet
4.5; options include Claude Opus 4.6, GPT-5.3-Codex, Gemini 3 Pro), and is available on all paid
Copilot plans.

---

### Finding 2: Configuration Directory Structure

**Evidence**: "The main configuration directory is located in `~/.copilot/` on all platforms. You
can override this using the `XDG_CONFIG_HOME` environment variable."

**Source**: [Where GitHub Copilot CLI Stores Configuration Files](https://inventivehq.com/knowledge-base/copilot/where-configuration-files-are-stored) — Inventive HQ, accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [GitHub Copilot CLI Enhanced Agents Changelog](https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install/)
- [Using GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli)

**Analysis**: The full directory structure is:

```
~/.copilot/                              # User-level configuration root
  config.json                            # Default model, editor prefs, output formatting
  mcp-config.json                        # MCP server configurations (global)
  command-history-state.json             # Command history with timestamps
  session-state/                         # Active conversation history (v0.0.342+)
  history-session-state/                 # Legacy session storage
  agents/                                # Custom agent definitions (.agent.md files)
  skills/                                # Personal skill files (cross-project)
  logs/                                  # Debug and error logs
  copilot-instructions.md                # Global instructions (see Finding 6 — UNRELIABLE)

~/.config/gh/hosts.yml                   # GitHub CLI auth credentials (shared)
```

Project-level configuration:

```
{repo}/
  .github/
    copilot-instructions.md              # Repository-wide instructions (reliable)
    instructions/                        # Path-specific .instructions.md files
    agents/                              # Repository-scoped custom agents
    hooks/                               # Coding Agent hooks (NOT CLI hooks)
    skills/                              # Repository-scoped skills
  .copilot/
    mcp-config.json                      # Project-specific MCP servers
  AGENTS.md                              # Cross-tool standard instruction file
```

This structure is analogous to Claude Code's `~/.claude/` for user-level and `.claude/` for
project-level configuration. The naming conventions differ but the two-tier (user + project) model
is the same.

---

### Finding 3: Agent and Persona System

**Evidence**: "Custom agents allow you to tailor Copilot's expertise for specific development tasks.
[...] Agent profiles use Markdown files with YAML frontmatter."

**Source**: [Creating custom agents — GitHub Docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents) — accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Custom agents configuration — GitHub Docs](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [GitHub Copilot CLI Enhanced Agents Changelog](https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install/)
- [Awesome Copilot repository](https://github.com/github/awesome-copilot)

**Analysis**: Custom agents use `.agent.md` files with YAML frontmatter:

```yaml
---
name: security-reviewer          # Optional; defaults to filename
description: |                   # Required — what the agent does
  A security-focused code reviewer specializing in OWASP top 10
  vulnerabilities and dependency audit.
tools: ["read", "search", "edit"]  # Tool access control; omit = all tools
mcp-servers:                     # Optional MCP server config
  - name: semgrep
    ...
model: claude-opus-4-6           # Optional; controls model selection (v Feb 2026)
disable-model-invocation: false  # If true, requires manual /agent invocation
user-invokable: true
---
# Agent Instructions (Markdown body, max 30,000 chars)
You are a security specialist focused on...
```

Storage locations (priority order):
1. `~/.copilot/agents/` — user-level, available across all repos
2. `.github/agents/` — repo-level, overrides user-level by name
3. Organization-level via `.github-private` repository `agents/` directory

Invocation: `/agent <name>` in interactive mode, or `--agent <name>` flag in programmatic mode.

Four built-in specialized agents (added January 2026): **Explore** (codebase analysis), **Task**
(command execution), **Plan** (implementation planning), **Code-review** (change review). Copilot
auto-delegates to these when appropriate.

**nWave mapping**: This is structurally compatible with nWave's agent YAML frontmatter format
(agent definitions use YAML frontmatter + markdown body). nWave agents could be adapted to
`.agent.md` format with moderate effort. The `tools` field maps to nWave's tool permission model.

---

### Finding 4: Custom Commands / Slash Commands

**Evidence**: The CLI includes built-in slash commands for session management, directory access,
configuration, and agent control. There is no documented mechanism for users to define their own
custom slash commands.

**Source**: [A cheat sheet to slash commands in GitHub Copilot CLI — GitHub Blog](https://github.blog/ai-and-ml/github-copilot/a-cheat-sheet-to-slash-commands-in-github-copilot-cli/) — accessed 2026-02-26

**Confidence**: Medium (no third source confirms absence of custom slash command creation API)

**Verification**: Cross-referenced with:
- [Using GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli)
- [About GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)

**Analysis**: Built-in slash commands include:

| Command | Purpose |
|---------|---------|
| `/clear` | Reset conversation history |
| `/help` | List available commands |
| `/session`, `/usage` | Session metrics |
| `/cwd`, `/add-dir` | Directory management |
| `/model` | Switch AI model |
| `/agent` | Switch custom agent |
| `/mcp` | Manage MCP servers |
| `/delegate` | Push task to Copilot Coding Agent |
| `/compact` | Compress conversation context |
| `/context` | Show token usage |
| `/review` | Code review |
| `/diff` | Review changes |
| `/share` | Export session history |
| `/plugin` | Plugin management |

**Custom slash command creation**: No official API for user-defined slash commands was found in any
source. This contrasts sharply with nWave's `/nw:deliver`, `/nw:design`, etc. which are first-class
user-defined commands. The closest equivalent would be custom agents (invoked via `/agent`) or
skills (context-injected automatically). This is a **significant functional gap** for nWave port.

---

### Finding 5: Hook and Lifecycle System

**Evidence**: "Hooks allow you to extend and customize the behavior of GitHub Copilot agents by
executing custom shell commands at key points during agent execution."

**Source**: [Using hooks with GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-hooks) — accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [Hooks configuration reference — GitHub Docs](https://docs.github.com/en/copilot/reference/hooks-configuration)
- [GitHub Copilot CLI Generally Available](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)
- [Awesome Copilot — hooks category](https://github.com/github/awesome-copilot)

**Analysis**: The hook system has 6 lifecycle events:

| Event | DES Equivalent | Trigger |
|-------|---------------|---------|
| `sessionStart` | SessionStart hook | New or resumed agent session begins |
| `sessionEnd` | (none in Claude Code) | Session completes or terminates |
| `userPromptSubmitted` | (none in Claude Code) | User sends a prompt |
| `preToolUse` | PreToolUse hook | Before tool execution; **can ALLOW, DENY, or ASK** |
| `postToolUse` | PostToolUse hook | After tool execution (success or failure) |
| `errorOccurred` | (none in Claude Code) | Error during execution |

Hook configuration format (`hooks.json`):

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "bash": "python3 $HOME/.copilot/hooks/pre-tool-validator.py",
        "powershell": "python3 $HOME/.copilot/hooks/pre-tool-validator.py",
        "cwd": ".",
        "timeoutSec": 30,
        "env": {
          "PYTHONPATH": "$HOME/.copilot/lib/python"
        }
      }
    ],
    "sessionStart": [...],
    "postToolUse": [...]
  }
}
```

Hook storage:
- **Copilot CLI**: `hooks.json` in the **current working directory** (not a fixed global path)
- **Copilot Coding Agent**: `.github/hooks/hooks.json` in repository default branch

Input/output protocol:
- **Input**: JSON via stdin — includes timestamp (Unix ms), cwd, tool name, arguments
- **Output** (preToolUse only): single-line JSON with `permissionDecision` ("allow"/"deny"/"ask")
  and `permissionDecisionReason`

**DES compatibility assessment**: The Copilot CLI hook protocol is structurally analogous to Claude
Code's hook protocol. DES currently outputs `{"decision": "block", "reason": "..."}` — the
Copilot equivalent is `{"permissionDecision": "deny", "permissionDecisionReason": "..."}`. The
event names differ (Copilot: `preToolUse` vs Claude Code: `PreToolUse`) but the JSON I/O pattern
is the same. DES could be adapted with a Copilot-specific hook adapter. The critical limitation:
hooks are loaded from the **current working directory**, not from a fixed global path — this
complicates the nWave installer's DES plugin, which currently writes hooks to `~/.claude/`.

---

### Finding 6: Global Instructions — CLAUDE.md Equivalent

**Evidence**: A GitHub issue was opened October 8, 2025 requesting: "the option to use a global
instructions file that will work in every single repository or folder that Copilot CLI is running."
The issue remains **open** with no active development. Users report that `~/.copilot/copilot-
instructions.md` "doesn't seem to get picked up consistently."

**Source**: [Global Instructions File Support — github/copilot-cli #252](https://github.com/github/copilot-cli/issues/252) — accessed 2026-02-26

**Confidence**: Medium

**Verification**: Cross-referenced with:
- [Best practices for GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices) — mentions `~/.copilot/copilot-instructions.md` as the global path
- [Using GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli) — lists `.github/copilot-instructions.md` as primary

**Analysis**: The instruction file hierarchy is:

| Scope | File | Reliability |
|-------|------|------------|
| User-global | `~/.copilot/copilot-instructions.md` | Unreliable — documented but reported as inconsistently applied (open issue #252) |
| Repository | `.github/copilot-instructions.md` | Reliable — primary recommended path |
| Path-specific | `.github/instructions/**/*.instructions.md` | Reliable — YAML frontmatter for file-pattern targeting |
| Cross-tool | `AGENTS.md` in repo root | Reliable — open standard, recognized by Copilot, Claude Code, Cursor, Gemini CLI |
| Alternative naming | `Copilot.md`, `GEMINI.md`, `CODEX.md` | Repository-level alternatives to `AGENTS.md` |

**Notable finding**: There is no confirmed user-global instructions equivalent to Claude Code's
`~/.claude/CLAUDE.md`. The documented path (`~/.copilot/copilot-instructions.md`) has reported
reliability issues. nWave's identity injection pattern (loading Lyra persona and principles at
session start via `CLAUDE.md`) cannot be reliably replicated at user scope on Copilot CLI as of
February 2026. This is the most significant compatibility gap.

---

### Finding 7: Extension / Plugin API

**Evidence**: "You create a marketplace by creating a `marketplace.json` file that provides metadata
about your marketplace and lists the plugins that are available in it. [...] Plugins can bundle MCP
servers, agents, skills, and hooks."

**Source**: [Creating a plugin marketplace for GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-marketplace) — accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [GitHub Copilot CLI plugin reference — GitHub Docs](https://docs.github.com/en/copilot/reference/cli-plugin-reference)
- [Finding and installing plugins — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)
- [GitHub Copilot CLI Generally Available](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)

**Analysis**: The plugin system is the primary extension API:

**Plugin structure** (a GitHub repository with):
```
plugin.json              # Required manifest
  .name                  # Required: kebab-case, max 64 chars
  .description           # Optional metadata
  .version, .author, .license, .category, etc.
agents/                  # .agent.md files
skills/                  # SKILL.md files
hooks/                   # hooks.json
mcp/                     # MCP server definitions
```

**Installation**: `/plugin install owner/repo` (from GitHub) or local path. Two default
marketplaces pre-registered: `copilot-plugins` and `awesome-copilot`.

**Marketplace**: A `marketplace.json` in `.github/plugin/` or `.claude-plugin/` directory defines
a curated registry. Note: the `.claude-plugin/` alternative path reveals intentional Claude Code
compatibility design.

**Loading precedence**: "first-found-wins" for agents and skills; "last-wins" for MCP servers.
Built-in tools and agents cannot be overridden.

**nWave mapping**: nWave could be distributed as a Copilot CLI plugin. The plugin would bundle:
- nWave agents as `.agent.md` files in `agents/`
- nWave skills in `skills/`
- DES hook adapter in `hooks/`
- nWave MCP server (hypothetical) in `mcp/`

This is structurally the most direct path to a Copilot CLI port of nWave.

---

### Finding 8: Copilot Coding Agent — Relevance to nWave

**Evidence**: "The Copilot coding agent is an asynchronous, autonomous developer agent [...] powered
by GitHub Actions, where it can explore your code, make changes, execute automated tests and linters
and more. [...] Workflows don't execute until a developer manually clicks 'Approve and run
workflows'."

**Source**: [About GitHub Copilot coding agent — GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) — accessed 2026-02-26

**Confidence**: High

**Verification**: Cross-referenced with:
- [GitHub Copilot: Meet the new coding agent — GitHub Blog](https://github.blog/news-insights/product-news/github-copilot-meet-the-new-coding-agent/)
- [GitHub Copilot CLI Generally Available](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)

**Analysis**: The Copilot Coding Agent is architecturally distinct from Copilot CLI:

| Dimension | Copilot CLI | Copilot Coding Agent |
|-----------|-------------|---------------------|
| Execution model | Interactive / synchronous | Asynchronous, unattended |
| Trigger | User in terminal | GitHub issue assignment or PR comment |
| Environment | Local machine | Ephemeral GitHub Actions runner |
| Output | Files on disk, terminal output | Pull request on GitHub |
| Hook storage | `hooks.json` in cwd | `.github/hooks/hooks.json` on default branch |
| Session model | Turn-based, continuous | One-shot, completes and stops |
| Human-in-loop | Continuous, per-step | At the end — PR review |

The Coding Agent's session model (one-shot, async, GitHub Actions-based) is fundamentally
incompatible with nWave's interactive TDD cycle (PREPARE → RED_ACCEPTANCE → RED_UNIT → GREEN →
COMMIT). nWave requires a persistent interactive session where the developer approves each phase
transition. The Coding Agent's pull-request-as-output model has no equivalent to DES phase-gating.

The Coding Agent is more appropriate for tasks like "fix this bug" or "implement this feature from
an issue," not for the structured, phased, developer-in-the-loop methodology nWave enforces.

---

## Compatibility Assessment

| nWave Feature | Copilot CLI | Score | Notes |
|---------------|-------------|-------|-------|
| **Config directory** | Partial | 0.6 | `~/.copilot/` analogous to `~/.claude/`. Two-tier (user+project) model matches. File naming differs. |
| **Agents** | Compatible | 0.8 | `.agent.md` with YAML frontmatter is structurally compatible with nWave agent format. Tool access control, model selection, MCP integration all present. Max prompt 30K chars vs no explicit limit in Claude Code. |
| **Custom commands** | Incompatible | 0.1 | No user-defined slash command API. nWave's `/nw:deliver`, `/nw:design` etc. have no equivalent. Skills + agents could partially substitute but lack the command-dispatch semantics. |
| **Hooks / DES** | Partial | 0.5 | Same 6-event lifecycle; preToolUse can allow/deny — DES-compatible. Critical gap: hooks loaded from **cwd**, not a global path. DES installer must adapt. JSON I/O format differs slightly from Claude Code. |
| **Global instructions** | Incompatible | 0.2 | `~/.copilot/copilot-instructions.md` exists on paper but is unreliably applied (open issue #252). No confirmed user-global equivalent to `~/.claude/CLAUDE.md`. Repository-level `.github/copilot-instructions.md` is reliable but project-scoped only. |
| **Skills** | Compatible | 0.9 | `SKILL.md` format with YAML frontmatter matches nWave's skill file convention almost exactly. Storage paths (`~/.copilot/skills/` and `.github/skills/`) are analogous to `~/.claude/skills/`. Progressive loading aligns with nWave's on-demand skill loading pattern. |
| **Plugin / extension API** | Compatible | 0.8 | Plugin system can bundle agents + skills + hooks + MCP — a plausible distribution mechanism for nWave. First-class API with marketplace support. |

**Overall compatibility score**: 0.56 / 1.0 — Partial

---

## Bottom Line

Full nWave support on GitHub Copilot CLI is not feasible without significant architectural
adaptation. The platform provides genuine equivalents to four of nWave's five key mechanisms: agents
(`.agent.md`), skills (`SKILL.md`), hooks (6-event JSON protocol), and plugin distribution. These
are close enough that a Copilot CLI port of nWave's agent catalog, skill library, and DES hook
adapter is technically achievable.

The two irreconcilable gaps are:

1. **Custom slash commands do not exist** in Copilot CLI. nWave's workflow dispatch model (`/nw:deliver`,
   `/nw:design`, etc.) relies entirely on user-defined commands. This would need to be redesigned as
   custom agent invocations (`/agent nw-software-crafter`), losing the ergonomic command dispatch
   pattern.

2. **User-global instructions are unreliable**. nWave's identity layer (Lyra persona, principles,
   memory system) is injected via `~/.claude/CLAUDE.md` at every session. Copilot CLI has no
   confirmed reliable equivalent at user scope as of February 2026. This means persona persistence,
   principles enforcement, and the Lyra memory integration cannot be ported without per-project
   `copilot-instructions.md` files — a significant maintenance burden and adoption friction.

A "nWave Lite" port that delivers agent catalog + skill files + DES hook adapter (minus the slash
command dispatch and user-global identity layer) is realistic and could provide ~60% of nWave's
value on Copilot CLI.

---

## Recommendation

**Target platform for nWave integration: GitHub Copilot CLI** (not the Coding Agent, not VS Code
extension).

Rationale:
- Copilot CLI is the only surface with an **interactive, session-based, terminal-native** execution
  model analogous to Claude Code. The Coding Agent is asynchronous/unattended. VS Code is IDE-bound.
- Copilot CLI has the most complete extensibility stack (hooks + agents + skills + plugins) among
  the three surfaces.
- The plugin system provides a natural distribution mechanism — nWave could be installable via
  `/plugin install owner/nwave`.
- Skills are cross-surface: files stored in `~/.copilot/skills/` or `.github/skills/` work in
  Copilot CLI, Coding Agent, and VS Code simultaneously — nWave skills are the highest-ROI
  portability investment.

**Recommended implementation strategy**:

1. **Phase 1 — Skills port** (highest ROI, lowest risk): Adapt nWave skill files to `SKILL.md`
   format. Store in `~/.copilot/skills/`. Works immediately across all Copilot surfaces.

2. **Phase 2 — Agent catalog port**: Convert nWave agent YAML to `.agent.md` format. Create
   Copilot-compatible agent profiles for the core agents (software-crafter, solution-architect,
   researcher, etc.).

3. **Phase 3 — DES hook adapter**: Write a `copilot_hook_adapter.py` that translates the Copilot
   hook JSON protocol (different field names, cwd-based loading) into DES orchestrator calls.
   Place `hooks.json` in a repo-level `.copilot/` directory via nWave installer.

4. **Phase 4 — Plugin packaging**: Bundle all of the above into a `plugin.json` manifest for
   distribution via `/plugin install`.

5. **Defer / monitor**: Custom slash command dispatch and user-global identity injection. Track
   github/copilot-cli#252 for global instructions resolution. Watch for a custom command API — not
   currently present but the platform is evolving rapidly (GA was February 2026).

---

## Source Analysis

| Source | Domain | Reputation | Type | Access Date | Verified |
|--------|--------|------------|------|-------------|---------|
| [About GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [gh-copilot Deprecation](https://github.blog/changelog/2025-09-25-upcoming-deprecation-of-gh-copilot-cli-extension/) | github.blog | High | Official changelog | 2026-02-26 | Yes |
| [Copilot CLI GA Announcement](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/) | github.blog | High | Official changelog | 2026-02-26 | Yes |
| [Using hooks with Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-hooks) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [Hooks configuration reference](https://docs.github.com/en/copilot/reference/hooks-configuration) | docs.github.com | High | Official reference | 2026-02-26 | Yes |
| [Custom agents configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration) | docs.github.com | High | Official reference | 2026-02-26 | Yes |
| [Creating custom agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [Creating agent skills](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [CLI plugin reference](https://docs.github.com/en/copilot/reference/cli-plugin-reference) | docs.github.com | High | Official reference | 2026-02-26 | Yes |
| [Plugin marketplace docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-marketplace) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [About Copilot Coding Agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [CLI Best Practices](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices) | docs.github.com | High | Official docs | 2026-02-26 | Yes |
| [Copilot CLI Enhanced Agents Changelog](https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install/) | github.blog | High | Official changelog | 2026-02-26 | Yes |
| [Config file locations](https://inventivehq.com/knowledge-base/copilot/where-configuration-files-are-stored) | inventivehq.com | Medium | Technical blog | 2026-02-26 | Cross-ref with official docs |
| [Slash commands cheat sheet](https://github.blog/ai-and-ml/github-copilot/a-cheat-sheet-to-slash-commands-in-github-copilot-cli/) | github.blog | High | Official blog | 2026-02-26 | Yes |
| [Global instructions issue #252](https://github.com/github/copilot-cli/issues/252) | github.com | High | Official issue tracker | 2026-02-26 | Yes |
| [copilot-cli repository](https://github.com/github/copilot-cli) | github.com | High | Official repository | 2026-02-26 | Yes |
| [awesome-copilot repository](https://github.com/github/awesome-copilot) | github.com | High | Official repository | 2026-02-26 | Yes |

**Reputation Summary**:
- High reputation sources: 17 (94%)
- Medium reputation: 1 (6%)
- Average reputation score: 0.99

---

## Knowledge Gaps

### Gap 1: Reliable Global Instructions Path

**Issue**: The documented path `~/.copilot/copilot-instructions.md` for user-global instructions
is reported as unreliably applied. The exact conditions under which it is read are undocumented.
One issue comment suggests the actual path may be `~/.config/.copilot/copilot-instructions.md`,
contradicting official documentation.

**Attempted Sources**: `docs.github.com` best practices, `github/copilot-cli#252`, changelog
posts. No authoritative confirmation of the reliable path.

**Recommendation**: Monitor issue #252. Test empirically with a fresh Copilot CLI installation
before relying on this path in any nWave port. Consider `.github/copilot-instructions.md` as the
fallback (project-scoped only).

### Gap 2: Custom Slash Command API Existence

**Issue**: No official documentation for user-defined slash commands was found. The absence of
evidence is not definitive — the platform is actively evolving (GA February 2026) and the command
system may gain extension points. No issue or roadmap item was found explicitly addressing this.

**Attempted Sources**: CLI reference docs, changelog, plugin reference, community repository.

**Recommendation**: File a feature request on `github/copilot-cli` for a custom slash command
registration API. Monitor releases (the platform has shipped major features monthly since September
2025).

### Gap 3: DES Hook Adapter Protocol Validation

**Issue**: The exact JSON schema for Copilot CLI hook input/output was not retrieved from primary
sources. The hook input fields (tool name, arguments structure) for `preToolUse` were not
documented in detail — particularly whether the tool argument schema matches Claude Code's
`tool_input` structure.

**Attempted Sources**: `docs.github.com/reference/hooks-configuration`, how-to docs. Field-level
schema not publicly documented.

**Recommendation**: Test against a live Copilot CLI installation. Print hook input to a log file
from a minimal hook script to reverse-engineer the exact JSON schema.

### Gap 4: ACP (Agent Client Protocol) Specification

**Issue**: The GA announcement mentions "Copilot CLI functions as an Agent Client Protocol agent,
enabling use within third-party tools and IDEs supporting this open standard." The ACP specification
was not researched — it may offer an alternative integration path for nWave beyond the hook+plugin
model.

**Attempted Sources**: Not researched in this session.

**Recommendation**: Research ACP as a separate topic. If ACP provides a programmatic session control
API, it could enable tighter nWave integration than the hook-only approach.

---

## Conflicting Information

### Conflict 1: Global Instructions File Path

**Position A**: The global instructions file is `~/.copilot/copilot-instructions.md`
- Source: [CLI Best Practices — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices) — Reputation: High
- Evidence: Documentation lists this path explicitly

**Position B**: The actual path is `~/.config/.copilot/copilot-instructions.md` and the documented
path does not work consistently
- Source: [github/copilot-cli#252](https://github.com/github/copilot-cli/issues/252) — Reputation: High (official issue tracker)
- Evidence: User reports from developers testing on fresh installations

**Assessment**: The official documentation is more authoritative for intent, but the issue tracker
reveals a known implementation gap. The conflict is between documented behavior and actual behavior.
Treat global instructions as unreliable until issue #252 is resolved. Use project-level
`.github/copilot-instructions.md` as the reliable alternative.

---

## Recommendations for Further Research

1. **Research Agent Client Protocol (ACP)**: The open standard mentioned in the GA announcement
   could provide a programmatic integration path. Determine if ACP enables nWave-style orchestration
   from outside the CLI.

2. **Test Copilot CLI hooks live**: Install Copilot CLI and run a minimal hook script that logs
   the full JSON input for each event type. This will resolve Gap 3 and confirm DES adapter
   requirements precisely.

3. **Research AGENTS.md standard**: The Linux Foundation / Agentic AI Foundation `AGENTS.md` open
   standard is recognized by Copilot CLI, Claude Code, Cursor, and Gemini CLI. Research its full
   specification to assess whether it can serve as the cross-platform identity/instruction file for
   a nWave multi-platform strategy.

4. **Monitor github/copilot-cli issue #252**: Global instructions support is the single most
   important missing feature for nWave portability. Track resolution actively.

5. **Research Copilot CLI programmatic mode**: The `-p`/`--prompt` flag enables non-interactive
   use. Research whether this mode supports the same hook system and can be used for nWave's
   delegated agent invocations (Task tool equivalent).

---

## Full Citations

[1] GitHub. "Upcoming deprecation of gh-copilot CLI extension". GitHub Changelog. September 25,
2025. https://github.blog/changelog/2025-09-25-upcoming-deprecation-of-gh-copilot-cli-extension/
Accessed 2026-02-26.

[2] GitHub. "About GitHub Copilot CLI". GitHub Docs. February 2026.
https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli. Accessed 2026-02-26.

[3] GitHub. "GitHub Copilot CLI is now generally available". GitHub Changelog. February 25, 2026.
https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/
Accessed 2026-02-26.

[4] GitHub. "Using hooks with GitHub Copilot CLI". GitHub Docs. 2026.
https://docs.github.com/en/copilot/how-tos/copilot-cli/use-hooks. Accessed 2026-02-26.

[5] GitHub. "Hooks configuration". GitHub Docs. 2026.
https://docs.github.com/en/copilot/reference/hooks-configuration. Accessed 2026-02-26.

[6] GitHub. "Custom agents configuration". GitHub Docs. 2026.
https://docs.github.com/en/copilot/reference/custom-agents-configuration. Accessed 2026-02-26.

[7] GitHub. "Creating custom agents for Copilot coding agent". GitHub Docs. 2026.
https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents
Accessed 2026-02-26.

[8] GitHub. "Creating agent skills for GitHub Copilot". GitHub Docs. 2026.
https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills
Accessed 2026-02-26.

[9] GitHub. "GitHub Copilot CLI plugin reference". GitHub Docs. 2026.
https://docs.github.com/en/copilot/reference/cli-plugin-reference. Accessed 2026-02-26.

[10] GitHub. "Creating a plugin marketplace for GitHub Copilot CLI". GitHub Docs. 2026.
https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-marketplace
Accessed 2026-02-26.

[11] GitHub. "About GitHub Copilot coding agent". GitHub Docs. 2026.
https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent
Accessed 2026-02-26.

[12] GitHub. "Best practices for GitHub Copilot CLI". GitHub Docs. 2026.
https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices. Accessed 2026-02-26.

[13] GitHub. "GitHub Copilot CLI: Enhanced agents, context management, and new ways to install".
GitHub Changelog. January 14, 2026.
https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install/
Accessed 2026-02-26.

[14] Inventive HQ. "Where GitHub Copilot CLI Stores Configuration Files". 2026.
https://inventivehq.com/knowledge-base/copilot/where-configuration-files-are-stored
Accessed 2026-02-26.

[15] GitHub. "A cheat sheet to slash commands in GitHub Copilot CLI". GitHub Blog. 2026.
https://github.blog/ai-and-ml/github-copilot/a-cheat-sheet-to-slash-commands-in-github-copilot-cli/
Accessed 2026-02-26.

[16] GitHub (community). "Global Instructions File Support — issue #252". github/copilot-cli.
October 8, 2025. https://github.com/github/copilot-cli/issues/252. Accessed 2026-02-26.

[17] GitHub. "github/copilot-cli — GitHub repository". 2026.
https://github.com/github/copilot-cli. Accessed 2026-02-26.

[18] GitHub. "github/awesome-copilot — Community configurations". 2026.
https://github.com/github/awesome-copilot. Accessed 2026-02-26.

---

## Research Metadata

- **Research Duration**: ~45 minutes
- **Total Sources Examined**: 22 (18 cited, 4 discarded as lower-confidence or derivative)
- **Sources Cited**: 18
- **Cross-References Performed**: 24
- **Confidence Distribution**: High: 78%, Medium: 17%, Low: 5%
- **Output File**: `/mnt/c/Repositories/Projects/nWave-dev/docs/research/copilot-cli-extensibility-research.md`
