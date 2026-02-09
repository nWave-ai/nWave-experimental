# NW-DELIVER: Complete DELIVER Wave Orchestrator

**Wave**: DELIVER (wave 6 of 6)
**Agent**: Main Instance (self -- orchestrator)
**Command**: `/nw:deliver "{feature-description}"`

## Overview

Orchestrates the complete DELIVER wave: from feature description to production-ready code with mandatory quality gates. You (the main Claude instance) coordinate by delegating to specialized agents via the Task tool. Final wave in nWave (DISCOVER > DISCUSS > DESIGN > DEVOP > DISTILL > DELIVER).

Sub-agents cannot use the Skill tool or execute `/nw:*` commands. Read the relevant command file yourself, extract instructions, and embed them in the Task prompt.

## Orchestration Flow

```
INPUT: "{feature-description}"
  |
  1. Parse input, derive project-id (kebab-case), create docs/feature/{project-id}/
  |
  2. Phase 1 — Roadmap Creation + Review
     a. Skip if roadmap.yaml exists with validation.status == "approved"
     b. @nw-solution-architect creates roadmap.yaml (read ~/.claude/commands/nw/roadmap.md)
     c. Automated quality gate (see below)
     d. @nw-software-crafter-reviewer reviews roadmap (read ~/.claude/commands/nw/review.md)
     e. Retry once on rejection, then stop for manual intervention
  |
  3. Phase 2 — Execute All Steps
     a. Extract steps from roadmap.yaml in dependency order
     b. For each step, check execution-log.yaml for prior completion (resume)
     c. @nw-software-crafter executes TDD cycle (read ~/.claude/commands/nw/execute.md)
        IMPORTANT: Use the DES Prompt Template from execute.md. Include all 4 DES
        markers (DES-VALIDATION, DES-PROJECT-ID, DES-STEP-ID) and all 8 mandatory
        sections in the Task prompt. Without these, DES validation is bypassed.
     d. Verify COMMIT/PASS in execution-log.yaml after each step
     e. If a phase is missing: RE-DISPATCH the agent to execute it.
        NEVER write execution-log entries yourself — only the agent
        that actually performed the work may write to the log.
     f. Stop on first failure
  |
  4. Phase 2.25 — Complete Refactoring (L1-L4, code + tests)
     a. @nw-software-crafter performs full L1-L4 refactoring on production code AND tests
        (read ~/.claude/commands/nw/refactor.md, specify --level=1-4 --scope=code+tests)
     b. @nw-software-crafter-reviewer reviews the refactoring result
     c. One revision pass on rejection, then proceed
  |
  5. Phase 2.5 — Mutation Testing
     a. Mutation testing gate >= 80% kill rate (read ~/.claude/commands/nw/mutation-test.md)
     b. Must pass before proceeding
  |
  6. Phase 3 — Finalize + Cleanup
     a. @nw-platform-architect archives to docs/evolution/ (read ~/.claude/commands/nw/finalize.md)
     b. Commit evolution document, push when ready
  |
  7. Phase 3.5 — Retrospective (conditional)
     a. Skip if clean execution (no failures, no retries, no warnings)
     b. @nw-troubleshooter performs 5 Whys analysis on issues found
  |
  8. Phase 4 — Report Completion
     a. Display summary: phases, steps, reviews, artifacts
     b. Workflow complete. Return to DISCOVER for next feature iteration.
```

## Orchestrator Responsibilities

You follow this flow directly. Do not delegate orchestration to another agent.

For each phase:
1. Read the relevant command file (paths listed above)
2. Extract instructions and embed them in the Task prompt
3. Include task boundary instructions to prevent workflow continuation
4. Verify output artifacts exist after each Task completes
5. Update .develop-progress.json for resume capability

## Task Invocation Pattern

All Task prompts for step execution include DES markers for validation. Without these markers, the DES hooks cannot validate the task and it passes through unmonitored.

The full DES Prompt Template (all 8 mandatory sections) is defined in `~/.claude/commands/nw/execute.md`. Read that file and embed all 8 sections (DES_METADATA, AGENT_IDENTITY, TASK_CONTEXT, TDD_7_PHASES, QUALITY_GATES, OUTCOME_RECORDING, BOUNDARY_RULES, TIMEOUT_INSTRUCTION) in each Task prompt.

```python
Task(
    subagent_type="{agent}",
    max_turns=35,
    prompt=f'''
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {project_id} -->
<!-- DES-STEP-ID : {step_id} -->

TASK BOUNDARY: {task_description}
Return control to orchestrator after completion.

Read the full DES Prompt Template from ~/.claude/commands/nw/execute.md and embed all 8 mandatory sections below.
Fill placeholders with: step_id={step_id}, project_id={project_id}, agent={agent},
task_context={instructions_extracted_from_command_file}
''',
    description="{phase description}"
)
```

## Roadmap Quality Gate (Automated, Zero Token Cost)

After roadmap creation, before reviewer, run these checks in your own context:
1. AC implementation coupling: flag acceptance criteria referencing private methods (`_method()`)
2. Step decomposition ratio: flag if steps/files ratio exceeds 2.5
3. Identical pattern detection: flag 3+ steps with identical AC structure (should be batched)
4. Validation-only steps: flag steps with no files_to_modify

If HIGH findings exist, return roadmap to architect for one revision pass.

## Skip and Resume Logic

- Check `.develop-progress.json` on start to resume from last failure
- Skip artifact creation if file exists with `validation.status == "approved"`
- Skip completed steps by checking execution-log.yaml for COMMIT/PASS
- Max 2 retry attempts per review rejection, then stop for manual intervention

## Input

- `feature-description` (string, required): natural language, minimum 10 characters
- Derive project-id: strip common prefixes (implement, add, create), remove stop words, kebab-case, max 5 words

## Output Artifacts

```
docs/feature/{project-id}/
  roadmap.yaml              # Phase 1
  execution-log.yaml        # Phase 2 (append-only state)
  .develop-progress.json    # Resume tracking
docs/evolution/
  {project-id}-evolution.md # Phase 3
```

## Quality Gates

- Roadmap review (1 review, max 2 attempts)
- Per-step TDD cycle with REVIEW + REFACTOR phases (2N reviews)
- Mutation testing >= 80% kill rate
- All tests passing after each phase
- Total: 1 + 2N mandatory reviews

## Success Criteria

- [ ] Roadmap created and approved
- [ ] All steps executed with COMMIT/PASS
- [ ] L1-L4 refactoring complete on code and tests, reviewer approved
- [ ] Mutation testing gate passed (>= 80%)
- [ ] Evolution document archived
- [ ] Retrospective completed (or clean execution noted)
- [ ] Completion report displayed

## Examples

### Example 1: Fresh Feature

```bash
/nw:deliver "Implement user authentication with JWT tokens"
```

Creates roadmap, reviews it, executes all steps with TDD, runs mutation testing, finalizes to docs/evolution/, reports completion.

### Example 2: Resume After Failure

```bash
/nw:deliver "Implement user authentication with JWT tokens"
```

Same command. Loads .develop-progress.json, skips completed phases, resumes from failure point.

### Example 3: Single Step Alternative

For manual granular control, use individual commands instead:
```bash
/nw:roadmap @nw-solution-architect "goal description"
/nw:execute @nw-software-crafter "project-id" "01-01"
/nw:finalize @nw-platform-architect "project-id"
```

## Completion

DELIVER is the final wave. After completion, return to DISCOVER for the next feature iteration or mark the project as complete.
