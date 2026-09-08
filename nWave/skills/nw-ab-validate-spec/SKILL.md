---
name: nw-ab-validate-spec
description: "PROCEDURE — validate an EXISTING agent spec against the 19-item checklist. Trigger: checking a spec for compliance (also the shared composition target create/migrate/merge invoke). One job: run the checklist, report pass/fail."
user-invocable: false
---

# nw-ab-validate-spec (PROCEDURE)

**Kind**: PROCEDURE | **One job**: validate an agent spec | **One trigger**: an existing agent spec must be checked for compliance (standalone, or composed by create/migrate/merge after a write).

This is the SHARED composition target. `nw-ab-create-agent`, `nw-ab-migrate-monolith`, and `nw-ab-merge-agents` all invoke this skill after writing — never re-inline the checklist.

## Deterministic step-sequence (run every time, in order)

Run these steps in order:

1. **Frontmatter** — name, description, model, tools, maxTurns, skills present. Gate: all required fields present.
2. **Line Count** — `wc -l` total under 400; domain knowledge in skills. Gate: count reported, under threshold.
3. **Divergence Only** — flag any instruction restating Claude defaults. Gate: zero redundant instructions.
6. **Least Privilege** — tools list contains only what the agent needs; no Write/Edit for reviewers. Gate: no unnecessary tools.
7. **Safety by construction (GDP-0)** — which producer makes the unsafe action unrepresentable? Tool-surface frontmatter fields and typed grammar first; a hook only with a recorded reason, never prose. Gate: zero prose security sections; any hook cites its construction-can't-cover reason.
8. **Affirmative Phrasing** — convert "Don't do Y" to "Do X". Gate: zero negative phrasings.
9. **Terminology** — one term per concept. Gate: consistent terminology.
10. **Description Quality** — description states WHEN to delegate. Gate: trigger condition present.
15. **Success Criteria Format** — criteria are numbered/checkbox list, not prose. Gate: structured.
16. **Caveman House Style** — dry/declarative, tables + compact lists, lean body, deep knowledge in skills. Gate: confirmed.
17. **Reasoning Mandate Present** — `## Reasoning Mandate` section present. Gate: present.
19. **One Job, One Trigger** — one job + one trigger per asset; KNOWLEDGE vs PROCEDURE classified; PROCEDURE states trigger + deterministic sequence + composition; zero multi-job parameterized switches; existing command + agent NAMES preserved (no rename/proliferation; new command is the rare `/nw-*` exception). Gate: confirmed.

Then run the anti-pattern scan (`nw-ab-anti-patterns`). Gate: zero anti-patterns.

## Composition

- COMPOSES (KNOWLEDGE): `nw-ab-validation-checklist` (the 19-item data), `nw-ab-anti-patterns`, `nw-ab-critique-dimensions`, `nw-agent-testing`.
- Note: the validator script `scripts/validation/validate_framework_templates.py` checks frontmatter, identity, reviewer write isolation, and declared-skill references.

## Success Criteria

- [ ] Applicable checklist items run as ordered tasks
- [ ] Anti-pattern scan run
- [ ] Pass/fail reported per item
