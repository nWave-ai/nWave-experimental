---
name: nw-ab-anti-patterns
description: "KNOWLEDGE — agent/skill/command anti-pattern catalog with fixes. Reference scanned by validate-spec; no sequence."
user-invocable: false
---

# nw-ab-anti-patterns (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference catalog). Scanned by `nw-ab-validate-spec` (anti-pattern step). No forced sequence.

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Monolithic agent (2000+ lines) | Context rot; 3x token cost | Extract to Skills, target 200-400 lines |
| Embedded safety frameworks | Duplicates platform; wastes tokens | Construct safety first — tool surface (frontmatter `tools`/`permissionMode`), typed grammar; hooks last resort (GDP-0) |
| Aggressive language | Overtriggering on Opus 4.6 | Calm, direct statements |
| Zero examples | Fails on subtle/critical behaviors | Include 3-5 canonical examples |
| Exhaustive examples (30+) | Diminishing returns; context rot | Keep 3-5 diverse canonical cases |
| Specifying default behaviors | 65% of specs redundant | Specify only divergent behaviors |
| Negatively phrased rules | Less effective than affirmative | Phrase affirmatively |
| Compound instructions | Confuses agent reasoning | Split into separate focused steps |
| Inconsistent terminology | Amplifies confusion in longer contexts | One term per concept throughout |
| Orphan skills in frontmatter | Skills declared but no `Load:` directives — never loaded in sub-agent mode | Add mandatory skill loading section + `Load:` per phase |
| Missing skills path | Sub-agents can't find skills without explicit path | Document `~/.claude/skills/nw-{skill-name}/SKILL.md` in agent |
| Soft skill loading language | "Should load", "if applicable", "consider loading" — agents skip under turn pressure | Use imperative: "You MUST load", "Load NOW before proceeding" |
| Over-compressed examples | `### Example N:` headers removed during compression — eval tools can't find them | Keep example section headers verbatim |
| Compressed AskUserQuestion options | Runtime menu items compressed to pipes — lose decision tree structure | Preserve numbered options with descriptions verbatim |
| Broad multi-job asset | One agent/skill does N jobs; runtime re-decides "what good means" each run | Split into N one-job-one-trigger INTERNAL skills — do not add rules, do not parameterize |
| Renaming/proliferating the command surface | Renaming an established command (e.g. `forge`) or adding new user-facing commands breaks muscle-memory + the preserve-names rule | Route the split to internal skills behind the EXISTING command/agent; preserve names; a new command is the rare exception, named `/nw-*` |
