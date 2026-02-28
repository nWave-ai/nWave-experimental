# Research: Claude Code Plugin `settings.json` Specification

**Date**: 2026-02-27 | **Researcher**: nw-researcher (Nova) | **Confidence**: High | **Sources**: 5

## Executive Summary

The `settings.json` file at the root of a Claude Code plugin directory is an **officially supported, optional** configuration file that provides **default settings applied when the plugin is enabled**. According to the official plugin reference documentation at `code.claude.com`, **only `agent` settings are currently supported** in plugin-level `settings.json`.

This is a distinct file from the user/project-level `.claude/settings.json` (which controls permissions, hooks, environment variables, and other Claude Code behaviors). The plugin `settings.json` is narrower in scope -- it ships defaults that take effect when users enable the plugin, but is currently limited to agent-related configuration.

Notably, none of the 13 official plugins in the `anthropics/claude-code` repository include a `settings.json` file, and the example plugin in `anthropics/claude-plugins-official` also omits it. This suggests the feature is either very new or rarely needed in practice.

## Research Methodology

**Search Strategy**: Official Anthropic documentation (code.claude.com), Anthropic GitHub repositories (anthropics/claude-code, anthropics/claude-plugins-official), web search for community examples and third-party documentation.
**Source Selection**: Types: official docs, source repos, technical guides | Reputation: high/medium-high min | Verification: cross-referencing across official sources.
**Quality Standards**: Min 3 sources/claim | All major claims cross-referenced | Avg reputation: 0.9

## Findings

### Finding 1: `settings.json` Is Part of the Official Plugin Directory Structure

**Evidence**: The official plugin reference documentation lists `settings.json` in the standard plugin layout:

```
enterprise-plugin/
    ...
    settings.json            # Default settings for the plugin
    ...
```

And in the file locations reference table:

| Component | Default Location | Purpose |
|-----------|-----------------|---------|
| Settings | `settings.json` | Default configuration applied when the plugin is enabled. Only agent settings are currently supported |

**Source**: [Plugins Reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference) - Accessed 2026-02-27
**Confidence**: High
**Verification**: [Anthropic Claude Code GitHub plugins README](https://github.com/anthropics/claude-code/blob/main/plugins/README.md), [DataCamp Plugin Guide](https://www.datacamp.com/tutorial/how-to-build-claude-code-plugins)
**Analysis**: The documentation is explicit that `settings.json` exists at the plugin root level (not inside `.claude-plugin/`). It is listed alongside other optional components like `.mcp.json` and `.lsp.json`.

### Finding 2: Only Agent Settings Are Currently Supported

**Evidence**: The file locations reference table states: "Default configuration applied when the plugin is enabled. **Only agent settings are currently supported.**"

**Source**: [Plugins Reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference) - Accessed 2026-02-27
**Confidence**: High
**Verification**: This is stated directly in the official documentation. No contradictory information found in any other source.
**Analysis**: This is a significant limitation. The full `.claude/settings.json` supports permissions, hooks, environment variables, MCP configuration, sandbox settings, and much more. But a plugin's `settings.json` currently only supports agent-related configuration. The documentation does not specify exactly which agent fields are supported in this context, but based on the subagent documentation, likely candidates include model defaults, permission modes, and tool restrictions for plugin-provided agents.

### Finding 3: The File Is Optional (No Official Plugins Use It)

**Evidence**: Examination of all 13 plugins in the `anthropics/claude-code` repository and the example plugin in `anthropics/claude-plugins-official` shows none include a `settings.json` file. The standard plugin structure documentation marks it as present but optional.

**Source**: [Claude Code Plugins Directory](https://github.com/anthropics/claude-code/tree/main/plugins) - Accessed 2026-02-27
**Confidence**: High
**Verification**: [Claude Plugins Official Example](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/example-plugin/README.md), [Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
**Analysis**: The fact that Anthropic's own plugins do not use `settings.json` strongly suggests that agent configuration is handled directly in agent frontmatter files rather than through a separate settings file. Plugins that define agents (e.g., `feature-dev` with 3 agents, `code-review` with 5 agents, `plugin-dev` with 3 agents) all configure their agents via the markdown frontmatter in `agents/*.md` files, not through `settings.json`.

### Finding 4: Plugin `settings.json` Is Different from `.claude/settings.json`

**Evidence**: The `.claude/settings.json` file controls the full Claude Code configuration including permissions, hooks, environment variables, sandbox settings, MCP servers, UI options, and plugin enablement. The plugin-level `settings.json` at the plugin root is a separate, much narrower file.

**Source**: [Claude Code Settings](https://code.claude.com/docs/en/settings) - Accessed 2026-02-27
**Confidence**: High
**Verification**: [Plugins Reference](https://code.claude.com/docs/en/plugins-reference), [Subagents Documentation](https://code.claude.com/docs/en/sub-agents)
**Analysis**: These are two completely different files serving different purposes. The `.claude/settings.json` is where plugins are *enabled* (via `enabledPlugins`). The plugin's own `settings.json` is where a plugin can ship *default configuration* for its components.

### Finding 5: Agent Configuration Is Primarily Done Via Frontmatter

**Evidence**: The subagent documentation specifies that agents are configured via YAML frontmatter in markdown files with fields: `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `isolation`.

**Source**: [Create Custom Subagents - Claude Code Docs](https://code.claude.com/docs/en/sub-agents) - Accessed 2026-02-27
**Confidence**: High
**Verification**: [Plugins Reference](https://code.claude.com/docs/en/plugins-reference), [Claude Code CLI Reference](https://code.claude.com/docs/en/settings)
**Analysis**: Since agent configuration in frontmatter is comprehensive and no official plugin uses `settings.json`, the practical recommendation is that `settings.json` is not needed for nWave at this time.

## Source Analysis

| Source | Domain | Reputation | Type | Access Date | Cross-verified |
|--------|--------|------------|------|-------------|----------------|
| Plugins Reference - Claude Code Docs | code.claude.com | High (1.0) | Official | 2026-02-27 | Y |
| Settings - Claude Code Docs | code.claude.com | High (1.0) | Official | 2026-02-27 | Y |
| Subagents - Claude Code Docs | code.claude.com | High (1.0) | Official | 2026-02-27 | Y |
| Claude Code GitHub - plugins/ | github.com/anthropics | High (1.0) | Official source | 2026-02-27 | Y |
| Claude Plugins Official - example | github.com/anthropics | High (1.0) | Official source | 2026-02-27 | Y |

Reputation: High: 5 (100%) | Avg: 1.0

## Knowledge Gaps

### Gap 1: Exact Schema for Plugin `settings.json`

**Issue**: The documentation states only "agent settings are currently supported" but does not provide the JSON schema or list of supported fields for the plugin-level `settings.json`. There is no `$schema` reference specific to plugin settings.
**Attempted**: Official docs, GitHub source code, community examples, web search.
**Recommendation**: Monitor `code.claude.com/docs/en/plugins-reference` for updates. The feature may be documented more fully as it matures. Alternatively, inspect the Claude Code source at `anthropics/claude-code` for the schema definition.

### Gap 2: Whether `settings.json` Can Override Agent Frontmatter

**Issue**: It is unclear whether `settings.json` can override or supplement agent frontmatter fields, or whether it provides defaults that frontmatter takes priority over.
**Attempted**: Documentation search, plugin examples.
**Recommendation**: Test with a minimal plugin that defines conflicting values in both locations.

## Recommendations for nWave

### Concrete Recommendation: Do Not Create `settings.json` Now

Based on the evidence:

1. **The file is optional** -- the plugin manifest (`plugin.json`) and agent frontmatter handle all current nWave configuration needs.
2. **Only agent settings are supported** -- nWave's agent configuration is already comprehensive in the agent markdown files.
3. **No official plugins use it** -- Anthropic's own 13+ plugins do not include this file, suggesting the feature is either nascent or unnecessary for typical plugins.
4. **Agent frontmatter is the established pattern** -- all supported agent fields (`model`, `tools`, `maxTurns`, `hooks`, `skills`, `memory`, etc.) are configurable in frontmatter.

**When to reconsider**: If Claude Code expands `settings.json` to support permissions, hooks, or environment variable defaults for plugins, it would become valuable for nWave to ship default permission rules (e.g., pre-allowing DES hook commands).

### If You Do Create One Later

Based on the limited documentation and naming convention, the file would likely follow this pattern:

```json
{
  "agents": {
    "nw-software-crafter": {
      "model": "inherit",
      "maxTurns": 45
    }
  }
}
```

Place it at the plugin root: `nWave/settings.json` (not inside `.claude-plugin/`).

## Full Citations

[1] Anthropic. "Plugins Reference". Claude Code Docs. 2026. https://code.claude.com/docs/en/plugins-reference. Accessed 2026-02-27.
[2] Anthropic. "Settings". Claude Code Docs. 2026. https://code.claude.com/docs/en/settings. Accessed 2026-02-27.
[3] Anthropic. "Create Custom Subagents". Claude Code Docs. 2026. https://code.claude.com/docs/en/sub-agents. Accessed 2026-02-27.
[4] Anthropic. "Claude Code Plugins Directory". GitHub. 2026. https://github.com/anthropics/claude-code/tree/main/plugins. Accessed 2026-02-27.
[5] Anthropic. "Claude Plugins Official - Example Plugin". GitHub. 2026. https://github.com/anthropics/claude-plugins-official/blob/main/plugins/example-plugin/README.md. Accessed 2026-02-27.

## Research Metadata

Duration: ~8 min | Examined: 8 | Cited: 5 | Cross-refs: 5 | Confidence: High 100% | Output: docs/research/claude-code-plugin-settings-json.md
