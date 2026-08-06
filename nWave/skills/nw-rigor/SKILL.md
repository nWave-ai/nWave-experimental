---
name: nw-rigor
description: "Selects a quality-vs-token-consumption profile (lean, standard, thorough, exhaustive, custom, inherit) and persists it globally (~/.nwave/global-config.json) or per-project (.nwave/des-config.json). Use when tuning how much rigor wave commands apply."
user-invocable: false
argument-hint: '[profile] - Optional: lean, standard, thorough, exhaustive, custom, inherit. Omit for interactive selection.'
---

# NW-RIGOR: Quality Profile Selection

**Wave**: CROSS_WAVE | **Agent**: Main Instance (self) | **Command**: `/nw-rigor [profile]`

## Overview

Interactive command to select a quality-vs-token-consumption profile. Persists choice to either `~/.nwave/global-config.json` (global scope) or `.nwave/des-config.json` (project scope) under the `rigor` key. All wave commands read this config to adjust agent models, review policy, examination depth, and refactoring effort.

You (the main Claude instance) run this directly. No subagent delegation.

Every delivery uses the same fixed floor: consume an upstream executable acceptance test, implement the smallest design-conformant change that makes it pass, refactor proportionately, and independently review or EXAMINE observable behaviour. Profiles do not select workflow phases or retain phase history.

## Profile Mappings (Single Source of Truth)

| Setting            | lean                                  | standard [recommended]                                                       | thorough                                                                     | exhaustive                                                                   | inherit                                                                      |
|--------------------|---------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| agent_model        | haiku                                 | sonnet                                                                       | opus                                                                         | opus                                                                         | inherit                                                                      |
| reviewer_model     | skip                                  | haiku                                                                        | sonnet                                                                       | opus                                                                         | haiku                                                                        |
| review_enabled     | false                                 | true                                                                         | true                                                                         | true                                                                         | true                                                                         |
| double_review      | false                                 | false                                                                        | true                                                                         | true                                                                         | false                                                                        |
| refactor_pass      | false                                 | true                                                                         | true                                                                         | true                                                                         | true                                                                         |
| examine_swarm_n    | 1                                     | 1                                                                           | 3                                                                           | 5                                                                           | 1                                                                           |

**v2 evolution notes (evidence-by-execution migration, 2026-07-03) — the rigor axes shifted with the flow:**
- `examine_swarm_n` (NEW): how many independent User-Examiners ("Vera") walk each slice's expectation charter at the DELIVER EXAMINE step. `1` = one exam; `≥3` = swarm, and **divergence between the session logs is itself a signal** (a charter that different examiners read differently is under-specified). The examiner runs on **haiku** (its work is walk/observe/describe, not code reasoning — model pinned in the `nw-user-examiner` agent, not a rigor knob).
- `reviewer_model` is now the **FEATURE-END** deep-review model (P2.2). The per-slice code-reading `C_REVIEWER_AUDIT` is REPLACED by the EXAMINE step (execution-observation) — see nw-deliver. `reviewer_model` is retained (backward-compat + the feature-end review), not deleted.
- `agent_model` is **UNCAPPED** — `thorough`/`exhaustive` legitimately offer `opus` for the user's high-stakes choice (vision principle 4). (The no-opus/fable rule governs Lyra's *own* migration dispatches + defaults, not the product ceiling.)
- The **mutation-testing knob** is **no longer a rigor axis**, and mutation testing is **DEPRECATED** (FR-1, velocity-v2) — NOT a per-feature knob and NOT a nightly job. New profiles disable it; its 2 consumers skip when it is off. The `mutation-test` task is explicit opt-in only; green ATs + EXAMINE are the truth.

## Execution-observing floor (ALWAYS on — NOT rigor-gated)

Ale 2026-07-03 (ratified). The gates that **observe execution** — `verify-red-green`
(the AT genuinely went RED→GREEN, non-vacuous), `verify-spec-coverage` (every requirement
has a covering AT), and the `examine-verdict` gate (a User-Examiner walked the charter on the
real surface) — are a **FIXED FLOOR present in EVERY profile, `lean` included**. No profile
can gate them off.

Rigor modulates only the **elevatable dimensions ABOVE the floor**: `agent_model`,
`examine_swarm_n`, `reviewer_model` (feature-end), `refactor_pass`, review depth. It NEVER
lowers the floor. This refines vision principle 4 (proportional quality) — proportional
*above* the floor, never *below* it: the execution-observation is the one thing that is not
bartered for speed (it is exactly the hole that shipped testing-theater in the external eval).
See `[[feedback_execution_observing_gates_are_fixed_floor_not_rigor_gated_2026_07_03]]`.

## Behavior Flow

### Mode Detection

- No argument -> Mode 1 (Interactive Selection)
- Argument is a preset name (lean, standard, thorough, exhaustive, inherit) -> Mode 2 (Quick Switch)
- Argument is `custom` -> Mode 3 (Custom Builder)

### Mode 1: Interactive Selection (no argument)

#### Step 1: Welcome

Read `.nwave/des-config.json`. If missing or `.nwave/` directory absent -> error: "No nWave config directory found. Run nwave install first."

If JSON is invalid -> backup as `.nwave/des-config.json.bak`, reset config to `{}`, note: "Config was corrupted. Backed up and reset."

Display current profile (from `config.rigor.profile`) or "none set" if absent.

Brief explanation: "Rigor profiles control how much quality infrastructure nWave applies per wave: agent models, review and examination depth, refactoring effort. Higher rigor = stronger optional assurance and higher token cost; the executable-AT floor remains fixed."

#### Step 1.5: Scope Selection

Display the current project rigor (from `.nwave/des-config.json`) and current global rigor (from `~/.nwave/global-config.json`, if it exists).

Ask via AskUserQuestion:
```
Where do you want to save this configuration?
```
Options:
1. Globally (~/.nwave/global-config.json) — applies to all projects without their own rigor
2. This project only (.nwave/des-config.json) — overrides global for this project

Store the user's choice as `{scope}` and the corresponding file path as `{target_file}`:
- If global: `{target_file}` = `~/.nwave/global-config.json`
- If project: `{target_file}` = `.nwave/des-config.json`

#### Step 2: Comparison Table

Display this table:

```
+-----------+--------+----------+----------+------------+---------+
|           | lean   | standard | thorough | exhaustive | inherit |
+-----------+--------+----------+----------+------------+---------+
| Agent     | haiku  | sonnet   | opus     | opus       | *yours* |
| Reviewer  | --     | haiku    | sonnet   | opus       | haiku   |
| Review    | no     | yes      | double   | double     | yes     |
| Refactor  | no     | yes      | yes      | yes        | yes     |
+-----------+--------+----------+----------+------------+---------+
| Est. cost | lowest | moderate | higher   | highest    | varies  |
| Est. time | fast   | moderate | slower   | slowest    | varies  |
+-----------+--------+----------+----------+------------+---------+
```

Mark "standard" as [recommended]. Below the table, note: "Or choose **custom** to configure each setting individually. Type **inherit** to use your current session model."

#### Step 3: User Selection

Ask user to select via AskUserQuestion (4 options + Other for inherit/custom):

1. standard [recommended]
2. lean
3. thorough
4. exhaustive

Note in the question text: "Type 'custom' to build your own profile, or 'inherit' to use your session model."

If user selects or types "custom" -> jump to Mode 3 (Custom Builder).
If user types "inherit" -> proceed with inherit profile to Step 4.

#### Step 4: Detail View

Show the detail view for the selected profile. Render in a code block for visual clarity.

**lean:**
```
WHAT YOU GET:
  - Haiku agent (fastest, cheapest)
  - The fixed executable-AT delivery floor

WHAT YOU LOSE:
  - No code review
  - No dedicated refactoring pass

WHEN TO USE:
  Config changes, documentation, simple bug fixes, spikes/prototypes

ESTIMATED IMPACT:
  Lowest token cost | Fastest per step
```

**standard [recommended]:**
```
WHAT YOU GET:
  - Sonnet agent (balanced quality/speed)
  - Haiku reviewer (cost-effective review)
  - Dedicated proportional refactoring pass

WHAT'S NOT INCLUDED:
  - No double review (single pass only)
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
  - Dedicated proportional refactoring pass

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
  - Dedicated proportional refactoring pass

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
  - Single review pass
  - Dedicated proportional refactoring pass

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

1. If `{scope}` is global AND the directory `~/.nwave/` does not exist, create it with `parents=True`
2. Read `{target_file}` (handle missing file or corrupt JSON: start with `{}`)
3. Parse JSON
4. Set `config["rigor"]` to the full profile object:
   ```json
   {
     "profile": "{selected}",
     "agent_model": "...",
     "reviewer_model": "...",
     "review_enabled": true/false,
     "double_review": true/false,
     "refactor_pass": true/false
   }
   ```
5. Write back to `{target_file}`, preserving all other top-level keys (audit_logging_enabled, skill_tracking, etc.)

#### Step 7: Summary

Display all resolved settings:

```
Rigor profile saved: {name}

  Resolved settings:
  +-----------------------+---------------------------------------------------+
  | agent_model           | {value}                                           |
  | reviewer_model        | {value}                                           |
  | review_enabled        | {value}                                           |
  | double_review         | {value}                                           |
  | refactor_pass         | {value}                                           |
  +-----------------------+---------------------------------------------------+

  Config: {target_file} ({scope})
  All wave commands will use these settings.
```

### Mode 2: Quick Switch (with argument)

#### Step 1: Validate Argument

If argument is not one of: lean, standard, thorough, exhaustive, custom, inherit -> error: "Unknown profile '{name}'. Available: lean, standard, thorough, exhaustive, custom, inherit"

If argument is `custom` -> redirect to Mode 3 (Custom Builder).

Read `.nwave/des-config.json`. If missing -> same error as Mode 1 Step 1.

#### Step 1.5: Scope Selection

Same as Mode 1 Step 1.5. Ask scope question, store `{scope}` and `{target_file}`.

#### Step 2: Show Diff

Display what changes from current profile to target profile:

```
Switching from {current} -> {target}:

  agent_model:      sonnet -> haiku
  reviewer_model:   haiku -> skip
  review_enabled:   true -> false
  refactor_pass:    true -> false
```

If downgrading (moving to a less rigorous profile), highlight what user will lose:

```
You will LOSE:
  - Code review (reviewer_model: skip)
  - Dedicated refactoring pass
```

If no current profile is set, show the target profile settings without diff.

#### Step 3: Confirm

Ask user to confirm via AskUserQuestion:
1. Yes, switch to {target}
2. No, keep current profile

#### Step 4: Save + Summary

Same as Mode 1 Steps 6 and 7. Uses `{target_file}` from Step 1.5.

### Mode 3: Custom Builder (`/nw-rigor custom` or selected from interactive)

Build a profile setting by setting. Each question uses AskUserQuestion with sensible defaults (standard values pre-selected). After all questions, show summary and confirm.

#### Step 1: Config Check

Same as Mode 1 Step 1 (read config, handle missing/corrupt).

#### Step 1.5: Scope Selection

Same as Mode 1 Step 1.5. Ask scope question, store `{scope}` and `{target_file}`.

#### Step 2: Agent Model

Ask via AskUserQuestion:
```
Which model should agents use? (crafter, architect, acceptance-designer)
```
Options:
1. sonnet (Recommended) — balanced quality and speed
2. haiku — fastest, lowest cost
3. opus — strongest reasoning, highest cost
4. inherit — use your current session model

#### Step 3: Reviewer Model

Ask via AskUserQuestion:
```
Which model for peer reviewers?
```
Options:
1. haiku (Recommended) — cost-effective review
2. sonnet — deeper analysis
3. opus — most thorough review
4. skip — no peer review

#### Step 4: Double Review

Ask via AskUserQuestion:
```
Run peer review twice (two independent passes)?
```
Options:
1. No (Recommended) — single review pass
2. Yes — two independent review passes (higher cost)

Only show this question if reviewer_model is not "skip". If "skip", set double_review = false automatically.

#### Step 5: Refactoring Pass

Ask via AskUserQuestion:
```
Include a dedicated refactoring pass after implementation?
```
Options:
1. Yes (Recommended) — a dedicated proportional refactoring pass after the AT is green
2. No — use only the fixed delivery floor's inline cleanup

#### Step 6: Summary + Confirm

Display the assembled profile:

```
Custom profile:

  +-----------------------+---------------------------------------------------+
  | agent_model           | {value}                                           |
  | reviewer_model        | {value}                                           |
  | double_review         | {value}                                           |
  | refactor_pass         | {value}                                           |
  +-----------------------+---------------------------------------------------+
```

Ask to confirm via AskUserQuestion:
1. Yes, apply this custom profile
2. Start over (return to Step 2)
3. Cancel (exit without saving)

#### Step 7: Save + Summary

Same as Mode 1 Steps 6 and 7. Uses `{target_file}` from Step 1.5. Save with `"profile": "custom"`.

## Error Handling

| Error | Response |
|-------|----------|
| Missing `.nwave/` directory | "No nWave config directory found. Run nwave install first." |
| Invalid JSON in des-config.json | Backup as `.bak`, reset to `{}`, proceed with notice |
| Unknown profile name | "Unknown profile '{name}'. Available: lean, standard, thorough, exhaustive, custom, inherit" |
| inherit with undetectable session model | Fallback to sonnet with notice: "Could not detect session model. Defaulting agent_model to sonnet." |

## Success Criteria

- [ ] Current profile displayed (or "none set")
- [ ] Scope question asked (global vs project) in all 3 modes
- [ ] Comparison table shown with all 5 profiles
- [ ] User selected and confirmed a profile
- [ ] Config written to `{target_file}` (read-modify-write, other keys preserved)
- [ ] `~/.nwave/` directory auto-created with `parents=True` on first global save
- [ ] Summary of all resolved settings displayed (including scope and target file path)

## Examples

### Example 1: Interactive first-time selection
```
/nw-rigor
```
No current profile set. Shows comparison table, user picks "standard", sees detail view, confirms. Config written with full rigor block.

### Example 2: Quick switch to lean
```
/nw-rigor lean
```
Current profile is "standard". Shows diff: loses review and the dedicated refactoring pass. Agent drops from sonnet to haiku. User confirms. Config updated.

### Example 3: Quick switch up
```
/nw-rigor thorough
```
Current profile is "standard". Shows diff: sonnet->opus agent, haiku->sonnet reviewer, double review enabled. No losses to highlight (pure upgrade). User confirms. Config updated.

### Example 4: Custom profile builder
```
/nw-rigor custom
```
Walks through 4 questions: agent model (opus), reviewer (haiku), double review (no), refactoring (yes). Saves as custom profile with opus agent, haiku reviewer, single review, and dedicated refactoring — a combination no preset offers.

### Example 5: Invalid profile name
```
/nw-rigor turbo
```
Error: "Unknown profile 'turbo'. Available: lean, standard, thorough, exhaustive, inherit"

### Example 6: No nWave installed
```
/nw-rigor
```
No `.nwave/` directory found. Shows: "No nWave config directory found. Run nwave install first." Stops.
