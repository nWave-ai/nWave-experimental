# ADR-003: Skill Structure Mapping for Plugin

## Status

Accepted

## Context

nWave skills are organized as:
```
nWave/skills/
  solution-architect/
    architecture-patterns.md
    roadmap-design.md
    critique-dimensions.md
    stress-analysis.md
  software-crafter/
    tdd-methodology.md
    hexagonal-testing.md
    ... (9 files)
  functional-software-crafter/
    fp-principles.md
    fp-domain-modeling.md
    ... (21 files)
  ... (22 agent directories, 98+ total files)
```

Each skill file has YAML frontmatter with `name` and `description` fields. Agent definitions reference skills by path (e.g., `~/.claude/skills/nw/solution-architect/architecture-patterns`).

The Claude Code plugin system discovers skills from `skills/` directory. Skills can be individual files or directories. The plugin system does NOT require a `SKILL.md` convention -- it discovers all `.md` files in skill subdirectories.

The question: does the nWave skill structure work as-is in the plugin, or does it need transformation?

## Decision

**Direct copy with no transformation.** The nWave skill structure (`skills/{agent-name}/{skill-file}.md`) is copied as-is into the plugin's `skills/` directory.

```
Plugin structure:
skills/
  solution-architect/
    architecture-patterns.md
    roadmap-design.md
    ...
  software-crafter/
    tdd-methodology.md
    ...
```

Agent definitions already reference skills by directory path. The plugin system auto-discovers skills from subdirectories. No renaming to `SKILL.md` is needed.

The existing custom installer installs skills to `~/.claude/skills/nw/{agent}/`. The plugin installs to `~/.claude/plugins/cache/nwave/skills/{agent}/`. Agent definitions within the plugin use relative references, so they resolve correctly within the plugin's directory.

## Alternatives Considered

### Alternative 1: Flatten to SKILL.md per directory

- **What**: Concatenate all skill files per agent into a single `SKILL.md`
- **Evaluation**: Matches what some Claude Code documentation suggests. Would reduce file count from 98 to 22.
- **Why Rejected**: Claude Code's progressive loading system works at the individual file level. Concatenating destroys the ability to load skills selectively (Level 2 loading). A single 5,000-token SKILL.md always loads fully, whereas individual files load only when relevant. Progressive loading is a core design advantage of nWave skills.

### Alternative 2: Add nw/ namespace prefix

- **What**: Install skills to `skills/nw/solution-architect/` instead of `skills/solution-architect/`
- **Evaluation**: Matches the custom installer's namespace convention. Prevents name collisions with other plugins' skills.
- **Why Rejected**: Plugin skills are already namespaced by plugin. `~/.claude/plugins/cache/nwave/skills/` is inherently namespaced. Adding `nw/` is redundant. Agent definitions within the plugin reference skills without the `nw/` prefix, so adding it would break references.

### Alternative 3: Transform to skill-per-file at root level

- **What**: Install each skill file as `skills/{skill-name}.md` (flatten directory structure)
- **Evaluation**: Simplest discovery. Each file is a standalone skill.
- **Why Rejected**: Loses the agent grouping. Agent definitions reference skills by `{agent-name}/{skill-name}`. Flattening creates 98 files at root level with naming collisions (multiple agents have `critique-dimensions.md`).

## Consequences

### Positive
- Zero transformation logic -- direct copy in build pipeline
- Preserves progressive skill loading (Level 2)
- Agent skill references work without modification
- Consistent with existing custom installer behavior

### Negative
- Plugin has 98+ skill files (larger plugin size, though all are small markdown)
- Skill names are agent-scoped, so discovering skills outside agent context requires browsing subdirectories
- If Claude Code plugin system changes skill discovery semantics, may need revisiting
