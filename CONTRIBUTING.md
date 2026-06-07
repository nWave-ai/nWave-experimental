# Contributing to nWave

## Development Setup

```bash
# Clone and install (uv installs the project + dev group from uv.lock)
git clone https://github.com/nWave-ai/nwave-dev.git
cd nwave-dev
uv sync

# Install pre-commit hooks (all types: pre-commit, pre-push, commit-msg, ...)
uv run poe install-hooks

# Verify
uv run poe test
```

> Don't have uv? `curl -LsSf https://astral.sh/uv/install.sh | sh` (see [uv docs](https://docs.astral.sh/uv/getting-started/installation/)).

### DES freshness gate (dev tree)

The repo ships a `.env` file with `NWAVE_FRESHNESS=skip` so that `uv run`
commands bypass the DES runtime freshness gate against the unmaintained dev
tree. Without this, every `uv run python -m des.cli.*` REFUSES with exit
78 (no install manifest is written until slice-02 of
`fix-des-self-hosted-gate-sync` lands). The bypass is audit-bearing — each
invocation emits a structured `des.runtime.freshness.skipped` event on stderr.
See `docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md` §1.8 / §6.

## Pre-commit Hooks

Hooks run automatically on every commit:

- Python linting and formatting (ruff)
- YAML syntax validation
- Test execution
- Trailing whitespace removal

For emergency bypass (not recommended):

```bash
git commit --no-verify
```

## Making Changes

```bash
# Run tests
uv run poe test

# Format code
uv run poe format

# Commit with conventional format
git commit -m "feat(agents): add new capability"
```

## Architecture Principles

1. Each agent has one responsibility
2. Agents communicate through file-based handoffs (JSON/YAML)
3. All behavioral changes ship with tests
4. Quality gates enforce standards at every commit

## Project Structure

```text
.
├── src/des/                    # DES runtime module
├── scripts/
│   ├── install/               # Installation scripts and CLI
│   │   └── plugins/           # Plugin system (agents, commands, DES, etc.)
│   └── utils/                 # Utility scripts
├── docs/
│   ├── guides/                # Tutorials and how-to guides
│   └── reference/             # API and command reference
├── tests/                     # Automated test suite
├── .pre-commit-config.yaml    # Quality gates
└── pyproject.toml             # Project configuration
```
