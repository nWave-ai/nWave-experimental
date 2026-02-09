# NW-GIT: Git Workflow Operations

**Wave**: CROSS_WAVE
**Agent**: Apex (nw-platform-architect)

## Overview

Git workflow assistant with automated commit message generation, branch management, and quality gate enforcement. Supports commit, branch, merge, status, and push operations.

## Agent Invocation

@nw-platform-architect

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

## Examples

### Example 1: Auto-generated commit
```
/nw:git commit
```
Apex analyzes staged changes, generates a conventional commit message (e.g., `feat(auth): add token refresh endpoint`), runs quality gates, and commits.

### Example 2: Feature branch creation
```
/nw:git branch feature/payment-webhook
```
Apex creates the branch from the current HEAD and switches to it.

## Expected Outputs

```
Git commits, branches, or merges as requested
```
