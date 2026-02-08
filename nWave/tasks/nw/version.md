# NW-VERSION: Framework Version Check

**Wave**: CROSS_WAVE
**Command**: `/nw:version`

## Overview

Display the current nWave framework version and build information by reading from project sources.

## How to Gather Version Data

1. **Version**: Read from `pyproject.toml` field `version`
2. **Build date**: Use current UTC timestamp (`date -u +"%Y-%m-%dT%H:%M:%SZ"`)
3. **Agent count**: Count files matching `nWave/agents/nw-*.md`
4. **Command count**: Count files matching `nWave/tasks/nw/*.md`

## Output

When invoked, gather data as described above and display:

```
nWave Framework
===============
Version: {version from pyproject.toml}
Build: {current UTC timestamp}
Agents: {count of nWave/agents/nw-*.md}
Commands: {count of nWave/tasks/nw/*.md}

Key Features:
- Task tool delegation for sub-commands
- TDD cycle methodology (tracked in execution-log.yaml)
- step_type support (atdd, research, infrastructure)
- Skill-based v2 architecture

Verification Markers:
- execute.md: Contains DES Prompt Template (single source of truth)
- develop.md: Contains "/nw:execute @nw-software-crafter" delegation pattern
```

## Verification

1. **TDD Cycle**: execute command references `execution-log.yaml` as phase tracking format
2. **Task Delegation**: develop command uses `Task(subagent_type=..., prompt='/nw:...')` pattern
3. **Counts**: Agent and command counts are derived dynamically from file system
