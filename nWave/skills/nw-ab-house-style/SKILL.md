---
name: nw-ab-house-style
description: "KNOWLEDGE — caveman-native authoring house style + by-construction guarantees (Reasoning Mandate injection, A05/A06 anchors, measured-gain compression). Reference for create/migrate; no sequence."
user-invocable: false
---

# nw-ab-house-style (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference). Loaded by `nw-ab-create-agent` (CREATE) and `nw-ab-migrate-monolith` (EXTRACT). No forced sequence.

## House style

Author caveman-curated: dry, declarative, tables and compact one-line bold-lead lists, zero narrative padding. Agent body lean (~100-200 lines, role+routing+contract); deep knowledge in skills (<5000 tokens each). Exemplar: `nw-security-analyst` — 104-line agent (93 body), deep knowledge in 2 skills (96+107=203). Byte-exact preservation: `### Example N:` headers, NORMATIVE blocks, code/YAML, AskUserQuestion trees, machine content. User-facing templates stay clear, not compressed.

## By-construction guarantees

1. **House style** — every created/modified asset is caveman-curated (above).
2. **Reasoning-mandate injection** — every created/modified agent gets the `## Reasoning Mandate` block inserted verbatim. Depth from rigor, never padding.
3. **A05/A06 literal-anchor guarantee** — `scripts/validation/validate_framework_templates.py` A05/A06 are LITERAL substring checks. Every authored agent MUST contain verbatim one of `You MUST load your skill files` OR `Your FIRST action before any other work` (A05) AND the path token `~/.claude/skills/nw-` (A06). Verify both before declaring done — absence blocks the commit.
4. **Opportunistic retro-compression (measured-gain ≥20% or skip)** — on MODIFY: measure prose share first. Projected reduction ≥20% → compress with hard invariants (pre-existing blocks/tables byte-identical, `### Example N:` + NORMATIVE preserved, content-pin tests green). Below 20% → SKIP and report the measurement. Hash-pinned skills (md5 baseline in `tests/build/unit/test_skill_restructuring.py`): never silently edit; REPORT the required hash bump, do not bump it yourself.

## Reasoning Mandate block (inject verbatim)

```markdown
## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.
```
