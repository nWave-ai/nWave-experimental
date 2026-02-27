# Skill Activation Strategy Review — All Agents

**Date**: 2026-02-27
**Status**: COMPLETE — All fixes applied, 204/204 tests green

## Review Protocol

Each agent loaded ALL its own skills and evaluated its own activation strategy against these criteria:

1. **Path correctness** — skill loading path matches installed location (`~/.claude/skills/nw/<dir>/`)
2. **Frontmatter ↔ body alignment** — every skill in YAML `skills:` appears in loading instructions (and vice versa)
3. **Phase/trigger coherence** — skills load at the right moment for the workflow
4. **Cross-reference safety** — no forward dependencies on unloaded skills
5. **Skill sufficiency** — no knowledge gaps for the agent's workflow
6. **Missing skills** — skills the agent needs but doesn't have
7. **Unnecessary skills** — skills the agent has but doesn't use

---

## Agents Already Reviewed

### nw-workshopper — APPROVED
All 12 skills, 9/9 dimensions PASS. Path fixed (`nw-workshopper/` → `workshopper/`).

### nw-workshopper-reviewer — FIXED
Path fixed + 2 BLOCKING skills added (`psychological-safety`, `curriculum-series-design`). Now 6 skills.

---

## Batch 1 — Heavy Agents

### nw-product-owner (17 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/product-owner/`
**Alignment**: PASS — 17/17 skills referenced
**Phase coherence**: FAIL
**Cross-references**: PASS
**Sufficiency**: PASS
**Missing skills**: NONE
**Unnecessary skills**: NONE

**Findings**:
1. `shared-artifact-tracking` — Strategy table places it in Phase 2 (correct) but Phase 2 workflow text only loads `design-methodology`. Phase 3 text loads `shared-artifact-tracking`. **Fix**: Add to Phase 2 workflow `Load:` directive alongside `design-methodology`.
2. `ux-emotional-design` — Assigned to Phase 3 ("Emotional Arc") but emotional arc mapping happens in Phase 2. By Phase 3, annotations are already written. **Fix**: Move to Phase 2 on-demand, triggered by "Journey has emotional annotations needing depth."
3. Strategy table Phase 3 shows `--` for Always Load but Phase 3 workflow loads `shared-artifact-tracking`. **Fix**: Align table with body text.

---

### nw-functional-software-crafter (15 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/functional-software-crafter/` + shared `~/.claude/skills/nw/software-crafter/`
**Alignment**: FAIL — 14 language-specific files exist on disk but are NOT in frontmatter or loading table: `fp-clojure`, `fp-fsharp`, `fp-haskell`, `fp-kotlin`, `fp-scala`, `pbt-dotnet`, `pbt-erlang-elixir`, `pbt-go`, `pbt-haskell`, `pbt-jvm`, `pbt-python`, `pbt-rust`, `pbt-typescript`, `tlaplus-verification`
**Phase coherence**: FAIL
**Cross-references**: PASS
**Sufficiency**: FAIL
**Missing skills**: Language detection mechanism needed
**Unnecessary skills**: NONE

**Findings**:
1. **14 orphaned skill files** — present on disk but invisible to agent. No loading trigger for language-specific FP/PBT skills. **Fix**: Add to frontmatter + add Phase 0 PREPARE language-detection step to load the matching `fp-{lang}` + `pbt-{platform}` skills.
2. `fp-algebra-driven-design` — Loaded at Phase 3 GREEN (too late). Algebraic API design should inform test writing. **Fix**: Move to Phase 0 PREPARE or Phase 1 RED_ACCEPTANCE.
3. `fp-usable-design` — Loaded at Phase 3 GREEN (too late). Naming conventions should be established before RED. **Fix**: Move to Phase 0 PREPARE.
4. `property-based-testing` (shared) overlaps with `pbt-fundamentals` (FP-specific) — both loaded at Phase 2 RED_UNIT. **Fix**: Clarify distinction or merge.
5. Phase "1-2" label is ambiguous (RED_ACCEPTANCE vs RED_UNIT are distinct phases). **Fix**: Clarify.

---

### nw-software-crafter (10 skills) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/software-crafter/`
**Alignment**: PASS — 10/10
**Phase coherence**: PASS (1 borderline LOW-severity item: `hexagonal-testing` could be earlier, but defensible)
**Cross-references**: PASS — 7 cross-refs all safe
**Sufficiency**: PASS
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

---

### nw-agent-builder (8 skills) — NEEDS_FIXES

**Path**: FAIL — No explicit skill loading path. The "Skill Loading" section is inside the template code block, not the agent's own instructions.
**Alignment**: FAIL — 4 of 6 operational skills are orphaned (`agent-testing`, `critique-dimensions` never referenced in workflow). Note: frontmatter says 8 but includes `{domain-knowledge-skill}` template variable and `migration-patterns`.
**Phase coherence**: FAIL — Phase 4 VALIDATE has no skills loaded; `critique-dimensions` and `agent-testing` should load there.
**Cross-references**: PASS
**Sufficiency**: FAIL — Phase 4 relies only on inline 14-point checklist, missing the richer 9-dimension review framework from `critique-dimensions` and 5-layer testing from `agent-testing`.
**Missing skills**: NONE (files exist, just not activated)
**Unnecessary skills**: NONE

**Findings**:
1. **No own Skill Loading section** — only the template has one. **Fix**: Add dedicated section with path `~/.claude/skills/nw/agent-builder/` and phase-skill table.
2. `agent-testing` orphaned — never referenced. **Fix**: Load at Phase 4 VALIDATE.
3. `critique-dimensions` orphaned — never referenced. **Fix**: Load at Phase 4 VALIDATE.
4. All loading language is soft ("load `skill-name` skill") instead of imperative. **Fix**: Convert to `Load:` directives.
5. Validation checklist count stale — says "11-point" but actually 14 items. **Fix**: Update references.
6. **Critical irony**: agent mandates robust skill loading for agents it creates but doesn't follow its own rules.

---

### nw-platform-architect (7 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/platform-architect/`
**Alignment**: PASS — 7/7
**Phase coherence**: PASS (with 1 gap)
**Cross-references**: PASS
**Sufficiency**: PASS (with 1 gap)
**Missing skills**: NONE
**Unnecessary skills**: NONE

**Findings**:
1. `production-readiness` — Not loaded until Phase 7, but Phase 6 (Completion Validation) needs its quality gate criteria. **Fix**: Load at Phase 6 (not just Phase 7).
2. `deployment-strategies` — Strategy table says conditional trigger ("Deployment strategy selection") but Phase 3 body loads it unconditionally. **Fix**: Make table entry unconditional to match body.
3. Minor content overlap between `cicd-and-deployment` and `deployment-strategies` deployment sections. **Fix**: Remove overlap from `cicd-and-deployment`, add cross-reference.

---

## Batch 2 — Medium Agents

### nw-solution-architect (4 skills) — NEEDS_FIXES

**Path**: PASS
**Alignment**: PASS — 4/4
**Phase coherence**: FAIL
**Sufficiency**: PASS
**Missing skills**: NONE
**Unnecessary skills**: FAIL — `critique-dimensions` ownership confused

**Findings**:
1. `critique-dimensions` — Phase 6 trigger says "Via reviewer" but Morgan loads it. The reviewer declares it in frontmatter but file does NOT exist at `nWave/skills/solution-architect-reviewer/`. **Cross-agent bug**: reviewer will fail at its Phase 2 `Load:`. **Fix**: Move file to reviewer's dir or keep in Morgan with clarified trigger.
2. `roadmap-design` — Loaded at Phase 5 (validation) but Phase 4 creates roadmap steps without it. **Fix**: Consider loading at Phase 4.

### nw-researcher (4 skills) — APPROVED

All 7 criteria PASS. Minor: `operational-safety` fallback references `source-verification` before loaded (edge case only).

### nw-data-engineer (4 skills) — APPROVED

All 7 criteria PASS. Clean on-demand strategy. Security skill unconditionally loaded at Phase 3.

### nw-troubleshooter (3 skills) — NEEDS_FIXES

**Phase coherence**: FAIL
**Sufficiency**: FAIL

**Findings**:
1. `investigation-techniques` — Loaded at Phase 4 but contains Problem Categorization and Evidence Collection needed at Phase 1. **Fix**: Load at Phase 1.
2. Phase 3 validation — Only ~6 lines for backwards chain validation. **Fix**: Expand in `five-whys-methodology`.
3. Loading table description misleading. **Fix**: Update.

### nw-product-discoverer (3 skills) — NEEDS_FIXES

**Phase coherence**: FAIL

**Findings**:
1. Claims "on-demand" but all 3 loaded at Phase 1. **Fix**: Relabel as eager loading or restructure.
2. Phase 4 implicitly depends on `opportunity-mapping` loaded at Phase 1. **Fix**: Add explicit reference.

### nw-documentarist (3 skills) — APPROVED

All 7 criteria PASS. Deterministic Phase 2→3→4 loading, dependency-safe.

---

## Batch 3 — Specialist Agents + Reviewers (Part 1)

### nw-acceptance-designer (3 skills) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/acceptance-designer/`
**Alignment**: PASS — 3/3
**Phase coherence**: PASS
**Cross-references**: PASS
**Sufficiency**: PASS
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

### nw-product-owner-reviewer (3 skills) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/product-owner/`
**Alignment**: PASS — 3/3
**Phase coherence**: PASS
**Cross-references**: PASS
**Sufficiency**: PASS
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

### nw-platform-architect-reviewer (3 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/platform-architect/`
**Alignment**: PASS — 3/3
**Phase coherence**: FAIL
**Sufficiency**: FAIL

**Findings**:
1. `review-criteria` skill lacks DESIGN wave-specific criteria. Reviewer evaluates DESIGN+DEVOP artifacts but criteria skew toward DEVOP. **Fix**: Add DESIGN-wave review dimensions (ADR quality, technology selection, component boundaries).
2. Agent not registered in `framework-catalog.yaml`. **Fix**: Add entry.

### nw-agent-builder-reviewer (2 skills) — NEEDS_FIXES

**Path**: FAIL — `~/.claude/skills/nw/agent-builder-reviewer/`
**Alignment**: FAIL
**Sufficiency**: FAIL

**Findings**:
1. **CRITICAL**: `critique-dimensions` declared in frontmatter but file does NOT exist at `nWave/skills/agent-builder-reviewer/critique-dimensions.md`. Phase 2 `Load:` will fail silently. **Fix**: Create the file or cross-reference from another agent's directory.
2. `agent-testing` — not in frontmatter but needed for Phase 2 validation depth. **Fix**: Add to frontmatter and loading table.

### nw-software-crafter-reviewer (2 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/software-crafter-reviewer/`
**Alignment**: PASS — 2/2
**Phase coherence**: PASS
**Sufficiency**: FAIL

**Findings**:
1. `tdd-methodology` — Referenced implicitly (reviewer checks TDD compliance) but not in frontmatter or loading table. Reviewer uses generic TDD knowledge instead of the project's specific TDD schema. **Fix**: Add `tdd-methodology` cross-ref from `software-crafter/` to frontmatter and load at Phase 1.

### nw-solution-architect-reviewer (2 skills) — NEEDS_FIXES

**Path**: FAIL — `critique-dimensions` file missing from `solution-architect-reviewer/`
**Alignment**: FAIL — frontmatter declares `critique-dimensions` but file absent
**Phase coherence**: FAIL — Phase 2 `Load:` will fail
**Sufficiency**: FAIL — only `roadmap-review-checks` present; no architecture review capability

**Findings**:
1. **CRITICAL**: `critique-dimensions` declared in frontmatter but file does NOT exist at `solution-architect-reviewer/`. Only `roadmap-review-checks.md` present. File exists at sibling `solution-architect/critique-dimensions.md`. **Fix**: Copy file to `solution-architect-reviewer/`.

---

## Batch 4 — Light Reviewers

### nw-acceptance-designer-reviewer (2 skills) — NEEDS_FIXES

**Path**: PASS — `~/.claude/skills/nw/acceptance-designer/` (cross-ref from parent)
**Alignment**: FAIL — `bdd-methodology` exists in `acceptance-designer/` but NOT declared in frontmatter or loading table
**Phase coherence**: PASS — both declared skills loaded at Phase 1
**Cross-references**: PASS
**Sufficiency**: FAIL — Phase 2 GWT format compliance lacks foundational BDD methodology
**Missing skills**: `bdd-methodology` (exists on disk, not declared)
**Unnecessary skills**: NONE

**Findings**:
1. `bdd-methodology` — Exists at `acceptance-designer/bdd-methodology.md` but not in frontmatter or loading table. Contains scenario writing rules, GWT structure, and pytest-bdd patterns needed for Phase 2 GWT evaluation. **Fix**: Add to frontmatter + load at Phase 1.

### nw-documentarist-reviewer (2 skills) — NEEDS_FIXES

**Path**: FAIL — Agent says load from `documentarist/` but `review-criteria` is at `documentarist-reviewer/review-criteria.md`, not `documentarist/`
**Alignment**: PASS — 2/2 declared skills referenced in body
**Phase coherence**: PASS — Phase 1 loads `divio-framework`, Phase 2 loads `review-criteria`
**Cross-references**: PASS
**Sufficiency**: PASS — `review-criteria` + `divio-framework` cover all 6 critique dimensions
**Missing skills**: NONE
**Unnecessary skills**: NONE

**Findings**:
1. **Path split**: `divio-framework` is correctly at `documentarist/` (cross-ref from parent), but `review-criteria` is at `documentarist-reviewer/`, NOT `documentarist/`. Single path instruction `~/.claude/skills/nw/documentarist/` cannot load both. **Fix**: Add dual-path loading — `documentarist/` for `divio-framework`, `documentarist-reviewer/` for `review-criteria`. Or move `divio-framework` to `documentarist-reviewer/`.

### nw-data-engineer-reviewer (1 skill) — NEEDS_FIXES

**Path**: FAIL — Agent says `~/.claude/skills/nw/data-engineer/` but skill is at `data-engineer-reviewer/review-criteria.md`
**Alignment**: PASS — 1/1
**Phase coherence**: PASS
**Cross-references**: PASS
**Sufficiency**: PASS — `review-criteria` covers all 7 review dimensions
**Missing skills**: NONE
**Unnecessary skills**: NONE

**Findings**:
1. Path references `data-engineer/` but skill is at `data-engineer-reviewer/`. **Fix**: Update path to `~/.claude/skills/nw/data-engineer-reviewer/`.

### nw-troubleshooter-reviewer (1 skill) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/troubleshooter-reviewer/`
**Alignment**: PASS — 1/1
**Phase coherence**: PASS — loaded at Phase 1 Intake
**Cross-references**: PASS
**Sufficiency**: PASS — `review-criteria` covers all 6 dimensions, scoring, YAML format
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

### nw-researcher-reviewer (1 skill) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/researcher-reviewer/`
**Alignment**: PASS — 1/1
**Phase coherence**: PASS — loaded at Phase 1
**Cross-references**: PASS
**Sufficiency**: PASS — `critique-dimensions` covers all 5 review dimensions
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

### nw-product-discoverer-reviewer (1 skill) — APPROVED

**Path**: PASS — `~/.claude/skills/nw/product-discoverer-reviewer/`
**Alignment**: PASS — 1/1
**Phase coherence**: PASS — loaded at Phase 1
**Cross-references**: PASS
**Sufficiency**: PASS — `review-criteria` covers all 5 review dimensions
**Missing skills**: NONE
**Unnecessary skills**: NONE

No fixes required.

### nw-solution-architect-reviewer (2 skills) — NEEDS_FIXES

**Path**: FAIL — `~/.claude/skills/nw/solution-architect-reviewer/` exists but only contains `roadmap-review-checks.md`
**Alignment**: FAIL — frontmatter declares `critique-dimensions` but file DOES NOT EXIST in directory
**Phase coherence**: FAIL — Phase 2 `Load: critique-dimensions` will fail
**Cross-references**: PASS
**Sufficiency**: FAIL — missing critique-dimensions = no 5-dimension architecture review capability
**Missing skills**: `critique-dimensions` (declared but file absent)
**Unnecessary skills**: NONE

**Findings**:
1. **CRITICAL**: `critique-dimensions` declared in frontmatter and referenced in Phase 2 but file does not exist at `solution-architect-reviewer/`. File exists at sibling `solution-architect/critique-dimensions.md`. **Fix**: Copy or symlink `solution-architect/critique-dimensions.md` to `solution-architect-reviewer/`.
2. Same cross-agent bug noted in nw-solution-architect's own review — ownership of `critique-dimensions` confused between architect and reviewer.

---

## Summary

### Status: ALL 25 AGENTS REVIEWED

| Verdict | Count | Agents |
|---------|-------|--------|
| APPROVED | 11 | workshopper, software-crafter, researcher, data-engineer, documentarist, acceptance-designer, product-owner-reviewer, troubleshooter-reviewer, researcher-reviewer, product-discoverer-reviewer, workshopper-reviewer (post-fix) |
| NEEDS_FIXES | 14 | product-owner, functional-software-crafter, agent-builder, platform-architect, solution-architect, troubleshooter, product-discoverer, platform-architect-reviewer, agent-builder-reviewer, software-crafter-reviewer, solution-architect-reviewer, acceptance-designer-reviewer, documentarist-reviewer, data-engineer-reviewer |

### Fix Categories

| Category | Count | Agents |
|----------|-------|--------|
| Path bugs | 3 | data-engineer-reviewer, documentarist-reviewer, agent-builder |
| Missing/orphaned skills | 6 | functional-software-crafter (14!), agent-builder (2), acceptance-designer-reviewer (1), solution-architect-reviewer (1), agent-builder-reviewer (1), software-crafter-reviewer (1) |
| Phase timing wrong | 5 | product-owner, functional-software-crafter, troubleshooter, platform-architect, product-discoverer |
| Cross-agent bugs | 2 | solution-architect ↔ solution-architect-reviewer, agent-builder-reviewer |
| Labeling/table inconsistencies | 3 | product-owner, platform-architect, product-discoverer |

---

## Reviewer Validation Phase

Each reviewer validated the self-assessment findings of its counterpart agent.

### nw-product-owner — PARTIALLY_AGREE

- Finding 1 (`shared-artifact-tracking` timing): **CONFIRMED**
- Finding 2 (`ux-emotional-design` late): **CONFIRMED**
- Finding 3 (table inconsistency): **CONFIRMED**
- **MISSED (CRITICAL)**: `ux-principles` loaded in Phase 4 body text but NOT in frontmatter `skills:` list. Frontmatter↔body alignment violation.
- **MISSED (MEDIUM)**: Phase 4 forward-dependency — assumes `ux-emotional-design` loaded in Phase 3 on-demand, but not guaranteed.

### nw-functional-software-crafter — PARTIALLY_AGREE

- Finding 1 (14 orphaned skills): **CONFIRMED**
- Finding 2 (`fp-algebra-driven-design` timing): **DISPUTED** — Phase 3 GREEN is defensible for implementation guidance; move to Phase 1 only if algebraic thinking informs tests
- Finding 3 (`fp-usable-design` timing): **DISPUTED** — partially confirmed; naming principles should be Phase 0 but application patterns defensible at Phase 3
- Finding 4 (PBT overlap): **CONFIRMED**
- Finding 5 (Phase 1-2 ambiguous): **CONFIRMED**
- **MISSED (CRITICAL)**: No language detection DESIGN mechanism — agent has no way to select which of 14 language-specific skills to load
- **MISSED (MEDIUM)**: Frontmatter path comments reference wrong directory `(docs/skills/)`

### nw-agent-builder — AGREE

- All 6 findings: **CONFIRMED**
- **MISSED (MEDIUM)**: Phase 4 VALIDATE is only 2 lines — undersized for agent whose primary job is validation
- **MISSED (LOW)**: Template code block bleeds into instructional content — unclear boundary

### nw-platform-architect — AGREE

- All 3 findings: **CONFIRMED**
- **MISSED (LOW)**: `stakeholder-engagement` trigger label says "Always" but only loads at Phase 8

### nw-solution-architect — PARTIALLY_AGREE

- Finding 1 (`critique-dimensions` ownership): **DISPUTED** — Morgan correctly loads it from `solution-architect/`; real bug is reviewer missing the file in `solution-architect-reviewer/`
- Finding 2 (`roadmap-design` timing): **CONFIRMED**, severity **UNDERSTATED** — should be HIGH (roadmap is mandatory deliverable)
- **MISSED (MEDIUM)**: Roadmap creation never explicitly instructed in any phase
- **MISSED (MEDIUM)**: Paradigm selection (OOP/functional) mentioned in handoff but no phase covers it

### nw-troubleshooter — AGREE

- All 3 findings: **CONFIRMED**
- **MISSED (MEDIUM)**: Phase 1 loads NO skills despite "MANDATORY" header
- **MISSED (LOW)**: Phase 3 validation text lacks explicit cross-references to `five-whys-methodology` sections

### nw-product-discoverer — PARTIALLY_AGREE

- Finding 1 (eager not on-demand): **CONFIRMED**
- Finding 2 (implicit Phase 4 dependency): **CONFIRMED**
- **MISSED (LOW)**: Trigger column says "Always" for all entries — contradicts "on-demand" label
- **MISSED (LOW)**: Phase 4 gate missing explicit cross-reference to Phase 2 opportunity data

---

## Consolidated Fix List for Zeus

Fixes incorporating both self-assessment findings and reviewer corrections, ordered by severity.

### CRITICAL (must fix)

1. **nw-product-owner**: Add `ux-principles` to frontmatter `skills:` list (reviewer caught missing alignment)
2. **nw-functional-software-crafter**: Add 14 orphaned skills to frontmatter + add Phase 0 language-detection mechanism
3. **nw-agent-builder**: Add dedicated Skill Loading section with path + phase-skill table; load `agent-testing` and `critique-dimensions` at Phase 4 VALIDATE
4. **nw-solution-architect-reviewer**: Copy `critique-dimensions.md` from `solution-architect/` to `solution-architect-reviewer/`
5. **nw-agent-builder-reviewer**: Create or copy `critique-dimensions.md` to `agent-builder-reviewer/`

### HIGH (should fix)

6. **nw-product-owner**: Move `ux-emotional-design` to Phase 2 on-demand; fix `shared-artifact-tracking` table↔body mismatch
7. **nw-troubleshooter**: Move `investigation-techniques` loading to Phase 1 (or split: categorization at Phase 1, solutions at Phase 4)
8. **nw-platform-architect**: Load `production-readiness` at Phase 6 (not just Phase 7)
9. **nw-solution-architect**: Clarify `critique-dimensions` ownership; load `roadmap-design` at Phase 4
10. **nw-data-engineer-reviewer**: Fix path `data-engineer/` → `data-engineer-reviewer/`
11. **nw-documentarist-reviewer**: Fix dual-path loading (reviewer skills at `documentarist-reviewer/`, shared at `documentarist/`)
12. **nw-acceptance-designer-reviewer**: Add `bdd-methodology` to frontmatter + load at Phase 1
13. **nw-software-crafter-reviewer**: Add `tdd-methodology` cross-ref from `software-crafter/`
14. **nw-agent-builder**: Convert soft loading language to imperative `Load:` directives; fix "11-point" → "14-point"

### MEDIUM (nice to fix)

15. **nw-platform-architect**: Make `deployment-strategies` table entry unconditional; remove overlap with `cicd-and-deployment`
16. **nw-product-discoverer**: Relabel "on-demand" as "eager loading" or restructure; add Phase 4 explicit reference
17. **nw-functional-software-crafter**: Clarify Phase "1-2" label; clarify `property-based-testing` vs `pbt-fundamentals` distinction

