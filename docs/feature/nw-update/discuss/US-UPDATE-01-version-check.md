# US-UPDATE-01: Automatic Version Check at Session Start

## Problem
RTodorov is a developer who installed nWave and has no way to know when a new version is available. He finds it frustrating to discover framework updates by accident -- checking PyPI manually, noticing a tweet, or hitting a bug that was already fixed in a newer release. His workaround is to periodically run `pip install --upgrade nwave-ai && nwave install` blindly, which wastes time when there is nothing new, and still offers no changelog context.

## Who
- Developer | Starts a new Claude Code session to work on a project | Wants to know if their tools are current without actively checking
- Tech Lead | Uses nWave daily with a team of 4 | Needs predictable awareness of framework changes without per-session noise
- Daily power user | Reads changelogs before updating | Needs to see what changed, not just that something changed

## Solution
A `SessionStart` hook that silently checks PyPI for a newer `nwave-ai` version once per session (per configured frequency), fetches a changelog summary from GitHub Releases when an update exists, and injects a compact notification into the session context via `additionalContext`. When the installed version is current, the hook completes without any output.

## Domain Examples

### 1: RTodorov opens a session with nWave 1.2.65 installed, 1.2.68 is on PyPI
RTodorov starts Claude Code to work on his API. Before his first prompt is processed, the `SessionStart` hook fires, checks PyPI (finds 1.2.68), fetches the GitHub releases between 1.2.65 and 1.2.68, and injects into his session:

```
nWave update available: 1.2.65 -> 1.2.68 (3 releases)

What's new:
- fix: DES hook no longer fires on compact sessions (#89)
- feat: /nw:rigor now supports 'exhaustive' profile
- fix: PyPI version check timeout now 5s (was 30s)

Options: "update now" / "remind me later" / "skip 1.2.68"
```

RTodorov says "update now" and Claude runs the upgrade. He is current in under 30 seconds.

### 2: Priya Sharma opens a session, nWave is already at latest (1.2.68)
Priya starts Claude Code. The hook fires, checks PyPI, finds local version equals latest version. No output is produced. Priya's session starts exactly as if the hook did not exist. No "you are up to date" banner, no noise.

### 3: Kai Nakamura opens a session, PyPI is unreachable (corporate proxy, no internet)
Kai is on a client site with a restrictive network. The hook fires, attempts PyPI fetch, hits a 5-second timeout, records `last_checked` as now (to avoid retry for the rest of the day per his daily setting), and exits silently. Kai's session starts normally. He never knows the check happened.

### 4: New install, first session, update available
A developer just ran `pip install nwave-ai && nwave install`. They open Claude Code. The hook fires, finds an update (their just-installed version was not the latest), shows the notification, and appends the frequency prompt:

```
nWave update available: 1.2.65 -> 1.2.68

[... changelog ...]

Options: "update now" / "remind me later" / "skip 1.2.68"
How often should I check for updates? (every session / daily / weekly / never) [daily]
```

## UAT Scenarios (BDD)

### Scenario 1: Update available -- notification shown with changelog
Given RTodorov has nwave-ai 1.2.65 installed
And PyPI reports the latest version is 1.2.68
And update_check.skipped_versions does not contain "1.2.68"
And GitHub Releases API returns 3 releases between 1.2.65 and 1.2.68
When the Claude Code SessionStart hook fires with source "startup"
Then the session context contains a notification header "nWave update available: 1.2.65 -> 1.2.68"
And the notification lists up to 5 salient changelog items from those 3 releases
And the notification offers three options: "update now", "remind me later", "skip 1.2.68"

### Scenario 2: No update -- complete silence
Given RTodorov has nwave-ai 1.2.68 installed
And PyPI reports the latest version is 1.2.68
When the SessionStart hook fires with source "startup"
Then no text is added to the session context
And last_checked is updated in .nwave/des-config.json

### Scenario 3: PyPI unreachable -- silent skip
Given the PyPI API is unreachable (timeout after 5 seconds)
When the SessionStart hook fires with source "startup"
Then no text is added to the session context
And last_checked is updated in .nwave/des-config.json to the current timestamp
And the Claude Code session starts without delay beyond the 5-second timeout

### Scenario 4: Hook skips for non-startup session source
Given a Claude Code session resumes from a previous conversation
When the SessionStart hook fires with source "resume"
Then no version check is performed
And no text is added to the session context

### Scenario 5: Changelog fetch fails -- version-only notification
Given RTodorov has nwave-ai 1.2.65 installed
And PyPI reports the latest version is 1.2.68
And the GitHub Releases API is unreachable (timeout)
When the SessionStart hook fires with source "startup"
Then the session context contains "nWave update available: 1.2.65 -> 1.2.68"
And the notification includes a link to https://github.com/nwave-ai/nwave/releases
And the notification still offers the three action options

### Scenario 6: Breaking change flagged prominently
Given nwave-ai 1.2.65 is installed
And the GitHub release for 1.2.68 contains "BREAKING CHANGE: DES config schema updated"
When the SessionStart hook fires with source "startup"
Then the notification begins with "[BREAKING CHANGE]" before the version header
And the breaking change description appears in the changelog summary

### Scenario 7: First run -- frequency prompt appended
Given .nwave/des-config.json has no "update_check" key
And nwave-ai 1.2.65 is installed
And PyPI reports the latest version is 1.2.68
When the SessionStart hook fires with source "startup"
Then the notification is shown with changelog
And the notification ends with a frequency-control prompt asking the user to set their preference
And the default shown is "daily"

## Acceptance Criteria
- [ ] Hook only performs version check when session source is "startup"; skips for resume, clear, compact
- [ ] When local version equals latest version, zero output is produced and no session context is modified
- [ ] When update is available and not skipped, notification is injected via stdout additionalContext
- [ ] Notification includes: version numbers, release count, up to 5 changelog items, three action options
- [ ] Breaking changes are prefixed with "[BREAKING CHANGE]" in the notification header area
- [ ] PyPI fetch has a 5-second hard timeout; timeout produces no output and updates last_checked
- [ ] GitHub Releases fetch has a 5-second hard timeout; timeout falls back to version-only notification
- [ ] Notification never exceeds 20 lines total
- [ ] First-run (no update_check config) appends frequency-control prompt to the notification
- [ ] last_checked is written to .nwave/des-config.json after every check attempt (success or failure)

## Technical Notes
- Hook invoked via: `PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter session-start`
- Hook output format: stdout text is injected as `additionalContext` in the session
- Local version: `importlib.metadata.version("nwave-ai")` -- handle `PackageNotFoundError` gracefully
- PyPI API: `GET https://pypi.org/pypi/nwave-ai/json` -- parse `info.version`
- GitHub Releases API: `GET https://api.github.com/repos/nwave-ai/nwave/releases` -- filter by tag semver range
- Config read-modify-write: preserve all other keys in .nwave/des-config.json
- Config schema under `update_check` key (see journey-update-notification.yaml shared_artifacts)
- Dependency: `update_check` key must not conflict with existing `rigor` key (US-RIGOR-03)
- Fire-and-forget: hook must not raise uncaught exceptions; all errors are silent and logged at DEBUG level

## Traceability
- **Job 1**: Know when a new nWave version is available without actively checking
- **Job 2**: Understand what changed before deciding to update
