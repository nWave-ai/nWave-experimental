# ADR-001: Plugin Marketplace Distribution Strategy

## Status

Accepted

## Context

nWave currently distributes via a custom CLI installer (`nwave-ai` on PyPI) that copies files to `~/.claude/`. This requires users to: discover nWave on GitHub, read docs, install via pip/pipx, run the installer, and configure. The Claude Code plugin system provides a native distribution channel with one-command install, auto-updates, and enterprise managed distribution.

JTBD analysis shows install friction is the #1 adoption bottleneck:
- Outcome #13 (time to install): Score 15.0, Extremely Underserved
- Outcome #15 (team deployment): Score 15.0, Extremely Underserved
- Outcome #14 (update effort): Score 13.0, Underserved

Constraints: 1 developer, 2-3 week timeline, must not break existing custom installer.

## Decision

Package nWave as a Claude Code plugin (build artifact from source tree) and distribute via:
1. Official Anthropic Plugin Marketplace (primary discovery channel)
2. Own GitHub marketplace repository `nwave-ai/nwave-plugin` (version control, enterprise distribution)

The custom installer (`nwave-ai` CLI) remains operational for non-plugin users but is no longer the recommended path for Claude Code users.

## Alternatives Considered

### Alternative 1: Improve custom installer UX only

- **What**: Add one-liner curl install, reduce setup steps, add auto-update to CLI
- **Evaluation**: Addresses install friction partially but cannot match `/plugin install` UX. No auto-updates, no enterprise `extraKnownMarketplaces`, no marketplace discovery. Still requires pip/pipx.
- **Why Rejected**: Even a perfect CLI installer cannot compete with a native plugin install UX that users already know. The plugin system provides auto-updates and enterprise distribution for free.

### Alternative 2: Plugin as primary, deprecate custom installer immediately

- **What**: Stop maintaining `nwave-ai` CLI, redirect all users to plugin
- **Evaluation**: Faster to maintain one channel. But breaks existing users who have CI/CD scripts depending on `nwave-ai install`.
- **Why Rejected**: Violates constraint "no breaking change." Some users may prefer CLI for automation. Deprecation should be gradual with migration guide, not immediate.

### Alternative 3: Plugin as thin wrapper that downloads from PyPI

- **What**: Plugin contains minimal metadata + a post-install script that runs `pip install nwave-ai && nwave install`
- **Evaluation**: Reuses 100% of existing installer code. Zero duplication.
- **Why Rejected**: Plugins are sandboxed -- they cannot run arbitrary install scripts. The plugin system expects static files in the plugin directory. Also adds pip as a runtime dependency inside the plugin, which defeats the purpose of native distribution.

## Consequences

### Positive
- Install friction drops from ~30 minutes to ~1 command
- Auto-updates deliver new agents/skills/DES improvements seamlessly
- Enterprise teams deploy via `extraKnownMarketplaces` in managed settings
- Marketplace presence provides legitimacy signal ("official Anthropic ecosystem")
- Project-scoped installs enable team standardization

### Negative
- Two distribution channels to maintain (plugin + CLI) until CLI deprecation
- Plugin build adds a CI/CD step (minor: ~30s build time)
- Plugin version must stay in sync with nwave-dev version (automated via build script)
- DES hook format differs between plugin (`${CLAUDE_PLUGIN_ROOT}`) and custom installer (`$HOME/.claude`), creating two code paths in hook generation
