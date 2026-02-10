# Test Non-Compliant Command

**Wave:** DEVELOP

**Status:** Test fixture for acceptance test validation

---

## Overview

This command serves as a test fixture for validating command template compliance checking. It intentionally violates multiple COMMAND_TEMPLATE.yaml requirements to test the validator's ability to detect non-compliant commands.

## Task Header

Execute a test orchestration that demonstrates workflow duplication violations.

## Background

This command operates in the context of the nWave framework (implicit context - NOT structured).

## What This Command Does

This section demonstrates the orchestration coordination pattern violation by describing procedural steps embedded in the command file rather than delegated to the agent specification.

### What Should Happen (Procedural Steps - VIOLATION)

STEP 1: Load the baseline metrics collection framework
STEP 2: Initialize the measurement protocol
STEP 3: Execute phase 1 baseline establishment
STEP 4: Validate phase 1 completion before proceeding
STEP 5: Execute phase 2 roadmap generation
STEP 6: Generate analysis report

### Progress Tracking (VIOLATION)

The command tracks progress through multiple phases:
- Phase 1: PENDING
- Phase 2: PENDING
- Phase 3: PENDING
- Phase 4: PENDING
- Phase 5: PENDING

### Orchestration Logic (VIOLATION)

You are the coordinator. Do NOT generate task files yourself. This embedded orchestration logic describes how the command should be executed across multiple subagents.

### Parameter Parsing (VIOLATION)

The command includes parameter extraction logic. Extract the agent name from the first argument to determine which agent to invoke. Validate agent name is one of: software-crafter, researcher, acceptance-designer, solution-architect, or feature-completion-coordinator.

## Agent Invocation

Call the software-crafter agent using: @software-crafter

## Success Criteria

The acceptance test should verify:
- Size violation detected (command exceeds 60 lines)
- Procedural step sequences detected (STEP 1, STEP 2, etc.)
- Progress tracking pattern detected
- Orchestration coordination logic detected
- Parameter parsing logic detected
- Context bundling violation detected (implicit vs explicit)
- Agent invocation pattern validated
- Approval blocked due to violations
- Actionable feedback provided for remediation
