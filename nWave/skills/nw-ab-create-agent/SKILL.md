---
name: nw-ab-create-agent
description: "PROCEDURE — create a NEW agent via the 5-phase workflow (ANALYZE→DESIGN→CREATE→VALIDATE→REFINE). Trigger: build a new AI agent. Composes nw-ab-validate-spec."
user-invocable: false
---

# nw-ab-create-agent (PROCEDURE)

**Kind**: PROCEDURE | **One job**: create one new agent | **One trigger**: a new AI agent must be built.

## Deterministic step-sequence (run every time, in order)

Run these steps in order:

1. **ANALYZE** — Load `~/.claude/skills/nw-agent-creation-workflow/SKILL.md`. Identify single clear responsibility. Check overlap with existing agents (Glob `nWave/agents/`). Classify specialist | reviewer | orchestrator. Determine minimum tools. Gate: responsibility defined, no overlap, classification chosen.
2. **DESIGN** — Load `~/.claude/skills/nw-design-patterns/SKILL.md`. Select design pattern. Define role, goal, divergent principles. Plan skills extraction. Draft frontmatter. Gate: pattern selected, principles drafted, frontmatter ready.
3. **CREATE** — Load `~/.claude/skills/nw-ab-agent-template/SKILL.md` + `~/.claude/skills/nw-ab-house-style/SKILL.md`. Write agent `.md` from the template, caveman-curated. Inject the Reasoning Mandate verbatim. Extract skills if domain knowledge >50 lines. Gate: file written and identity metadata present.
4. **VALIDATE** — compose ▶ `nw-ab-validate-spec` (the 19-item checklist + anti-pattern scan). Gate: all 19 pass, zero anti-patterns.
5. **REFINE** — Address failures. Add instructions only for observed failure modes. Re-validate. Gate: all items pass.

## Composition

- COMPOSES (KNOWLEDGE): `nw-agent-creation-workflow`, `nw-design-patterns`, `nw-ab-agent-template`, `nw-ab-house-style`.
- COMPOSES (PROCEDURE): `nw-ab-validate-spec` (phase 4).

## Success Criteria

- [ ] Agent invoked via the 5-phase sequence, no phase skipped
- [ ] `nw-ab-validate-spec` composed at phase 4 (not re-inlined)
- [ ] Under 400 lines, anchors + Reasoning Mandate present, before/after lines reported
