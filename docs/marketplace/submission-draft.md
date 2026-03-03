# Anthropic Plugin Directory — Submission Draft

**Prepared**: 2026-03-03
**Target**: Google Form at `clau.de/plugin-directory-submission`
**Version**: 1.8.1

---

## Form Fields

### Plugin Name

```
nw
```

### Description (50-100 words)

```
nWave orchestrates 23 specialized AI agents through six development waves:
Discover, Discuss, Design, Devops, Distill, and Deliver. You work one feature
at a time — each wave is a human-machine loop where the agent produces artifacts
and you review, refine, and approve before moving on. The Deliver wave enforces
Outside-In TDD: every feature ships with tests, and a runtime guard ensures
agents stay on track. A meta-agent (/nw:forge) creates custom agents tailored
to your domain. Works equally well for greenfield features and legacy
modernization.
```

Word count: 82

### Target Platform

```
Claude Code
```

### GitHub Repository

```
https://github.com/nwave-ai/nwave
```

### Company/Organization URL

```
https://github.com/nwave-ai
```

### Primary Contact Email

```
hello@nwave.ai
```

### Plugin Examples (minimum 3)

**Example 1: Full lifecycle — from market validation to working code**

```
/nw:discover "team task management"         # Validate the problem exists
/nw:discuss "task assignment and tracking"  # Requirements + user stories
/nw:design --architecture=hexagonal         # Architecture + ADRs
/nw:devops                                  # CI/CD, infrastructure, deployment
/nw:distill "task-assignment"               # BDD acceptance tests (Given-When-Then)
/nw:deliver                                 # TDD implementation
```

Six waves, six human checkpoints. One feature flows through the entire pipeline
— the agent proposes, you decide. Start from Discover for greenfield projects,
or jump straight to Deliver for existing codebases. The Deliver phase enforces
Outside-In TDD: failing test first, then implementation, then refactor — with
automated phase tracking.

**Example 2: Create custom agents with the meta-agent**

```
/nw:forge "security auditor for OWASP Top 10 compliance"
```

The forge agent analyzes your request, researches best practices, generates a
complete agent specification (YAML frontmatter + markdown), creates matching
skills with domain knowledge, and validates the result against nWave's quality
standards. The new agent integrates with the existing wave system — it can be
dispatched via `/nw:execute` and reviewed via `/nw:review`. Build agents tailored
to your team's domain without writing specifications by hand.

**Example 3: Modernize legacy code with structured refactoring**

```
/nw:refactor "payments module"              # Systematic: naming → complexity → structure → abstractions
/nw:mikado "migrate from REST to GraphQL"   # Map dependencies, tackle in safe order
```

Legacy code gets the same structured treatment as greenfield. `/nw:refactor`
walks through four levels — from quick readability fixes to deep abstraction
redesign — with an architect planning the target and a crafter (OOP or
functional) executing each step under TDD. `/nw:mikado` handles large-scale
changes by mapping what depends on what, so you never break the system mid-migration.
Use `/nw:rigor` to scale quality depth and token cost to match the task.

---

## Compliance Checklist (Internal Record)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Privacy policy | PASS | `PRIVACY.md` — no data collection, local-only storage, one optional anonymous update check |
| 2 | Verified contact info | PASS | `hello@nwave.ai` — active, monitored |
| 3 | Documentation | PASS | Installation guide, tutorial, troubleshooting guide, full command reference |
| 4 | Working examples | PASS | 3 examples above + tutorial "Your First Feature" |
| 5 | No financial/ad/generative-media | PASS | Development workflow tool — none of the auto-reject categories |
| 6 | No dynamic external instructions | PASS | All skills bundled in plugin directory, no runtime URL fetching |
| 7 | No memory/history extraction | PASS | Agents read project files only when user invokes a command |
| 8 | Tool names under 64 chars | PASS | No MCP servers — commands are slash commands (markdown files) |
| 9 | Accurate descriptions | PASS | All agent/command descriptions match actual functionality |
| 10 | MIT license | PASS | `LICENSE` file in repository root |
| 11 | Indemnification acceptance | READY | Accepted via form submission |

## Plugin Structure (for reviewer reference)

```
nwave-ai/nwave/
├── .claude-plugin/
│   └── marketplace.json        # Self-hosted marketplace catalog
├── plugins/nw/
│   ├── .claude-plugin/
│   │   └── plugin.json         # Plugin manifest (name: "nw")
│   ├── agents/                 # 23 agent specifications
│   ├── commands/               # 21 slash commands (/nw:*)
│   ├── skills/                 # 98 domain skill files
│   ├── hooks/                  # DES enforcement hooks
│   └── scripts/                # Hook runtime scripts
├── README.md
├── PRIVACY.md
├── LICENSE
└── CONTRIBUTING.md
```

## Notes

- **Category**: `development` (matches official directory taxonomy)
- **Version pinning**: Anthropic pins approved versions. Updates require resubmission.
- **Self-hosted marketplace**: Already live at `nwave-ai/nwave`. Users can install today via `/plugin marketplace add nwave-ai/nwave`. Official directory listing adds discoverability, not new functionality.
- **Novel plugin type**: nWave is a methodology/workflow plugin, not a service integration. Most approved external plugins are integrations (GitHub, Slack, Stripe). Frame the value proposition clearly for reviewers unfamiliar with TDD workflow tooling.
