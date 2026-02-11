# nWave: Intelligent ATDD Pipeline with Specialized Agent Network

<!-- version: 1.7.1 -->

A systematic approach to software development using ATDD (Acceptance Test Driven Development) with intelligent AI agent orchestration. The framework automates the 6-wave workflow through 26 specialized agents (13 primary + 13 reviewers), each following the Single Responsibility Principle.

## What is nWave?

nWave is an agentic system that guides you through systematic software development:

- **Discover evidence** (DISCOVER phase) - Evidence-based product discovery and market validation
- **Gather requirements** (DISCUSS phase) - Collect business needs with AI assistance
- **Design solutions** (DESIGN phase) - Architecture decisions with visual documentation
- **Define acceptance tests** (DISTILL phase) - BDD scenarios that define "done"
- **Implement with TDD** (DEVELOP phase) - Outside-in development with quality gates
- **Validate production readiness** (DELIVER phase) - Comprehensive quality assurance

Each phase involves specialized AI agents that understand domain-specific best practices.

## Quick Start

### 1. Installation (5 minutes)

```bash
# macOS/Linux
curl -O https://github.com/nWave-ai/nwave-dev/releases/latest/download/install-nwave-claude-code.py
python3 install-nwave-claude-code.py

# Or from repository
git clone https://github.com/nWave-ai/nwave-dev.git nwave
cd nwave
python3 scripts/install/install_nwave.py
```

Full installation details: [Installation Guide](docs/guides/installation-guide.md)

### 2. Your First Development Cycle

```bash
# Build a complete feature with automatic workflow
/nw:develop "Build user authentication system"

# This automatically:
# 1. Baseline: Measure starting state
# 2. Roadmap: Create comprehensive plan
# 3. Split: Break into atomic tasks
# 4. Execute: Run each task with clean context
# 5. Review: Quality gate each step
# 6. Finalize: Archive completed work

# NOTE: /nw:develop is optimized for technical development tasks.
# For features requiring deeper business analysis or design exploration,
# use the manual step-by-step workflow below.
```

Or use the complete workflow with human-in-the-loop control:

```bash
# Full ATDD workflow with human decision points at each stage
# (recommended for complex features, first-time use, or non-technical tasks)
/nw:discover "authentication market research"      # Product discovery
/nw:discuss "authentication requirements"           # Requirements gathering
/nw:design --architecture=hexagonal                # Architecture design
/nw:distill "user-login-story"                     # Acceptance tests
/nw:baseline "implement authentication"             # Measure starting point
/nw:roadmap @solution-architect "implement auth"   # Create plan
/nw:split @devop "auth-implementation"             # Break into tasks
/nw:execute @software-crafter "docs/workflow/..."  # Execute tasks
/nw:review @software-crafter task "docs/workflow/..." # Quality check
```

## Documentation Structure

nWave documentation is organized using the **DIVIO framework** for maximum usability. Find what you need:

### Getting Started
Start here if you're new to nWave:
- **[Jobs To Be Done Guide](docs/guides/jobs-to-be-done-guide.md)** - Understand when and how to use each workflow
- **[Installation Guide](docs/guides/installation-guide.md)** - Step-by-step setup instructions

### Practical Guides (How-To)
Learn how to accomplish specific tasks:
- **[Invoke Reviewer Agents](docs/guides/invoke-reviewer-agents.md)** - Request peer reviews for quality assurance
- **[Layer 4 for Developers](docs/guides/layer-4-for-developers.md)** - Programmatic review integration in code
- **[Layer 4 for Users](docs/guides/layer-4-for-users.md)** - Manual review workflows
- **[Layer 4 for CI/CD](docs/guides/layer-4-for-cicd.md)** - Automated review in pipelines

### Reference (Lookup)
Find exact specifications and configuration:
- **[nWave Commands Reference](docs/reference/nwave-commands-reference.md)** - All commands, agents, file locations
- **[Reviewer Agents Reference](docs/reference/reviewer-agents-reference.md)** - Reviewer specifications and configuration
- **[Layer 4 API Reference](docs/reference/layer-4-api-reference.md)** - API contracts and interfaces
- **[Troubleshooting Guide](docs/troubleshooting/troubleshooting-guide.md)** - Common issues and solutions

### Understanding Concepts (Explanation)
Deepen your understanding of why nWave works:
- **[Layer 4 Implementation Summary](docs/guides/layer-4-implementation-summary.md)** - How peer review by equal-expertise agents reduces bias
- **[Architecture Patterns](docs/guides/knowledge-architecture-analysis.md)** - Design decisions and rationale

## Core Concepts

### 6-Wave Workflow (ATDD Pipeline)

```
DISCOVER → DISCUSS → DESIGN → DISTILL → DEVELOP → DELIVER
   ↓         ↓         ↓        ↓         ↓         ↓
Discovery  Requirements  Architecture  Acceptance  Test-First  Feature
Validation Gathering     Design        Tests       Implementation Completion
```

Each stage involves specialized AI agents and produces validated artifacts.

### Agent Organization (26 Agents)

**Core Wave Agents** (one per phase):
- `@product-discoverer` - Evidence-based product discovery (DISCOVER)
- `@product-owner` - Requirements gathering and business analysis (DISCUSS)
- `@solution-architect` - Architecture design with visual diagrams (DESIGN)
- `@acceptance-designer` - BDD scenarios and acceptance tests (DISTILL)
- `@software-crafter` - Outside-in TDD implementation (DEVELOP)
- `@devop` - Production readiness and operations (DELIVER)

**Cross-Wave Specialists** (use anytime):
- `@researcher` - Evidence-based research and analysis
- `@troubleshooter` - Root cause analysis (Toyota 5 Whys)
- `@visual-architect` - Architecture diagrams and visualization
- `@data-engineer` - Database design and query optimization
- `@product-discoverer` - Evidence-based product discovery
- `@agent-builder` - Create and validate new agents
- `@illustrator` - Visual diagrams and design artifacts

**Reviewer Agents** (Layer 4 quality assurance):
- 12 reviewer agents providing peer review with bias detection
- Each reviewer has equal expertise to primary agent
- Structured YAML feedback with severity classification

### Quality Assurance (5-Layer Testing)

```
Layer 1: Unit Testing            - Individual agent output validation
Layer 2: Integration Testing     - Handoff validation between agents
Layer 3: Adversarial Validation  - Challenge output validity
Layer 4: Peer Review             - Equal-expertise reviewer critique ← Unique to nWave
Layer 5: Mutation Testing        - Test suite effectiveness validation ← NEW
```

## Use Cases

### Building New Features (Greenfield)

```bash
/nw:discover "feature market research"
/nw:discuss "feature requirements"
/nw:design --architecture=hexagonal
/nw:distill "acceptance tests"
/nw:baseline "measure starting state"
/nw:roadmap @solution-architect
/nw:split @devop
/nw:execute @software-crafter
/nw:review @software-crafter
```

### Improving Existing System (Brownfield)

```bash
/nw:baseline "current state measurement"        # MANDATORY - blocks roadmap
/nw:roadmap @solution-architect                # Plan while context fresh
/nw:split @devop                               # Break into atomic tasks
/nw:execute @software-crafter                  # Execute with clean context
/nw:review @software-crafter                   # Quality gate
```

### Complex Refactoring

```bash
/nw:baseline "measure starting state"
/nw:roadmap @solution-architect "methodology: mikado"
/nw:split @devop
/nw:execute @software-crafter
# Mikado Method ensures reversibility at every step
```

### Investigating Issues

```bash
/nw:root-why "description of symptom"          # Find root cause (not symptoms)
/nw:develop "fix-issue"                        # Implement fix with TDD
/nw:deliver                                    # Validate production readiness
```

### Research & Learning

```bash
/nw:research "topic or technology"
# Output: docs/research/{category}/{topic}.md
# Then proceed with appropriate job (greenfield, brownfield, etc.)
```

## Development Workflow

### Making Changes to Framework

After modifying agents, commands, or framework components:

```bash
# Option 1: Full update (build + install + validate) - Recommended
python scripts/install/update_nwave.py --force

# Option 2: Build only (without installing)
python tools/build.py --clean

# Option 3: Manual install after build
python scripts/install/install_nwave.py
```

### Pre-Commit Hooks

nWave enforces quality gates through pre-commit hooks:

```bash
# Install pre-commit (first time only)
pip install pre-commit
cd nwave
pre-commit install

# Hooks validate automatically on commit:
# - nwave-version-bump: Version consistency
# - pytest-validation: All tests pass (58 tests)
# - docs-version-validation: Documentation stays in sync
# - ruff: Python linting and formatting
# - trailing-whitespace: Removes trailing spaces
# - check-yaml: Validates YAML syntax
```

For emergency bypass (not recommended):
```bash
git commit --no-verify  # Bypasses ALL validation - requires immediate fix
```

## Troubleshooting

**Issue**: Agents not found after installation?
- Check: [Troubleshooting Guide](docs/troubleshooting/TROUBLESHOOTING.md)

**Issue**: Tests failing on commit?
- Run: `pytest` locally to debug
- Ensure: All tests pass before commit

**Issue**: Documentation out of sync with code?
- Run: `pre-commit run --all-files`
- Ensures: Version tags match across tracked files

## Project Structure

```
nwave/
├── README.md                    # This file (entry point)
├── .claude/                     # User-specific configuration (excluded from version control)
├── docs/                        # DIVIO-organized documentation
│   ├── guides/                  # How-to guides (practical tasks)
│   │   ├── jobs-to-be-done-guide.md        # When to use each workflow
│   │   ├── how-to-invoke-reviewers.md       # How to request reviews
│   │   ├── layer-4-for-developers.md        # Programmatic review API
│   │   ├── layer-4-for-users.md             # Manual review workflows
│   │   └── layer-4-for-cicd.md              # Automated review pipelines
│   ├── reference/               # Reference (lookup)
│   │   ├── nwave-commands-reference.md      # All commands and agents
│   │   ├── reviewer-agents-reference.md     # Reviewer specs
│   │   └── layer-4-api-reference.md         # API contracts
│   ├── installation/            # Installation documentation
│   │   ├── INSTALL.md                       # Setup guide
│   │   └── UNINSTALL.md                     # Removal guide
│   ├── troubleshooting/         # Troubleshooting
│   │   └── TROUBLESHOOTING.md               # Common issues
│   ├── analysis/                # Analysis and audits
│   │   └── divio-audit/                     # DIVIO compliance audit
│   └── research/                # Research and background
│
├── nWave/                       # ATDD workflow framework
│   ├── agents/                  # Agent specifications
│   ├── commands/                # Slash command definitions
│   └── data/                    # Reference data and research
│
├── scripts/                     # Installation and utility scripts
├── tools/                       # Build and development tools
├── tests/                       # Automated test suite
└── .pre-commit-config.yaml      # Quality gates (5-layer testing framework)
```

## Architecture Overview

### Agent Communication

Agents communicate through **file-based handoffs** with structured JSON/YAML:
- Clean context isolation (no accumulated confusion)
- Traceable decisions (audit trail)
- Parallel processing (independent task execution)
- State tracking (TODO → IN_PROGRESS → DONE)

### Framework Configuration

Centralized configuration through:
- `nWave/framework-catalog.yaml` - Command definitions and agent mappings
- `.dependency-map.yaml` - Version tracking and documentation synchronization
- `.pre-commit-config.yaml` - Quality gates

### Quality Gates

Progressive refactoring with validation:
- **L1 Refactoring**: Basic code cleanup
- **L2 Refactoring**: Structure improvements
- **L3 Refactoring**: Design pattern application
- **L4 Refactoring**: Advanced architectural improvements
- **L5-L6 Refactoring**: Major restructuring with comprehensive validation

## Contributing

nWave follows clean architecture principles:
1. Each agent has **one responsibility**
2. Communication through **well-defined interfaces** (JSON/YAML)
3. **Testable code** with 58-test validation suite
4. **Quality gates** at every commit

See individual agent documentation in `nWave/agents/` for implementation details.

## Key Features

✅ **26 Specialized AI Agents** - 13 primary agents + 13 peer reviewers, each understanding domain-specific best practices
✅ **6-Wave ATDD Workflow** - Proven development methodology with discovery phase
✅ **Layer 4 Peer Review** - Unique equal-expertise reviewer critique
✅ **Progressive Refactoring** - L1-L6 quality improvement framework
✅ **Walking Skeleton Validation** - E2E architecture proof
✅ **Evidence-Based Discovery** - Market research and problem validation
✅ **Evidence-Based Planning** - Baseline measurement blocks roadmap
✅ **Atomic Task Execution** - Clean context per task (no degradation)
✅ **Cross-Platform** - Works on Windows, macOS, Linux
✅ **Offline Documentation** - Complete reference materials included

## Version

- Current Version: 1.7.1
- Last Updated: 2026-01-25
- Status: Production Ready

## Related Documentation

- [DIVIO Audit & Classification](docs/analysis/divio-audit/DIVIO_CLASSIFICATION_SUMMARY.md) - Documentation quality assessment
- [CI/CD Integration](docs/guides/CI-CD-README.md) - Continuous integration setup
- [Releasing & Deployment](docs/RELEASING.md) - Release process
- [Project Evolution](docs/evolution/) - Framework enhancements and improvements

## License

This project is open source. See individual agent documentation for specific implementation details and usage patterns.

---

**For detailed information about specific topics, use the documentation structure above to find exactly what you need.**
