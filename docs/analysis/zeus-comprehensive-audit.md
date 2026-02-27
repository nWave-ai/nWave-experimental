# Zeus Comprehensive Agent & Skill Audit

**Date**: 2026-02-27
**Auditor**: nw-agent-builder (Zeus) — 6 parallel instances
**Scope**: All 25 agents, ~100 skill files
**Status**: COMPLETE

---

## Token Budget Summary (Worst Case — All Skills Loaded)

| Agent | Agent Tk | Skills Tk | Total Tk | Remaining (%) | Verdict |
|-------|----------|-----------|----------|---------------|---------|
| **nw-product-owner** | 2,300 | 25,550 | 29,950 | 162,050 (81%) | PASS |
| **nw-functional-software-crafter** (typical: 1 lang) | 4,675 | 41,600 | 54,275 | 145,725 (73%) | NEEDS_WORK |
| **nw-functional-software-crafter** (worst: all langs) | 4,675 | 84,550 | 97,225 | 102,775 (51%) | N/A — unrealistic |
| **nw-software-crafter** | 3,375 | 14,400 | 25,775 | 174,225 (87%) | NEEDS_WORK |
| **nw-workshopper** | 2,625 | 36,750 | 47,375 | 152,625 (76%) | PASS |
| **nw-agent-builder** | 925 | 5,875 | 14,800 | 185,200 (93%) | PASS |
| **nw-platform-architect** | 775 | 5,600 | 14,375 | 185,625 (93%) | PASS |
| **nw-solution-architect** | 3,314 | 5,872 | 9,186 | 186,814 (97%) | PASS |
| **nw-researcher** | 1,829 | 6,050 | 7,879 | 184,121 (96%) | PASS |
| **nw-data-engineer** | 1,801 | 8,072 | 9,873 | 182,127 (95%) | PASS |
| **nw-troubleshooter** | 1,733 | 3,397 | 5,130 | 186,870 (97%) | PASS |
| **nw-product-discoverer** | 2,393 | 4,373 | 6,766 | 185,234 (96%) | PASS |
| **nw-documentarist** | 2,104 | 2,765 | 4,869 | 187,131 (97%) | PASS |
| **nw-acceptance-designer** | 3,011 | 5,349 | 8,360 | 183,640 (96%) | PASS |
| **nw-workshopper-reviewer** | 2,100 | 16,700 | 18,800 | 173,200 (87%) | PASS |
| **nw-product-owner-reviewer** | 1,800 | 4,300 | 6,100 | 185,900 (93%) | PASS |
| **nw-software-crafter-reviewer** | 1,500 | 7,000 | 8,500 | 183,500 (92%) | NEEDS_WORK |
| **nw-acceptance-designer-reviewer** | 1,875 | 4,300 | 6,175 | 185,825 (93%) | PASS |
| **nw-platform-architect-reviewer** | 1,325 | 2,750 | 4,075 | 187,925 (94%) | PASS |
| **nw-solution-architect-reviewer** | 1,550 | 2,100 | 3,650 | 188,350 (94%) | PASS |
| **nw-agent-builder-reviewer** | 1,300 | 2,100 | 3,400 | 188,600 (94%) | NEEDS_WORK |
| **nw-documentarist-reviewer** | 1,400 | 2,500 | 3,900 | 188,100 (94%) | PASS |
| **nw-data-engineer-reviewer** | 1,450 | 750 | 2,200 | 189,800 (95%) | NEEDS_WORK |
| **nw-troubleshooter-reviewer** | 1,050 | 1,200 | 2,250 | 189,750 (95%) | PASS |
| **nw-researcher-reviewer** | 1,450 | 1,100 | 2,550 | 189,450 (95%) | PASS |
| **nw-product-discoverer-reviewer** | 1,650 | 1,300 | 2,950 | 189,050 (95%) | PASS |

**Context window**: 200,000 tokens. System overhead: ~8,000 tokens.

### Key Takeaways

- **Heaviest agent**: nw-product-owner (29,950 tk worst case = 81% remaining) — healthy
- **Most efficient**: nw-data-engineer-reviewer (2,200 tk = 95% remaining)
- **functional-crafter typical case**: 54,275 tk (73% remaining) — acceptable with language detection
- **No agent exceeds 50% of context** in realistic usage scenarios

---

## Agent Structure Audit Results

### PASS (20 agents)

| Agent | Lines | Skills | Structure Quality |
|-------|-------|--------|-------------------|
| nw-product-owner | 224 | 17 | Gold standard — exemplary skill loading |
| nw-workshopper | 205 | 12 | Clean skill separation, 5 examples |
| nw-agent-builder | 295 | 6 | Self-referential meta-agent, 5 examples |
| nw-platform-architect | 220 | 7 | Perfect alignment, 6 examples |
| nw-solution-architect | 241 | 4 | Good, 5 examples |
| nw-researcher | 133 | 4 | Very lean, efficient |
| nw-data-engineer | 131 | 4 | Leanest definition |
| nw-troubleshooter | 126 | 3 | Leanest agent overall |
| nw-product-discoverer | 174 | 3 | Well-structured |
| nw-documentarist | 153 | 3 | Excellent for haiku model |
| nw-acceptance-designer | 219 | 3 | Good BDD focus |
| nw-product-owner-reviewer | 166 | 3 | Strictest read-only |
| nw-acceptance-designer-reviewer | 154 | 3 | Clean cross-refs |
| nw-platform-architect-reviewer | 113 | 3 | Compact |
| nw-workshopper-reviewer | 164 | 6 | Heavy but phase-gated |
| nw-solution-architect-reviewer | 139 | 2 | Lean |
| nw-documentarist-reviewer | 124 | 2 | Good dual-path docs |
| nw-troubleshooter-reviewer | 100 | 1 | Leanest reviewer |
| nw-researcher-reviewer | 132 | 1 | Clean |
| nw-product-discoverer-reviewer | 141 | 1 | Good meta-review protocol |

### NEEDS_WORK (5 agents)

| Agent | Issue | Severity |
|-------|-------|----------|
| **nw-functional-software-crafter** | Missing language detection mechanism; 14 orphaned skills not in frontmatter; no YAML frontmatter on any of 21 skills | HIGH |
| **nw-software-crafter** | Missing Examples section (0 examples, needs 3-5); missing Constraints section | HIGH |
| **nw-software-crafter-reviewer** | Cross-ref skill paths not documented in Skill Loading section | MEDIUM |
| **nw-agent-builder-reviewer** | Stale "7 dimensions" count (now 9 in skill) | LOW |
| **nw-data-engineer-reviewer** | Review dimensions duplicated in agent body AND skill (~500 tk wasted) | LOW |

---

## Compression Analysis

### Skills Worth Compressing (>200 tokens saveable)

| Skill | Agent | Current Tk | Saveable | Technique |
|-------|-------|-----------|----------|-----------|
| research-methodology | researcher | 2,241 | ~800 (35%) | Compress markdown template skeleton |
| security-and-governance | data-engineer | 2,434 | ~600 (25%) | Reduce SQL examples to 1/concept |
| bdd-requirements | product-owner | 3,100 | ~465 (15%) | Compress Discovery Workshop prose |
| query-optimization | data-engineer | 2,173 | ~500 (23%) | Reduce SQL code blocks from 6 to 2 |
| data-architecture-patterns | data-engineer | 2,461 | ~500 (20%) | Remove ASCII art, compress streaming |
| review-dimensions | software-crafter | 3,250 | ~500 (15%) | RPP table deduplication |
| authoritative-sources | researcher | 1,733 | ~400 (23%) | Merge domain tables |
| leanux-methodology | product-owner | 2,100 | ~420 (10%) | DoR overlap with reviewer skill |

**Total compressible**: ~4,185 tokens across 8 skills.

### Skills NOT Worth Compressing

All reviewer skills (23 files) are already lean — averaging 1,100 tokens each. No compression needed.

Workshopper skills have ~500 tokens of inter-skill duplication (Bloom's arc tables, spacing formula, virtual delivery) but the deduplication effort is not justified by the savings.

---

## Cross-Cutting Issues

### 1. Persona Name Collisions (3 duplicates across 6 agents)

| Name | Agents |
|------|--------|
| Atlas | platform-architect-reviewer, solution-architect-reviewer |
| Sentinel | acceptance-designer-reviewer, data-engineer-reviewer |
| Scholar | workshopper-reviewer, researcher-reviewer |

**Fix**: Rename duplicates.

### 2. Skill Frontmatter Inconsistency

| Pattern | Agents |
|---------|--------|
| Full frontmatter (name, agent, description, source_research, confidence) | workshopper only (12 skills) |
| Minimal frontmatter (name, description only) | All other agents (~80 skills) |
| No YAML frontmatter | functional-software-crafter (21 skills) |

### 3. Cross-Skill Content Duplication (platform-architect)

Deployment strategies (canary/blue-green/rolling) appear in 3 skills: `cicd-and-deployment`, `deployment-strategies`, and `platform-engineering-foundations`. ~500 tokens wasted. Fix: single source of truth in `cicd-and-deployment`.

### 4. Missing `shared-artifact-tracking` Load Directive (product-owner)

Skill is in frontmatter and strategy table but has no explicit `Load:` directive in Phase 2/3 workflow text.

### 5. Phantom Reference (agent-builder)

`migration-patterns` referenced in body (line 50, "On request" row) but does not exist as a file and is not in frontmatter.

---

## Recommendations (Priority Order)

### CRITICAL

1. **nw-functional-software-crafter**: Add language detection mechanism (Phase 0 with file pattern detection → skill mapping table). Without this, 14/21 skills are unreachable.

### HIGH

2. **nw-software-crafter**: Add 3-5 Examples section (walking skeleton, port-boundary violation, test budget, mikado trigger, testing theater detection).
3. **nw-software-crafter**: Add explicit Constraints section.
4. **nw-functional-software-crafter**: Add YAML frontmatter to all 21 skill files.
5. **Compress 3 data-engineer skills**: ~1,600 tokens saveable (SQL example reduction).

### MEDIUM

6. **nw-platform-architect**: Deduplicate deployment strategy content across 3 skills (~500 tokens).
7. **nw-software-crafter-reviewer**: Document dual skill paths in Skill Loading section.
8. **nw-data-engineer-reviewer**: Remove inline review dimensions (duplicated from skill, ~500 tokens).
9. **nw-agent-builder-reviewer**: Update "7 dimensions" → "9 dimensions".
10. **nw-agent-builder**: Remove phantom `migration-patterns` reference.
11. **Persona collisions**: Rename 3 duplicate persona names.

### LOW

12. **nw-product-owner**: Add `Load: shared-artifact-tracking` to Phase 2/3 workflow text.
13. **nw-agent-builder**: Update skill to say "14-point" checklist (currently "11-point").
14. Standardize skill frontmatter schema across all agents (full vs minimal).
15. **nw-researcher**: Compress `research-methodology` template (~800 tokens saveable).
