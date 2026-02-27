# Architecture Review: nWave Plugin Marketplace

**Review ID**: arch_rev_20260227_001
**Reviewer**: Atlas (nw-solution-architect-reviewer)
**Date**: 2026-02-27
**Verdict**: **CONDITIONALLY APPROVED**

---

## Artifacts Reviewed

- `docs/feature/nwave-plugin/design/architecture-design.md`
- `docs/feature/nwave-plugin/design/technology-stack.md`
- `docs/feature/nwave-plugin/design/component-boundaries.md`
- `docs/adrs/ADR-001-plugin-marketplace-distribution.md`
- `docs/adrs/ADR-002-des-hooks-in-plugin.md`
- `docs/adrs/ADR-003-skill-structure-mapping.md`

---

## Findings (priority order)

### issue (blocking): Step 01-02 AC is implementation-coupled

**Location**: architecture-design.md, roadmap section, step 01-02
**Severity**: High

Step 01-02 acceptance criteria references implementation details ("shell wrapper invokes DES adapter via PYTHONPATH"). PYTHONPATH, shell wrapper, plugin root are all HOW — AC should specify WHAT.

**Recommendation**: Rewrite AC to be behavioral: "DES hook invocations return allow/block decisions based on phase validation, with error messages when phase violated." Crafter decides implementation (shell wrapper vs Python wrapper vs other) during GREEN phase.

---

### issue (blocking): Security model for DES hook execution not documented

**Location**: architecture-design.md (missing section)
**Severity**: High

DES hooks run inside the plugin sandbox but the security model is not explicitly documented. ADR-002 acknowledges "hooks will fail silently if pyyaml/pydantic missing" but design does not address who installs these dependencies or what prevents unmet dependencies.

**Recommendation**: Add "Security Architecture" section covering:
1. What DES hooks can/cannot do in plugin context (file I/O boundaries, settings.json access scope)
2. Process isolation model (PYTHONPATH isolation sufficient?)
3. Dependency ownership — who installs pyyaml/pydantic? Plugin users may hit silent failures
4. Fallback/error messaging when dependencies are missing

---

### suggestion (blocking): Coexistence verification needs operational definition

**Location**: architecture-design.md, roadmap section, step 02-02
**Severity**: Medium

"Both installations active simultaneously without errors" is vague. Needs concrete test steps.

**Recommendation**: Define acceptance tests:
- Install plugin via plugin system + custom installer via nwave-ai CLI
- Run `/nw:deliver`, verify both sources discovered correctly
- Verify no duplicate hook registrations (no double PreToolUse/PostToolUse)
- Verify no path conflicts
- Document switchover procedure (disable one, verify other works)

---

### suggestion (non-blocking): Skill performance not quantified

**Location**: ADR-003
**Severity**: Medium

ADR-003 claims "progressive loading is core design advantage" but provides no quantitative evidence. Plugin system may have different discovery costs than custom installer.

**Recommendation**: Measure plugin discovery time with 98 files vs monolithic SKILL.md. If progressive loading benefit < 10% token savings, reconsider consolidation.

---

### praise: Data-justified problem statement

JTBD outcomes #13/#14/#15 (all Extremely Underserved, scores 15.0/13.0/15.0) provide quantified evidence for the design. The 30-minute → 1-minute install friction reduction is a concrete, measurable improvement.

### praise: Mature ADR quality

All three ADRs include genuine alternative analysis with specific rejection rationale. No straw-manning detected.

### praise: Excellent roadmap efficiency

5 steps for 6 files = 0.83 step/file ratio (target ≤ 2.5). Steps have distinct concerns.

### praise: FP paradigm alignment

Build pipeline modeled as pure function composition (config → transformer → assembler → validator). No mutable state, side effects isolated to file I/O only.

### praise: Zero new dependencies

Technology choices are requirement-driven (stdlib only), not resume-driven. Design explicitly evaluates and rejects Jinja2, Docker, Makefile.

---

## Gate Items Before Proceeding

1. **BEFORE step 01-02 coding**: Rewrite AC to remove implementation coupling
2. **BEFORE step 01-03 coding**: Add "Security Architecture" section to architecture-design.md
3. **BEFORE step 02-02 coding**: Define operational coexistence tests

---

## Priority Validation

| Question | Assessment | Evidence |
|----------|-----------|----------|
| Largest bottleneck? | YES | JTBD #13/#14/#15 all Extremely Underserved |
| Simple alternatives? | ADEQUATE | Symlink and manual restructuring evaluated and rejected |
| Constraint prioritization? | CORRECT | Time-to-market > maintainability > testability matches 2-3 week timeline |
| Data-justified? | JUSTIFIED | Evidence chain: JTBD → strategic assessment → ADRs → existing code patterns |

**Critical issues**: 0
**High issues**: 2 (both fixable, no rework needed)
**Recommendation**: Fix the 2 blocking issues, then proceed to DISTILL wave.
