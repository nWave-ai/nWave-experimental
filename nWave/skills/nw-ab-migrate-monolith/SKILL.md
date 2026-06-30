---
name: nw-ab-migrate-monolith
description: "PROCEDURE — migrate a legacy monolithic agent (>400L / embedded config / aggressive language) to lean core + skills, RECURSING into oversized referenced skills. Trigger: a bloated legacy agent spec, or a monolithic skill (>250L bundling >1 job). Composes nw-ab-validate-spec."
user-invocable: false
---

# nw-ab-migrate-monolith (PROCEDURE)

**Kind**: PROCEDURE | **One job**: migrate one monolith (agent OR skill) to v2 (lean core + narrow skills) | **One trigger**: a legacy agent over 400 lines / with embedded config / aggressive language, OR a referenced skill over ~250 lines that bundles more than one job.

A monolithic SKILL migrates exactly like a monolithic AGENT: the skill keeps its NAME as a lean core that COMPOSES the extracted one-job-one-trigger skills. Decomposition is recursive — extracting the agent's knowledge is not done until every skill it references (new OR reused) is itself one-job-one-trigger.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **MEASURE** — Load `~/.claude/skills/nw-design-patterns/SKILL.md`. `wc -l` the source; measure prose share. Gate: before-count + prose-share recorded.
2. **EXTRACT FRONTMATTER** — Move any embedded YAML config to frontmatter (name, description, model, tools, maxTurns, skills). Gate: frontmatter valid.
3. **REMOVE DUPLICATION** — Delete platform-duplicating frameworks (safety/security prose → frontmatter+hooks) and default-behavior specifications. Gate: zero platform-duplicating sections.
4. **EXTRACT KNOWLEDGE (REUSE-first)** — grep existing skills FIRST; extract ONLY still-inline blocks. Move domain knowledge into skills. Gate: core body lean, knowledge in skills, zero duplication.
5. **DECOMPOSE-AND-RECOMPOSE OVERSIZED SKILLS (recursive)** — for EVERY skill the migrated agent references (new OR reused), if it is over ~250L OR bundles more than one job, it is itself a migrate-monolith target. Apply this same procedure recursively:
   - **DECOMPOSE** — split each bundled job into its own one-job-one-trigger skill (KNOWLEDGE vs PROCEDURE classified). One skill per Mandate / per concern / per rubric — never one parameterized skill behind a switch.
   - **DEFINE TRIGGERS (the hard part — particular attention here)** — the trigger is what makes a skill one-job-one-trigger, not the line count. Give each narrow skill a SHARP, DISTINCT trigger stated as a concrete firing condition (not "load when relevant"). The full set of triggers must PARTITION the monolith's trigger-space: zero overlap (two skills firing on the same condition = ambiguous routing — sharpen one), zero gap (a condition that fires nothing = lost coverage — add/widen one). A skill that would misfire has a too-broad trigger; fix the trigger, never add rules. Gate: every narrow skill has a concrete distinct trigger; triggers partition the monolith's space with no overlap and no gap.
   - **RECOMPOSE** — the original skill KEEPS its name and becomes a lean core that COMPOSES the extracted narrow skills (lists them under Composition + a loading table); it is NOT left gutted and the narrow skills are NOT left orphaned. The recomposed core + its narrow skills together cover everything the monolith did.
   - **VERIFY EQUIVALENCE** — diff coverage: every job/section/rule the monolith held maps to exactly one narrow skill (no knowledge lost, no duplication, no orphan). Gate: no referenced skill >250L bundling >1 job remains; every extracted narrow skill is composed by a named core; coverage diff is complete.
   - **TERMINAL STOP CONDITION — trigger-unity, not line-count.** The recursion stops when each skill fires on ONE trigger, NOT when each skill is under a line count. A narrow skill that lands at 150-250L bundling several SUB-concerns under a SINGLE trigger is DONE — do not split it further. The ~250L figure is the *entry* threshold (a skill over it is a decomposition CANDIDATE); the *exit* test is "does this skill have exactly one firing condition?". Split on multiple triggers, never on size alone.
6. **DE-ESCALATE LANGUAGE** — Replace CRITICAL/ABSOLUTE with direct statements (exception: skill-loading MUST). Gate: zero aggressive language outside skill loading.
7. **VALIDATE** — compose ▶ `nw-ab-validate-spec`. Gate: all 19 pass, zero anti-patterns.
8. **REPORT** — before/after line counts for the agent AND every decomposed-and-recomposed skill. Gate: all numbers reported.

Hard rule: do NOT silently edit hash-pinned skills (`tests/build/unit/test_skill_restructuring.py` baseline). If a pinned skill must change (including a decompose-and-recompose), REPORT the required hash update; do not bump it yourself.

Names rule: decomposition NEVER renames the agent or an established skill. A decomposed skill keeps its name as the recomposing core; the extracted narrow skills take new descriptive names under the same domain prefix. The user-facing command/agent surface is untouched.

## Composition

- COMPOSES (KNOWLEDGE): `nw-design-patterns`, `nw-ab-house-style`.
- COMPOSES (PROCEDURE): `nw-ab-validate-spec` (step 7); RECURSES into itself for oversized referenced skills (step 5).

## Success Criteria

- [ ] Before/after line counts reported for the agent AND every decomposed skill
- [ ] Domain knowledge in skills, core lean
- [ ] No referenced skill >250L bundling >1 job left intact (decomposed-and-recomposed)
- [ ] Every extracted narrow skill composed by a named recomposing core (zero orphans, name preserved)
- [ ] Every narrow skill has a concrete, distinct trigger; the trigger-set partitions the monolith's space (no overlap, no gap)
- [ ] Coverage-equivalence diff complete (monolith → narrow skills, no knowledge lost)
- [ ] `nw-ab-validate-spec` composed (not re-inlined), all 19 pass
