# nWave

AI agents that guide you from idea to working code — with you in control at every step.

nWave runs inside [Claude Code](https://claude.com/product/claude-code). You describe what to build. Specialized agents handle requirements, architecture, test design, and implementation. You review and approve at each stage.

## Quick Start

**1. Install** (in your terminal — not inside Claude Code):

```bash
pipx install nwave-ai
nwave-ai install
```

No repository clone needed. This installs nWave from PyPI and sets up agents and commands in `~/.claude/`.

> **Don't have pipx?** Install it first: `pip install pipx && pipx ensurepath`, then restart your terminal. [pipx docs](https://pipx.pypa.io).
> **Windows users**: Use WSL, not cmd.exe or PowerShell. Install WSL first: `wsl --install`

Full setup details: **[Installation Guide](https://github.com/nWave-ai/nWave/blob/main/docs/guides/installation-guide.md)**

**2. Use** (inside Claude Code, after reopening it):

```
/nw:discuss "user login with email and password"   # Requirements
/nw:design --architecture=hexagonal                 # Architecture
/nw:distill "user-login"                            # Acceptance tests
/nw:deliver                                         # TDD implementation
```

Four commands. Four human checkpoints. One working feature.

Full walkthrough: **[Your First Feature](docs/guides/tutorial-first-feature.md)**

## Control Your Token Spend — Without Sacrificing Quality

nWave enforces proven engineering practices — TDD, peer review, mutation testing — at every step. `/nw:rigor` lets you scale the depth of those practices to match the stakes of your work. A config tweak doesn't need the same investment as a security-critical feature. You pick the profile; nWave enforces it everywhere.

```
/nw:rigor                    # Interactive: compare profiles, pick one
/nw:rigor lean               # Quick switch: apply immediately
```

| Profile | Agent | Reviewer | Review | TDD | Mutation | Est. Cost | When to Use |
|---------|-------|----------|--------|-----|----------|-----------|-------------|
| **lean** | haiku | -- | no | R→G | no | lowest | Spikes, config, docs |
| **standard** ⭐ | sonnet | haiku | single | full 5-phase | no | moderate | Most work |
| **thorough** | opus | sonnet | double | full 5-phase | no | higher | Critical features |
| **exhaustive** | opus | opus | double | full 5-phase | ≥80% kill | highest | Production core |
| **inherit** | *yours* | haiku | single | full 5-phase | no | varies | You pick the model |

Pick once — it persists across sessions. Change anytime. Every `/nw:deliver`, `/nw:design`, `/nw:review` respects your choice automatically.

```
/nw:rigor lean        # prototype fast
/nw:deliver           # haiku crafter, no review, RED→GREEN only
/nw:rigor standard    # ready to ship — bump up
/nw:deliver           # sonnet crafter, haiku reviewer, full TDD
```

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

- **[Discord](https://discord.gg/DeYdSNk6)** — Questions, feedback, success stories
- **[GitHub Issues](https://github.com/nWave-ai/nWave/issues)** — Bug reports and feature requests
- **[Contributing](CONTRIBUTING.md)** — Development setup and guidelines

## License

MIT — see [LICENSE](LICENSE) for details.
