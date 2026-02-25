---
description: "Selects a quality-vs-token-consumption profile (lean, standard, thorough, exhaustive, inherit) and persists it to .nwave/des-config.json. Use when tuning how much rigor wave commands apply."
disable-model-invocation: true
argument-hint: '[profile] - Optional: lean, standard, thorough, exhaustive, inherit. Omit for interactive selection.'
---

# NW-RIGOR: Quality Profile Selection

**Wave**: CROSS_WAVE | **Agent**: Main Instance (self) | **Command**: `/nw:rigor [profile]`

## Overview

Interactive command to select a quality-vs-token-consumption profile. Persists choice to `.nwave/des-config.json` under the `rigor` key. All wave commands read this config to adjust agent models, review policy, TDD phases, and mutation testing.

You (the main Claude instance) run this directly. No subagent delegation.

## Profile Mappings (Single Source of Truth)

| Setting            | lean                  | standard [recommended]                              | thorough                                            | exhaustive                                          | inherit                                             |
|--------------------|-----------------------|-----------------------------------------------------|-----------------------------------------------------|-----------------------------------------------------|-----------------------------------------------------|
| agent_model        | haiku                 | sonnet                                              | opus                                                | opus                                                | inherit                                             |
| reviewer_model     | skip                  | haiku                                               | sonnet                                              | opus                                                | haiku                                               |
| review_enabled     | false                 | true                                                | true                                                | true                                                | true                                                |
| double_review      | false                 | false                                               | true                                                | true                                                | false                                               |
| tdd_phases         | [RED_UNIT, GREEN]     | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]  | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]  | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]  | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]  |
| refactor_pass      | false                 | true                                                | true                                                | true                                                | true                                                |
| mutation_enabled   | false                 | false                                               | false                                               | true                                                | false                                               |

## Behavior Flow

### Mode Detection

If argument provided -> Mode 2 (Quick Switch). Otherwise -> Mode 1 (Interactive).

### Mode 1: Interactive Selection (no argument)

#### Step 1: Welcome

Read `.nwave/des-config.json`. If missing or `.nwave/` directory absent -> error: "No nWave config directory found. Run nwave install first."

If JSON is invalid -> backup as `.nwave/des-config.json.bak`, reset config to `{}`, note: "Config was corrupted. Backed up and reset."

Display current profile (from `config.rigor.profile`) or "none set" if absent.

Brief explanation: "Rigor profiles control how much quality infrastructure nWave applies per wave: agent models, review depth, TDD phases, mutation testing. Higher rigor = better guarantees, higher token cost."

#### Step 2: Comparison Table

Display this table:

```
+-----------+--------+----------+----------+------------+---------+
|           | lean   | standard | thorough | exhaustive | inherit |
+-----------+--------+----------+----------+------------+---------+
| Agent     | haiku  | sonnet   | opus     | opus       | *yours* |
| Reviewer  | --     | haiku    | sonnet   | opus       | haiku   |
| Review    | no     | yes      | double   | double     | yes     |
| TDD       | R->G   | 5-phase  | 5-phase  | 5-phase    | 5-phase |
| Refactor  | no     | yes      | yes      | yes        | yes     |
| Mutation  | no     | no       | no       | yes        | no      |
+-----------+--------+----------+----------+------------+---------+
| Est. cost | lowest | moderate | higher   | highest    | varies  |
| Est. time | fast   | moderate | slower   | slowest    | varies  |
+-----------+--------+----------+----------+------------+---------+
```

Mark "standard" as [recommended].

#### Step 3: User Selection

Ask user to select by number (1-5) or name via AskUserQuestion:

1. lean
2. standard [recommended]
3. thorough
4. exhaustive
5. inherit

#### Step 4: Detail View

Show the detail view for the selected profile. Render in a code block for visual clarity.

**lean:**
```
WHAT YOU GET:
  - Haiku agent (fastest, cheapest)
  - RED -> GREEN TDD (skip PREPARE, RED_ACCEPTANCE, COMMIT phases)

WHAT YOU LOSE:
  - No code review
  - No PREPARE phase (no test fixture setup)
  - No RED_ACCEPTANCE phase (no acceptance tests)
  - No COMMIT phase (no refactoring pass)
  - No mutation testing

WHEN TO USE:
  Config changes, documentation, simple bug fixes, spikes/prototypes

ESTIMATED IMPACT:
  Lowest token cost | Fastest per step
```

**standard [recommended]:**
```
WHAT YOU GET:
  - Sonnet agent (balanced quality/speed)
  - Full 5-phase TDD (PREPARE -> RED_ACCEPTANCE -> RED_UNIT -> GREEN -> COMMIT)
  - Haiku reviewer (cost-effective review)
  - Refactoring pass in COMMIT phase

WHAT'S NOT INCLUDED:
  - No double review (single pass only)
  - No mutation testing
  - Not opus-level reasoning

WHEN TO USE:
  Most development work — features, integrations, refactoring

ESTIMATED IMPACT:
  Moderate token cost | Moderate time per step
```

**thorough:**
```
WHAT YOU GET:
  - Opus agent (strongest reasoning)
  - Sonnet reviewer (deeper review analysis)
  - Double review (two independent review passes)
  - Full 5-phase TDD
  - Refactoring pass

WHAT IT COSTS:
  Higher token cost | Slower per step

WHEN TO USE:
  Critical features, security-sensitive code, public APIs, complex algorithms
```

**exhaustive:**
```
WHAT YOU GET:
  - Opus agent and opus reviewer (strongest at every stage)
  - Double review (two independent review passes)
  - Full 5-phase TDD
  - Refactoring pass
  - Mutation testing (>= 80% kill rate gate)

WHAT IT COSTS:
  Highest token cost | Slowest per step

WHEN TO USE:
  Critical production systems, compliance-sensitive code, long-lived core modules
```

**inherit:**
```
WHAT YOU GET:
  - Your session model for agents (nWave inherits, does not override)
  - Haiku reviewer
  - Full 5-phase TDD
  - Single review pass
  - Refactoring pass

WHAT THIS MEANS:
  nWave respects your model choice and controls the process around it.
  If your session runs opus, agents get opus. If sonnet, agents get sonnet.

WHEN TO USE:
  When you have strong opinions about which model to use,
  or your organization controls model selection externally.
```

#### Step 5: Confirm

Ask user to confirm via AskUserQuestion:
1. Yes, apply this profile
2. No, go back to selection (return to Step 2)
3. Cancel (exit without saving)

#### Step 6: Save to Config

1. Read `.nwave/des-config.json`
2. Parse JSON (handle corruption as in Step 1)
3. Set `config["rigor"]` to the full profile object:
   ```json
   {
     "profile": "{selected}",
     "agent_model": "...",
     "reviewer_model": "...",
     "tdd_phases": [...],
     "review_enabled": true/false,
     "double_review": true/false,
     "mutation_enabled": true/false,
     "refactor_pass": true/false
   }
   ```
4. Write back, preserving all other top-level keys (audit_logging_enabled, skill_tracking, etc.)

#### Step 7: Summary

Display all resolved settings:

```
Rigor profile saved: {name}

  Resolved settings:
  +-----------------------+---------------------------------------------------+
  | agent_model           | {value}                                           |
  | reviewer_model        | {value}                                           |
  | tdd_phases            | {value}                                           |
  | review_enabled        | {value}                                           |
  | double_review         | {value}                                           |
  | mutation_enabled      | {value}                                           |
  | refactor_pass         | {value}                                           |
  +-----------------------+---------------------------------------------------+

  Config: .nwave/des-config.json
  All wave commands will use these settings.
```

### Mode 2: Quick Switch (with argument)

#### Step 1: Validate Argument

If argument is not one of: lean, standard, thorough, exhaustive, inherit -> error: "Unknown profile '{name}'. Available: lean, standard, thorough, exhaustive, inherit"

Read `.nwave/des-config.json`. If missing -> same error as Mode 1 Step 1.

#### Step 2: Show Diff

Display what changes from current profile to target profile:

```
Switching from {current} -> {target}:

  agent_model:      sonnet -> haiku
  reviewer_model:   haiku -> skip
  review_enabled:   true -> false
  tdd_phases:       5-phase -> R->G
  refactor_pass:    true -> false
  mutation_enabled: (unchanged) false
```

If downgrading (moving to a less rigorous profile), highlight what user will lose:

```
You will LOSE:
  - Code review (reviewer_model: skip)
  - PREPARE, RED_ACCEPTANCE, COMMIT phases
  - Refactoring pass
```

If no current profile is set, show the target profile settings without diff.

#### Step 3: Confirm

Ask user to confirm via AskUserQuestion:
1. Yes, switch to {target}
2. No, keep current profile

#### Step 4: Save + Summary

Same as Mode 1 Steps 6 and 7.

## Error Handling

| Error | Response |
|-------|----------|
| Missing `.nwave/` directory | "No nWave config directory found. Run nwave install first." |
| Invalid JSON in des-config.json | Backup as `.bak`, reset to `{}`, proceed with notice |
| Unknown profile name | "Unknown profile '{name}'. Available: lean, standard, thorough, exhaustive, inherit" |
| inherit with undetectable session model | Fallback to sonnet with notice: "Could not detect session model. Defaulting agent_model to sonnet." |

## Success Criteria

- [ ] Current profile displayed (or "none set")
- [ ] Comparison table shown with all 5 profiles
- [ ] User selected and confirmed a profile
- [ ] Config written to `.nwave/des-config.json` (read-modify-write, other keys preserved)
- [ ] Summary of all resolved settings displayed

## Examples

### Example 1: Interactive first-time selection
```
/nw:rigor
```
No current profile set. Shows comparison table, user picks "standard", sees detail view, confirms. Config written with full rigor block.

### Example 2: Quick switch to lean
```
/nw:rigor lean
```
Current profile is "standard". Shows diff: loses review, loses PREPARE/COMMIT phases, loses refactoring pass. Agent drops from sonnet to haiku. User confirms. Config updated.

### Example 3: Quick switch up
```
/nw:rigor thorough
```
Current profile is "standard". Shows diff: sonnet->opus agent, haiku->sonnet reviewer, double review enabled. No losses to highlight (pure upgrade). User confirms. Config updated.

### Example 4: Invalid profile name
```
/nw:rigor turbo
```
Error: "Unknown profile 'turbo'. Available: lean, standard, thorough, exhaustive, inherit"

### Example 5: No nWave installed
```
/nw:rigor
```
No `.nwave/` directory found. Shows: "No nWave config directory found. Run nwave install first." Stops.
