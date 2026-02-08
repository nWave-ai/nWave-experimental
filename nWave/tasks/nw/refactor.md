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

# Expected outputs:
# - src/* (refactored production code)
# - tests/* (refactored test code)
# - docs/refactoring/refactoring-log.md
# - docs/refactoring/quality-metrics.md
