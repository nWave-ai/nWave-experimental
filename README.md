# nWave: Acceptance Test Driven Development with AI

A structured approach to software development using ATDD (Acceptance Test Driven Development) with intelligent AI agent orchestration. The nWave framework guides you through a systematic 6-wave workflow with 22 specialized agents, each following the Single Responsibility Principle.

## What is nWave?

nWave is an agentic system that guides you through systematic software development:

- **Discover evidence** (DISCOVER phase) - Evidence-based product discovery and market validation
- **Gather requirements** (DISCUSS phase) - Collect business needs with AI assistance
- **Design solutions** (DESIGN phase) - Architecture decisions with visual documentation
- **Define acceptance tests** (DISTILL phase) - BDD scenarios that define "done"
- **Implement with TDD** (DEVELOP phase) - Outside-in development with quality gates
- **Validate production readiness** (DELIVER phase) - Comprehensive quality assurance

Each phase involves specialized AI agents that understand domain-specific best practices. A comprehensive quality assurance framework with peer review, mutation testing, and deterministic execution ensures code quality at every step.

## Quick Start

### Installation (1 minute)

```bash
pipx install nwave-ai
nwave-ai install
```

Close and reopen Claude Code. The nWave agents and commands will appear.

Full installation details: [Installation Guide](docs/guides/installation-guide.md)

### Your First Workflow

Use the manual step-by-step workflow with human decision points at each stage:

```bash
/nw:discuss "feature requirements"           # Requirements gathering
/nw:design --architecture=hexagonal          # Architecture design
/nw:distill "user-story-name"                # Acceptance tests
/nw:roadmap @solution-architect              # Create plan
/nw:execute @software-crafter                # Execute tasks
/nw:review @software-crafter task            # Quality check
```

For complex features or when you need business analysis first:

```bash
/nw:discover "feature market research"       # Product discovery
# Then continue with discuss, design, distill...
```

## 6-Wave Workflow

```text
DISCOVER → DISCUSS → DESIGN → DISTILL → DEVELOP → DELIVER
   ↓         ↓         ↓        ↓         ↓         ↓
Discovery  Requirements  Architecture  Acceptance  Test-First  Feature
Validation Gathering     Design        Tests       Implementation Completion
```

Each stage involves specialized AI agents and produces validated artifacts.

## Current Agent Roster (22 Agents)

### Core Wave Agents (one per phase)

- `@product-discoverer` (DISCOVER) - Evidence-based product discovery
- `@product-owner` (DISCUSS) - Requirements gathering and business analysis
- `@solution-architect` (DESIGN) - Architecture design with visual diagrams
- `@acceptance-designer` (DISTILL) - BDD scenarios and acceptance tests
- `@software-crafter` (DEVELOP) - Outside-in TDD implementation
- `@platform-architect` (DELIVER) - Production readiness and deployment

### Cross-Wave Specialists (use anytime)

- `@researcher` - Evidence-based research and analysis
- `@troubleshooter` - Root cause analysis (Toyota 5 Whys)
- `@data-engineer` - Database design and query optimization
- `@documentarist` - DIVIO-compliant documentation
- `@agent-builder` - Create and validate new agents

### Reviewer Agents (Layer 4 Quality Assurance)

Each primary agent has a matching `*-reviewer` variant providing peer review with equal expertise:
- `@product-discoverer-reviewer`, `@product-owner-reviewer`, `@solution-architect-reviewer`
- `@acceptance-designer-reviewer`, `@software-crafter-reviewer`, `@platform-architect-reviewer`
- `@researcher-reviewer`, `@troubleshooter-reviewer`, `@data-engineer-reviewer`
- `@documentarist-reviewer`, `@agent-builder-reviewer`

## Slash Commands (18 Total)

### Wave Commands

- `/nw:discover` - Evidence-based product discovery
- `/nw:discuss` - Requirements gathering
- `/nw:design` - Architecture design
- `/nw:distill` - Acceptance test creation
- `/nw:deliver` - Production readiness validation
- `/nw:devops` - Platform readiness, CI/CD, infrastructure

### Execution Commands

- `/nw:roadmap` - Create comprehensive planning document
- `/nw:execute` - Execute atomic task with state tracking
- `/nw:review` - Expert critique and quality assurance
- `/nw:finalize` - Archive project and clean up workflow

### Cross-Wave Commands

- `/nw:research` - Evidence-driven research with source verification
- `/nw:document` - DIVIO-compliant documentation
- `/nw:root-why` - Toyota 5 Whys root cause analysis
- `/nw:refactor` - Systematic code refactoring
- `/nw:mikado` - Complex refactoring with visual tracking
- `/nw:mutation-test` - Layer 5 mutation testing for test effectiveness

### Utility Commands

- `/nw:diagram` - Architecture diagram lifecycle management
- `/nw:forge` - Create new agents from templates

## Documentation Structure

nWave documentation is organized using the DIVIO framework. Find what you need:

### Getting Started

- **[Jobs To Be Done Guide](docs/guides/jobs-to-be-done-guide.md)** - Understand when and how to use each workflow
- **[Installation Guide](docs/guides/installation-guide.md)** - Step-by-step setup instructions

### Practical Guides

- **[5-Layer Testing for Users](docs/guides/5-layer-testing-users.md)** - Manual review workflows
- **[5-Layer Testing for Developers](docs/guides/5-layer-testing-developers.md)** - Programmatic review integration
- **[5-Layer Testing for CI/CD](docs/guides/5-layer-testing-cicd.md)** - Automated review in pipelines
- **[Invoke Reviewer Agents](docs/guides/invoke-reviewer-agents.md)** - Request peer reviews
- **[Troubleshooting Guide](docs/guides/troubleshooting-guide.md)** - Common issues and solutions

### Reference (Lookup)

- **[nWave Commands Reference](docs/reference/nwave-commands-reference.md)** - All commands, agents, file locations
- **[Reviewer Agents Reference](docs/reference/reviewer-agents-reference.md)** - Reviewer specifications
- **[DES Audit Trail Guide](docs/reference/des-audit-trail-guide.md)** - Deterministic execution tracking

### Understanding Concepts

- **[Knowledge Architecture Analysis](docs/guides/knowledge-architecture-analysis.md)** - Design patterns and rationale

## Quality Assurance: 5-Layer Testing

```text
Layer 1: Unit Testing            - Individual agent output validation
Layer 2: Integration Testing     - Handoff validation between agents
Layer 3: Adversarial Validation  - Challenge output validity
Layer 4: Peer Review             - Equal-expertise reviewer critique
Layer 5: Mutation Testing        - Test suite effectiveness validation
```

## Core Concepts

### DES (Deterministic Execution System)

DES enforces execution discipline through Claude Code hooks and audit logging:

- Pre-task validation and post-tool-use monitoring
- Comprehensive audit logging for compliance and debugging
- Configurable per-project via `.nwave/des-config.json`

Projects can customize DES behavior with per-project configuration.

### Agent Communication

Agents communicate through file-based handoffs with structured JSON/YAML:

- Clean context isolation (no accumulated confusion)
- Traceable decisions (audit trail for compliance)
- Parallel processing (independent task execution)
- State tracking (TODO, IN_PROGRESS, DONE)

## Development Workflow

### For Contributors

After cloning the repository, set up your development environment:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests to verify setup
pytest

# Install pre-commit hooks
pre-commit install
```

Pre-commit hooks validate automatically on commit:

- Python linting and formatting (ruff)
- YAML syntax validation
- Test execution (58+ tests)
- Trailing whitespace removal

For emergency bypass (not recommended):

```bash
git commit --no-verify
```

### Making Changes to Framework

After modifying agents, commands, or framework components:

```bash
# Run tests to verify changes
pytest

# Format code
ruff format .

# Commit with conventional format
git commit -m "feat(agents): add new capability"
```

## Community

Have questions, run into issues, or want to share your success stories? Join the **[nWave Discord community](https://discord.gg/DeYdSNk6)** to connect with other users and the team.

## Project Structure

```text
.
├── README.md                    # This file (entry point)
├── pyproject.toml              # Project configuration
├── src/des/                    # DES runtime module
├── scripts/
│   ├── install/               # Installation scripts and CLI
│   └── utils/                 # Utility scripts
├── docs/                       # DIVIO-organized documentation
│   ├── guides/                # How-to guides (practical tasks)
│   │   ├── jobs-to-be-done-guide.md
│   │   ├── installation-guide.md
│   │   ├── 5-layer-testing-users.md
│   │   ├── 5-layer-testing-developers.md
│   │   ├── 5-layer-testing-cicd.md
│   │   ├── invoke-reviewer-agents.md
│   │   ├── troubleshooting-guide.md
│   │   └── knowledge-architecture-analysis.md
│   ├── reference/              # Reference (lookup)
│   │   ├── nwave-commands-reference.md
│   │   ├── reviewer-agents-reference.md
│   │   ├── des-audit-trail-guide.md
│   │   └── nwave-plugin-architecture.md
│   └── research/               # Research and background
├── tests/                      # Automated test suite
├── .pre-commit-config.yaml     # Quality gates
└── LICENSE                     # MIT License
```

## Contributing

nWave follows clean architecture principles:
1. Each agent has one responsibility
2. Communication through well-defined interfaces (JSON/YAML)
3. Testable code with 58+ test validation suite
4. Quality gates at every commit

See individual agent documentation for implementation details.

## Key Features

- **22 Specialized AI Agents** - Primary agents plus reviewer agents for peer review
- **6-Wave ATDD Workflow** - Proven development methodology with discovery phase
- **Layer 4 Peer Review** - Equal-expertise reviewer critique reducing bias
- **Layer 5 Mutation Testing** - Validate test suite effectiveness
- **Evidence-Based Discovery** - Market research and problem validation
- **Evidence-Based Planning** - Baseline measurement blocks roadmap
- **Atomic Task Execution** - Clean context per task prevents degradation
- **DES Hooks** - Deterministic execution with audit logging
- **Cross-Platform** - Works on Windows, macOS, Linux
- **Offline Documentation** - Complete reference materials included

## License

This project is open source under the MIT License. See LICENSE for details.

---

For detailed information about specific topics, use the documentation structure above to find exactly what you need.
