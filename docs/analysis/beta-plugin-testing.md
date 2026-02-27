# nWave Plugin Beta Testing Guide

Thank you for helping us test the nWave Claude Code plugin! This guide walks you through installation and verification.

## Prerequisites

- Claude Code CLI installed (`claude` command available)
- Python 3.10+ installed
- ~5 minutes

## Step 1: Download the Plugin

Download the plugin ZIP from the latest beta release:

```bash
curl -L -o nwave-plugin.zip \
  "https://github.com/nWave-ai/nWave-beta/releases/latest/download/nwave-plugin-v1.4.0rc3.zip"
```

Or download it manually from:
https://github.com/nWave-ai/nWave-beta/releases

## Step 2: Install the Plugin

```bash
# Create the plugin directory
mkdir -p ~/.claude/plugins/cache/nwave

# Extract the ZIP
unzip nwave-plugin.zip -d ~/.claude/plugins/cache/nwave
```

## Step 3: Verify the Structure

Run this quick check to confirm the plugin extracted correctly:

```bash
ls ~/.claude/plugins/cache/nwave/.claude-plugin/plugin.json && echo "OK: plugin.json found"
ls ~/.claude/plugins/cache/nwave/agents/ | wc -l | xargs -I{} echo "OK: {} agents found"
ls ~/.claude/plugins/cache/nwave/commands/nw/ | wc -l | xargs -I{} echo "OK: {} commands found"
ls ~/.claude/plugins/cache/nwave/hooks/hooks.json && echo "OK: hooks.json found"
```

Expected output:
```
OK: plugin.json found
OK: 23 agents found
OK: 22 commands found
OK: hooks.json found
```

## Step 4: Start Claude Code

Open a terminal in any project directory and start Claude Code:

```bash
claude
```

## Step 5: Verify the Plugin Loaded

Once Claude Code starts, check the following:

### 5a. Check agents are available

Type:
```
/agents
```

You should see nWave agents listed (e.g., `nw-software-crafter`, `nw-solution-architect`).

### 5b. Check commands are available

Type:
```
/commands
```

You should see nWave commands (e.g., `nw:deliver`, `nw:design`, `nw:review`).

### 5c. Check hooks are active

Type:
```
/hooks
```

You should see nWave hooks registered for `PreToolUse`, `PostToolUse`, `SubagentStop`, `SessionStart`, and `SubagentStart`.

## Step 6: Smoke Test

Try running a simple command to verify end-to-end functionality:

```
/nw:review
```

This should display the review command help or prompt you for arguments. If you see an error about missing files or modules, please report it.

## Reporting Results

Please report your results with the following information:

1. **OS**: macOS / Linux / Windows (WSL)
2. **Python version**: `python3 --version`
3. **Claude Code version**: `claude --version`
4. **Step 5a**: Did agents load? How many?
5. **Step 5b**: Did commands load? How many?
6. **Step 5c**: Did hooks register? Which ones?
7. **Step 6**: Did the smoke test work?
8. **Any errors**: Copy-paste any error messages

## Uninstall

To remove the plugin:

```bash
rm -rf ~/.claude/plugins/cache/nwave
```

This does not affect your Claude Code installation or any other plugins.
