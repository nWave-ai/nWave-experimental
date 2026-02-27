# Journey: CZ-Driven Dev Release Version Calculation

**Epic**: release-commitizen
**Persona**: Mike (release engineer, nwave-dev repo)
**Trigger**: Mike triggers a dev release; the version bump level should reflect conventional commits, not always patch
**Emotional arc**: Frustrated (wrong version) -> Trusting (CZ analyzes commits) -> Confident (correct bump level)

---

## Problem: Before (Hardcoded Patch)

```
Mike pushes 4 feat: commits on master
                    |
                    v
    +-------------------------------+
    | release-dev.yml               |   Feeling: FRUSTRATED
    | next_version.py --stage dev   |   "I pushed 4 features but the
    | _bump_patch() always          |    version only bumped patch"
    |                               |
    | current: 1.1.22               |
    | result:  1.1.23.dev2          |   WRONG: should be 1.2.0.dev1
    +-------------------------------+
```

## Solution: After (CZ + Floor Override)

```
Mike triggers workflow_dispatch on release-dev.yml
                    |
                    v
    +-------------------------------+
    | CI Status Gate                |   Feeling: TRUSTING
    | (unchanged from existing)     |   "Same gate, same safety"
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Step A: Commitizen analysis   |   Feeling: TRUSTING
    | cz bump --get-next            |   "CZ reads my commits and
    |                               |    determines the right level"
    | Reads: pyproject.toml version |
    | Scans: commits since v1.1.22  |
    | Finds: 4 feat: commits        |
    | Output: "1.2.0"              |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Step B: Read version floor    |   Feeling: AWARE
    | [tool.nwave].public_version   |   "There is a manual override
    |                               |    if the team needs one"
    | Reads: pyproject.toml         |
    | Output: "1.1.0"              |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Step C: next_version.py       |   Feeling: CONFIDENT
    | --stage dev                   |   "The priority chain picks
    | --base-version 1.2.0          |    the right version"
    | --version-floor 1.1.0         |
    |                               |
    | Priority resolution:          |
    |   1. Floor 1.1.0 < CZ 1.2.0  |
    |   2. CZ wins: base = 1.2.0   |
    |   3. Counter: .dev1           |
    |                               |
    | Output: 1.2.0.dev1            |   CORRECT
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Build + Tag + Notify          |   Feeling: CONFIRMED
    | (unchanged from existing)     |   "Right version, tagged, done"
    +-------------------------------+
```

## Mid-Cycle Bump Escalation (Patch to Minor)

```
Day 1-5: Mike + Ale push ci: and fix: commits
                    |
                    v
    +-------------------------------+
    | CZ scans commits since v1.1.25|   Feeling: ROUTINE
    | Highest bump: fix: -> PATCH   |   "Fix work, patch bumps,
    | Output: "1.1.26"              |    business as usual"
    +-------------------------------+
                    |
                    v
    v1.1.26.dev1 ... v1.1.26.dev8      8 dev releases tagged

Day 6: Ale pushes feat: commit (new agent)
                    |
                    v
    +-------------------------------+
    | CZ re-scans ALL commits       |   Feeling: TRUSTING
    | since v1.1.25 (not just new!) |   "CZ sees the full picture,
    |                               |    not just the latest commit"
    | Finds: fix: + feat:           |
    | Highest bump: feat: -> MINOR  |
    | Output: "1.2.0"              |   BASE CHANGED
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | _highest_counter("1.2.0")     |   Feeling: CONFIDENT
    | Searches for v1.2.0.dev* tags |   "Counter reset is automatic,
    | Finds: NONE                   |    no manual intervention"
    | Old v1.1.26.dev* = invisible  |
    |                               |
    | Output: 1.2.0.dev1            |   COUNTER RESET
    +-------------------------------+
                    |
                    v
    Tag coexistence in repo:
    v1.1.26.dev1 ... v1.1.26.dev8      (old base, still valid)
    v1.2.0.dev1                         (new base, counter starts fresh)
```

## Why De-Escalation Cannot Happen

```
    +---------------------------------------------------+
    | CZ scans ALL commits since last stable tag.       |
    | A feat: commit is ALWAYS in the history, even     |
    | if a revert: follows it.                          |
    |                                                   |
    | Commits: fix: fix: feat: revert: fix:             |
    |          ^    ^    ^     ^        ^               |
    |          |    |    |     |        |               |
    |          |    |    |     Does NOT erase feat:     |
    |          |    |    |     from CZ's scan           |
    |          |    |    Highest bump = MINOR           |
    |          |    PATCH                               |
    |          PATCH                                    |
    |                                                   |
    | Result: CZ still outputs "1.2.0"                  |
    | The only way to "de-escalate" is a new stable     |
    | release that resets the commit scan window.       |
    +---------------------------------------------------+
```

## RC Promotion After Escalation

```
    Tags in repo after escalation:
    v1.1.26.dev1 ... v1.1.26.dev8      (old patch-bump base)
    v1.2.0.dev1, v1.2.0.dev2           (new minor-bump base)
                    |
                    v
    +-------------------------------+
    | Team clicks "Promote to RC"   |   Feeling: CONFIDENT
    | RC inherits from highest      |   "One click, right version,
    | dev base: v1.2.0.dev2         |    the path is clear"
    +-------------------------------+
                    |
                    v
    v1.2.0.dev2 --> v1.2.0rc1 --> v1.2.0     One-click at each stage
```

## Floor Override Scenario

```
nwave-ai team sets public_version = "2.0.0" for a major release
                    |
                    v
    +-------------------------------+
    | CZ says: 1.2.0 (feat: only)  |
    | Floor says: 2.0.0             |
    |                               |
    | 2.0.0 > 1.2.0                |
    | Floor wins: base = 2.0.0     |
    |                               |
    | Output: 2.0.0.dev1            |   Feeling: CONFIDENT
    +-------------------------------+               "Floor override
                                                     works as expected"
```

## Fallback Scenario

```
CZ fails or returns empty (broken config, no parseable commits)
                    |
                    v
    +-------------------------------+
    | CZ output: "" (empty)         |
    | Floor: 1.1.0                  |
    |                               |
    | No base-version provided      |
    | Fallback: _bump_patch(1.1.22) |
    | base = 1.1.23                 |
    |                               |
    | Floor 1.1.0 < fallback 1.1.23 |
    | Fallback wins: 1.1.23        |
    |                               |
    | Output: 1.1.23.dev1           |   Feeling: SAFE
    +-------------------------------+   "Pipeline did not break;
                                         I can investigate CZ later"
```

## Version Resolution Priority Chain

```
+---------------------------------------------------+
| 1. Floor override (highest priority)              |
|    [tool.nwave].public_version                    |
|    Only wins when floor > base                    |
+---------------------------------------------------+
          |  floor <= base? skip
          v
+---------------------------------------------------+
| 2. Commitizen commit analysis (primary)           |
|    cz bump --get-next                             |
|    feat: -> minor, fix: -> patch, !: -> major     |
+---------------------------------------------------+
          |  CZ empty or fails? skip
          v
+---------------------------------------------------+
| 3. _bump_patch fallback (safety net)              |
|    current_version.micro + 1                      |
|    Preserves today's behavior as last resort      |
+---------------------------------------------------+
```

## Shared Artifacts Produced

| Artifact | Value | Source | Consumed By |
|----------|-------|--------|-------------|
| `cz_base_version` | `1.2.0` | CZ analysis step | next_version.py `--base-version` |
| `version_floor` | `1.1.0` | pyproject.toml `[tool.nwave]` | next_version.py `--version-floor` |
| `dev_version` | `1.2.0.dev1` | next_version.py output | Tag, GitHub release, Slack |
| `dev_tag` | `v1.2.0.dev1` | next_version.py output | Stage 2 RC promotion |

## Full Three-Stage Promotion Chain (Dev -> RC -> Stable)

```
STAGE 1: DEV RELEASE (release-dev.yml)
=========================================

    Day 1-5: fix: commits             Day 6: Ale pushes feat:
    CZ -> 1.1.26                      CZ re-scans -> 1.2.0
              |                                 |
              v                                 v
    v1.1.26.dev1                       v1.2.0.dev1
    v1.1.26.dev2                       v1.2.0.dev2        <-- LATEST
    ...
    v1.1.26.dev8 (ORPHANED)
                                                |
                                                v
STAGE 2: RC PROMOTION (release-rc.yml)          |         Feeling: CONFIDENT
=========================================      |         "One click, right version"
                                                |
    Mike clicks "Promote to RC"                 |
    Leaves tag field EMPTY                      |
                    |                           |
                    v                           |
    +-------------------------------+           |
    | discover_tag.py --pattern dev |           |
    | Parses ALL dev tags:          |           |
    |   v1.1.26.dev8 -> Version()   |           |
    |   v1.2.0.dev2  -> Version()   |           |
    |                               |           |
    | packaging.Version sort:       |           |
    |   1.2.0.dev2 > 1.1.26.dev8   |           |
    |                               |           |
    | Result: v1.2.0.dev2           | <---------+
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | calculate_rc("v1.2.0.dev2")   |
    |                               |
    | Strip dev suffix:             |
    |   parsed.major = 1            |
    |   parsed.minor = 2            |
    |   parsed.micro = 0            |
    |   base = "1.2.0"             |
    |                               |
    | _highest_counter(base, "rc")  |
    |   No v1.2.0rc* tags -> 0     |
    |   next_rc = 1                 |
    |                               |
    | Output: 1.2.0rc1              |
    +-------------------------------+
                    |
                    v
    Tag v1.2.0rc1 created                       Feeling: ASSURED
    GitHub pre-release published                "RC is the right version"
    nWave-beta synced
    Slack notified
                    |
                    v
    (Bug found in RC? Fix, push, new dev3, promote again -> v1.2.0rc2)
                    |
                    v
STAGE 3: STABLE PROMOTION (release-prod.yml)    Feeling: CONFIDENT
=========================================      "Final step, clean version"

    Mike clicks "Promote to Stable"
    Leaves tag field EMPTY
                    |
                    v
    +-------------------------------+
    | discover_tag.py --pattern rc  |
    | Parses ALL RC tags:           |
    |   v1.2.0rc1 -> Version()      |
    |   v1.2.0rc2 -> Version()      |
    |                               |
    | packaging.Version sort:       |
    |   1.2.0rc2 > 1.2.0rc1        |
    |                               |
    | Result: v1.2.0rc2             |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | calculate_stable("v1.2.0rc2") |
    |                               |
    | Strip RC suffix:              |
    |   parsed.major = 1            |
    |   parsed.minor = 2            |
    |   parsed.micro = 0            |
    |   base = "1.2.0"             |
    |                               |
    | Output: 1.2.0                 |
    +-------------------------------+
                    |
                    v
    pyproject.toml updated: version = "1.2.0"
    Tag v1.2.0 created                          Feeling: DONE
    GitHub Release (full, not pre-release)      "Clean version number,
    PyPI stable publish                          published everywhere"
    nwave-ai/nwave public repo synced
    Slack notified
```

## Self-Healing: Accidental Wrong-Tag Promotion

```
    Someone manually enters "v1.1.26.dev8" in RC tag field
                    |
                    v
    +-------------------------------+
    | discover_tag.py --validate    |   Feeling: CONCERNED
    | "v1.1.26.dev8"               |   "Someone used the
    | Tag exists -> validated       |    wrong tag..."
    +-------------------------------+
                    |
                    v
    calculate_rc("v1.1.26.dev8") -> v1.1.26rc1 created (ACCIDENTAL)

    Later: correct RC promotion -> v1.2.0rc1 created (CORRECT)

    Now repo has BOTH:
    v1.1.26rc1 (accidental)
    v1.2.0rc1  (correct)
                    |
                    v
    +-------------------------------+
    | Stable promotion:             |   Feeling: RELIEVED
    | discover_tag.py --pattern rc  |   "System picked the
    |                               |    right one anyway"
    | 1.2.0rc1 > 1.1.26rc1        |
    | (packaging.Version sort)      |
    |                               |
    | Result: v1.2.0rc1             |
    | Stable: 1.2.0 (CORRECT)     |
    +-------------------------------+

    v1.1.26rc1 remains as dead-end artifact (never reaches stable)
    System self-heals because discover_tag ALWAYS picks the highest
```

## Floor Override Scope (Dev Only)

```
    +---------------------------------------------------+
    | Floor override: [tool.nwave].public_version       |
    |                                                   |
    | Stage 1 (Dev):   Floor IS consulted               |
    |   release-dev.yml reads floor via                 |
    |   read_toml_field.py, passes --version-floor      |
    |   Floor wins when floor > CZ base                 |
    |                                                   |
    | Stage 2 (RC):    Floor is NOT consulted            |
    |   release-rc.yml does not read floor              |
    |   calculate_rc receives dev tag directly          |
    |   Base comes from stripping dev suffix            |
    |                                                   |
    | Stage 3 (Stable): Floor is NOT consulted           |
    |   release-prod.yml does not read floor            |
    |   calculate_stable receives RC tag directly       |
    |   Base comes from stripping RC suffix             |
    |                                                   |
    | Key: RC and stable inherit the base from the      |
    | tag being promoted. No floor override at these    |
    | stages. This is by design.                        |
    +---------------------------------------------------+
```

## One-Click UX at Each Stage

```
    +-------+     +-------+     +--------+
    | DEV   | --> | RC    | --> | STABLE |
    +-------+     +-------+     +--------+
    trigger:      tag empty     tag empty
    auto via CZ   auto-discover auto-discover

    Click 1          Click 2        Click 3
    (or auto)        (manual)       (manual)

    v1.2.0.dev2  ->  v1.2.0rc1  ->  v1.2.0

    Each stage:
    - User clicks workflow_dispatch
    - Leaves tag input field EMPTY
    - discover_tag.py auto-discovers the correct tag
    - Version calculation produces the right next version
    - No manual tag typing required
```

## Error Paths

| Error | User Sees | Recovery |
|-------|-----------|----------|
| CZ not installed | CZ step outputs empty; fallback to patch bump | Install commitizen, re-run |
| CZ config missing | CZ step outputs empty; fallback to patch bump | Add `[tool.commitizen]` to pyproject.toml |
| CZ returns unparseable output | CZ step outputs empty; fallback to patch bump | Check CZ version/config |
| Floor is invalid PEP 440 | next_version.py exits code 2: "Invalid version-floor" | Fix pyproject.toml value |
| Base-version is invalid PEP 440 | next_version.py exits code 2: "Invalid base-version" | Investigate CZ output |
| No dev tags found (RC promotion) | discover_tag.py exits code 1: "No dev tags found. Run Stage 1 first." | Run a dev release first |
| No RC tags found (stable promotion) | discover_tag.py exits code 1: "No rc tags found. Run Stage 2 first." | Run an RC promotion first |
| RC tag manually entered does not exist | discover_tag.py exits code 1: "Tag not found" | Check tag name, use auto-discover |
