# NW-REFACTOR: Systematic Code Refactoring

**Wave**: CROSS_WAVE
**Agent**: Crafty (nw-software-crafter)
**Command**: `*refactor`

## Overview

Apply systematic refactoring through the six-level hierarchy: Readability (L1-2), Structure (L3-4), Design (L5-6). Each level builds on the previous. For complex refactorings spanning multiple classes, the agent applies Mikado Method planning internally.

## Context Files Required

- src/\* - Production codebase to refactor
- tests/\* - Test codebase to refactor

## Agent Invocation

@nw-software-crafter

Execute \*refactor for {target-class-or-module}.

**Context Files:**

- src/\*
- tests/\*

**Configuration:**

- level: 3 # Refactoring levels 1-6 (1=readability, 6=SOLID)
- scope: module # file/module/project
- method: extract # extract/inline/rename/move
- mikado_planning: false # Use Mikado Method for complex refactorings

## Success Criteria

- [ ] Code quality metrics improved (measured before/after)
- [ ] All tests passing after refactoring
- [ ] Refactoring levels applied in sequence (L1 before L2, etc.)
- [ ] Technical debt reduced measurably

## Next Wave

**Handoff To**: {invoking-agent-returns-to-workflow}
**Deliverables**: Refactored codebase with quality improvements

## Examples

### Example 1: Module-level readability refactor
```
/nw:refactor src/auth/token_manager.py --level=2 --scope=module
```
Crafty applies L1-L2 readability improvements: rename ambiguous variables, extract magic numbers, simplify conditionals.

### Example 2: SOLID-level design refactor
```
/nw:refactor src/billing/ --level=6 --scope=module --mikado_planning=true
```
Crafty uses Mikado Method to plan a multi-class refactoring, applies dependency inversion and interface segregation across the billing module.

## Expected Outputs

```
src/*                              (refactored production code)
tests/*                            (refactored test code)
docs/refactoring/
  refactoring-log.md
  quality-metrics.md
```
