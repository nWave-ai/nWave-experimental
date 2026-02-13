# nwave-ai

CLI installer for the nWave methodology framework, a structured approach to software development with Claude Code.

nWave organizes work into waves (Discuss, Design, Distill, Deliver, DevOps) with specialized AI agents that handle requirements, architecture, testing, implementation, and deployment.

## Install

```bash
pipx install nwave-ai
```

## Usage

```bash
# Install nWave framework to ~/.claude/
nwave-ai install

# Preview changes without installing
nwave-ai install --dry-run

# Remove nWave framework
nwave-ai uninstall

# Show version
nwave-ai version
```

## What gets installed

The installer sets up nWave's agent definitions, slash commands, and workflow contracts in your `~/.claude/` directory, making them available across all your Claude Code projects.

## Requirements

- Python 3.10+
- Claude Code CLI

## Links

- [Source](https://github.com/nwave-ai/nwave)
- [License: MIT](https://github.com/nwave-ai/nwave/blob/main/LICENSE)
