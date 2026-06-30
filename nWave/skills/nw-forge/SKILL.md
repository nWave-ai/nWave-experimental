---
name: nw-forge
description: "Creates new specialized agents using the 5-phase workflow (ANALYZE > DESIGN > CREATE > VALIDATE > REFINE). Use when building a new AI agent or validating an existing agent specification."
user-invocable: true
argument-hint: '[agent-name] - Optional: --type=[specialist|reviewer|orchestrator] --pattern=[react|reflection|router]'
---

# NW-FORGE: Create Agent (V2)

**Wave**: CROSS_WAVE
**Agent**: Zeus (nw-agent-builder)

## SSOT pointer (de-duplicated 2026-06-17)

This skill previously duplicated the `forge.md` command near-verbatim. The single
source of truth for the create-agent procedure is now:
- Command surface: `nWave/tasks/nw/forge.md` — PRESERVED, unchanged. `forge` keeps its
  name (no rename, no replacement command).
- Procedure: skill `nw-ab-create-agent` (one job, one trigger, deterministic 5-phase
  sequence: ANALYZE → DESIGN → CREATE → VALIDATE → REFINE; VALIDATE composes
  `nw-ab-validate-spec`). `forge` routes to this internal procedure.

Do not edit the procedure here — edit `nw-ab-create-agent`. This file is retained as
a pointer for backward compatibility and is flagged for DELETION at the cutover step
(held for Ale's explicit OK).

## Agent Invocation

@nw-agent-builder

Run the `nw-ab-create-agent` procedure to create the {agent-name} agent.

**Configuration:**
- agent_type: specialist | reviewer | orchestrator
- design_pattern: react | reflection | router | planning | sequential | parallel | hierarchical

## Success Criteria

- [ ] Agent definition under 400 lines (`wc -l`)
- [ ] Official YAML frontmatter format (name, description, tools, maxTurns)
- [ ] 11-point validation checklist passes
- [ ] Only divergent behaviors specified (no Claude defaults)
- [ ] 3-5 canonical examples included
- [ ] Domain knowledge extracted to Skills if >50 lines
- [ ] No aggressive language (no CRITICAL/MANDATORY/ABSOLUTE)
- [ ] Safety via platform features (frontmatter/hooks), not prose
- [ ] Caveman house style — dry/declarative, tables and compact lists, lean body, deep knowledge in skills
- [ ] `## Reasoning Mandate` section present (verdict-first, tables, evidence-dense)
- [ ] A05/A06 literal anchors present (`You MUST load your skill files` or `Your FIRST action before any other work`, AND `~/.claude/skills/nw-`)

## Next Wave

**Handoff To**: Agent installation and deployment
**Deliverables**: Agent specification file + Skill files (if any)

## Expected Outputs

```
~/.claude/agents/nw/nw-{agent-name}.md
~/.claude/skills/nw-{skill-name}/SKILL.md*.md    (if Skills needed)
```
