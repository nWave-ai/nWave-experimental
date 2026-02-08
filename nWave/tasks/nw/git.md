# NW-GIT: Git Workflow Operations

**Wave**: CROSS_WAVE
**Agent**: Dakota (nw-devop)

## Overview

Git workflow assistant with automated commit message generation, branch management, and quality gate enforcement. Supports commit, branch, merge, status, and push operations.

## Agent Invocation

@nw-devop

Execute \*git-workflow with {operation}.

**Configuration:**

- operation: commit | branch | merge | status | push
- auto_message: true
- quality_gates: true

## Success Criteria

- [ ] Git operation completed successfully
- [ ] Commit message follows conventions
- [ ] Quality gates passed (if commit operation)
- [ ] Tests passing (if commit operation)

## Next Wave

**Handoff To**: {invoking-agent-returns-to-workflow}
**Deliverables**: Git operation completed

# Expected outputs:

# - Git commits, branches, or merges as requested
