# Observability Design: Versioning and Release Management

## Document Metadata

| Field | Value |
|-------|-------|
| Feature | nWave Versioning and Release Management |
| Wave | DESIGN (Platform) |
| Status | Platform Design Complete |
| Author | Apex (platform-architect) |
| Created | 2026-01-28 |
| Version | 1.0.0 |

---

## 1. Service Level Objectives (SLOs)

### 1.1 SLO Definitions

| Service | SLI | SLO Target | Measurement Method |
|---------|-----|------------|-------------------|
| **Version Check** | Latency (p50) | < 500ms | Timer from command start to version display |
| **Version Check** | Latency (p99) | < 2s | Timer from command start to version display |
| **Update Success** | Success rate | 99% | Successful updates / total update attempts (network failures excluded via graceful degradation) |
| **Release Pipeline** | Completion rate | 100% | Pipeline runs that complete all stages / total pipeline runs (failures block merge, so 100% of merged PRs result in releases) |
| **Release Availability** | Availability | 99.9% | GitHub Releases API availability (inherited from GitHub's SLA) |

### 1.2 SLO Measurement

#### Version Check Latency

```python
# Measured in /nw:version command
import time

start = time.perf_counter()
result = check_version()
latency_ms = (time.perf_counter() - start) * 1000

# Log for debugging (verbose mode only)
if verbose:
    print(f"[debug] Version check completed in {latency_ms:.0f}ms")
```

**Factors affecting latency**:
- Cache hit (watermark fresh): ~50-100ms (local file read)
- Cache miss (API call): ~200-800ms (network round-trip)
- Offline fallback: ~50ms (immediate cache return)

#### Update Success Rate

**Counted as successful**:
- Update completes with new version installed
- Graceful degradation (network error, user informed, installation unchanged)

**Counted as failure**:
- Checksum mismatch after download
- Partial installation (should never happen due to atomic design)
- Permission errors

**Exclusions** (not counted in success rate):
- User cancellation (major version warning declined)
- Rate limit with valid cache (graceful degradation)

#### Release Pipeline Completion

**Measured via GitHub Actions**:
- Pipeline runs triggered by merge to main
- Success = all 3 stages complete (version-bump, build, release)
- Failure = any stage fails

**Note**: Since PR merge is blocked until pipeline passes, and release pipeline only runs on successful merge, the completion rate should be 100%. Any failure indicates infrastructure issues requiring investigation.

#### Release Availability

**Inherited from GitHub**:
- GitHub's published SLA for GitHub Releases is 99.9%
- We inherit this availability for `/nw:update` operations
- Graceful offline mode provides user experience even when GitHub is unavailable

### 1.3 SLO Alerting (Pipeline Only)

Since we have no external telemetry, SLO monitoring happens in the pipeline:

```yaml
# In release.yml - example annotation for SLO tracking
- name: SLO Check
  run: |
    # Log pipeline timing for historical analysis
    echo "::notice::Release pipeline completed in ${SECONDS}s"

    # Flag if build stage exceeded target
    if [ "$BUILD_DURATION" -gt 1200 ]; then
      echo "::warning::Build stage exceeded 20-minute target"
    fi
```

### 1.4 Error Budget Policy

| SLO | Error Budget (monthly) | Action When Exhausted |
|-----|----------------------|----------------------|
| Version Check p99 < 2s | 1% (43 minutes) | Investigate GitHub API performance |
| Update Success 99% | 1% (~3 failures per 300 updates) | Review error logs, improve error handling |
| Release Pipeline 100% | 0% (zero tolerance) | Immediate investigation, rollback if needed |

---

## 2. Observability Philosophy

### Privacy-First Design

nWave follows a **privacy-first** approach to observability:

| Principle | Implementation |
|-----------|----------------|
| **Terminal-only output** | All feedback displayed in user's terminal |
| **No external telemetry** | No data sent to external services |
| **No analytics collection** | No usage tracking or metrics gathering |
| **Local state only** | Watermark file stored locally |
| **User controls data** | All data under `~/.claude/` is user-owned |

### Observability Scope

| In Scope | Out of Scope |
|----------|--------------|
| User feedback in terminal | External telemetry services |
| Structured logging to stdout | Log aggregation (Loki, ELK) |
| Error messages with context | Error reporting services (Sentry) |
| Progress indicators | Performance monitoring (APM) |
| Local watermark file | Cloud metrics storage |

---

## 3. Terminal Output Strategy

### 3.1 Output Levels

| Level | Use Case | Format |
|-------|----------|--------|
| **Success** | Operation completed | Green checkmark + message |
| **Info** | Progress updates | Neutral message |
| **Warning** | Non-blocking issues | Yellow warning + message |
| **Error** | Blocking failures | Red X + message + remediation |

### 3.2 Output Format Specification

```
Success:  [check] nWave v1.3.0 (up to date)
Info:     Downloading nWave v1.3.0...
Warning:  [!] Major version change detected (1.x to 2.x)
Error:    [x] Download failed: network error
          Your nWave installation is unchanged.
```

### 3.3 ASCII Art Guidelines

Following "Less is more" philosophy:

| Element | Allowed | Forbidden |
|---------|---------|-----------|
| Checkmarks | Yes (simple) | Elaborate symbols |
| Progress dots | Yes (`...`) | Spinner animations |
| Status indicators | Yes (`[x]`, `[!]`) | Emoji |
| Separators | Yes (simple lines) | Complex borders |

---

## 4. Structured Logging

### 4.1 Log Format

All commands use structured logging to stdout:

```python
def log(level: str, message: str, context: dict = None):
    """Structured log output to terminal."""
    timestamp = datetime.now().isoformat()
    output = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "command": current_command,
    }
    if context:
        output["context"] = context

    # Human-readable output to terminal
    print(format_for_human(output))
```

### 4.2 Log Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the event occurred |
| `level` | string | success/info/warning/error |
| `message` | string | Human-readable message |
| `command` | string | Which command is running |
| `context` | object | Additional structured data |

### 4.3 Context Fields by Command

#### /nw:version

```python
context = {
    "installed_version": "1.2.3",
    "latest_version": "1.3.0",
    "update_available": True,
    "check_source": "github_api" | "watermark_cache" | "offline"
}
```

#### /nw:update

```python
context = {
    "current_version": "1.2.3",
    "target_version": "1.3.0",
    "backup_path": "~/.claude.backup.20260128143022",
    "download_size_mb": 2.4,
    "checksum_valid": True
}
```

#### /nw:forge

```python
context = {
    "base_version": "1.2.3",
    "rc_version": "1.2.3-rc.main.20260128.1",
    "branch": "main",
    "tests_passed": True,
    "test_count": 45
}
```

#### /nw:forge:install

```python
context = {
    "source": "dist/",
    "target": "~/.claude/",
    "version": "1.2.3-rc.main.20260128.1",
    "smoke_test_passed": True
}
```

#### /nw:forge:release

```python
context = {
    "branch": "development",
    "pr_number": 123,
    "pr_url": "https://github.com/owner/repo/pull/123"
}
```

---

## 5. Error Handling and User Feedback

### 5.1 Error Message Structure

All errors follow this format:

```
[x] {What went wrong}
    {Why it matters / what was preserved}
    {What to do next}
```

### 5.2 Error Examples

#### Network Error

```
[x] Download failed: connection timed out
    Your nWave installation is unchanged.
    Check your network connection and try again.
```

#### Checksum Mismatch

```
[x] Download corrupted (checksum mismatch)
    Expected: abc123...
    Received: def456...
    Your nWave installation is unchanged.
    This may be a network issue. Try again or report if persistent.
```

#### Permission Error

```
[x] Permission denied writing to ~/.claude/
    Cannot complete installation.
    Check directory permissions: ls -la ~/.claude
```

#### Test Failure

```
[x] Build failed: 3 test failures
    dist/ was not modified.
    Fix the failing tests before building:
      - tests/test_version.py::test_compare_major FAILED
      - tests/test_update.py::test_backup_creation FAILED
      - tests/test_update.py::test_rollback FAILED
```

### 5.3 Warning Examples

#### Major Version Warning

```
[!] Major version change detected (1.x to 2.x)
    This may include breaking changes that affect your workflows.
    Continue? [y/N]
```

#### Local RC Warning

```
[!] Local customizations detected
    You have version 1.2.3-rc.main.20260128.1 installed.
    Update will replace with official version 1.3.0.
    Continue? [y/N]
```

---

## 6. Progress Indicators

### 6.1 Progress Format

Simple text-based progress for long operations:

```
Downloading nWave v1.3.0... done
Validating checksum... done
Creating backup... done
Installing... done

[check] Update complete.
View changelog in browser? [y/N]
```

### 6.2 Progress States

| State | Display |
|-------|---------|
| In progress | `{action}...` |
| Complete | `{action}... done` |
| Failed | `{action}... failed` |
| Skipped | `{action}... skipped` |

### 6.3 No Fancy Animations

Per privacy-first design, avoid:
- Spinner animations (require cursor manipulation)
- Progress bars (require terminal width detection)
- Color gradients (accessibility concerns)

Simple `...` suffix is sufficient and works in all terminals.

---

## 7. Watermark File (Local State)

### 7.1 Purpose

The watermark file caches version check results to avoid excessive GitHub API calls:

```yaml
# ~/.claude/nwave.update
last_check: 2026-01-28T14:30:22Z
latest_version: 1.3.0
```

### 7.2 Staleness Threshold

| Condition | Action |
|-----------|--------|
| `last_check` < 24 hours ago | Use cached `latest_version` |
| `last_check` >= 24 hours ago | Query GitHub API |
| File missing | Query GitHub API |
| File corrupted | Delete and query GitHub API |

### 7.3 Update Triggers

| Event | Watermark Update |
|-------|------------------|
| Successful version check | Yes |
| Failed version check (network) | No (preserve cache) |
| Successful update | Yes (new version) |
| Any nWave command (daily) | Yes (if stale) |

---

## 8. Debugging Support

### 8.1 Verbose Mode

Commands support `--verbose` flag for troubleshooting:

```bash
/nw:version --verbose
```

Verbose output includes:
- Full request/response details
- File paths being accessed
- Timing information
- Decision logic

### 8.2 Verbose Output Example

```
[debug] Reading version from ~/.claude/VERSION
[debug] Found version: 1.2.3
[debug] Reading watermark from ~/.claude/nwave.update
[debug] Watermark last_check: 2026-01-28T10:00:00Z (4h ago)
[debug] Watermark not stale, using cached latest_version
[debug] Cached latest_version: 1.3.0
[debug] Comparison: 1.2.3 < 1.3.0 -> update available

nWave v1.2.3 (update available: v1.3.0)
```

### 8.3 Debug Context

Verbose mode logs additional context:

```python
context = {
    "version_file_path": "~/.claude/VERSION",
    "watermark_path": "~/.claude/nwave.update",
    "watermark_age_hours": 4,
    "api_call_made": False,
    "cache_used": True,
    "comparison_result": "update_available"
}
```

---

## 9. CI/CD Pipeline Observability

### 9.1 GitHub Actions Annotations

Pipeline uses GitHub annotations for visibility:

```yaml
- name: Check version
  run: |
    if [ "$TAG_VERSION" != "$CATALOG_VERSION" ]; then
      echo "::error::Version mismatch - tag: ${TAG_VERSION}, catalog: ${CATALOG_VERSION}"
      exit 1
    fi
    echo "::notice::Version validation passed: ${TAG_VERSION}"
```

### 9.2 Annotation Types

| Type | Use Case |
|------|----------|
| `::error::` | Blocking failures |
| `::warning::` | Non-blocking issues |
| `::notice::` | Informational messages |

### 9.3 Job Summary

Release pipeline creates job summary:

```yaml
- name: Release Summary
  run: |
    echo "## Release Summary" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "- **Version**: ${{ steps.version.outputs.version }}" >> $GITHUB_STEP_SUMMARY
    echo "- **Changelog entries**: ${{ steps.changelog.outputs.count }}" >> $GITHUB_STEP_SUMMARY
    echo "- **Assets uploaded**: 5" >> $GITHUB_STEP_SUMMARY
```

---

## 10. Metrics (Pipeline-Only)

### 10.1 Build Metrics

Captured in pipeline logs only (not external):

| Metric | Captured In |
|--------|-------------|
| Build duration | GitHub Actions timing |
| Test count | pytest output |
| Test pass rate | pytest output |
| Package size | Build step output |

### 10.2 Release Metrics

Derived from GitHub data (not custom telemetry):

| Metric | Source |
|--------|--------|
| Release count | GitHub Releases API |
| Download count | GitHub Release assets |
| Time since last release | GitHub Releases API |

---

## 11. What We Explicitly Do NOT Collect

### Privacy Guarantees

| Data Type | Collected | Reason |
|-----------|-----------|--------|
| User identity | No | Privacy |
| IP address | No | Privacy |
| Usage frequency | No | Privacy |
| Error reports | No | User controls |
| Feature usage | No | Privacy |
| System info | No | Privacy |
| Install count | No | Privacy |

### User Control

Users have full control:
- All data in `~/.claude/` is user-owned
- Watermark file can be deleted anytime
- No external accounts or registration
- No opt-in/opt-out (nothing to opt into)

---

## 12. Handoff to DISTILL Wave

This observability design provides scenarios for acceptance tests:

### Output Format Scenarios

1. **Success messages show checkmark**
2. **Errors show X with remediation**
3. **Warnings show exclamation with prompt**
4. **Progress shows action with dots**

### Error Handling Scenarios

1. **Network errors preserve installation**
2. **Checksum errors show expected vs actual**
3. **Permission errors show fix command**
4. **Test failures list specific failures**

### Watermark Scenarios

1. **Fresh watermark uses cache**
2. **Stale watermark triggers API call**
3. **Missing watermark triggers API call**
4. **Offline mode uses stale cache gracefully**

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-28 | Apex (platform-architect) | Initial platform design |
| 1.1.0 | 2026-01-28 | Apex (platform-architect) | Added SLO section (PLAT-MAJOR-001) |
