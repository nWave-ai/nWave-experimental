# Journey: Dev Release (Stage 1)

**Epic**: release-train-revamp
**Persona**: Mike (maintainer, nwave-dev repo)
**Trigger**: Mike decides a set of commits on master is worth tagging as a dev release
**Emotional arc**: Intentional -> Confident -> Verified

---

## Flow

```
Mike decides "this commit set is ready for a dev snapshot"
                    |
                    v
    +-------------------------------+
    | GitHub Actions UI             |   Feeling: INTENTIONAL
    | workflow_dispatch             |   "I'm choosing to mark this point"
    | [release-dev.yml]            |
    |                               |
    | Inputs:                       |
    |   target_version: [auto]      |
    |   dry_run: [no]               |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | CI Status Gate                |   Feeling: TRUSTING
    | Verify CI passed on commit   |   "Trust the CI, verify the proof"
    | GET /repos/.../check-runs    |
    | One API call, four outcomes   |
    | (fail fast: 2s check first)  |
    +-------------------------------+
                    |
       +------------+------------+
       |      |      |           |
    [GREEN] [FAIL] [PENDING] [NONE]
       |      |      |           |
       v      v      v           v
    +------+  +-------------------------------+
    | OK   |  | STOP                          |
    |      |  |  FAIL: "CI failed on {sha}"   |   Feeling: INFORMED
    +------+  |  PEND: "CI still running on   |   "Good, it caught it
       |      |   {sha}, retry later"         |    before calculating"
       v      |  NONE: "No CI run found       |
              |   for {sha}"                  |
              | Slack: FAIL                   |
              +-------------------------------+
    +-------------------------------+
    | Calculate next dev version    |   Feeling: TRUSTING
    | v1.1.22.dev1                  |   "The system knows the sequence"
    |                               |
    | Read current version (1.1.21) |
    | Determine next: 1.1.22       |
    | Append .dev{N} (sequential)   |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Build dist packages           |   Feeling: EFFICIENT
    | wheel + sdist                 |   "Just packaging, no re-testing"
    | Generate checksums            |
    +-------------------------------+
       |
       v
    +--------------+
    | Create tag   |
    | v1.1.22.dev1 |
    | GitHub       |
    | pre-release  |
    +--------------+
           |
           v
    +-------------------------------+
    | Optional: Publish to TestPyPI |   Feeling: VERIFYING
    | Smoke test upload mechanics   |   "Just checking the plumbing works"
    | NOT for distribution          |
    +-------------------------------+
           |
           v
    +-------------------------------+
    | Slack notification            |   Feeling: CONFIRMED
    | "Dev release v1.1.22.dev1     |   "Tagged, traceable, done"
    |  created on nwave-dev"        |
    +-------------------------------+
```

## TUI: GitHub Actions Summary

```
+----------------------------------------------------------+
| ## Dev Release: v1.1.22.dev1                             |
|                                                          |
| | Step              | Status  | Duration |              |
| |-------------------|---------|----------|              |
| | CI status gate    | PASS    | 3s       |              |
| | Version calculate | PASS    | 12s      |              |
| | Build dist        | PASS    | 1m 15s   |              |
| | Tag + pre-release | PASS    | 8s       |              |
| | TestPyPI publish  | SKIP    | --       |              |
| | Slack notify      | PASS    | 2s       |              |
|                                                          |
| **Tag**: v1.1.22.dev1                                    |
| **Commit**: abc123d (feat(cli): add verbose flag)        |
| **Pre-release**: [View on GitHub]                        |
+----------------------------------------------------------+
```

## Shared Artifacts Produced

| Artifact | Value | Consumed By |
|----------|-------|-------------|
| `dev_version` | `1.1.22.dev1` | Stage 2 (RC promotion) |
| `dev_tag` | `v1.1.22.dev1` | Stage 2 (RC promotion), traceability |
| `source_commit_sha` | `abc123def456` | All downstream stages |
| `github_pre_release_url` | URL | Slack notification |
| `dist_artifacts` | wheel + sdist | TestPyPI (optional) |

## Error Paths

| Error | User Sees | Recovery |
|-------|-----------|----------|
| CI failed on commit | Slack: "Dev release BLOCKED: CI failed on {sha}" | Fix code, push, re-trigger |
| CI still running on commit | "CI still running on {sha}, retry later" | Wait for CI to finish, re-trigger |
| No CI run found for commit | "No CI run found for {sha}" | Push to trigger CI, then re-trigger release |
| No version-bump commits since last tag | "No version bump needed" (workflow exits clean) | Expected; nothing to release |
| TestPyPI upload fails | Warning in summary; tag still created | Ignore (smoke test only) |
| Tag already exists | "Tag v1.1.22.dev1 already exists, incrementing to dev2" | Auto-handled |
