---
description: "Archives a completed feature to docs/evolution/, migrates lasting artifacts to permanent directories, and preserves the feature workspace as living history. Use after current feature completion evidence passes."
disable-model-invocation: true
argument-hint: '[agent] [feature-id] - Example: @nw-platform-architect "auth-upgrade"'
---

# NW-FINALIZE

## Invocation Contract

```
/nw-finalize @{agent} "{feature-id}"
```

- `agent` defaults to `nw-platform-architect` when omitted.
- `feature-id` identifies the feature workspace and completion evidence to archive.

## Methodology

Load `~/.claude/skills/nw-finalize/SKILL.md` before validating completion or dispatching. That skill is the sole owner of completion evidence, evolution-document content, artifact migration, workspace preservation, session-artifact cleanup, and final outputs.
