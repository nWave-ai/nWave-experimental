---
description: Dispatches an expert reviewer for a baseline, feature delta, task, or implementation.
disable-model-invocation: true
argument-hint: '[agent] [artifact-type] [artifact-path] - Example: @<base-agent> feature-delta "docs/feature-delta.md"'
---

# NW-REVIEW

## Invocation Contract

```
/nw-review @{agent-name} {artifact-type} "{artifact-path}" [--dimensions=rpp] [--from=1] [--to=3]
```

- Artifact type: `baseline`, `feature-delta`, `task`, or `implementation`.
- Artifact path: an existing file or directory.
- RPP options: `--dimensions=rpp` with optional `--from=1..6` and `--to=1..6`.

## Methodology

Load `~/.claude/skills/nw-review/SKILL.md` before validating or dispatching. That skill is the sole owner of review standards, rigor handling, reviewer derivation, RPP, feedback labels, and verdicts.
