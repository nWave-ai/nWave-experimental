---
name: nw-ab-validation-checklist
description: "KNOWLEDGE (data) — the 19-item agent-spec validation checklist. The item definitions the validate-spec procedure RUNS against. No sequence of its own."
user-invocable: false
---

# nw-ab-validation-checklist (KNOWLEDGE / data)

**Kind**: KNOWLEDGE (data). The canonical 19-item list. `nw-ab-validate-spec` runs all 19 in order. This skill holds the definitions (SSOT), not the run-sequence.

| # | Item | Gate |
|---|------|------|
| 1 | Frontmatter | name, description, model, tools, maxTurns, skills present |
| 2 | Line Count | `wc -l` under 400; domain knowledge in skills |
| 3 | Divergence Only | zero instructions restating Claude defaults |
| 6 | Least Privilege | tools list minimal; no Write/Edit for reviewers |
| 7 | Safety by construction (GDP-0) | tool-surface frontmatter + typed grammar first, not prose; a hook only last-resort with a recorded reason |
| 8 | Affirmative Phrasing | zero negatively-phrased rules |
| 9 | Terminology | one term per concept |
| 10 | Description Quality | description states WHEN to delegate |
| 15 | Success Criteria Format | numbered/checkbox list, not prose |
| 16 | Caveman House Style | dry/declarative, tables + compact lists, lean body |
| 17 | Reasoning Mandate Present | `## Reasoning Mandate` section present |
| 19 | One Job, One Trigger | one job + one trigger; KNOWLEDGE vs PROCEDURE classified; PROCEDURE states trigger + sequence + composition; zero multi-job parameterized switches; existing command + agent NAMES preserved (no rename/proliferation; new command is the rare `/nw-*` exception) |
