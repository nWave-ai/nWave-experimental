# nWave

AI agents that guide you from idea to working code — with you in control at every step.

nWave runs inside [Claude Code](https://claude.com/product/claude-code). You describe what to build. Specialized agents handle requirements, architecture, test design, and implementation. You review and approve at each stage.

## Quick Start

Choose your installation method below. Both work equally well; the plugin method has zero dependencies and is recommended for most users.

### Plugin (Recommended — 1 command, zero dependencies)

From Claude Code, run:

```
/plugin marketplace add nwave-ai/nwave
/plugin install nwave@nwave-marketplace
```

That's it. Restart Claude Code and type `/nw:` to see all available commands.

> **Coming soon**: We're working to be hosted on Anthropic's official plugin marketplace.
> Once available, installation will be even simpler:
> ```
> /plugin install nwave@claude-plugins-official
> ```

### CLI Installer (Python 3.10+ required)

For users who prefer pip-based installation or need advanced configuration:

```bash
pipx install nwave-ai
nwave-ai install
```

No repository clone needed. This installs nWave from PyPI and sets up agents and commands in `~/.claude/`.

> **Don't have pipx?** Install it first: `pip install pipx && pipx ensurepath`, then restart your terminal. [pipx docs](https://pipx.pypa.io).
> **Windows users**: Use WSL, not cmd.exe or PowerShell. Install WSL first: `wsl --install`

Full setup details: **[Installation Guide](https://github.com/nWave-ai/nWave/blob/main/docs/guides/installation-guide.md)**

### Which method should I use?

| I am... | Use | Why |
|---------|-----|-----|
| Trying nWave for the first time | Plugin | Zero dependencies, instant setup |
| Rolling out to my team | Plugin | Same command on every machine |
| Already using the CLI installer | Either | Both coexist safely, migrate at your pace |
| Contributing to nWave development | CLI | Access to dev scripts and DES internals |

### Use (inside Claude Code, after reopening it)

```
/nw:discuss "user login with email and password"   # Requirements
/nw:design --architecture=hexagonal                 # Architecture
/nw:distill "user-login"                            # Acceptance tests
/nw:deliver                                         # TDD implementation
```

Four commands. Four human checkpoints. One working feature.

Full walkthrough: **[Your First Feature](docs/guides/tutorial-first-feature.md)**

## Staying Updated

nWave checks for new versions when you open Claude Code. When an update is available, you'll see a note in Claude's context with the version and what changed.

**If you used the plugin method:**
```
/plugin marketplace update nwave-marketplace
```

Or enable auto-updates in your Claude Code plugin settings.

**If you used the CLI installer:**
```bash
pipx upgrade nwave-ai   # pull the latest package (use pip install --upgrade nwave-ai if you installed via pip)
nwave-ai install        # deploy the new framework files to ~/.claude/
```

To control check frequency: set `update_check.frequency` in `~/.nwave/des-config.json` (`daily` / `weekly` / `every_session` / `never`).

## Control Your Token Spend — Without Sacrificing Quality

nWave enforces proven engineering practices — TDD, peer review, mutation testing — at every step. `/nw:rigor` lets you scale the depth of those practices to match the stakes of your work. A config tweak doesn't need the same investment as a security-critical feature. You pick the profile; nWave enforces it everywhere.

```
/nw:rigor                    # Interactive: compare profiles, pick one
/nw:rigor lean               # Quick switch: apply immediately
/nw:rigor custom             # Build your own: choose each setting
```

| Profile | Agent | Reviewer | Review | TDD | Mutation | Est. Cost | When to Use |
|---------|-------|----------|--------|-----|----------|-----------|-------------|
| **lean** | haiku | -- | no | R→G | no | lowest | Spikes, config, docs |
| **standard** ⭐ | sonnet | haiku | single | full 5-phase | no | moderate | Most work |
| **thorough** | opus | sonnet | double | full 5-phase | no | higher | Critical features |
| **exhaustive** | opus | opus | double | full 5-phase | ≥80% kill | highest | Production core |
| **custom** | *you choose* | *you choose* | *you choose* | *you choose* | *you choose* | depends | Your exact combo |
| **inherit** | *yours* | haiku | single | full 5-phase | no | varies | You pick the model |

Pick once — it persists across sessions. Change anytime. Every `/nw:deliver`, `/nw:design`, `/nw:review` respects your choice automatically. Need a combination no preset covers? `/nw:rigor custom` walks you through each setting.

```
/nw:rigor lean        # prototype fast
/nw:deliver           # haiku crafter, no review, RED→GREEN only
/nw:rigor standard    # ready to ship — bump up
/nw:deliver           # sonnet crafter, haiku reviewer, full TDD
```

## Understanding DES Messages

DES is nWave's quality enforcement layer — it monitors every agent Task invocation during feature delivery to prevent unbounded execution, enforce TDD discipline, and protect accidental edits. Most DES messages are normal enforcement, not errors. They appear when agents skip required safety checks or when your code contains patterns that look like step execution.

DES also runs automatic housekeeping at every session start: it removes audit logs beyond the retention window, cleans up signal files left by crashed sessions, and rotates the skill-loading log when it grows too large. This happens silently in the background and never blocks your session.

| Message | What It Means | What To Do |
|---------|---------------|-----------|
| **MISSING_MAX_TURNS** | Task invocation forgot to set `max_turns` parameter. | Add `max_turns=30` (or appropriate value) to the Task call. Recommended: 15 (quick), 25 (background), 30 (standard), 35 (research). |
| **DES_MARKERS_MISSING** | Task prompt mentions a step ID (01-01 pattern) but lacks DES markers. | Either: add DES markers for step execution, OR add `<!-- DES-ENFORCEMENT : exempt -->` comment if it's not actually step work. |
| **Source write blocked** | You tried to edit a file during active `/nw:deliver` outside a DES task. | Edit requests must go through the active deliver session. If you need to make changes, finalize the current session first. |
| **TDD phase incomplete** | Sub-agent returned without finishing all required TDD phases. | Re-dispatch the same agent to complete missing phases (typically COMMIT or refactoring steps). |
| **nWave update available** | SessionStart detected a newer version available. | Optional. Run `pipx upgrade nwave-ai && nwave-ai install` when ready to upgrade, or dismiss and continue working. |
| **False positive blocks** | Your prompt accidentally matches step-ID pattern (e.g., dates like "2026-02-09"). | Add `<!-- DES-ENFORCEMENT : exempt -->` comment to exempt the Task from step-ID enforcement. |

These messages protect code quality but never prevent your work — they guide you toward the safe path.

## How It Works

```text
  machine        human         machine        human         machine
    │              │              │              │              │
    ▼              ▼              ▼              ▼              ▼
  Agent ──→ Documentation ──→ Review ──→ Decision ──→ Agent ──→ ...
 generates    artifacts      validates   approves    continues
```

Each wave produces artifacts that you review before the next wave begins. The machine never runs unsupervised end-to-end.

The full workflow has six waves. Use all six for greenfield projects, or jump straight to `/nw:deliver` for brownfield work.

| Wave | Command | Agent | Produces |
|------|---------|-------|----------|
| DISCOVER | `/nw:discover` | product-discoverer | Market validation |
| DISCUSS | `/nw:discuss` | product-owner | Requirements |
| DESIGN | `/nw:design` | solution-architect | Architecture + ADRs |
| DEVOPS | `/nw:devops` | platform-architect | Infrastructure readiness |
| DISTILL | `/nw:distill` | acceptance-designer | Given-When-Then tests |
| DELIVER | `/nw:deliver` | software-crafter | Working implementation |

22 agents total: 6 wave agents, 5 cross-wave specialists, 11 peer reviewers. Full list: **[Commands Reference](docs/reference/commands/index.md)**

## Documentation

### Getting Started

- **[Installation Guide](https://github.com/nWave-ai/nWave/blob/main/docs/guides/installation-guide.md)** — Setup instructions
- **[Your First Feature](docs/guides/tutorial-first-feature.md)** — Build a feature end-to-end (tutorial)
- **[Jobs To Be Done](docs/guides/jobs-to-be-done-guide.md)** — Which workflow fits your task

### Guides & Reference

- **[Agents & Commands Reference](docs/reference/index.md)** — All agents, commands, skills, templates
- **[Invoke Reviewers](docs/guides/invoke-reviewer-agents.md)** — Peer review workflow
- **[Troubleshooting](docs/guides/troubleshooting-guide.md)** — Common issues and fixes

## Community

- **[Discord](https://discord.gg/Cywj3uFdpd)** — Questions, feedback, success stories
- **[GitHub Issues](https://github.com/nWave-ai/nWave/issues)** — Bug reports and feature requests
- **[Contributing](CONTRIBUTING.md)** — Development setup and guidelines

## License

MIT — see [LICENSE](LICENSE) for details.
