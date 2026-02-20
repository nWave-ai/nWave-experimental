# Journey: RC Release / Promote to Beta (Stage 2)

**Epic**: release-train-revamp
**Persona**: Mike (maintainer, promoting from dev to RC)
**Trigger**: Mike has a stable dev release and wants beta testers to exercise it
**Emotional arc**: Deliberate -> Transparent -> Distributed

---

## Flow

```
Mike reviews dev release v2.18.0.dev3 and decides "this is RC-worthy"
                    |
                    v
    +-------------------------------+
    | GitHub Actions UI             |   Feeling: DELIBERATE
    | workflow_dispatch             |   "I'm promoting with intention"
    | [release-rc.yml]             |
    |                               |
    | Inputs:                       |
    |   source_dev_tag: v2.18.0.dev3|
    |   dry_run: [no]               |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Validate source               |   Feeling: TRUSTING
    | Confirm dev tag exists        |   "The system checks before acting"
    | Checkout that exact commit    |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | CI Status Gate                |   Feeling: TRUSTING
    | Verify CI passed on commit    |   "Trust the CI, verify the proof"
    | GET /repos/.../check-runs    |
    | (fail fast: 2s check first)  |
    +-------------------------------+
                    |
           +--------+--------+
           |                 |
        [GREEN]         [NOT GREEN]
           |                 |
           v                 v
    +-----------+  +-------------------+
    | Proceed   |  | STOP              |
    |           |  | "CI {status} on   |
    +-----------+  |  {sha}"           |
           |       +-------------------+
           v
    +-------------------------------+
    | Calculate RC version          |   Feeling: TRUSTING
    | v2.18.0rc1                    |   "The system knows the sequence"
    | PEP 440 rcN (sequential)      |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Build from SAME commit        |   Feeling: RIGOROUS
    | (promotion, not rebuild)      |   "Same code, different label"
    | Build dist packages           |
    | Generate checksums            |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Create tag v2.18.0rc1         |   Feeling: PROGRESSING
    | GitHub pre-release on         |
    | nwave-dev                     |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Publish to PyPI (production)  |   Feeling: TRANSPARENT
    | Pre-release marker            |   "On prod PyPI but pip ignores
    | pip ignores by default        |    unless you ask for --pre"
    | Trusted Publisher (OIDC)      |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Sync to nWave-beta repo       |   Feeling: DISTRIBUTING
    | rsync with exclusions         |   "Beta testers get their own repo"
    | Patch pyproject.toml          |
    | Commit with traceability:     |
    |   Source: nwave-dev@{sha}     |
    |   Dev tag: v2.18.0.dev3       |
    |   RC tag: v2.18.0rc1          |
    | Tag v2.18.0rc1 on beta repo   |
    | Create GitHub pre-release     |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Slack notification            |   Feeling: ACCOMPLISHED
    | "RC v2.18.0rc1 published      |   "Beta testers can start testing"
    |  to PyPI + nWave-beta"        |
    | Install: pip install --pre    |
    |          nwave-ai==2.18.0rc1  |
    +-------------------------------+
```

## TUI: GitHub Actions Summary

```
+----------------------------------------------------------+
| ## RC Release: v2.18.0rc1                                |
|                                                          |
| **Promoted from**: v2.18.0.dev3                          |
| **Source commit**: abc123d                                |
|                                                          |
| | Step              | Status  | Duration |              |
| |-------------------|---------|----------|              |
| | Validate source   | PASS    | 5s       |              |
| | CI status gate    | PASS    | 3s       |              |
| | Version calculate | PASS    | 8s       |              |
| | Build             | PASS    | 1m 15s   |              |
| | Tag + pre-release | PASS    | 8s       |              |
| | PyPI publish      | PASS    | 45s      |              |
| | Sync nWave-beta   | PASS    | 1m 12s   |              |
| | Slack notify      | PASS    | 2s       |              |
|                                                          |
| **PyPI**: pip install --pre nwave-ai==2.18.0rc1         |
| **Beta repo**: nwave-ai/nWave-beta @ v2.18.0rc1         |
+----------------------------------------------------------+
```

## Beta Tester Experience

```
Beta tester (invited) visits github.com/nwave-ai/nWave-beta
                    |
                    v
    +-------------------------------+
    | Sees GitHub pre-release       |   Feeling: INVITED
    | "v2.18.0rc1"                  |   "I have early access"
    | Release notes from dev        |
    | Install instructions          |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | pip install --pre nwave-ai    |   Feeling: EASY
    |   ==2.18.0rc1                 |   "Standard pip, nothing weird"
    |                               |
    | OR: pipx install nwave-ai     |
    |     ==2.18.0rc1               |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Tests, reports feedback        |   Feeling: VALUED
    | via GitHub Issues on           |   "My feedback matters before
    | nWave-beta repo                |    stable release"
    +-------------------------------+
```

## Shared Artifacts Produced

| Artifact | Value | Consumed By |
|----------|-------|-------------|
| `rc_version` | `2.18.0rc1` | Stage 3 (stable promotion) |
| `rc_tag` | `v2.18.0rc1` | Stage 3, traceability |
| `source_dev_tag` | `v2.18.0.dev3` | Traceability chain |
| `source_commit_sha` | `abc123def456` | All downstream, cross-repo commit msg |
| `pypi_package_url` | PyPI URL | Beta testers, Slack |
| `beta_repo_release_url` | GitHub URL | Beta testers |
| `dist_artifacts` | wheel + sdist (same build) | PyPI, beta repo |

## Error Paths

| Error | User Sees | Recovery |
|-------|-----------|----------|
| Source dev tag does not exist | "Tag v2.18.0.dev3 not found. Available dev tags: ..." | Pick correct tag |
| CI failed on source commit | "CI failed on {sha}" | Fix code, create new dev tag, re-trigger |
| CI still running on source commit | "CI still running on {sha}, retry later" | Wait for CI, re-trigger |
| No CI run found on source commit | "No CI run found for {sha}" | Investigate missing CI run |
| PyPI version already exists | "v2.18.0rc1 already on PyPI (skipping upload)" | Increment to rc2 |
| nWave-beta repo sync fails | Slack: "RC release FAILED at Sync nWave-beta" | Check RELEASETRAIN token perms |
| pyproject.toml patch fails | "Regex patch failed; review pyproject.toml structure" | Manual fix + re-trigger |
| OIDC token acquisition fails | "Trusted Publisher not configured for this workflow" | Fall back to API token or configure TP |
