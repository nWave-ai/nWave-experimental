# JTBD Job Stories: DES Housekeeping

## Job Statement

"Help me trust that my development tooling maintains itself so I can focus on building software."

---

## Job Story 1: Self-Maintaining Workspace

**When** I open Claude Code to start a new development session after weeks of daily usage,
**I want to** trust that the tooling has kept its own workspace clean,
**so I can** focus entirely on my work without worrying about disk accumulation or stale state from past sessions.

### Functional Job
Prevent unbounded growth of operational files (.nwave/ directory) without manual intervention.

### Emotional Job
Feel that the tool is professionally maintained -- it cleans up after itself like any well-engineered system should.

### Social Job
Not be the developer whose project directory has hundreds of megabytes of tool debris when a colleague clones and installs.

### Forces Analysis
- **Push**: 21+ audit log files accumulating visibly in `.nwave/des/logs/`; `skill-loading-log.jsonl` grows without bound; orphaned signal files from crashed sessions linger indefinitely
- **Pull**: Zero-maintenance operation where the tool quietly handles its own hygiene like log rotation in any production system
- **Anxiety**: "Will cleanup accidentally delete a log I need for debugging a recent issue?" / "Will housekeeping slow down session start?"
- **Habit**: Currently ignoring the problem -- `.nwave/` is in `.gitignore` so it is out of sight, out of mind until disk pressure forces attention

### Assessment
- Switch likelihood: **High** (zero effort for users, solves visible problem)
- Key blocker: Anxiety about losing recent debugging data
- Key enabler: Push from visible log accumulation
- Design implication: Retention period must be generous enough that users never lose data they might need, and fast enough that they never notice it running

---

## Job Story 2: Clean Slate on Session Start

**When** I start a new Claude Code session after a previous session crashed or was force-killed,
**I want to** begin with a clean state free of stale signal files from the dead session,
**so I can** avoid phantom "task already active" blocks or stale session guards that would interfere with my work.

### Functional Job
Detect and remove orphaned signal files (des-task-active-*, deliver-session.json) that no longer correspond to running processes.

### Emotional Job
Feel confident that each session starts fresh -- no ghosts from past sessions haunting current work.

### Social Job
Not waste time debugging tool state issues that look like bugs ("Why is DES blocking my writes? I don't have a deliver session running!").

### Forces Analysis
- **Push**: Orphaned `des-task-active-*` files block new DES tasks; stale `deliver-session.json` triggers write guards on source files when no deliver session is actually running
- **Pull**: Every session starts from known-good state regardless of how the previous session ended
- **Anxiety**: "What if I have two Claude Code windows open and housekeeping kills the signal file the other window is using?"
- **Habit**: Manually deleting `.nwave/des/des-task-active*` files when things seem stuck

### Assessment
- Switch likelihood: **High** (directly fixes user-visible pain)
- Key blocker: Anxiety about multi-window scenarios (concurrent sessions)
- Key enabler: Push from stale signal files causing real workflow blocks
- Design implication: Staleness detection must use time-based heuristics (file age), not just existence checks, to avoid killing active signals from concurrent sessions

---

## Job Story 3: Predictable Resource Usage

**When** I use nWave daily across multiple projects over weeks and months,
**I want to** know that operational files will not grow unboundedly,
**so I can** rely on the tool without periodically auditing and manually cleaning its working directory.

### Functional Job
Bound the disk footprint of all DES operational files to a predictable, reasonable size.

### Emotional Job
Feel that the tool respects my system resources -- it is a good citizen on my machine.

### Social Job
Recommend nWave to colleagues without the caveat "oh, and you'll need to manually clean `.nwave/` every few weeks."

### Forces Analysis
- **Push**: `skill-loading-log.jsonl` has no rotation and grows linearly with every session; audit logs accumulate one file per day of usage with no expiry
- **Pull**: Bounded, predictable disk usage with sensible defaults (keep recent logs, rotate/truncate the rest)
- **Anxiety**: "Can I customize retention if I need longer history for compliance or debugging?"
- **Habit**: Not thinking about tool storage -- most CLI tools either manage their own storage or use temp directories

### Assessment
- Switch likelihood: **High** (invisible improvement, zero user cost)
- Key blocker: Minimal -- defaults just need to be sensible
- Key enabler: Push from unbounded growth in long-running projects
- Design implication: Sensible defaults (7 days audit retention, truncate skill log at reasonable size) with optional configuration for power users via des-config.json

---

## Outcome Statements

1. **Minimize** the likelihood that DES operational files interfere with the user's development workflow
2. **Minimize** the time a user spends managing or troubleshooting DES file accumulation (target: zero)
3. **Minimize** the disk footprint of DES operational files to a bounded, predictable size
4. **Minimize** the likelihood that housekeeping removes data the user actively needs
5. **Minimize** the time added to session startup by housekeeping operations (target: imperceptible, <100ms typical)

---

## 8-Step Job Map: Workspace Self-Maintenance

| Step | In This Context | Key Requirement |
|------|----------------|-----------------|
| 1. Define | Determine what needs cleaning and retention policy | Sensible defaults, optional config |
| 2. Locate | Find `.nwave/` directory and its operational files | Known, fixed paths within project |
| 3. Prepare | Check if housekeeping is due (frequency gating) | Avoid running every single session if unnecessary |
| 4. Confirm | Validate files are safe to remove (age, staleness) | Time-based staleness, not just existence |
| 5. Execute | Delete old logs, remove orphans, truncate oversized files | Atomic per-file operations, fail-open |
| 6. Monitor | Track what was cleaned (optional, debug-level) | No output by default; summary available for troubleshooting |
| 7. Modify | Handle exceptions (permission errors, locked files) | Skip and continue -- never fail the session |
| 8. Conclude | Session continues normally | User is unaware housekeeping ran |
