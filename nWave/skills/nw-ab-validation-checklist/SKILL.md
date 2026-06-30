---
name: nw-ab-validation-checklist
description: "KNOWLEDGE (data) — the 19-item agent-spec validation checklist. The item definitions the validate-spec / todoify procedures RUN against. No sequence of its own."
user-invocable: false
---

# nw-ab-validation-checklist (KNOWLEDGE / data)

**Kind**: KNOWLEDGE (data). The canonical 19-item list. `nw-ab-validate-spec` runs all 19 as ordered tasks; `nw-ab-todoify-file` runs items #14 + #15. This skill holds the definitions (SSOT), not the run-sequence.

| # | Item | Gate |
|---|------|------|
| 1 | Frontmatter | name, description, model, tools, maxTurns, skills present |
| 2 | Line Count | `wc -l` under 400; domain knowledge in skills |
| 3 | Divergence Only | zero instructions restating Claude defaults |
| 4 | Language Tone | zero CRITICAL/MANDATORY/ABSOLUTE outside skill loading |
| 5 | Examples | 3-5 `### Example` sections |
| 6 | Least Privilege | tools list minimal; no Write/Edit for reviewers |
| 7 | Safety | safety via frontmatter + hooks, not prose |
| 8 | Affirmative Phrasing | zero negatively-phrased rules |
| 9 | Terminology | one term per concept |
| 10 | Description Quality | description states WHEN to delegate |
| 11 | Skill Loading | mandatory section, imperative language, explicit `~/.claude/skills/nw-{name}/SKILL.md` |
| 12 | Load Directives | every phase has `Load:` matching frontmatter skills |
| 13 | No Orphan Skills | every frontmatter skill appears in a phase |
| 14 | Workflow Format | numbered task list (`N. **Name** — action. Gate: condition.`), not prose |
| 15 | Success Criteria Format | numbered/checkbox list, not prose |
| 16 | Caveman House Style | dry/declarative, tables + compact lists, lean body |
| 17 | Reasoning Mandate Present | `## Reasoning Mandate` section present |
| 18 | A05/A06 Literal Anchors | verbatim `You MUST load your skill files` OR `Your FIRST action before any other work` AND `~/.claude/skills/nw-` |
| 19 | One Job, One Trigger | one job + one trigger; KNOWLEDGE vs PROCEDURE classified; PROCEDURE states trigger + sequence + composition; zero multi-job parameterized switches; existing command + agent NAMES preserved (no rename/proliferation; new command is the rare `/nw-*` exception) |
