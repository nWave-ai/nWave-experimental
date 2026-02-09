# NW-VERSION: Framework Version Check

**Wave**: CROSS_WAVE
**Command**: `/nw:version`

## Overview

Display the current nWave framework version and build information by reading from project sources.

## How to Gather Version Data

1. **Version**: Read from `pyproject.toml` field `version`
2. **Build date**: Use current UTC timestamp (`date -u +"%Y-%m-%dT%H:%M:%SZ"`)
3. **Agent count**: Count files matching `~/.claude/agents/nw/nw-*.md`
4. **Command count**: Count files matching `~/.claude/commands/nw/*.md`

## Output

When invoked, gather data as described above and display:

```
nWave Framework
===============
Version: {version from pyproject.toml}
Build: {current UTC timestamp}
Agents: {count of ~/.claude/agents/nw/nw-*.md}
Commands: {count of ~/.claude/commands/nw/*.md}
```
