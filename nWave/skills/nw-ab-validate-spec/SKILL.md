---
name: nw-ab-validate-spec
description: "PROCEDURE — validate an EXISTING agent spec against the 19-item checklist. Trigger: checking a spec for compliance (also the shared composition target create/migrate/merge invoke). One job: run the checklist, report pass/fail."
user-invocable: false
---

# nw-ab-validate-spec (PROCEDURE)

**Kind**: PROCEDURE | **One job**: validate an agent spec | **One trigger**: an existing agent spec must be checked for compliance (standalone, or composed by create/migrate/merge after a write).

This is the SHARED composition target. `nw-ab-create-agent`, `nw-ab-migrate-monolith`, and `nw-ab-merge-agents` all invoke this skill after writing — never re-inline the checklist.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **Frontmatter** — name, description, model, tools, maxTurns, skills present. Gate: all required fields present.
2. **Line Count** — `wc -l` total under 400; domain knowledge in skills. Gate: count reported, under threshold.
3. **Divergence Only** — flag any instruction restating Claude defaults. Gate: zero redundant instructions.
4. **Language Tone** — scan for CRITICAL/MANDATORY/ABSOLUTE (exception: skill-loading MUST). Gate: zero violations outside skill loading.
5. **Examples** — count `### Example` sections. Gate: 3-5 present.
6. **Least Privilege** — tools list contains only what the agent needs; no Write/Edit for reviewers. Gate: no unnecessary tools.
7. **Safety** — safety via frontmatter fields + hooks, not prose. Gate: zero prose security sections.
8. **Affirmative Phrasing** — convert "Don't do Y" to "Do X". Gate: zero negative phrasings.
9. **Terminology** — one term per concept. Gate: consistent terminology.
10. **Description Quality** — description states WHEN to delegate. Gate: trigger condition present.
11. **Skill Loading** — mandatory section with imperative language + explicit `~/.claude/skills/nw-{name}/SKILL.md` paths. Gate: present, paths explicit.
12. **Load Directives** — every workflow phase has `Load:` matching frontmatter skills. Gate: no phases missing loads.
13. **No Orphan Skills** — every frontmatter skill appears in a phase. Gate: zero orphans.
14. **Workflow Format** — workflow is numbered task list (`N. **Name** — action. Gate: condition.`), not prose. Gate: all phases numbered.
15. **Success Criteria Format** — criteria are numbered/checkbox list, not prose. Gate: structured.
16. **Caveman House Style** — dry/declarative, tables + compact lists, lean body, deep knowledge in skills. Gate: confirmed.
17. **Reasoning Mandate Present** — `## Reasoning Mandate` section present. Gate: present.
18. **A05/A06 Literal Anchors** — verbatim `You MUST load your skill files` OR `Your FIRST action before any other work` AND token `~/.claude/skills/nw-`. Gate: both present.
19. **One Job, One Trigger** — one job + one trigger per asset; KNOWLEDGE vs PROCEDURE classified; PROCEDURE states trigger + deterministic sequence + composition; zero multi-job parameterized switches; existing command + agent NAMES preserved (no rename/proliferation; new command is the rare `/nw-*` exception). Gate: confirmed.

Then run the anti-pattern scan (`nw-ab-anti-patterns`). Gate: zero anti-patterns.

## Composition

- COMPOSES (KNOWLEDGE): `nw-ab-validation-checklist` (the 19-item data), `nw-ab-anti-patterns`, `nw-ab-critique-dimensions`, `nw-agent-testing`.
- Note: the validator script `scripts/validation/validate_framework_templates.py` (A05/A06 literal checks) is run by the orchestrator/reviewer, not inside this skill.

## Success Criteria

- [ ] All 19 checklist items run as ordered tasks
- [ ] Anti-pattern scan run
- [ ] Pass/fail reported per item with line-count
