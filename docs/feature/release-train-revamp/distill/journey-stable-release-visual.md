# Journey: Stable Release (Stage 3)

**Epic**: release-train-revamp
**Persona**: Mike (maintainer, promoting from RC to stable)
**Trigger**: Beta testing is complete, RC is validated, time for public release
**Emotional arc**: Confident -> Meticulous -> Celebratory

---

## Flow

```
Mike reviews RC v1.1.22rc1 feedback: "No blockers, beta testers happy"
                    |
                    v
    +-------------------------------+
    | GitHub Actions UI             |   Feeling: CONFIDENT
    | workflow_dispatch             |   "This RC has been vetted"
    | [release-prod.yml]           |
    |                               |
    | Inputs:                       |
    |   source_rc_tag: v1.1.22rc1   |
    |   dry_run: [no]               |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Validate source RC            |   Feeling: TRUSTING
    | Confirm RC tag exists         |   "Same code that was tested"
    | Checkout that exact commit    |
    | Calculate: v1.1.22            |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | CI Status Gate                |   Feeling: TRUSTING
    | Verify CI passed on commit    |   "Trust the CI, verify the proof"
    | GET /repos/.../check-runs    |
    | Same commit as the RC tag     |
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
    | Build from SAME commit        |   Feeling: METICULOUS
    | (promotion, not rebuild)      |   "Byte-identical to what
    | Build dist packages           |    beta testers ran"
    | Generate checksums            |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Version bump on nwave-dev     |   Feeling: ORDERLY
    | Update pyproject.toml         |   "Source of truth stays clean"
    | Update framework-catalog.yaml |
    | Commit: "chore(release):      |
    |          v1.1.22 [skip ci]"   |
    | Tag v1.1.22 on nwave-dev      |
    | GitHub Release (full, not pre)|
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Publish to PyPI (production)  |   Feeling: RELEASING
    | Stable version (no marker)    |   "pip install nwave-ai gets
    | Trusted Publisher (OIDC)      |    this version by default"
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Sync to nWave public repo     |   Feeling: PROUD
    | rsync with exclusions         |   "The public face is updated"
    | Patch pyproject.toml for      |
    |   nwave-ai identity           |
    | Auto-bump nwave-ai version    |
    | Commit with full traceability:|
    |   Source: nwave-dev@{sha}     |
    |   Dev tag: v1.1.22.dev3       |
    |   RC tag: v1.1.22rc1          |
    |   Pipeline: {run_url}         |
    | Tag on nWave public repo      |
    | Create GitHub Release (full)  |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Tag nwave-dev with marker     |   Feeling: TRACEABLE
    | v{public_version}             |   "I can trace from any repo
    |                               |    back to source"
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | Slack notification            |   Feeling: CELEBRATORY
    | "nwave-ai v1.1.22 released!   |   "Ship it!"
    |  PyPI + nWave public repo     |
    |  pip install nwave-ai"        |
    | [View Release] [View Run]     |
    +-------------------------------+
```

## TUI: GitHub Actions Summary

```
+----------------------------------------------------------+
| ## Stable Release: v1.1.22                               |
|                                                          |
| **Promoted from**: v1.1.22rc1 (via v1.1.22.dev3)        |
| **Source commit**: abc123d                                |
|                                                          |
| | Step              | Status  | Duration |              |
| |-------------------|---------|----------|              |
| | Validate source   | PASS    | 5s       |              |
| | CI status gate    | PASS    | 3s       |              |
| | Build             | PASS    | 1m 15s   |              |
| | Version bump      | PASS    | 15s      |              |
| | Tag + release     | PASS    | 10s      |              |
| | PyPI publish      | PASS    | 48s      |              |
| | Sync nWave public | PASS    | 1m 30s   |              |
| | nwave-dev marker  | PASS    | 5s       |              |
| | Slack notify      | PASS    | 2s       |              |
|                                                          |
| **PyPI**: pip install nwave-ai (v1.1.22)                  |
| **Public repo**: nwave-ai/nwave @ v1.1.22                 |
| **Traceability**: nwave-dev v1.1.22 -> nWave v1.1.22     |
+----------------------------------------------------------+
```

## Shared Artifacts Produced

| Artifact | Value | Consumed By |
|----------|-------|-------------|
| `ci_check_status` | `green` | Gate for build step |
| `stable_version` | `1.1.22` | pyproject.toml, framework-catalog.yaml |
| `stable_tag` | `v1.1.22` | GitHub Release, traceability |
| `nwave_ai_version` | `1.1.22` | Public repo, PyPI |
| `nwave_ai_tag` | `v1.1.22` | Public repo GitHub Release |
| `nwave_dev_marker` | `v1.1.22` | Reverse traceability |
| `source_commit_sha` | `abc123def456` | Cross-repo commit messages |
| `full_traceability_chain` | dev3 -> rc1 -> stable | Commit messages in target repos |
| `pypi_stable_url` | PyPI URL | Slack, public docs |

## Error Paths

| Error | User Sees | Recovery |
|-------|-----------|----------|
| Source RC tag does not exist | "Tag v1.1.22rc1 not found" | Check RC was actually created |
| CI failed on source commit | "CI failed on {sha}" | Fix code, create new RC, re-trigger |
| CI still running on source commit | "CI still running on {sha}, retry later" | Wait for CI, re-trigger |
| No CI run found on source commit | "No CI run found for {sha}" | Investigate missing CI run |
| PyPI version already exists | "v1.1.22 already on PyPI" | Should not happen; investigate |
| nWave public repo sync fails | Slack: "Stable release FAILED at Sync nWave" | Check RELEASETRAIN token |
| Version mismatch (tag vs catalog) | "Version mismatch: tag 1.1.22, catalog 1.1.21" | Ensure version bump committed |
| Changelog generation fails | Warning; release proceeds with minimal notes | Manual release notes edit |
