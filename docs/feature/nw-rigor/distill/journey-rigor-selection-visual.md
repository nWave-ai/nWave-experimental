# Journey: Rigor Profile Selection

**Epic**: nw-rigor
**Persona**: Kai Nakamura (pragmatic crafter) / Priya Sharma (budget-conscious lead) / Tomasz Kowalski (model-opinionated dev)
**Trigger**: User runs `/nw:rigor` or starts first nWave session without a profile set
**Emotional arc**: Uncertain -> Informed -> Decided -> Confident

---

## Flow

```
User runs /nw:rigor (or first session without profile)
                    |
                    v
    +----------------------------------------------+
    | nWave Rigor Configuration                    |   Feeling: WELCOMED
    |                                              |
    | "nWave adapts its quality checks to match    |
    |  your needs. Let's find the right balance."  |
    |                                              |
    | Current profile: [none set]                  |
    +----------------------------------------------+
                    |
                    v
    +----------------------------------------------+
    | Profile Overview (comparison table)          |   Feeling: INFORMED
    |                                              |
    | Shows all 5 profiles side-by-side:           |
    |   lean / standard / thorough / exhaustive   |
    |   / inherit                                  |
    |                                              |
    | For each: what's included, what's excluded,  |
    | estimated token range, time impact           |
    |                                              |
    | "standard" marked as [recommended]           |
    +----------------------------------------------+
                    |
                    v
    +----------------------------------------------+
    | "Which profile fits your current work?"      |   Feeling: GUIDED
    |                                              |
    | > 1. lean       -- fast iteration, minimal   |
    | > 2. standard   -- balanced [recommended]    |
    | > 3. thorough   -- high confidence           |
    | > 4. exhaustive -- maximum confidence        |
    | > 5. inherit    -- respect my model choice   |
    |                                              |
    | Enter number or name:                        |
    +----------------------------------------------+
                    |
         +----+----+----+----+----+
         |    |         |    |    |
         v    v         v    v    v
      [lean] [std]  [thor] [exh] [inherit]
         |    |         |    |    |
         v    v         v    v    v
    +----------------------------------------------+
    | Detail view for selected profile             |   Feeling: TRANSPARENT
    |                                              |
    | Shows EXACTLY what you get and what you lose |
    |                                              |
    | "With 'lean' you will NOT get:               |
    |   - Peer review of your code                 |
    |   - PREPARE/COMMIT TDD phases                |
    |   - Mutation testing                          |
    |   - Refactoring pass                         |
    |                                              |
    |  Estimated token savings: ~60% vs standard"  |
    |                                              |
    | Confirm? [Y/n/back]                          |
    +----------------------------------------------+
                    |
         +---------+---------+
         |                   |
      [confirm]           [back]
         |                   |
         v                   v
    +-----------------------+  (returns to profile list)
    | Saving to config...  |
    | Profile: standard    |   Feeling: DECIDED
    | Stored in:           |
    |  .nwave/des-config   |
    |                      |
    | All wave commands    |
    | will now use this    |
    | profile.             |
    +-----------------------+
                    |
                    v
    +----------------------------------------------+
    | Session confirmation                         |   Feeling: CONFIDENT
    |                                              |
    | "Profile 'standard' active.                  |
    |  Agent model: sonnet                         |
    |  Reviewer model: haiku                       |
    |  TDD: full 5-phase cycle                     |
    |  Review: yes                                 |
    |  Mutation: no                                |
    |                                              |
    |  Change anytime with /nw:rigor"              |
    +----------------------------------------------+
```

## TUI Mockup: Profile Comparison Table

```
$ /nw:rigor

nWave Rigor Configuration
=========================

Current profile: none set

Choose how much quality ceremony nWave applies to your session.
nWave recommends 'standard' for most development work.

+-----------+--------+----------+----------+------------+---------+
|           | lean   | standard | thorough | exhaustive | inherit |
+-----------+--------+----------+----------+------------+---------+
| Agent     | haiku  | sonnet   | opus     | opus       | *yours* |
| Reviewer  | --     | haiku    | sonnet   | opus       | haiku   |
| Review    | no     | yes      | double   | double     | yes     |
| TDD       | R->G   | 5-phase  | 5-phase+ | 5-phase+   | 5-phase |
| Refactor  | no     | yes      | yes+pass | yes+pass   | yes     |
| Mutation  | no     | no       | no       | yes        | no      |
+-----------+--------+----------+----------+------------+---------+
| Est. cost | ~40%   | baseline | ~180%    | ~250%      | varies  |
| Est. time | ~3 min | ~8 min   | ~20 min  | ~30 min    | ~8 min  |
+-----------+--------+----------+----------+------------+---------+
              ^                                           ^
              fast iteration                         your model,
              less confidence                       our checks
                         ^
                    [recommended]

Which profile? [1-5 or name]: _
```

## TUI Mockup: Detail View (lean selected)

```
Profile: lean
=============

WHAT YOU GET:
  + Haiku model for agents (fast, cheap)
  + RED -> GREEN TDD cycle (tests still required)
  + Basic implementation validation

WHAT YOU LOSE:
  - No peer review of your code
  - No PREPARE phase (test fixture setup skipped)
  - No COMMIT phase (no refactoring gate)
  - No mutation testing
  - No dedicated refactoring pass
  - Haiku may struggle with complex architectural decisions

WHEN TO USE:
  Config changes, documentation, simple bug fixes,
  experimental spikes, prototyping

ESTIMATED IMPACT:
  Token savings: ~60% vs standard
  Time savings:  ~50% vs standard
  Risk increase: moderate -- no review catches

Confirm 'lean'? [Y/n/back]: _
```

## TUI Mockup: Detail View (thorough selected)

```
Profile: thorough
=================

WHAT YOU GET:
  + Opus model for agents (highest capability)
  + Sonnet model for reviewers (strong review quality)
  + Double peer review (two review passes)
  + Full 5-phase TDD cycle with extra pass
  + Dedicated refactoring pass after GREEN

WHAT IT COSTS:
  - ~180% token usage vs standard
  - ~20 minutes per step (vs ~8 min standard)
  - Higher API cost per session

WHEN TO USE:
  Critical features, security-sensitive code, public API changes,
  release-blocking work, code that others will maintain

Confirm 'thorough'? [Y/n/back]: _
```

## TUI Mockup: Detail View (exhaustive selected)

```
Profile: exhaustive
===================

WHAT YOU GET:
  + Opus model for agents AND reviewers (highest capability everywhere)
  + Double peer review (two review passes)
  + Full 5-phase TDD cycle
  + Dedicated refactoring pass after GREEN
  + Mutation testing (>= 80% kill rate gate)

WHAT IT COSTS:
  - ~250% token usage vs standard
  - ~30 minutes per step (vs ~8 min standard)
  - Highest API cost per session
  - Opus reviewer significantly increases review cost

WHEN TO USE:
  Critical production systems, security-sensitive code, compliance-required,
  public API changes, code that will be maintained for years

Confirm 'exhaustive'? [Y/n/back]: _
```

## TUI Mockup: Detail View (inherit selected)

```
Profile: inherit
================

WHAT YOU GET:
  + Your current session model for agents (*currently: haiku*)
  + Haiku model for reviewers
  + Full 5-phase TDD cycle
  + Peer review (single pass)

WHAT THIS MEANS:
  nWave respects whatever model you chose in Claude Code.
  Quality checks stay at 'standard' level -- you control
  the model, nWave controls the process.

  If you switch models mid-session in Claude Code,
  nWave will use the new model for subsequent commands.

WHEN TO USE:
  When you have strong opinions about which model to use
  and want nWave to stay out of model selection.

Confirm 'inherit'? [Y/n/back]: _
```

## TUI Mockup: Confirmation

```
Profile 'standard' saved.
=========================

  Agent model:    sonnet
  Reviewer model: haiku
  TDD phases:     PREPARE -> RED_ACCEPTANCE -> RED_UNIT -> GREEN -> COMMIT
  Peer review:    yes (single pass)
  Mutation test:  no
  Refactor pass:  yes

  Stored in: .nwave/des-config.json
  Applies to: all /nw:* commands this session

  Change anytime: /nw:rigor
  Quick switch:   /nw:rigor lean
                  /nw:rigor thorough
                  /nw:rigor exhaustive
```

## TUI Mockup: Quick Switch (shortcut)

```
$ /nw:rigor lean

Switching profile: standard -> lean

  - Agent model:    sonnet -> haiku
  - Reviewer model: haiku -> skipped
  - Peer review:    yes -> no
  - TDD phases:     5-phase -> RED/GREEN only
  - Mutation test:  no -> no (unchanged)

  You will LOSE: peer review, PREPARE/COMMIT phases

Confirm? [Y/n]: _
```

## Error Paths

| Error | User Sees | Recovery |
|-------|-----------|----------|
| .nwave/ directory missing | "No nWave config directory found. Run nwave install first." | Install nWave |
| des-config.json not writable | "Cannot write to .nwave/des-config.json: permission denied" | Fix permissions |
| Invalid profile name | "Unknown profile 'turbo'. Available: lean, standard, thorough, exhaustive, inherit" | Re-enter |
| Config file corrupted | "Config file corrupted. Resetting to defaults." + backup old file | Auto-recovery |

## Shared Artifacts Produced

| Artifact | Value | Consumed By |
|----------|-------|-------------|
| `rigor_profile` | `lean\|standard\|thorough\|exhaustive\|inherit` | All /nw:* wave commands |
| `agent_model` | `haiku\|sonnet\|opus\|inherit` | DES orchestrator, Task tool invocations |
| `reviewer_model` | `skip\|haiku\|sonnet\|opus` | Review commands |
| `tdd_phases` | `[RED,GREEN]\|[PREPARE,RED_A,RED_U,GREEN,COMMIT]` | DES TDD cycle enforcement |
| `review_enabled` | `boolean` | Deliver, Design commands |
| `mutation_enabled` | `boolean` | Deliver Phase 5 |
